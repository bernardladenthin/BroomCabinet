// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.sendAndReceive;

import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.is;

import com.google.gson.reflect.TypeToken;

import java.io.IOException;
import java.net.ServerSocket;
import java.net.Socket;
import java.util.ArrayList;
import java.util.List;
import java.util.Observable;
import java.util.Observer;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;

import net.ladenthin.jackpot.Transceiver;
import net.ladenthin.jackpot.configuration.CClientSocketConnector;
import net.ladenthin.jackpot.configuration.CConnector;
import net.ladenthin.jackpot.configuration.CMessageIdLong;
import net.ladenthin.jackpot.configuration.CTransceiver;
import net.ladenthin.jackpot.configuration.CTransceiverSession;
import net.ladenthin.jackpot.configuration.ConnectionType;
import net.ladenthin.jackpot.configuration.Heartbeat;
import net.ladenthin.jackpot.configuration.SerializationType;
import net.ladenthin.jackpot.configuration.SettingsCompression;
import net.ladenthin.jackpot.message.TCommand;
import net.ladenthin.jackpot.message.TError;

/**
 * Dead-connection detection: a peer that is transport-alive but never sends anything (not
 * even heartbeats — e.g. a frozen process behind an open TCP connection) must be detected
 * after {@link Heartbeat#connectionTimeout} and surfaced as a {@link TError} with the
 * {@code expired} flag. Historically the timeout was documented but never enforced — the
 * {@code notifyExpired} path was dead code and a silent peer went unnoticed forever on
 * transports without SO_TIMEOUT.
 */
public class ConnectionExpiredTest {

    private final static String HOST = "localhost";

    /**
     * A dedicated port, distinct from the other socket integration tests, so the tests can
     * never collide inside one Surefire fork.
     */
    private final static int PORT = 61234;

    /**
     * A short connection timeout so the expiration is observable within the test. Unit: [ms].
     */
    private static final int CONNECTION_TIMEOUT_MILLIS = 3000;

    /**
     * Upper bound to wait for the expired error — a few multiples of the connection timeout.
     * Unit: [ms].
     */
    private static final long EXPIRED_TIMEOUT_MILLIS = 15000;

    /**
     * Poll interval. Unit: [ms].
     */
    private static final long POLL_INTERVAL_MILLIS = 100;

    /**
     * The silent peer: accepts the TCP connection and then never sends a single byte.
     */
    private ServerSocket silentServerSocket;
    private volatile Socket acceptedSocket;

    private volatile Transceiver<SimpleMessage> clientTransceiver;

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

    private CTransceiverSession clientSession() {
        return new CTransceiverSession(
            "connectionExpiredClient",
            new TypeToken<SimpleMessage>() {}.getType(),
            SimpleMessage.class,
            new CTransceiver(
                SerializationType.ObjectOutputStreamSerialization,
                SerializationType.ObjectOutputStreamSerialization,
                ConnectionType.ClientSocketConnection,
                new SettingsCompression(),
                new CConnector(new CClientSocketConnector(HOST, PORT)),
                new Heartbeat(CONNECTION_TIMEOUT_MILLIS / 2, CONNECTION_TIMEOUT_MILLIS),
                new CMessageIdLong()
            )
        );
    }

    @BeforeEach
    public void setUp() throws IOException {
        silentServerSocket = new ServerSocket(PORT);
        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    acceptedSocket = silentServerSocket.accept();
                    // deliberately never write anything: the peer is silent
                } catch (IOException e) {
                    // closed in tearDown
                }
            }
        }).start();
    }

    @AfterEach
    public void tearDown() throws IOException {
        if (clientTransceiver != null) {
            final TCommand command = new TCommand();
            command.shutdown = true;
            clientTransceiver.update(null, command);
        }
        if (acceptedSocket != null) {
            acceptedSocket.close();
        }
        silentServerSocket.close();
    }

    @Test
    @Timeout(60)
    public void run_peerNeverSendsAnything_expiredErrorSurfacedAfterConnectionTimeout() throws InterruptedException {
        // arrange: connect to the silent peer
        clientTransceiver = new Transceiver<>(clientSession());
        clientTransceiver.addObserver(recordingClientObserver);

        // act: nothing — the peer stays silent

        // assert: the expired error surfaces after the connection timeout
        final long deadline = System.currentTimeMillis() + EXPIRED_TIMEOUT_MILLIS;
        boolean expiredSurfaced = false;
        while (!expiredSurfaced && System.currentTimeMillis() < deadline) {
            synchronized (clientErrors) {
                for (final TError error : clientErrors) {
                    if (error.expired) {
                        expiredSurfaced = true;
                        break;
                    }
                }
            }
            Thread.sleep(POLL_INTERVAL_MILLIS);
        }
        assertThat("No expired error surfaced although the peer never sent anything"
            + " for far longer than the connection timeout.",
            expiredSurfaced, is(true));
    }
}
