// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.sendAndReceive;

import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.greaterThanOrEqualTo;
import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.is;

import com.google.gson.reflect.TypeToken;

import java.util.ArrayList;
import java.util.List;
import java.util.Observable;
import java.util.Observer;
import java.util.concurrent.Semaphore;
import java.util.concurrent.TimeUnit;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;

import net.ladenthin.jackpot.Transceiver;
import net.ladenthin.jackpot.configuration.CClientSocketConnector;
import net.ladenthin.jackpot.configuration.CConnector;
import net.ladenthin.jackpot.configuration.CServerSocketConnector;
import net.ladenthin.jackpot.configuration.CTransceiver;
import net.ladenthin.jackpot.configuration.CTransceiverSession;
import net.ladenthin.jackpot.configuration.ConnectionType;
import net.ladenthin.jackpot.message.TCommand;
import net.ladenthin.jackpot.message.TError;

/**
 * Regression test for the "hanging transceiver" defect: the sender allocates the wire message
 * id BEFORE the (parallel) serialization runs. When a serialization fails — here forced
 * deterministically with {@link UnserializableMessage}, historically also triggered by the
 * {@code ConcurrentModificationException} case called out in
 * {@code SerializeLayer#run()} — nothing was ever sent for the already-allocated id. The
 * receiver processes messages in strictly consecutive id order, so it waited forever for the
 * missing id and NO later message ever came through, although the connection stayed alive.
 */
public class SerializationFailureRecoveryTest {

    private final static String HOST = "localhost";

    /**
     * A dedicated port, distinct from {@link SocketConnectorRoundTripTest}'s 12345, so the
     * two integration tests can never collide inside one Surefire fork.
     */
    private final static int PORT = 23456;

    /**
     * Time budget for the server to open its connector before the client connects. Unit: [ms].
     */
    private static final long SERVER_STARTUP_MILLIS = 3000;

    /**
     * Time budget for the client and server transceivers to finish connecting. Unit: [ms].
     */
    private static final long CONNECT_SETTLE_MILLIS = 1000;

    /**
     * Upper bound to wait for the recovered message. Generous on purpose: a healthy pipeline
     * delivers within milliseconds; the bound is only exhausted when the pipeline is wedged.
     * Unit: [ms].
     */
    private static final long DELIVERY_TIMEOUT_MILLIS = 10000;

    /**
     * Poll interval while waiting for delivery. Unit: [ms].
     */
    private static final long POLL_INTERVAL_MILLIS = 50;

    private volatile Transceiver<SimpleMessage> serverTransceiver;
    private volatile Transceiver<SimpleMessage> clientTransceiver;
    private final Semaphore createClientAndServer = new Semaphore(0);
    private volatile Exception startupException;

    /**
     * Messages received by the server side.
     */
    private final List<SimpleMessage> serverReceived = new ArrayList<>();

    /**
     * Errors reported by either side (the failed serialization must surface here).
     */
    private final List<TError> reportedErrors = new ArrayList<>();

    /**
     * Recording observer: collects messages and errors instead of throwing, so the failed
     * poison serialization does not kill the notifying thread.
     */
    private final Observer recordingServerObserver = new Observer() {
        @Override
        public void update(Observable o, Object arg) {
            synchronized (serverReceived) {
                if (arg instanceof SimpleMessage) {
                    serverReceived.add((SimpleMessage) arg);
                } else if (arg instanceof TError) {
                    reportedErrors.add((TError) arg);
                }
            }
        }
    };

    private final Observer recordingClientObserver = new Observer() {
        @Override
        public void update(Observable o, Object arg) {
            synchronized (serverReceived) {
                if (arg instanceof TError) {
                    reportedErrors.add((TError) arg);
                }
            }
        }
    };

    private CTransceiverSession serverSession() {
        return new CTransceiverSession(
            "serverTransceiver",
            new TypeToken<SimpleMessage>() {}.getType(),
            SimpleMessage.class,
            new CTransceiver(
                ConnectionType.ServerSocketConnection,
                new CConnector(new CServerSocketConnector(PORT))
            )
        );
    }

    private CTransceiverSession clientSession() {
        return new CTransceiverSession(
            "clientTransceiver",
            new TypeToken<SimpleMessage>() {}.getType(),
            SimpleMessage.class,
            new CTransceiver(
                ConnectionType.ClientSocketConnection,
                new CConnector(new CClientSocketConnector(HOST, PORT))
            )
        );
    }

    private void startServerAndClient() throws InterruptedException {
        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    serverTransceiver = new Transceiver<>(serverSession());
                } catch (Exception e) {
                    startupException = e;
                } finally {
                    createClientAndServer.release();
                }
            }
        }).start();

        // give the server a few seconds to open its socket before the client connects
        Thread.sleep(SERVER_STARTUP_MILLIS);

        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    clientTransceiver = new Transceiver<>(clientSession());
                } catch (Exception e) {
                    startupException = e;
                } finally {
                    createClientAndServer.release();
                }
            }
        }).start();

        final boolean successful = createClientAndServer.tryAcquire(2, 3, TimeUnit.SECONDS);
        if (!successful) {
            throw new RuntimeException("Timeout. Wait too long to start up threads.");
        }
        if (startupException != null) {
            throw new RuntimeException(startupException);
        }

        // give the server and client a few seconds to connect
        Thread.sleep(CONNECT_SETTLE_MILLIS);

        serverTransceiver.addObserver(recordingServerObserver);
        clientTransceiver.addObserver(recordingClientObserver);
    }

    private void shutdownServerAndClient() {
        final TCommand command = new TCommand();
        command.shutdown = true;
        if (clientTransceiver != null) {
            clientTransceiver.update(null, command);
        }
        if (serverTransceiver != null) {
            serverTransceiver.update(null, command);
        }
    }

    @AfterEach
    public void tearDown() {
        shutdownServerAndClient();
    }

    /**
     * Polls until the server received the expected number of messages or the timeout elapses.
     *
     * @return the number of messages the server received
     */
    private int waitForServerReceived(int expectedCount) throws InterruptedException {
        final long deadline = System.currentTimeMillis() + DELIVERY_TIMEOUT_MILLIS;
        for (;;) {
            synchronized (serverReceived) {
                if (serverReceived.size() >= expectedCount) {
                    return serverReceived.size();
                }
            }
            if (System.currentTimeMillis() >= deadline) {
                synchronized (serverReceived) {
                    return serverReceived.size();
                }
            }
            Thread.sleep(POLL_INTERVAL_MILLIS);
        }
    }

    @Test
    @Timeout(60)
    public void transmitMessage_serializationOfPreviousMessageFailed_subsequentMessageStillDelivered() throws InterruptedException {
        // arrange
        startServerAndClient();
        final UnserializableMessage poisonMessage =
            new UnserializableMessage("poison".getBytes());
        final SimpleMessage regularMessage =
            new SimpleMessage(SerializationFailureRecoveryTest.class.getCanonicalName().getBytes());

        // act: the poison message consumes a wire id but its serialization fails; the regular
        // message afterwards must nevertheless come through
        clientTransceiver.update(null, poisonMessage);
        clientTransceiver.update(null, regularMessage);
        final int received = waitForServerReceived(1);

        // assert: the regular message is delivered although the previous serialization failed
        assertThat("The message after the failed serialization never came through"
            + " (receiver starved waiting for the lost wire id).",
            received, is(equalTo(1)));
        synchronized (serverReceived) {
            assertThat(serverReceived, hasSize(1));
            assertThat(serverReceived.get(0), is(equalTo(regularMessage)));
            // the failed serialization must be surfaced as an error, never swallowed silently
            assertThat(reportedErrors.size(), is(greaterThanOrEqualTo(1)));
        }
    }
}
