// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.sendAndReceive;

import static org.hamcrest.MatcherAssert.assertThat;
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
 * Regression guard for the reconnect path: when the other side disappears for good, the
 * surviving transceiver must SURFACE the failure as a {@link TError} once its reconnect
 * budget is exhausted — it must never hang silently. The historical silent hang was a lock
 * ordering deadlock during simultaneous reader/writer reconnects (the reader owned the
 * readLock and blocked on the assignLock while the connecting writer owned the assignLock
 * and blocked on the readLock); the deadlock cycle is removed by never entering the connect
 * path while a stream lock is held. This test exercises exactly that reconnect path — both
 * the reader and the writer of the survivor fail and reconnect concurrently — and pins the
 * observable contract.
 */
public class ReconnectFailureSurfacesErrorTest {

    private final static String HOST = "localhost";

    /**
     * A dedicated port, distinct from the other socket integration tests, so the tests can
     * never collide inside one Surefire fork.
     */
    private final static int PORT = 45678;

    /**
     * Time budget for the server to open its connector before the client connects. Unit: [ms].
     */
    private static final long SERVER_STARTUP_MILLIS = 3000;

    /**
     * Time budget for the client and server transceivers to finish connecting. Unit: [ms].
     */
    private static final long CONNECT_SETTLE_MILLIS = 1000;

    /**
     * Upper bound to wait for the surfaced error. The reconnect loop tries for up to 30
     * seconds before it gives up with NoConnectionPossible, so this must exceed that budget
     * with margin. Unit: [ms].
     */
    private static final long ERROR_TIMEOUT_MILLIS = 60000;

    /**
     * Poll interval. Unit: [ms].
     */
    private static final long POLL_INTERVAL_MILLIS = 200;

    private volatile Transceiver<SimpleMessage> serverTransceiver;
    private volatile Transceiver<SimpleMessage> clientTransceiver;
    private final Semaphore createClientAndServer = new Semaphore(0);
    private volatile Exception startupException;

    /**
     * Errors surfaced by the client side.
     */
    private final List<TError> clientErrors = new ArrayList<>();

    private final Observer recordingClientObserver = new Observer() {
        @Override
        public void update(Observable o, Object arg) {
            if (arg instanceof TError) {
                synchronized (clientErrors) {
                    clientErrors.add((TError) arg);
                }
            }
        }
    };

    private CTransceiverSession serverSession() {
        return new CTransceiverSession(
            "reconnectFailureServer",
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
            "reconnectFailureClient",
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

        clientTransceiver.addObserver(recordingClientObserver);
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
    @Timeout(120)
    public void run_serverDisappearsForGood_clientSurfacesErrorInsteadOfHangingSilently() throws InterruptedException {
        // arrange
        startServerAndClient();

        // act: the server goes away for good; the client's reader and writer both hit their
        // IOExceptions and reconnect concurrently — the historical deadlock window
        final TCommand shutdownServer = new TCommand();
        shutdownServer.shutdown = true;
        serverTransceiver.update(null, shutdownServer);

        // assert: the client surfaces an error within its reconnect budget — a silent
        // (deadlocked) client would record nothing and time out here
        final long deadline = System.currentTimeMillis() + ERROR_TIMEOUT_MILLIS;
        boolean errorSurfaced = false;
        while (!errorSurfaced && System.currentTimeMillis() < deadline) {
            synchronized (clientErrors) {
                errorSurfaced = !clientErrors.isEmpty();
            }
            Thread.sleep(POLL_INTERVAL_MILLIS);
        }
        assertThat("The client neither reconnected nor surfaced an error"
            + " — it hung silently.",
            errorSurfaced, is(true));
    }
}
