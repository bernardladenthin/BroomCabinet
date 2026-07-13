// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.layer;

import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.greaterThanOrEqualTo;
import static org.hamcrest.Matchers.is;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;

import net.ladenthin.jackpot.FlowControl;

/**
 * Unit tests for the sender-side backpressure primitive {@link FlowControl}: a bounded
 * number of pending permits, blocking acquisition with a timeout, release on
 * acknowledgement, an unbounded mode, and shutdown that permanently unblocks waiters.
 */
public class FlowControlTest {

    /**
     * A short acquisition timeout so the reject path is observable within the test. Unit: [ms].
     */
    private static final long SHORT_SEND_TIMEOUT_MILLIS = 300;

    /**
     * Upper bound for cross-thread waits. Unit: [ms].
     */
    private static final long WAIT_TIMEOUT_MILLIS = 5000;

    // <editor-fold defaultstate="collapsed" desc="bounded acquisition">
    @Test
    @Timeout(30)
    public void acquire_withinCapacity_proceedsAndCountsPending() {
        // arrange
        final FlowControl flowControl = new FlowControl(2, SHORT_SEND_TIMEOUT_MILLIS);

        // act
        flowControl.acquire();
        flowControl.acquire();

        // assert
        assertThat(flowControl.getPendingCount(), is(equalTo(2)));
    }

    @Test
    @Timeout(30)
    public void release_afterAcquire_capacityRestored() {
        // arrange
        final FlowControl flowControl = new FlowControl(1, SHORT_SEND_TIMEOUT_MILLIS);
        flowControl.acquire();

        // act
        flowControl.release();

        // assert: the next acquire proceeds without timing out
        flowControl.acquire();
        assertThat(flowControl.getPendingCount(), is(equalTo(1)));
    }

    @Test
    @Timeout(30)
    public void acquire_capacityExhausted_throwsExceptionAfterSendTimeout() {
        // arrange
        final FlowControl flowControl = new FlowControl(1, SHORT_SEND_TIMEOUT_MILLIS);
        flowControl.acquire();
        final long before = System.currentTimeMillis();

        // act
        final IllegalStateException exception =
            assertThrows(IllegalStateException.class, flowControl::acquire);

        // assert: it waited for the timeout before rejecting
        final long waited = System.currentTimeMillis() - before;
        assertThat(waited, is(greaterThanOrEqualTo(SHORT_SEND_TIMEOUT_MILLIS - 50)));
        assertThat(exception.getMessage().contains("backpressure"), is(true));
    }

    @Test
    @Timeout(30)
    public void acquire_capacityFreedWhileWaiting_blockedAcquireProceeds() throws InterruptedException {
        // arrange: capacity 1, taken; a second acquire blocks (no timeout = wait forever)
        final FlowControl flowControl = new FlowControl(1, 0);
        flowControl.acquire();

        final CountDownLatch acquired = new CountDownLatch(1);
        final Thread waiter = new Thread(new Runnable() {
            @Override
            public void run() {
                flowControl.acquire();
                acquired.countDown();
            }
        });
        waiter.start();

        // pre-assert: the waiter is genuinely blocked
        assertThat(acquired.await(200, TimeUnit.MILLISECONDS), is(false));

        // act: an acknowledgement frees capacity
        flowControl.release();

        // assert
        assertThat(acquired.await(WAIT_TIMEOUT_MILLIS, TimeUnit.MILLISECONDS), is(true));
    }
    // </editor-fold>

    // <editor-fold defaultstate="collapsed" desc="unbounded mode">
    @Test
    @Timeout(30)
    public void acquire_unboundedConfiguration_neverBlocks() {
        // arrange: maxPendingMessages 0 disables the bound
        final FlowControl flowControl = new FlowControl(0, SHORT_SEND_TIMEOUT_MILLIS);

        // act: far more acquisitions than any bound
        for (int i = 0; i < 10000; i++) {
            flowControl.acquire();
        }

        // assert
        assertThat(flowControl.getPendingCount(), is(equalTo(0)));
    }
    // </editor-fold>

    // <editor-fold defaultstate="collapsed" desc="shutdown">
    @Test
    @Timeout(30)
    public void shutdown_waiterBlockedOnFullCapacity_waiterIsReleased() throws InterruptedException {
        // arrange
        final FlowControl flowControl = new FlowControl(1, 0);
        flowControl.acquire();

        final CountDownLatch returned = new CountDownLatch(1);
        final AtomicBoolean threw = new AtomicBoolean(false);
        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    flowControl.acquire();
                } catch (RuntimeException e) {
                    threw.set(true);
                } finally {
                    returned.countDown();
                }
            }
        }).start();

        // act
        Thread.sleep(100);
        flowControl.shutdown();

        // assert: the blocked sender returns (without an exception) instead of hanging forever
        assertThat(returned.await(WAIT_TIMEOUT_MILLIS, TimeUnit.MILLISECONDS), is(true));
        assertThat(threw.get(), is(false));
    }

    @Test
    @Timeout(30)
    public void acquire_afterShutdown_neverBlocks() {
        // arrange
        final FlowControl flowControl = new FlowControl(1, 0);
        flowControl.acquire();
        flowControl.shutdown();

        // act, assert: no blocking, no exception
        flowControl.acquire();
        assertThat(flowControl.getPendingCount(), is(equalTo(0)));
    }
    // </editor-fold>
}
