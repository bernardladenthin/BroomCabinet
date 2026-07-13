// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.layer;

import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.instanceOf;
import static org.hamcrest.Matchers.is;
import static org.hamcrest.Matchers.sameInstance;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.io.IOException;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;

import net.ladenthin.jackpot.SendCompletionTracker;

/**
 * Unit contract of {@link SendCompletionTracker}: the id-to-future bookkeeping behind
 * {@link net.ladenthin.jackpot.Transceiver#send} — complete on acknowledgement, fail on
 * pre-wire failure, fail everything pending on shutdown, tolerate unregistered ids.
 */
public class SendCompletionTrackerTest {

    /**
     * An arbitrary wire message id.
     */
    private static final long ANY_ID = 42L;

    /**
     * A second, distinct wire message id.
     */
    private static final long OTHER_ID = 43L;

    /**
     * Upper bound for {@link CompletableFuture#get(long, TimeUnit)} on a future that must
     * already be completed. Unit: [s].
     */
    private static final long GET_TIMEOUT_SECONDS = 1;

    private final SendCompletionTracker tracker = new SendCompletionTracker();

    // <editor-fold defaultstate="collapsed" desc="complete">
    @Test
    @Timeout(10)
    public void complete_registeredId_futureCompletesNormally() throws Exception {
        // arrange
        final CompletableFuture<Void> future = new CompletableFuture<>();
        tracker.register(ANY_ID, future);

        // act
        tracker.complete(ANY_ID);

        // assert
        assertThat(future.isDone(), is(true));
        assertThat(future.isCompletedExceptionally(), is(false));
        future.get(GET_TIMEOUT_SECONDS, TimeUnit.SECONDS);
    }

    @Test
    @Timeout(10)
    public void complete_unregisteredId_noOpAndOtherFuturesUnaffected() {
        // arrange
        final CompletableFuture<Void> future = new CompletableFuture<>();
        tracker.register(ANY_ID, future);

        // act: an id nobody registered (fire-and-forget message, heartbeat, duplicate ack)
        tracker.complete(OTHER_ID);

        // assert
        assertThat(future.isDone(), is(false));
    }
    // </editor-fold>

    // <editor-fold defaultstate="collapsed" desc="fail">
    @Test
    @Timeout(10)
    public void fail_registeredId_futureCompletesExceptionallyWithGivenCause() {
        // arrange
        final CompletableFuture<Void> future = new CompletableFuture<>();
        final IOException cause = new IOException("serialization failed");
        tracker.register(ANY_ID, future);

        // act
        tracker.fail(ANY_ID, cause);

        // assert
        assertThat(future.isCompletedExceptionally(), is(true));
        final ExecutionException exception = assertThrows(ExecutionException.class,
            () -> future.get(GET_TIMEOUT_SECONDS, TimeUnit.SECONDS));
        assertThat(exception.getCause(), is(sameInstance((Throwable) cause)));
    }

    @Test
    @Timeout(10)
    public void fail_unregisteredId_noOp() {
        // arrange
        final CompletableFuture<Void> future = new CompletableFuture<>();
        tracker.register(ANY_ID, future);

        // act
        tracker.fail(OTHER_ID, new IOException("unrelated"));

        // assert
        assertThat(future.isDone(), is(false));
    }
    // </editor-fold>

    // <editor-fold defaultstate="collapsed" desc="shutdown">
    @Test
    @Timeout(10)
    public void shutdown_pendingFutures_allCompleteExceptionally() {
        // arrange
        final CompletableFuture<Void> first = new CompletableFuture<>();
        final CompletableFuture<Void> second = new CompletableFuture<>();
        tracker.register(ANY_ID, first);
        tracker.register(OTHER_ID, second);

        // act
        tracker.shutdown();

        // assert: a pending send can never succeed on a shut-down transceiver
        assertThat(first.isCompletedExceptionally(), is(true));
        assertThat(second.isCompletedExceptionally(), is(true));
        final ExecutionException exception = assertThrows(ExecutionException.class,
            () -> first.get(GET_TIMEOUT_SECONDS, TimeUnit.SECONDS));
        assertThat(exception.getCause(), is(instanceOf(IllegalStateException.class)));
    }

    @Test
    @Timeout(10)
    public void register_afterShutdown_futureCompletesExceptionallyImmediately() {
        // arrange
        tracker.shutdown();
        final CompletableFuture<Void> future = new CompletableFuture<>();

        // act
        tracker.register(ANY_ID, future);

        // assert
        assertThat(future.isCompletedExceptionally(), is(true));
        final ExecutionException exception = assertThrows(ExecutionException.class,
            () -> future.get(GET_TIMEOUT_SECONDS, TimeUnit.SECONDS));
        assertThat(exception.getCause(), is(instanceOf(IllegalStateException.class)));
    }
    // </editor-fold>
}
