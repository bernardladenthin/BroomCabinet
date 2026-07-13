// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.sendAndReceive;

import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.greaterThanOrEqualTo;
import static org.hamcrest.Matchers.is;
import static org.junit.jupiter.api.Assertions.assertThrows;

import com.google.gson.reflect.TypeToken;

import java.io.IOException;
import java.net.ServerSocket;
import java.net.Socket;
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

/**
 * End-to-end contract of the sender-side backpressure
 * ({@link CTransceiver#maxPendingMessages} / {@link CTransceiver#sendTimeout}):
 * when the peer stops acknowledging, {@link Transceiver#update} accepts at most the
 * configured number of messages and then rejects with an {@link IllegalStateException}
 * after the timeout — instead of buffering without bound. Against a healthy peer the
 * throttling never deadlocks: a burst far above the bound is delivered completely and in
 * order, paced by the acknowledgements.
 */
public class BackpressureTest {

    private final static String HOST = "localhost";

    /**
     * Port for the silent-peer test. Distinct from all other integration test ports.
     */
    private final static int SILENT_PORT = 27000;

    /**
     * Port for the throttled-liveness test.
     */
    private final static int LIVENESS_PORT = 27001;

    /**
     * The pending bound configured for these tests.
     */
    private static final int MAX_PENDING_MESSAGES = 5;

    /**
     * A short send timeout so the reject path is observable within the test. Unit: [ms].
     */
    private static final long SHORT_SEND_TIMEOUT_MILLIS = 1500;

    /**
     * Messages sent in the liveness test — deliberately far above the pending bound.
     */
    private static final int LIVENESS_BURST_SIZE = 20;

    /**
     * Time budget for connecting. Unit: [ms].
     */
    private static final long SERVER_STARTUP_MILLIS = 3000;
    private static final long CONNECT_SETTLE_MILLIS = 1000;

    /**
     * Upper bound to wait for the throttled burst (acknowledgements pace it at roughly the
     * heartbeat check interval). Unit: [ms].
     */
    private static final long DELIVERY_TIMEOUT_MILLIS = 45000;

    /**
     * Poll interval. Unit: [ms].
     */
    private static final long POLL_INTERVAL_MILLIS = 100;

    private volatile Transceiver<SimpleMessage> serverTransceiver;
    private volatile Transceiver<SimpleMessage> clientTransceiver;
    private ServerSocket silentServerSocket;
    private volatile Socket acceptedSocket;
    private final Semaphore createClientAndServer = new Semaphore(0);
    private volatile Exception startupException;

    private final List<SimpleMessage> serverReceived = new ArrayList<>();

    private CTransceiverSession session(String id, ConnectionType connectionType,
        CConnector connector, long sendTimeout) {
        final CTransceiver transceiverConfiguration = new CTransceiver(connectionType, connector);
        transceiverConfiguration.maxPendingMessages = MAX_PENDING_MESSAGES;
        transceiverConfiguration.sendTimeout = sendTimeout;
        return new CTransceiverSession(
            id,
            new TypeToken<SimpleMessage>() {}.getType(),
            SimpleMessage.class,
            transceiverConfiguration
        );
    }

    @AfterEach
    public void tearDown() throws IOException {
        final TCommand command = new TCommand();
        command.shutdown = true;
        if (clientTransceiver != null) {
            clientTransceiver.update(null, command);
        }
        if (serverTransceiver != null) {
            serverTransceiver.update(null, command);
        }
        if (acceptedSocket != null) {
            acceptedSocket.close();
        }
        if (silentServerSocket != null) {
            silentServerSocket.close();
        }
    }

    // <editor-fold defaultstate="collapsed" desc="reject when the peer stops acknowledging">
    @Test
    @Timeout(60)
    public void update_peerNeverAcknowledges_rejectsAfterMaxPendingMessages() throws IOException, InterruptedException {
        // arrange: a silent raw TCP peer — accepts the connection, never acknowledges
        silentServerSocket = new ServerSocket(SILENT_PORT);
        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    acceptedSocket = silentServerSocket.accept();
                } catch (IOException e) {
                    // closed in tearDown
                }
            }
        }).start();

        clientTransceiver = new Transceiver<>(session("backpressureClient",
            ConnectionType.ClientSocketConnection,
            new CConnector(new CClientSocketConnector(HOST, SILENT_PORT)),
            SHORT_SEND_TIMEOUT_MILLIS));
        Thread.sleep(CONNECT_SETTLE_MILLIS);

        // act: the bound is reached without a single rejection ...
        for (int i = 0; i < MAX_PENDING_MESSAGES; i++) {
            clientTransceiver.update(null, new SimpleMessage(("pending-" + i).getBytes()));
        }

        // ... and the next message is rejected after the send timeout
        final long before = System.currentTimeMillis();
        final IllegalStateException exception = assertThrows(IllegalStateException.class,
            () -> clientTransceiver.update(null, new SimpleMessage("one-too-many".getBytes())));

        // assert
        final long waited = System.currentTimeMillis() - before;
        assertThat("The rejection must come from the backpressure timeout, not immediately.",
            waited, is(greaterThanOrEqualTo(SHORT_SEND_TIMEOUT_MILLIS - 100)));
        assertThat(exception.getMessage().contains("backpressure"), is(true));
    }
    // </editor-fold>

    // <editor-fold defaultstate="collapsed" desc="throttled liveness against a healthy peer">
    @Test
    @Timeout(120)
    public void update_burstFarAboveBoundAgainstHealthyPeer_allMessagesDeliveredInOrder() throws InterruptedException {
        // arrange: a real transceiver pair; the client waits indefinitely for capacity
        // (sendTimeout 0), so this proves the throttling makes progress and never deadlocks
        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    serverTransceiver = new Transceiver<>(session("backpressureServer",
                        ConnectionType.ServerSocketConnection,
                        new CConnector(new CServerSocketConnector(LIVENESS_PORT)), 0));
                } catch (Exception e) {
                    startupException = e;
                } finally {
                    createClientAndServer.release();
                }
            }
        }).start();

        Thread.sleep(SERVER_STARTUP_MILLIS);

        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    clientTransceiver = new Transceiver<>(session("backpressureLivenessClient",
                        ConnectionType.ClientSocketConnection,
                        new CConnector(new CClientSocketConnector(HOST, LIVENESS_PORT)), 0));
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

        Thread.sleep(CONNECT_SETTLE_MILLIS);

        serverTransceiver.addObserver(new Observer() {
            @Override
            public void update(Observable o, Object arg) {
                if (arg instanceof SimpleMessage) {
                    synchronized (serverReceived) {
                        serverReceived.add((SimpleMessage) arg);
                    }
                }
            }
        });

        // act: a burst four times the pending bound — update() blocks whenever the bound is
        // reached and proceeds as acknowledgements free capacity
        for (int i = 0; i < LIVENESS_BURST_SIZE; i++) {
            clientTransceiver.update(null, new SimpleMessage(("burst-" + i).getBytes()));
        }

        // assert: everything arrives, in order
        final long deadline = System.currentTimeMillis() + DELIVERY_TIMEOUT_MILLIS;
        for (;;) {
            synchronized (serverReceived) {
                if (serverReceived.size() >= LIVENESS_BURST_SIZE) {
                    break;
                }
            }
            if (System.currentTimeMillis() >= deadline) {
                break;
            }
            Thread.sleep(POLL_INTERVAL_MILLIS);
        }
        synchronized (serverReceived) {
            assertThat("The throttled burst did not arrive completely.",
                serverReceived.size(), is(equalTo(LIVENESS_BURST_SIZE)));
            for (int i = 0; i < LIVENESS_BURST_SIZE; i++) {
                assertThat(serverReceived.get(i),
                    is(equalTo(new SimpleMessage(("burst-" + i).getBytes()))));
            }
        }
    }
    // </editor-fold>
}
