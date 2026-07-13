// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.sendAndReceive;

import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.hasItem;
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
 * End-to-end contract of {@link CTransceiver#maxPayloadLength}: an oversized message is
 * rejected on the SENDER side (surfaced as a {@link TError}; the receiver never sees it and
 * the wire id is filled so the sequence stays intact), and the pipeline keeps working for
 * later, legal messages.
 */
public class MaxPayloadLengthTest {

    private final static String HOST = "localhost";

    /**
     * A dedicated port, distinct from the other socket integration tests, so the tests can
     * never collide inside one Surefire fork.
     */
    private final static int PORT = 25001;

    /**
     * The payload bound configured on both sides for this test. Unit: [bytes].
     */
    private static final int MAX_PAYLOAD_LENGTH = 1024;

    /**
     * Time budget for the server to open its connector before the client connects. Unit: [ms].
     */
    private static final long SERVER_STARTUP_MILLIS = 3000;

    /**
     * Time budget for the client and server transceivers to finish connecting. Unit: [ms].
     */
    private static final long CONNECT_SETTLE_MILLIS = 1000;

    /**
     * Upper bound to wait for delivery / the surfaced error. Unit: [ms].
     */
    private static final long DELIVERY_TIMEOUT_MILLIS = 10000;

    /**
     * Poll interval. Unit: [ms].
     */
    private static final long POLL_INTERVAL_MILLIS = 50;

    private volatile Transceiver<SimpleMessage> serverTransceiver;
    private volatile Transceiver<SimpleMessage> clientTransceiver;
    private final Semaphore createClientAndServer = new Semaphore(0);
    private volatile Exception startupException;

    private final List<SimpleMessage> serverReceived = new ArrayList<>();
    private final List<TError> clientErrors = new ArrayList<>();

    private CTransceiverSession session(String id, ConnectionType connectionType, CConnector connector) {
        final CTransceiver transceiverConfiguration = new CTransceiver(connectionType, connector);
        transceiverConfiguration.maxPayloadLength = MAX_PAYLOAD_LENGTH;
        return new CTransceiverSession(
            id,
            new TypeToken<SimpleMessage>() {}.getType(),
            SimpleMessage.class,
            transceiverConfiguration
        );
    }

    private void startServerAndClient() throws InterruptedException {
        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    serverTransceiver = new Transceiver<>(session("maxPayloadServer",
                        ConnectionType.ServerSocketConnection,
                        new CConnector(new CServerSocketConnector(PORT))));
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
                    clientTransceiver = new Transceiver<>(session("maxPayloadClient",
                        ConnectionType.ClientSocketConnection,
                        new CConnector(new CClientSocketConnector(HOST, PORT))));
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
                if (arg instanceof TError) {
                    synchronized (clientErrors) {
                        clientErrors.add((TError) arg);
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

    // <editor-fold defaultstate="collapsed" desc="payload bound end to end">
    @Test
    @Timeout(60)
    public void update_messageAboveMaxPayloadLength_rejectedWithErrorAndPipelineKeepsWorking() throws InterruptedException {
        // arrange
        startServerAndClient();
        // four times the bound; the serialized form is certainly above it
        final SimpleMessage oversized = new SimpleMessage(new byte[4 * MAX_PAYLOAD_LENGTH]);
        final SimpleMessage regular = new SimpleMessage("small enough".getBytes());

        // act: oversized first, then a legal message
        clientTransceiver.update(null, oversized);
        clientTransceiver.update(null, regular);

        // assert: the legal message arrives although the oversized one was rejected
        final long deadline = System.currentTimeMillis() + DELIVERY_TIMEOUT_MILLIS;
        boolean delivered = false;
        while (!delivered && System.currentTimeMillis() < deadline) {
            synchronized (serverReceived) {
                delivered = !serverReceived.isEmpty();
            }
            Thread.sleep(POLL_INTERVAL_MILLIS);
        }
        synchronized (serverReceived) {
            assertThat("The legal message after the oversized one never arrived.",
                serverReceived, hasSize(1));
            assertThat(serverReceived, hasItem(regular));
        }

        // ... and the rejection was surfaced to the sender, not swallowed
        synchronized (clientErrors) {
            assertThat("The oversized message was dropped without surfacing an error.",
                clientErrors.isEmpty(), is(false));
        }
    }
    // </editor-fold>
}
