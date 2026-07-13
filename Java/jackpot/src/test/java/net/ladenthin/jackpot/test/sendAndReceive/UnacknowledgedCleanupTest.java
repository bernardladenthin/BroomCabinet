// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.sendAndReceive;

import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.hasItem;
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

/**
 * End-to-end test of the acknowledgement protocol over a real socket: every transmitted
 * message (payload, heartbeats, acknowledgements) must eventually be acknowledged by the
 * other side and released from the sender's retain buffer. Before the protocol was completed
 * no acknowledgement was ever sent, so {@link Transceiver#getUnacknowledgedMessageCount()}
 * grew without bound (memory growth) and messages lost on a reconnect were never resent.
 */
public class UnacknowledgedCleanupTest {

    private final static String HOST = "localhost";

    /**
     * A dedicated port, distinct from the other socket integration tests, so the tests can
     * never collide inside one Surefire fork.
     */
    private final static int PORT = 56789;

    /**
     * Time budget for the server to open its connector before the client connects. Unit: [ms].
     */
    private static final long SERVER_STARTUP_MILLIS = 3000;

    /**
     * Time budget for the client and server transceivers to finish connecting. Unit: [ms].
     */
    private static final long CONNECT_SETTLE_MILLIS = 1000;

    /**
     * Upper bound to wait for delivery and for the retain buffers to drain. Acknowledgements
     * are nudged at most once per heartbeat check interval (1 s by default), so a few round
     * trips fit comfortably. Unit: [ms].
     */
    private static final long DRAIN_TIMEOUT_MILLIS = 20000;

    /**
     * Poll interval. Unit: [ms].
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

    private final Observer recordingServerObserver = new Observer() {
        @Override
        public void update(Observable o, Object arg) {
            if (arg instanceof SimpleMessage) {
                synchronized (serverReceived) {
                    serverReceived.add((SimpleMessage) arg);
                }
            }
        }
    };

    private CTransceiverSession serverSession() {
        return new CTransceiverSession(
            "unackedCleanupServer",
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
            "unackedCleanupClient",
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

        Thread.sleep(CONNECT_SETTLE_MILLIS);

        serverTransceiver.addObserver(recordingServerObserver);
    }

    @AfterEach
    public void tearDown() {
        final TCommand command = new TCommand();
        command.shutdown = true;
        if (clientTransceiver != null) {
            clientTransceiver.update(null, command);
        }
        if (serverTransceiver != null) {
            serverTransceiver.update(null, command);
        }
    }

    @Test
    @Timeout(60)
    public void getUnacknowledgedMessageCount_messageDelivered_bothRetainBuffersDrainToZero() throws InterruptedException {
        // arrange
        startServerAndClient();
        final SimpleMessage payload =
            new SimpleMessage(UnacknowledgedCleanupTest.class.getCanonicalName().getBytes());

        // act
        clientTransceiver.update(null, payload);

        // pre-assert: the payload arrives
        final long deliveryDeadline = System.currentTimeMillis() + DRAIN_TIMEOUT_MILLIS;
        boolean delivered = false;
        while (!delivered && System.currentTimeMillis() < deliveryDeadline) {
            synchronized (serverReceived) {
                delivered = !serverReceived.isEmpty();
            }
            Thread.sleep(POLL_INTERVAL_MILLIS);
        }
        synchronized (serverReceived) {
            assertThat(serverReceived, hasItem(payload));
        }

        // assert: each side's retain buffer drains to zero at some point (every written
        // message got acknowledged) — before the acknowledgement protocol existed the counts
        // only ever grew
        final long drainDeadline = System.currentTimeMillis() + DRAIN_TIMEOUT_MILLIS;
        boolean clientDrained = false;
        boolean serverDrained = false;
        while ((!clientDrained || !serverDrained) && System.currentTimeMillis() < drainDeadline) {
            clientDrained |= clientTransceiver.getUnacknowledgedMessageCount() == 0;
            serverDrained |= serverTransceiver.getUnacknowledgedMessageCount() == 0;
            Thread.sleep(POLL_INTERVAL_MILLIS);
        }
        assertThat("The client never drained its unacknowledged messages"
            + " (count: " + clientTransceiver.getUnacknowledgedMessageCount() + ").",
            clientDrained, is(true));
        assertThat("The server never drained its unacknowledged messages"
            + " (count: " + serverTransceiver.getUnacknowledgedMessageCount() + ").",
            serverDrained, is(true));
    }
}
