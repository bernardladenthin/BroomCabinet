// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.sendAndReceive;

import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.equalTo;
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
 * The core delivery guarantee of the library, exercised as a burst: many messages handed to
 * the transceiver in quick succession must ALL arrive, in EXACTLY the submission order, on
 * the other side — although serialization runs in a parallel pool and the wire pipeline is
 * fully asynchronous. Runs one directed burst and one simultaneous bidirectional burst.
 */
public class OrderedBurstRoundTripTest {

    private final static String HOST = "localhost";

    /**
     * A dedicated port, distinct from the other socket integration tests, so the tests can
     * never collide inside one Surefire fork.
     */
    private final static int PORT = 25000;

    /**
     * The number of messages per burst.
     */
    private static final int BURST_SIZE = 100;

    /**
     * Time budget for the server to open its connector before the client connects. Unit: [ms].
     */
    private static final long SERVER_STARTUP_MILLIS = 3000;

    /**
     * Time budget for the client and server transceivers to finish connecting. Unit: [ms].
     */
    private static final long CONNECT_SETTLE_MILLIS = 1000;

    /**
     * Upper bound to wait for a full burst to arrive. Unit: [ms].
     */
    private static final long DELIVERY_TIMEOUT_MILLIS = 30000;

    /**
     * Poll interval. Unit: [ms].
     */
    private static final long POLL_INTERVAL_MILLIS = 50;

    private volatile Transceiver<SimpleMessage> serverTransceiver;
    private volatile Transceiver<SimpleMessage> clientTransceiver;
    private final Semaphore createClientAndServer = new Semaphore(0);
    private volatile Exception startupException;

    private final List<SimpleMessage> serverReceived = new ArrayList<>();
    private final List<SimpleMessage> clientReceived = new ArrayList<>();

    private CTransceiverSession serverSession() {
        return new CTransceiverSession(
            "orderedBurstServer",
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
            "orderedBurstClient",
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
        clientTransceiver.addObserver(new Observer() {
            @Override
            public void update(Observable o, Object arg) {
                if (arg instanceof SimpleMessage) {
                    synchronized (clientReceived) {
                        clientReceived.add((SimpleMessage) arg);
                    }
                }
            }
        });
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

    /**
     * @return a message carrying the burst index and a direction marker as content
     */
    private SimpleMessage burstMessage(String direction, int index) {
        return new SimpleMessage((direction + "-" + index).getBytes());
    }

    /**
     * Polls until the list holds the expected number of messages or the timeout elapses.
     */
    private void awaitCount(List<SimpleMessage> received, int expectedCount) throws InterruptedException {
        final long deadline = System.currentTimeMillis() + DELIVERY_TIMEOUT_MILLIS;
        for (;;) {
            synchronized (received) {
                if (received.size() >= expectedCount) {
                    return;
                }
            }
            if (System.currentTimeMillis() >= deadline) {
                return;
            }
            Thread.sleep(POLL_INTERVAL_MILLIS);
        }
    }

    private void assertBurstInOrder(List<SimpleMessage> received, String direction) {
        synchronized (received) {
            assertThat("Not every message of the burst arrived (direction " + direction + ").",
                received.size(), is(equalTo(BURST_SIZE)));
            for (int i = 0; i < BURST_SIZE; i++) {
                assertThat("Wrong message at position " + i + " (direction " + direction + ").",
                    received.get(i), is(equalTo(burstMessage(direction, i))));
            }
        }
    }

    // <editor-fold defaultstate="collapsed" desc="burst ordering">
    @Test
    @Timeout(90)
    public void update_burstOfMessagesSent_allArriveInSubmissionOrder() throws InterruptedException {
        // arrange
        startServerAndClient();

        // act: hand the whole burst to the transceiver as fast as possible
        for (int i = 0; i < BURST_SIZE; i++) {
            clientTransceiver.update(null, burstMessage("c2s", i));
        }
        awaitCount(serverReceived, BURST_SIZE);

        // assert
        assertBurstInOrder(serverReceived, "c2s");
    }

    @Test
    @Timeout(90)
    public void update_simultaneousBurstsInBothDirections_bothArriveCompleteAndInOrder() throws InterruptedException {
        // arrange
        startServerAndClient();

        // act: both sides fire their burst concurrently
        final Thread clientSender = new Thread(new Runnable() {
            @Override
            public void run() {
                for (int i = 0; i < BURST_SIZE; i++) {
                    clientTransceiver.update(null, burstMessage("c2s", i));
                }
            }
        });
        final Thread serverSender = new Thread(new Runnable() {
            @Override
            public void run() {
                for (int i = 0; i < BURST_SIZE; i++) {
                    serverTransceiver.update(null, burstMessage("s2c", i));
                }
            }
        });
        clientSender.start();
        serverSender.start();
        clientSender.join();
        serverSender.join();

        awaitCount(serverReceived, BURST_SIZE);
        awaitCount(clientReceived, BURST_SIZE);

        // assert: both directions complete and ordered
        assertBurstInOrder(serverReceived, "c2s");
        assertBurstInOrder(clientReceived, "s2c");
    }
    // </editor-fold>
}
