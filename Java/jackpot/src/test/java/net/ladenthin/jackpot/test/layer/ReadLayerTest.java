// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.layer;

import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.is;
import static org.mockito.Mockito.mock;

import com.google.gson.reflect.TypeToken;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;

import net.ladenthin.jackpot.ConnectionLayer;
import net.ladenthin.jackpot.ErrorLayer;
import net.ladenthin.jackpot.ReadLayer;
import net.ladenthin.jackpot.Transceiver;
import net.ladenthin.jackpot.configuration.CClientSocketConnector;
import net.ladenthin.jackpot.configuration.CConnector;
import net.ladenthin.jackpot.configuration.CTransceiver;
import net.ladenthin.jackpot.configuration.CTransceiverSession;
import net.ladenthin.jackpot.configuration.ConnectionType;
import net.ladenthin.jackpot.message.TError;
import net.ladenthin.jackpot.messageprocessing.ParallelErrorInformant;
import net.ladenthin.jackpot.test.sendAndReceive.SimpleMessage;
import net.ladenthin.jackpot.util.BinaryMessage;

/**
 * Unit tests for the {@link ReadLayer} message-sequencing loop, driven directly through
 * {@link ReadLayer#receiveMessage} with heartbeat messages (heartbeats advance the sequence
 * and are observable through {@link ReadLayer#getHeartbeatReceivedCount()} without needing
 * the deserialization pipeline). The {@link ConnectionLayer} collaborator is mocked — no
 * socket is involved.
 */
public class ReadLayerTest {

    /**
     * The first message id the {@link ReadLayer} expects:
     * {@link CTransceiverSession#initialMessageId} + 1.
     */
    private static final long FIRST_EXPECTED_ID = Long.MIN_VALUE + 1;

    /**
     * Upper bound for {@link #waitForHeartbeatCount}. A healthy loop processes a heartbeat in
     * microseconds; this bound is only ever exhausted when the loop is genuinely wedged.
     * Unit: [ms].
     */
    private static final long WAIT_TIMEOUT_MILLIS = 3000;

    /**
     * Poll interval for {@link #waitForHeartbeatCount}. Unit: [ms].
     */
    private static final long POLL_INTERVAL_MILLIS = 10;

    private ReadLayer<SimpleMessage> readLayer;

    /**
     * Records errors instead of throwing, so a background-thread failure surfaces as a test
     * assertion rather than a hidden stack trace.
     */
    private volatile TError lastError;

    @BeforeEach
    public void setUp() {
        final CTransceiverSession session = new CTransceiverSession(
            "readLayerTest",
            new TypeToken<SimpleMessage>() {}.getType(),
            SimpleMessage.class,
            new CTransceiver(
                ConnectionType.ClientSocketConnection,
                // never connected: the ConnectionLayer collaborator is a mock
                new CConnector(new CClientSocketConnector("localhost", 1))
            )
        );

        final ErrorLayer errorLayer = new ErrorLayer(new ParallelErrorInformant() {
            @Override
            public void informError(TError error) {
                lastError = error;
            }
        });

        @SuppressWarnings("unchecked")
        final Transceiver<SimpleMessage> transceiver = mock(Transceiver.class);

        readLayer = new ReadLayer<>(session, mock(ConnectionLayer.class), errorLayer, transceiver);
    }

    @AfterEach
    public void tearDown() {
        readLayer.shutdownRunnable();
    }

    /**
     * Polls until the heartbeat counter reaches the expectation or the timeout elapses.
     *
     * @return the last observed heartbeat count
     */
    private long waitForHeartbeatCount(long expectedCount) throws InterruptedException {
        final long deadline = System.currentTimeMillis() + WAIT_TIMEOUT_MILLIS;
        while (readLayer.getHeartbeatReceivedCount() < expectedCount
            && System.currentTimeMillis() < deadline) {
            Thread.sleep(POLL_INTERVAL_MILLIS);
        }
        return readLayer.getHeartbeatReceivedCount();
    }

    // <editor-fold defaultstate="collapsed" desc="receiveMessage sequencing">
    @Test
    @Timeout(30)
    public void receiveMessage_consecutiveIds_allMessagesProcessed() throws InterruptedException {
        // arrange
        final BinaryMessage first = BinaryMessage.createHeartbeat(FIRST_EXPECTED_ID);
        final BinaryMessage second = BinaryMessage.createHeartbeat(FIRST_EXPECTED_ID + 1);

        // act
        readLayer.receiveMessage(first);
        readLayer.receiveMessage(second);

        // assert
        assertThat(waitForHeartbeatCount(2), is(equalTo(2L)));
    }

    @Test
    @Timeout(30)
    public void receiveMessage_outOfOrderArrival_messagesProcessedInIdOrder() throws InterruptedException {
        // arrange: the second id arrives before the first (e.g. reordered by parallel
        // serialization on the sender)
        final BinaryMessage first = BinaryMessage.createHeartbeat(FIRST_EXPECTED_ID);
        final BinaryMessage second = BinaryMessage.createHeartbeat(FIRST_EXPECTED_ID + 1);

        // act
        readLayer.receiveMessage(second);
        readLayer.receiveMessage(first);

        // assert
        assertThat(waitForHeartbeatCount(2), is(equalTo(2L)));
    }

    /**
     * A message with an id lower than the next expected id (an already-processed duplicate,
     * e.g. delivered again after a reconnect resend) must be discarded — it must NOT wedge
     * the sequencing loop. Before the fix, the stale duplicate stayed the lowest element of
     * the received set forever, so no later message could ever match the expected id and the
     * pipeline hung permanently ("messages don't come through").
     */
    @Test
    @Timeout(30)
    public void receiveMessage_duplicateOfProcessedIdArrives_subsequentMessagesStillProcessed() throws InterruptedException {
        // arrange
        final BinaryMessage first = BinaryMessage.createHeartbeat(FIRST_EXPECTED_ID);
        final BinaryMessage duplicateOfFirst = BinaryMessage.createHeartbeat(FIRST_EXPECTED_ID);
        final BinaryMessage second = BinaryMessage.createHeartbeat(FIRST_EXPECTED_ID + 1);

        readLayer.receiveMessage(first);

        // pre-assert: the first message is processed normally
        assertThat(waitForHeartbeatCount(1), is(equalTo(1L)));

        // act: the stale duplicate arrives, followed by the next regular message
        readLayer.receiveMessage(duplicateOfFirst);
        readLayer.receiveMessage(second);

        // assert: the regular message must still be processed (the duplicate is discarded,
        // not counted)
        assertThat(waitForHeartbeatCount(2), is(equalTo(2L)));
    }

    /**
     * Same wedge as above, but the stale duplicate arrives while a newer message is already
     * buffered — the discard must unblock the buffered message too.
     */
    @Test
    @Timeout(30)
    public void receiveMessage_duplicateArrivesBeforeBufferedSuccessor_bufferedMessageStillProcessed() throws InterruptedException {
        // arrange
        final BinaryMessage first = BinaryMessage.createHeartbeat(FIRST_EXPECTED_ID);
        final BinaryMessage duplicateOfFirst = BinaryMessage.createHeartbeat(FIRST_EXPECTED_ID);
        final BinaryMessage third = BinaryMessage.createHeartbeat(FIRST_EXPECTED_ID + 2);
        final BinaryMessage second = BinaryMessage.createHeartbeat(FIRST_EXPECTED_ID + 1);

        readLayer.receiveMessage(first);

        // pre-assert
        assertThat(waitForHeartbeatCount(1), is(equalTo(1L)));

        // act: a future message is buffered, then the stale duplicate poisons the set, then
        // the gap closes
        readLayer.receiveMessage(third);
        readLayer.receiveMessage(duplicateOfFirst);
        readLayer.receiveMessage(second);

        // assert: all three regular messages must be processed
        assertThat(waitForHeartbeatCount(3), is(equalTo(3L)));
    }
    // </editor-fold>
}
