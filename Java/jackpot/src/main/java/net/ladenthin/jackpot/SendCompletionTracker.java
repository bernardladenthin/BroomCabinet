// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot;

import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Maps in-flight wire message ids to the {@link CompletableFuture} handed out by
 * {@link Transceiver#send(Object)}: a future completes normally when the peer's
 * acknowledgement for its id arrives, exceptionally when the message failed before reaching
 * the wire or the transceiver shuts down with the message still unacknowledged.
 */
public final class SendCompletionTracker {

    /**
     * The failure message used when a pending send can never complete anymore.
     */
    private static final String SHUT_DOWN_MESSAGE =
        "the transceiver was shut down before the message was acknowledged";

    /**
     * The pending futures by wire message id. Fire-and-forget messages, heartbeats and
     * acknowledgement messages never appear here.
     */
    private final ConcurrentMap<Long, CompletableFuture<Void>> pending =
        new ConcurrentHashMap<>();

    /**
     * After shutdown every new registration fails immediately.
     */
    private final AtomicBoolean shutdown = new AtomicBoolean(false);

    /**
     * Associate a wire id with its completion future. A registration after
     * {@link #shutdown()} fails the future immediately.
     *
     * @param id the allocated wire message id
     * @param future the future to complete; {@code null} is a no-op (fire-and-forget path)
     */
    public void register(final long id, final CompletableFuture<Void> future) {
        if (future == null) {
            return;
        }
        if (shutdown.get()) {
            future.completeExceptionally(new IllegalStateException(SHUT_DOWN_MESSAGE));
            return;
        }
        pending.put(id, future);
        /**
         * Close the race with a concurrent {@link #shutdown()}: it may have drained the map
         * between the flag check and the put, leaving this future stranded.
         */
        if (shutdown.get()) {
            fail(id, new IllegalStateException(SHUT_DOWN_MESSAGE));
        }
    }

    /**
     * The acknowledgement for the id arrived: complete its future normally. Unregistered
     * ids (fire-and-forget messages, heartbeats, duplicate acknowledgements) are a no-op.
     *
     * @param id the acknowledged wire message id
     */
    public void complete(final long id) {
        final CompletableFuture<Void> future = pending.remove(id);
        if (future != null) {
            future.complete(null);
        }
    }

    /**
     * The message failed before it could ever be acknowledged (failed serialization,
     * oversized payload): complete its future exceptionally. Unregistered ids are a no-op.
     *
     * @param id the failed wire message id
     * @param cause the failure
     */
    public void fail(final long id, final Throwable cause) {
        final CompletableFuture<Void> future = pending.remove(id);
        if (future != null) {
            future.completeExceptionally(cause);
        }
    }

    /**
     * The transceiver shuts down: every still-pending future completes exceptionally with
     * an {@link IllegalStateException} — a pending send can never succeed anymore.
     */
    public void shutdown() {
        shutdown.set(true);
        for (final Long id : pending.keySet()) {
            fail(id, new IllegalStateException(SHUT_DOWN_MESSAGE));
        }
    }
}
