// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.sendAndReceive;

import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.empty;
import static org.hamcrest.Matchers.is;
import static org.hamcrest.Matchers.not;

import com.google.gson.reflect.TypeToken;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.concurrent.Semaphore;
import java.util.concurrent.TimeUnit;

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
 * Regression test for the shutdown thread leak: after the shutdown command, every thread the
 * library created (all named with the {@code jackpot-} prefix) must terminate. Before the fix
 * the {@code ConnectionLayer} reader thread stayed blocked in a stream read forever on a
 * non-daemon thread, so an application using the library could never exit cleanly.
 */
public class ShutdownTerminatesThreadsTest {

    /**
     * The common name prefix of every thread created by the library.
     */
    private static final String JACKPOT_THREAD_PREFIX = "jackpot-";

    /**
     * A dedicated port, distinct from the other socket integration tests in this package, so
     * the tests can never collide inside one Surefire fork.
     */
    private final static int PORT = 34567;

    private final static String HOST = "localhost";

    /**
     * Time budget for the server to open its connector before the client connects. Unit: [ms].
     */
    private static final long SERVER_STARTUP_MILLIS = 3000;

    /**
     * Time budget for the client and server transceivers to finish connecting. Unit: [ms].
     */
    private static final long CONNECT_SETTLE_MILLIS = 1000;

    /**
     * Upper bound to wait for all jackpot threads to terminate after shutdown. Unit: [ms].
     */
    private static final long TERMINATION_TIMEOUT_MILLIS = 15000;

    /**
     * Poll interval while waiting for thread termination. Unit: [ms].
     */
    private static final long POLL_INTERVAL_MILLIS = 100;

    private volatile Transceiver<SimpleMessage> serverTransceiver;
    private volatile Transceiver<SimpleMessage> clientTransceiver;
    private final Semaphore createClientAndServer = new Semaphore(0);
    private volatile Exception startupException;

    private CTransceiverSession serverSession() {
        return new CTransceiverSession(
            "shutdownTestServer",
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
            "shutdownTestClient",
            new TypeToken<SimpleMessage>() {}.getType(),
            SimpleMessage.class,
            new CTransceiver(
                ConnectionType.ClientSocketConnection,
                new CConnector(new CClientSocketConnector(HOST, PORT))
            )
        );
    }

    /**
     * @return all currently live threads whose name carries the jackpot prefix
     */
    private Set<Thread> liveJackpotThreads() {
        final Set<Thread> result = new HashSet<>();
        for (Thread thread : Thread.getAllStackTraces().keySet()) {
            if (thread.isAlive() && thread.getName().startsWith(JACKPOT_THREAD_PREFIX)) {
                result.add(thread);
            }
        }
        return result;
    }

    @Test
    @Timeout(60)
    public void shutdownRunnable_connectedTransceiverPairShutDown_allJackpotThreadsTerminate() throws InterruptedException {
        // arrange: remember pre-existing jackpot threads (possible strays of other tests in
        // the same fork) so this test only judges the threads it created itself
        final Set<Thread> preExisting = liveJackpotThreads();

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

        // pre-assert: the transceiver pair actually created jackpot threads
        final Set<Thread> createdThreads = new HashSet<>(liveJackpotThreads());
        createdThreads.removeAll(preExisting);
        assertThat("Expected the transceiver pair to create jackpot threads",
            createdThreads, is(not(empty())));

        // act: shut both sides down
        final TCommand command = new TCommand();
        command.shutdown = true;
        clientTransceiver.update(null, command);
        serverTransceiver.update(null, command);

        // assert: every created jackpot thread terminates within the timeout
        final long deadline = System.currentTimeMillis() + TERMINATION_TIMEOUT_MILLIS;
        List<String> survivors = survivorNames(createdThreads);
        while (!survivors.isEmpty() && System.currentTimeMillis() < deadline) {
            Thread.sleep(POLL_INTERVAL_MILLIS);
            survivors = survivorNames(createdThreads);
        }
        assertThat("jackpot threads still alive after shutdown: " + survivors,
            survivors, is(empty()));
    }

    /**
     * @return the names of the given threads that are still alive
     */
    private List<String> survivorNames(Set<Thread> threads) {
        final List<String> names = new ArrayList<>();
        for (Thread thread : threads) {
            if (thread.isAlive()) {
                names.add(thread.getName());
            }
        }
        return names;
    }
}
