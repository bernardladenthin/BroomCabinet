// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.layer;

import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.greaterThanOrEqualTo;
import static org.hamcrest.Matchers.is;
import static org.hamcrest.Matchers.notNullValue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.google.gson.reflect.TypeToken;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.atomic.AtomicLong;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;
import org.mockito.invocation.InvocationOnMock;
import org.mockito.stubbing.Answer;

import net.ladenthin.jackpot.ConnectionLayer;
import net.ladenthin.jackpot.ErrorLayer;
import net.ladenthin.jackpot.FlowControl;
import net.ladenthin.jackpot.SendCompletionTracker;
import net.ladenthin.jackpot.WriteLayer;
import net.ladenthin.jackpot.configuration.CClientSocketConnector;
import net.ladenthin.jackpot.configuration.CConnector;
import net.ladenthin.jackpot.configuration.CMessageIdLong;
import net.ladenthin.jackpot.configuration.CTransceiver;
import net.ladenthin.jackpot.configuration.CTransceiverSession;
import net.ladenthin.jackpot.configuration.ConnectionType;
import net.ladenthin.jackpot.configuration.Heartbeat;
import net.ladenthin.jackpot.configuration.SerializationType;
import net.ladenthin.jackpot.configuration.SettingsCompression;
import net.ladenthin.jackpot.interfaces.MessageIdGenerator;
import net.ladenthin.jackpot.message.TError;
import net.ladenthin.jackpot.messageprocessing.ParallelErrorInformant;
import net.ladenthin.jackpot.test.Common;
import net.ladenthin.jackpot.test.sendAndReceive.SimpleMessage;
import net.ladenthin.jackpot.util.BinaryMessage;

/**
 * Unit tests for the {@link WriteLayer} reliability bookkeeping: every written message is
 * retained until acknowledged, unacknowledged messages are resent after
 * {@link Heartbeat#resendInterval}, and pending acknowledgements from the
 * {@link ConnectionLayer} are sent with priority. The {@link ConnectionLayer} collaborator is
 * mocked — no socket is involved; writes are captured into a list.
 */
public class WriteLayerTest {

    /**
     * A short resend interval so the resend behaviour is observable within the test. Unit: [ms].
     */
    private static final long RESEND_INTERVAL_MILLIS = 200;

    /**
     * The id used for the payload message under test. Distinct from the small ids the
     * generator hands out for heartbeats/acknowledgement messages within a test run.
     */
    private static final long PAYLOAD_ID = 4242;

    /**
     * Upper bound for all polls in this test. Unit: [ms].
     */
    private static final long WAIT_TIMEOUT_MILLIS = 5000;

    /**
     * Poll interval; also the pace of the manual heartbeat signals. Unit: [ms].
     */
    private static final long POLL_INTERVAL_MILLIS = 25;

    private WriteLayer writeLayer;
    private ConnectionLayer<SimpleMessage> connectionLayer;

    /**
     * Every message the {@link WriteLayer} wrote "to the wire" (captured from the mocked
     * {@link ConnectionLayer#writeBoxedSendableByteMessage}).
     */
    private final List<BinaryMessage> writtenToWire = new CopyOnWriteArrayList<>();

    private volatile TError lastError;

    @BeforeEach
    @SuppressWarnings("unchecked")
    public void setUp() throws Exception {
        final CTransceiverSession session = new CTransceiverSession(
            "writeLayerTest",
            new TypeToken<SimpleMessage>() {}.getType(),
            SimpleMessage.class,
            new CTransceiver(
                SerializationType.ObjectOutputStreamSerialization,
                SerializationType.ObjectOutputStreamSerialization,
                ConnectionType.ClientSocketConnection,
                new SettingsCompression(),
                new CConnector(new CClientSocketConnector("localhost", 1)),
                new Heartbeat(RESEND_INTERVAL_MILLIS),
                new CMessageIdLong()
            )
        );

        final MessageIdGenerator idGenerator = new MessageIdGenerator() {
            private final AtomicLong counter = new AtomicLong();

            @Override
            public long getNextId() {
                return counter.incrementAndGet();
            }
        };

        connectionLayer = mock(ConnectionLayer.class);
        when(connectionLayer.getTransceiverSession()).thenReturn(session);
        when(connectionLayer.getMessageIdGenerator()).thenReturn(idGenerator);
        doAnswer(new Answer<Void>() {
            @Override
            public Void answer(InvocationOnMock invocation) {
                writtenToWire.add((BinaryMessage) invocation.getArgument(0));
                return null;
            }
        }).when(connectionLayer).writeBoxedSendableByteMessage(any(BinaryMessage.class));

        final ErrorLayer errorLayer = new ErrorLayer(new ParallelErrorInformant() {
            @Override
            public void informError(TError error) {
                lastError = error;
            }
        });

        writeLayer = new WriteLayer(errorLayer, connectionLayer, new FlowControl(0, 0),
            new SendCompletionTracker());
    }

    @AfterEach
    public void tearDown() {
        writeLayer.shutdownRunnable();
    }

    /**
     * @return how many captured wire writes carry the given message id
     */
    private int writeCountForId(long id) {
        int count = 0;
        for (BinaryMessage bm : writtenToWire) {
            if (bm.getId() == id) {
                count++;
            }
        }
        return count;
    }

    /**
     * Polls (while pumping manual heartbeat signals, standing in for the timer) until the
     * given id was written at least the expected number of times or the timeout elapses.
     *
     * @return the observed write count for the id
     */
    private int waitForWriteCount(long id, int expectedCount) throws InterruptedException {
        final long deadline = System.currentTimeMillis() + WAIT_TIMEOUT_MILLIS;
        while (writeCountForId(id) < expectedCount && System.currentTimeMillis() < deadline) {
            writeLayer.heartbeatSignal();
            Thread.sleep(POLL_INTERVAL_MILLIS);
        }
        return writeCountForId(id);
    }

    // <editor-fold defaultstate="collapsed" desc="tracking until acknowledged">
    @Test
    @Timeout(30)
    public void transmitMessage_messageWritten_retainedUntilAcknowledged() throws Exception {
        // arrange
        final BinaryMessage payload = BinaryMessage.box(
            PAYLOAD_ID, Common.simpleByteArray, Common.simpleSettingsCompression);

        // act
        writeLayer.transmitMessage(payload);

        // pre-assert: the message reached the wire and is retained
        assertThat(waitForWriteCount(PAYLOAD_ID, 1), is(greaterThanOrEqualTo(1)));
        assertThat(writeLayer.getUnacknowledgedMessageCount(), is(greaterThanOrEqualTo(1L)));

        // act: the acknowledgement arrives; the payload is the only tracked message so far
        final long countBeforeAcknowledgement = writeLayer.getUnacknowledgedMessageCount();
        writeLayer.deleteId(PAYLOAD_ID);

        // assert: the message is released
        assertThat(writeLayer.getUnacknowledgedMessageCount(),
            is(equalTo(countBeforeAcknowledgement - 1)));
    }

    @Test
    @Timeout(30)
    public void deleteId_unknownIdGiven_noExceptionThrown() {
        // arrange: nothing written

        // act, assert: a duplicate/unknown acknowledgement must be a tolerated no-op
        writeLayer.deleteId(999999L);
        assertThat(writeLayer.getUnacknowledgedMessageCount(), is(equalTo(0L)));
    }
    // </editor-fold>

    // <editor-fold defaultstate="collapsed" desc="resend of unacknowledged messages">
    /**
     * The core reliability guarantee: a message that is never acknowledged must be written
     * again after {@link Heartbeat#resendInterval} — this is what un-wedges a receiver that
     * lost the message (it waits for exactly this id before processing anything newer).
     */
    @Test
    @Timeout(30)
    public void transmitMessage_neverAcknowledged_messageResentAfterResendInterval() throws Exception {
        // arrange
        final BinaryMessage payload = BinaryMessage.box(
            PAYLOAD_ID, Common.simpleByteArray, Common.simpleSettingsCompression);
        writeLayer.transmitMessage(payload);
        assertThat(waitForWriteCount(PAYLOAD_ID, 1), is(greaterThanOrEqualTo(1)));

        // act: no acknowledgement arrives; heartbeat ticks keep the loop running
        final int writes = waitForWriteCount(PAYLOAD_ID, 2);

        // assert: the same id was written again (resend)
        assertThat("The unacknowledged message was never resent.",
            writes, is(greaterThanOrEqualTo(2)));
    }

    @Test
    @Timeout(30)
    public void transmitMessage_acknowledgedInTime_messageNotResent() throws Exception {
        // arrange
        final BinaryMessage payload = BinaryMessage.box(
            PAYLOAD_ID, Common.simpleByteArray, Common.simpleSettingsCompression);
        writeLayer.transmitMessage(payload);
        assertThat(waitForWriteCount(PAYLOAD_ID, 1), is(greaterThanOrEqualTo(1)));

        // act: acknowledge promptly, then keep the loop ticking well past the resend interval
        writeLayer.deleteId(PAYLOAD_ID);
        final long deadline = System.currentTimeMillis() + 3 * RESEND_INTERVAL_MILLIS;
        while (System.currentTimeMillis() < deadline) {
            writeLayer.heartbeatSignal();
            Thread.sleep(POLL_INTERVAL_MILLIS);
        }

        // assert: no further write of the acknowledged id happened
        assertThat(writeCountForId(PAYLOAD_ID), is(equalTo(1)));
    }
    // </editor-fold>

    // <editor-fold defaultstate="collapsed" desc="loop robustness">
    /**
     * A {@link RuntimeException} inside the write loop (e.g. message id range exhaustion in
     * the id generator, which throws a RuntimeException) must be surfaced as an error and
     * must NOT kill the loop thread — a dead writer thread hangs the whole transceiver
     * silently.
     */
    @Test
    @Timeout(30)
    public void run_idGeneratorThrowsOnce_errorSurfacedAndLoopKeepsWorking() throws Exception {
        // arrange: the generator fails exactly once (on the heartbeat the first idle tick
        // creates), afterwards it works again
        final java.util.concurrent.atomic.AtomicBoolean thrown = new java.util.concurrent.atomic.AtomicBoolean(false);
        when(connectionLayer.getMessageIdGenerator()).thenReturn(new MessageIdGenerator() {
            private final AtomicLong counter = new AtomicLong();

            @Override
            public long getNextId() {
                if (thrown.compareAndSet(false, true)) {
                    throw new RuntimeException("getLastMessageId reached.");
                }
                return counter.incrementAndGet();
            }
        });

        // act: the first idle tick creates a heartbeat -> the generator throws
        writeLayer.heartbeatSignal();
        final long errorDeadline = System.currentTimeMillis() + WAIT_TIMEOUT_MILLIS;
        while (lastError == null && System.currentTimeMillis() < errorDeadline) {
            Thread.sleep(POLL_INTERVAL_MILLIS);
        }

        // pre-assert: the failure is surfaced, not swallowed
        assertThat("The id generator failure was never surfaced as an error.",
            lastError, is(notNullValue()));

        // act: the loop must still be alive and process further messages
        final BinaryMessage payload = BinaryMessage.box(
            PAYLOAD_ID, Common.simpleByteArray, Common.simpleSettingsCompression);
        writeLayer.transmitMessage(payload);

        // assert
        assertThat("The write loop died after the RuntimeException — later messages are never written.",
            waitForWriteCount(PAYLOAD_ID, 1), is(greaterThanOrEqualTo(1)));
    }
    // </editor-fold>

    // <editor-fold defaultstate="collapsed" desc="acknowledgement sending">
    @Test
    @Timeout(30)
    public void heartbeatSignal_pendingAcknowledgementsAvailable_acknowledgementMessageWritten() throws Exception {
        // arrange: the connection layer reports two received ids awaiting acknowledgement
        when(connectionLayer.drainPendingAcknowledgements())
            .thenReturn(Arrays.asList(7L, 8L))
            .thenReturn(Collections.<Long>emptyList());

        // act
        writeLayer.heartbeatSignal();

        // assert: an acknowledgement message carrying exactly those ids is written
        final long deadline = System.currentTimeMillis() + WAIT_TIMEOUT_MILLIS;
        BinaryMessage acknowledgement = null;
        while (acknowledgement == null && System.currentTimeMillis() < deadline) {
            for (BinaryMessage bm : writtenToWire) {
                if (bm.isStateAcknowledged()) {
                    acknowledgement = bm;
                    break;
                }
            }
            if (acknowledgement == null) {
                writeLayer.heartbeatSignal();
                Thread.sleep(POLL_INTERVAL_MILLIS);
            }
        }
        assertThat("No acknowledgement message was written although acknowledgements were pending.",
            acknowledgement, is(notNullValue()));
        assertThat(acknowledgement.getAcknowledged(), is(equalTo(Arrays.asList(7L, 8L))));
    }
    // </editor-fold>
}
