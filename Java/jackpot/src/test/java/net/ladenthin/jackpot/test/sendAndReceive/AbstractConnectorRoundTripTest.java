// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.sendAndReceive;

import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.is;
import static org.hamcrest.Matchers.not;
import static org.hamcrest.Matchers.sameInstance;

import java.util.Observable;
import java.util.Observer;
import java.util.Stack;
import java.util.concurrent.Semaphore;
import java.util.concurrent.TimeUnit;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;

import net.ladenthin.jackpot.Transceiver;
import net.ladenthin.jackpot.configuration.CTransceiverSession;
import net.ladenthin.jackpot.message.TCommand;
import net.ladenthin.jackpot.message.TError;

/**
 * Abstract round-trip test: a server and a client {@link Transceiver} are connected through
 * the connector supplied by the concrete subclass, one message is fired at both sides, and
 * both sides must receive a deserialized copy.
 */
public abstract class AbstractConnectorRoundTripTest extends Observable implements Observer {

    abstract CTransceiverSession getServerTransceiver();
    abstract CTransceiverSession getClientTransceiver();

    private volatile Transceiver<SimpleMessage> serverTransceiver;
    private volatile Transceiver<SimpleMessage> clientTransceiver;
    private final Semaphore createClientAndServer = new Semaphore(0);
    private final static SimpleMessage testMessage =
        new SimpleMessage(AbstractConnectorRoundTripTest.class.getCanonicalName().getBytes());

    private final Stack<SimpleMessage> receivedMessages = new Stack<>();

    private volatile Exception exception;

    /**
     * Upper bound for {@link #awaitMessages(int)}. Generous on purpose: the test only ever
     * needs to wait this long when something is actually broken (a healthy localhost round
     * trip typically finishes in well under a second).
     */
    private static final long MESSAGE_WAIT_TIMEOUT_MILLIS = 5000;

    /**
     * Poll interval for {@link #awaitMessages(int)}. Unit: [ms].
     */
    private static final long MESSAGE_POLL_INTERVAL_MILLIS = 50;

    /**
     * Time budget for the server to open its connector before the client connects. Unit: [ms].
     */
    private static final long SERVER_STARTUP_MILLIS = 3000;

    /**
     * Time budget for the client and server transceivers to finish connecting. Unit: [ms].
     */
    private static final long CONNECT_SETTLE_MILLIS = 1000;

    /**
     * Polls {@link #receivedMessages} instead of sleeping a fixed duration, so a healthy run
     * finishes as soon as both messages arrive rather than always paying the worst-case delay.
     */
    private void awaitMessages(int expectedCount) throws InterruptedException {
        final long deadline = System.currentTimeMillis() + MESSAGE_WAIT_TIMEOUT_MILLIS;
        while (exception == null && receivedMessages.size() < expectedCount
            && System.currentTimeMillis() < deadline) {
            Thread.sleep(MESSAGE_POLL_INTERVAL_MILLIS);
        }
    }

    private void fireMessage() {
        setChanged();
        notifyObservers(testMessage);
    }

    private void newServerTransceiver() {
        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    serverTransceiver = new Transceiver<>(getServerTransceiver());
                } catch (Exception e) {
                    exception = e;
                } finally {
                    createClientAndServer.release();
                }
            }
        }).start();
    }

    private void newClientTransceiver() {
        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    clientTransceiver = new Transceiver<>(getClientTransceiver());
                } catch (Exception e) {
                    exception = e;
                } finally {
                    createClientAndServer.release();
                }
            }
        }).start();
    }

    @Test
    @Timeout(60)
    public void roundTrip_messageFiredAtBothSides_bothSidesReceiveDistinctCopies() throws InterruptedException {
        // arrange
        newServerTransceiver();

        // give the server a few seconds to initialize the connectors
        Thread.sleep(SERVER_STARTUP_MILLIS);

        newClientTransceiver();

        final boolean successful = createClientAndServer.tryAcquire(2, 3, TimeUnit.SECONDS);
        if (!successful) {
            throw new RuntimeException("Timeout. Wait too long to start up threads.");
        }
        if (exception != null) {
            throw new RuntimeException(exception);
        }

        // give the server and client a few seconds to connect
        Thread.sleep(CONNECT_SETTLE_MILLIS);

        serverTransceiver.addObserver(this);
        clientTransceiver.addObserver(this);

        this.addObserver(serverTransceiver);
        this.addObserver(clientTransceiver);

        // The shutdown command must always be sent, even if an assertion below fails —
        // otherwise the server/client worker threads and their sockets are leaked into
        // whichever test runs next in this fork (Surefire reuses the forked JVM by default).
        try {
            // act
            fireMessage();
            awaitMessages(2);

            if (exception != null) {
                throw new RuntimeException(exception);
            }

            // assert
            assertThat("Did not receive exactly two messages (server echo + client echo).",
                receivedMessages, hasSize(2));
            for (SimpleMessage sm : receivedMessages) {
                assertThat("The received message must be a deserialized copy, not the sent instance",
                    sm, is(not(sameInstance(testMessage))));
            }
        } finally {
            receivedMessages.clear();
            setChanged();
            TCommand command = new TCommand();
            command.shutdown = true;
            notifyObservers(command);
        }
    }

    @Override
    public synchronized void update(Observable o, Object arg) {
        if (arg instanceof SimpleMessage) {
            SimpleMessage sm = (SimpleMessage) arg;
            receivedMessages.add(sm);
        } else if (arg instanceof TError) {
            TError te = (TError) arg;
            throw new RuntimeException(te.toString());
        }
    }
}
