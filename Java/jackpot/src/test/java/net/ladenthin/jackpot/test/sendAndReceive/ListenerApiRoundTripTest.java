// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.sendAndReceive;

import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.greaterThanOrEqualTo;
import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.instanceOf;
import static org.hamcrest.Matchers.is;
import static org.junit.jupiter.api.Assertions.assertThrows;

import com.google.gson.reflect.TypeToken;

import java.io.IOException;
import java.net.ServerSocket;
import java.net.Socket;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.Semaphore;
import java.util.concurrent.TimeUnit;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;

import net.ladenthin.jackpot.Transceiver;
import net.ladenthin.jackpot.TransceiverListener;
import net.ladenthin.jackpot.configuration.CClientSocketConnector;
import net.ladenthin.jackpot.configuration.CConnector;
import net.ladenthin.jackpot.configuration.CServerSocketConnector;
import net.ladenthin.jackpot.configuration.CTransceiver;
import net.ladenthin.jackpot.configuration.CTransceiverSession;
import net.ladenthin.jackpot.configuration.ConnectionType;
import net.ladenthin.jackpot.message.TCommand;
import net.ladenthin.jackpot.message.TError;

/**
 * End-to-end contract of the modern listener API: {@link Transceiver#addListener} /
 * {@link Transceiver#removeListener} deliver typed messages and errors without the
 * deprecated {@link java.util.Observer} plumbing, {@link Transceiver#send} returns a
 * {@link CompletableFuture} completed exactly when the peer's acknowledgement arrives (and
 * exceptionally when the message can never be acknowledged), and
 * {@link Transceiver#shutdown()} replaces the hand-built shutdown {@link TCommand}.
 */
public class ListenerApiRoundTripTest {

    private final static String HOST = "localhost";

    /**
     * Port for the healthy-pair tests. Distinct from all other integration test ports.
     */
    private final static int PORT = 28000;

    /**
     * Port for the silent-peer shutdown test.
     */
    private final static int SILENT_PORT = 28001;

    /**
     * Time budget for the server to open its connector before the client connects. Unit: [ms].
     */
    private static final long SERVER_STARTUP_MILLIS = 3000;

    /**
     * Time budget for the client and server transceivers to finish connecting. Unit: [ms].
     */
    private static final long CONNECT_SETTLE_MILLIS = 1000;

    /**
     * Upper bound for an acknowledgement of a healthy peer (acks are batched and nudged
     * roughly once per heartbeat check interval, so they arrive within seconds). Unit: [s].
     */
    private static final long ACKNOWLEDGE_TIMEOUT_SECONDS = 15;

    /**
     * Upper bound to wait for message delivery to a listener. Unit: [ms].
     */
    private static final long DELIVERY_TIMEOUT_MILLIS = 10000;

    /**
     * Upper bound for a future that must complete exceptionally. Unit: [s].
     */
    private static final long FAILURE_TIMEOUT_SECONDS = 10;

    /**
     * Settle time after a delivery to prove a removed listener stays silent. Unit: [ms].
     */
    private static final long SETTLE_AFTER_DELIVERY_MILLIS = 500;

    /**
     * Poll interval while waiting for delivery. Unit: [ms].
     */
    private static final long POLL_INTERVAL_MILLIS = 50;

    private volatile Transceiver<SimpleMessage> serverTransceiver;
    private volatile Transceiver<SimpleMessage> clientTransceiver;
    private ServerSocket silentServerSocket;
    private volatile Socket acceptedSocket;
    private final Semaphore createClientAndServer = new Semaphore(0);
    private volatile Exception startupException;

    /**
     * A recording {@link TransceiverListener}: collects messages and errors thread-safely.
     */
    private static final class RecordingListener implements TransceiverListener<SimpleMessage> {

        private final List<SimpleMessage> messages = new ArrayList<>();
        private final List<TError> errors = new ArrayList<>();

        @Override
        public void onMessage(SimpleMessage message) {
            synchronized (messages) {
                messages.add(message);
            }
        }

        @Override
        public void onError(TError error) {
            synchronized (messages) {
                errors.add(error);
            }
        }

        private int messageCount() {
            synchronized (messages) {
                return messages.size();
            }
        }

        private int errorCount() {
            synchronized (messages) {
                return errors.size();
            }
        }
    }

    // <editor-fold defaultstate="collapsed" desc="test harness">
    private CTransceiverSession serverSession() {
        return new CTransceiverSession(
            "listenerApiServer",
            new TypeToken<SimpleMessage>() {}.getType(),
            SimpleMessage.class,
            new CTransceiver(
                ConnectionType.ServerSocketConnection,
                new CConnector(new CServerSocketConnector(PORT))
            )
        );
    }

    private CTransceiverSession clientSession(int port) {
        return new CTransceiverSession(
            "listenerApiClient",
            new TypeToken<SimpleMessage>() {}.getType(),
            SimpleMessage.class,
            new CTransceiver(
                ConnectionType.ClientSocketConnection,
                new CConnector(new CClientSocketConnector(HOST, port))
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
                    clientTransceiver = new Transceiver<>(clientSession(PORT));
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

    /**
     * Polls until the listener received the expected number of messages or the timeout
     * elapses.
     *
     * @return the number of messages the listener received
     */
    private int waitForMessages(RecordingListener listener, int expectedCount)
        throws InterruptedException {
        final long deadline = System.currentTimeMillis() + DELIVERY_TIMEOUT_MILLIS;
        while (listener.messageCount() < expectedCount
            && System.currentTimeMillis() < deadline) {
            Thread.sleep(POLL_INTERVAL_MILLIS);
        }
        return listener.messageCount();
    }

    /**
     * Polls until the listener received at least one error or the timeout elapses.
     *
     * @return the number of errors the listener received
     */
    private int waitForErrors(RecordingListener listener) throws InterruptedException {
        final long deadline = System.currentTimeMillis() + DELIVERY_TIMEOUT_MILLIS;
        while (listener.errorCount() < 1 && System.currentTimeMillis() < deadline) {
            Thread.sleep(POLL_INTERVAL_MILLIS);
        }
        return listener.errorCount();
    }
    // </editor-fold>

    // <editor-fold defaultstate="collapsed" desc="send + listener happy path">
    @Test
    @Timeout(60)
    public void send_healthyPeer_listenerReceivesMessageAndFutureCompletesOnAcknowledgement()
        throws Exception {
        // arrange
        startServerAndClient();
        final RecordingListener serverListener = new RecordingListener();
        serverTransceiver.addListener(serverListener);
        final SimpleMessage message = new SimpleMessage("listener-api-hello".getBytes());

        // act
        final CompletableFuture<Void> acknowledged = clientTransceiver.send(message);
        acknowledged.get(ACKNOWLEDGE_TIMEOUT_SECONDS, TimeUnit.SECONDS);
        final int received = waitForMessages(serverListener, 1);

        // assert: the listener got the typed message, no Observer plumbing involved
        assertThat(received, is(equalTo(1)));
        synchronized (serverListener.messages) {
            assertThat(serverListener.messages, hasSize(1));
            assertThat(serverListener.messages.get(0), is(equalTo(message)));
        }
    }
    // </editor-fold>

    // <editor-fold defaultstate="collapsed" desc="removeListener">
    @Test
    @Timeout(60)
    public void removeListener_removedListener_notInvokedAnymore() throws Exception {
        // arrange
        startServerAndClient();
        final RecordingListener keptListener = new RecordingListener();
        final RecordingListener removedListener = new RecordingListener();
        serverTransceiver.addListener(keptListener);
        serverTransceiver.addListener(removedListener);

        // act
        final boolean removed = serverTransceiver.removeListener(removedListener);
        final boolean removedAgain = serverTransceiver.removeListener(removedListener);
        clientTransceiver.send(new SimpleMessage("after-removal".getBytes()))
            .get(ACKNOWLEDGE_TIMEOUT_SECONDS, TimeUnit.SECONDS);
        final int keptReceived = waitForMessages(keptListener, 1);
        Thread.sleep(SETTLE_AFTER_DELIVERY_MILLIS);

        // assert
        assertThat(removed, is(true));
        assertThat(removedAgain, is(false));
        assertThat(keptReceived, is(equalTo(1)));
        assertThat(removedListener.messageCount(), is(equalTo(0)));
    }
    // </editor-fold>

    // <editor-fold defaultstate="collapsed" desc="throwing listener isolation">
    @Test
    @Timeout(60)
    public void onMessage_firstListenerThrows_secondListenerStillReceives() throws Exception {
        // arrange
        startServerAndClient();
        final TransceiverListener<SimpleMessage> throwingListener =
            new TransceiverListener<SimpleMessage>() {
                @Override
                public void onMessage(SimpleMessage message) {
                    throw new RuntimeException("deliberately misbehaving listener");
                }
            };
        final RecordingListener recordingListener = new RecordingListener();
        serverTransceiver.addListener(throwingListener);
        serverTransceiver.addListener(recordingListener);

        // act
        clientTransceiver.send(new SimpleMessage("survives-throwing-listener".getBytes()))
            .get(ACKNOWLEDGE_TIMEOUT_SECONDS, TimeUnit.SECONDS);
        final int received = waitForMessages(recordingListener, 1);

        // assert: the misbehaving listener neither starved the second listener nor killed
        // the delivering library thread
        assertThat(received, is(equalTo(1)));
    }
    // </editor-fold>

    // <editor-fold defaultstate="collapsed" desc="send failure surfaces in the future + onError">
    @Test
    @Timeout(60)
    public void send_serializationFails_futureCompletesExceptionallyAndListenerOnErrorInvoked()
        throws Exception {
        // arrange
        startServerAndClient();
        final RecordingListener clientListener = new RecordingListener();
        clientTransceiver.addListener(clientListener);
        final UnserializableMessage poisonMessage =
            new UnserializableMessage("poison".getBytes());

        // act
        final CompletableFuture<Void> acknowledged = clientTransceiver.send(poisonMessage);
        final ExecutionException exception = assertThrows(ExecutionException.class,
            () -> acknowledged.get(FAILURE_TIMEOUT_SECONDS, TimeUnit.SECONDS));
        final int errors = waitForErrors(clientListener);

        // assert: the failure reaches both the send future and the error callback
        assertThat(exception.getCause(), is(instanceOf(Exception.class)));
        assertThat(errors, is(greaterThanOrEqualTo(1)));
    }
    // </editor-fold>

    // <editor-fold defaultstate="collapsed" desc="shutdown fails pending futures">
    @Test
    @Timeout(60)
    public void send_peerNeverAcknowledges_shutdownCompletesFutureExceptionally()
        throws Exception {
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
        clientTransceiver = new Transceiver<>(clientSession(SILENT_PORT));
        Thread.sleep(CONNECT_SETTLE_MILLIS);

        // act: the message is written but never acknowledged, then the modern shutdown
        final CompletableFuture<Void> acknowledged =
            clientTransceiver.send(new SimpleMessage("never-acknowledged".getBytes()));
        clientTransceiver.shutdown();

        // assert: the pending future fails instead of hanging forever
        final ExecutionException exception = assertThrows(ExecutionException.class,
            () -> acknowledged.get(FAILURE_TIMEOUT_SECONDS, TimeUnit.SECONDS));
        assertThat(exception.getCause(), is(instanceOf(IllegalStateException.class)));
        clientTransceiver = null;
    }
    // </editor-fold>
}
