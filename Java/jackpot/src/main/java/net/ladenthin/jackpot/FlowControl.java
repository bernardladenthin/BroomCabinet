// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot;

import java.util.concurrent.Semaphore;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Sender-side backpressure: bounds the number of application messages that were accepted for
 * sending but not yet acknowledged by the other side. {@link Transceiver#update} acquires a
 * permit per message and blocks when the bound is reached; a permit is released when the
 * message is acknowledged (or its serialization failed). Configured through
 * {@link net.ladenthin.jackpot.configuration.CTransceiver#maxPendingMessages} and
 * {@link net.ladenthin.jackpot.configuration.CTransceiver#sendTimeout}.
 */
public final class FlowControl {

    /**
     * The configured bound; {@code 0} disables backpressure entirely.
     */
    private final int maxPendingMessages;

    /**
     * How long an acquisition waits for capacity before rejecting; {@code <= 0} waits
     * indefinitely. Unit: [ms].
     */
    private final long sendTimeout;

    /**
     * The permits; {@code null} in unbounded mode. Fair, so blocked senders proceed in
     * arrival order.
     */
    private final Semaphore permits;

    /**
     * After shutdown every acquisition is a no-op, so senders can never block on a dying
     * transceiver.
     */
    private final AtomicBoolean shutdown = new AtomicBoolean(false);

    /**
     * @param maxPendingMessages the pending bound; {@code 0} disables backpressure
     * @param sendTimeout reject an acquisition after this wait; {@code <= 0} waits
     * indefinitely. Unit: [ms].
     */
    public FlowControl(final int maxPendingMessages, final long sendTimeout) {
        this.maxPendingMessages = maxPendingMessages;
        this.sendTimeout = sendTimeout;
        this.permits = maxPendingMessages > 0 ? new Semaphore(maxPendingMessages, true) : null;
    }

    /**
     * Acquire capacity for one message. Blocks while {@link #maxPendingMessages} messages are
     * pending; rejects with an {@link IllegalStateException} when {@link #sendTimeout}
     * elapses without capacity.
     */
    public void acquire() {
        if (permits == null || shutdown.get()) {
            return;
        }
        try {
            if (sendTimeout > 0) {
                if (!permits.tryAcquire(sendTimeout, TimeUnit.MILLISECONDS)) {
                    if (shutdown.get()) {
                        return;
                    }
                    throw new IllegalStateException("backpressure: " + maxPendingMessages
                        + " messages are pending unacknowledged and no capacity was freed within "
                        + sendTimeout + " ms");
                }
            } else {
                permits.acquire();
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("interrupted while waiting for send capacity", e);
        }
    }

    /**
     * Release the capacity of one message (it was acknowledged, or it failed before reaching
     * the wire).
     */
    public void release() {
        if (permits == null || shutdown.get()) {
            return;
        }
        permits.release();
    }

    /**
     * Permanently disables backpressure and wakes every blocked sender, so no application
     * thread can stay blocked on a shut-down transceiver.
     */
    public void shutdown() {
        if (shutdown.compareAndSet(false, true) && permits != null) {
            /**
             * Enough permits to satisfy every possible waiter; acquire() is a no-op from now
             * on, so the count can never be exhausted again.
             */
            permits.release(Integer.MAX_VALUE / 2);
        }
    }

    /**
     * The number of messages currently accepted but not yet acknowledged.
     *
     * @return the pending count; always {@code 0} in unbounded mode and after shutdown
     */
    public int getPendingCount() {
        if (permits == null || shutdown.get()) {
            return 0;
        }
        return Math.max(0, maxPendingMessages - permits.availablePermits());
    }
}
