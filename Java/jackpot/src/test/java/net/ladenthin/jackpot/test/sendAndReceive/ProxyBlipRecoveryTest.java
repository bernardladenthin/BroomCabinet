// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.sendAndReceive;

import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.is;

import com.google.gson.reflect.TypeToken;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
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
import net.ladenthin.jackpot.configuration.CMessageIdLong;
import net.ladenthin.jackpot.configuration.CServerSocketConnector;
import net.ladenthin.jackpot.configuration.CTransceiver;
import net.ladenthin.jackpot.configuration.CTransceiverSession;
import net.ladenthin.jackpot.configuration.ConnectionType;
import net.ladenthin.jackpot.configuration.Heartbeat;
import net.ladenthin.jackpot.configuration.SerializationType;
import net.ladenthin.jackpot.configuration.SettingsCompression;
import net.ladenthin.jackpot.message.TCommand;

/**
 * The end-to-end reliability proof: the client talks to the server through a TCP proxy that
 * is KILLED mid-session and restarted a moment later — a real connection loss while both
 * transceivers stay alive. Messages handed to the transceiver during the outage must arrive,
 * complete and in order, after the connection recovers (transparent reconnect on both sides
 * plus the retain/resend machinery closing any wire gap).
 */
public class ProxyBlipRecoveryTest {

    private final static String HOST = "localhost";

    /**
     * The proxy port the client connects to. Distinct from all other integration test ports.
     */
    private final static int PROXY_PORT = 26000;

    /**
     * The real server port the proxy forwards to.
     */
    private final static int SERVER_PORT = 26001;

    /**
     * Fast resend so recovery happens within the test budget. Unit: [ms].
     */
    private static final long RESEND_INTERVAL_MILLIS = 1000;

    /**
     * Time budget for the server to open its connector before the client connects. Unit: [ms].
     */
    private static final long SERVER_STARTUP_MILLIS = 3000;

    /**
     * Time budget for the client and server transceivers to finish connecting. Unit: [ms].
     */
    private static final long CONNECT_SETTLE_MILLIS = 1000;

    /**
     * How long the connection stays dead. Unit: [ms].
     */
    private static final long OUTAGE_MILLIS = 2000;

    /**
     * Upper bound to wait for delivery. Covers a few reconnect attempts (the reconnect loop
     * retries every 5 seconds). Unit: [ms].
     */
    private static final long DELIVERY_TIMEOUT_MILLIS = 45000;

    /**
     * Poll interval. Unit: [ms].
     */
    private static final long POLL_INTERVAL_MILLIS = 100;

    /**
     * A minimal single-connection TCP forwarder that can be killed abruptly.
     */
    private static final class TcpProxy {

        private final ServerSocket listener;
        private volatile Socket clientSide;
        private volatile Socket serverSide;

        TcpProxy() throws IOException {
            listener = new ServerSocket();
            listener.setReuseAddress(true);
            listener.bind(new InetSocketAddress(PROXY_PORT));
            new Thread(new Runnable() {
                @Override
                public void run() {
                    try {
                        clientSide = listener.accept();
                        serverSide = new Socket(HOST, SERVER_PORT);
                        pump(clientSide.getInputStream(), serverSide.getOutputStream());
                        pump(serverSide.getInputStream(), clientSide.getOutputStream());
                    } catch (IOException e) {
                        // killed or peer gone — nothing to do
                    }
                }
            }, "test-proxy-acceptor").start();
        }

        private void pump(final InputStream in, final OutputStream out) {
            new Thread(new Runnable() {
                @Override
                public void run() {
                    final byte[] buffer = new byte[8192];
                    try {
                        int read;
                        while ((read = in.read(buffer)) >= 0) {
                            out.write(buffer, 0, read);
                            out.flush();
                        }
                    } catch (IOException e) {
                        // killed or peer gone
                    } finally {
                        kill();
                    }
                }
            }, "test-proxy-pump").start();
        }

        /**
         * Tears the forwarded connection down abruptly — both endpoints observe a broken
         * connection.
         */
        void kill() {
            closeQuietly(listener);
            if (clientSide != null) {
                closeQuietly(clientSide);
            }
            if (serverSide != null) {
                closeQuietly(serverSide);
            }
        }

        private static void closeQuietly(final java.io.Closeable closeable) {
            try {
                closeable.close();
            } catch (IOException e) {
                // best effort
            }
        }
    }

    private volatile Transceiver<SimpleMessage> serverTransceiver;
    private volatile Transceiver<SimpleMessage> clientTransceiver;
    private volatile TcpProxy proxy;
    private final Semaphore createClientAndServer = new Semaphore(0);
    private volatile Exception startupException;

    private final List<SimpleMessage> serverReceived = new ArrayList<>();

    private CTransceiverSession session(String id, ConnectionType connectionType, CConnector connector) {
        return new CTransceiverSession(
            id,
            new TypeToken<SimpleMessage>() {}.getType(),
            SimpleMessage.class,
            new CTransceiver(
                SerializationType.ObjectOutputStreamSerialization,
                SerializationType.ObjectOutputStreamSerialization,
                connectionType,
                new SettingsCompression(),
                connector,
                new Heartbeat(RESEND_INTERVAL_MILLIS),
                new CMessageIdLong()
            )
        );
    }

    private void startEverything() throws IOException, InterruptedException {
        proxy = new TcpProxy();

        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    serverTransceiver = new Transceiver<>(session("blipServer",
                        ConnectionType.ServerSocketConnection,
                        new CConnector(new CServerSocketConnector(SERVER_PORT))));
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
                    clientTransceiver = new Transceiver<>(session("blipClient",
                        ConnectionType.ClientSocketConnection,
                        new CConnector(new CClientSocketConnector(HOST, PROXY_PORT))));
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
        if (proxy != null) {
            proxy.kill();
        }
    }

    private void awaitCount(int expectedCount) throws InterruptedException {
        final long deadline = System.currentTimeMillis() + DELIVERY_TIMEOUT_MILLIS;
        for (;;) {
            synchronized (serverReceived) {
                if (serverReceived.size() >= expectedCount) {
                    return;
                }
            }
            if (System.currentTimeMillis() >= deadline) {
                return;
            }
            Thread.sleep(POLL_INTERVAL_MILLIS);
        }
    }

    // <editor-fold defaultstate="collapsed" desc="connection loss recovery">
    @Test
    @Timeout(120)
    public void update_connectionKilledAndRestoredMidSession_messagesSentDuringOutageArriveInOrder()
        throws IOException, InterruptedException {
        // arrange: a healthy session through the proxy
        startEverything();
        final SimpleMessage before = new SimpleMessage("before-outage".getBytes());
        final SimpleMessage duringFirst = new SimpleMessage("during-outage-1".getBytes());
        final SimpleMessage duringSecond = new SimpleMessage("during-outage-2".getBytes());

        clientTransceiver.update(null, before);
        awaitCount(1);
        synchronized (serverReceived) {
            assertThat("Sanity: the pre-outage message must arrive.",
                serverReceived.size(), is(equalTo(1)));
        }

        // act: kill the connection, send while dead, then restore
        proxy.kill();
        clientTransceiver.update(null, duringFirst);
        clientTransceiver.update(null, duringSecond);
        Thread.sleep(OUTAGE_MILLIS);
        proxy = new TcpProxy();

        // assert: both outage messages arrive after recovery, in order
        awaitCount(3);
        synchronized (serverReceived) {
            assertThat("Messages sent during the outage were lost"
                + " (received: " + serverReceived.size() + " of 3).",
                serverReceived.size(), is(equalTo(3)));
            assertThat(serverReceived.get(0), is(equalTo(before)));
            assertThat(serverReceived.get(1), is(equalTo(duringFirst)));
            assertThat(serverReceived.get(2), is(equalTo(duringSecond)));
        }
    }
    // </editor-fold>
}
