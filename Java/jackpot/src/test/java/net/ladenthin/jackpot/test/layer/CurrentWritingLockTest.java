// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.layer;

import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.is;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;

import net.ladenthin.jackpot.CurrentWritingLock;
import net.ladenthin.jackpot.ErrorLayer;
import net.ladenthin.jackpot.message.TError;
import net.ladenthin.jackpot.messageprocessing.ParallelErrorInformant;

/**
 * Unit tests for {@link CurrentWritingLock}: {@code blockUntilCurrentWriting} must spin only
 * while exactly the probed id is being written, and must return immediately otherwise. A
 * leaked lock here previously wedged {@code WriteLayer.resendId}/{@code deleteId} forever
 * (see the try/finally around the stream write in {@code WriteLayer.run()}).
 */
public class CurrentWritingLockTest {

    /**
     * Upper bound for the cross-thread assertions. Unit: [ms].
     */
    private static final long WAIT_TIMEOUT_MILLIS = 3000;

    /**
     * How long the blocked state must be observable before the lock is released. Unit: [ms].
     */
    private static final long BLOCK_OBSERVATION_MILLIS = 200;

    private CurrentWritingLock currentWritingLock;

    @BeforeEach
    public void setUp() {
        currentWritingLock = new CurrentWritingLock(new ErrorLayer(new ParallelErrorInformant() {
            @Override
            public void informError(TError error) {
                // not relevant for these tests
            }
        }));
    }

    // <editor-fold defaultstate="collapsed" desc="blockUntilCurrentWriting">
    @Test
    @Timeout(30)
    public void blockUntilCurrentWriting_noLockSet_returnsImmediately() {
        // arrange: nothing locked

        // act, assert: must not block (the @Timeout guards against a regression)
        currentWritingLock.blockUntilCurrentWriting(1L);
    }

    @Test
    @Timeout(30)
    public void blockUntilCurrentWriting_differentIdLocked_returnsImmediately() {
        // arrange
        currentWritingLock.setLock(1L);

        // act, assert: only the locked id itself may block
        currentWritingLock.blockUntilCurrentWriting(2L);
    }

    @Test
    @Timeout(30)
    public void blockUntilCurrentWriting_lockedIdReleasedLater_blocksUntilReleaseLock() throws InterruptedException {
        // arrange
        final long lockedId = 1L;
        currentWritingLock.setLock(lockedId);

        final CountDownLatch blockerStarted = new CountDownLatch(1);
        final CountDownLatch blockerReturned = new CountDownLatch(1);
        final AtomicBoolean returnedWhileLocked = new AtomicBoolean(false);

        final Thread blocker = new Thread(new Runnable() {
            @Override
            public void run() {
                blockerStarted.countDown();
                currentWritingLock.blockUntilCurrentWriting(lockedId);
                blockerReturned.countDown();
            }
        });
        blocker.start();

        // pre-assert: the blocker is inside the spin loop and does not return early
        assertThat(blockerStarted.await(WAIT_TIMEOUT_MILLIS, TimeUnit.MILLISECONDS), is(true));
        if (blockerReturned.await(BLOCK_OBSERVATION_MILLIS, TimeUnit.MILLISECONDS)) {
            returnedWhileLocked.set(true);
        }
        assertThat("blockUntilCurrentWriting returned although the probed id is being written",
            returnedWhileLocked.get(), is(false));

        // act
        currentWritingLock.releaseLock();

        // assert: the blocker returns promptly after the release
        assertThat("blockUntilCurrentWriting did not return after releaseLock",
            blockerReturned.await(WAIT_TIMEOUT_MILLIS, TimeUnit.MILLISECONDS), is(true));
    }

    @Test
    @Timeout(30)
    public void blockUntilCurrentWriting_lockReleasedAndSetForOtherId_returnsImmediately() {
        // arrange: a full lock/release cycle, then another id is being written
        currentWritingLock.setLock(1L);
        currentWritingLock.releaseLock();
        currentWritingLock.setLock(2L);

        // act, assert: the released id must not block anymore
        currentWritingLock.blockUntilCurrentWriting(1L);
    }
    // </editor-fold>
}
