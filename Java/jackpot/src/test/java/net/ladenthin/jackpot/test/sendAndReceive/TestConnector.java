// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.sendAndReceive;

import net.ladenthin.jackpot.Transceiver;
import net.ladenthin.jackpot.configuration.CTransceiverSession;
import net.ladenthin.jackpot.message.TCommand;
import net.ladenthin.jackpot.message.TError;
import org.junit.Test;

import java.util.*;
import java.util.concurrent.Semaphore;
import java.util.concurrent.TimeUnit;

import static org.junit.Assert.assertTrue;

public abstract class TestConnector extends Observable implements Observer {

    abstract CTransceiverSession getServerTransceiver();
    abstract CTransceiverSession getClientTransceiver();

    private volatile Transceiver<SimpleMessage> serverTransceiver;
    private volatile Transceiver<SimpleMessage> clientTransceiver;
    private final Semaphore createClientAndServer = new Semaphore(0);
    private final static SimpleMessage testMessage = new SimpleMessage(TestSocket.class.getCanonicalName().getBytes());

    private final Stack<SimpleMessage> receivedMessages = new Stack<>();

    private volatile Exception exception;

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
    public void roundTrip() {
        newServerTransceiver();

        //give the server a few seconds to initialize the connectors
        try {
            Thread.sleep(3000);
        } catch (InterruptedException e) {
            e.printStackTrace();
        }

        newClientTransceiver();

        try {
            boolean successful = createClientAndServer.tryAcquire(2, 3, TimeUnit.SECONDS);
            if (!successful) {
                throw new RuntimeException("Timeout. Wait too long to start up threads.");
            }
            if (exception != null) {
                throw new RuntimeException(exception);
            }
        } catch (InterruptedException e1) {
            e1.printStackTrace();
        }

        //give the server and client a few seconds to connect
        try {
            Thread.sleep(1000);
        } catch (InterruptedException e) {
            e.printStackTrace();
        }

        serverTransceiver.addObserver(this);
        clientTransceiver.addObserver(this);

        this.addObserver(serverTransceiver);
        this.addObserver(clientTransceiver);

        fireMessage();
        try {
            Thread.sleep(3000);
        } catch (InterruptedException e) {
            e.printStackTrace();
        }
        assertTrue("Do not received two messages. Received " + receivedMessages.size(),
                receivedMessages.size() == 2);
        for (SimpleMessage sm : receivedMessages) {
            assertTrue("Test message is the same as the received", sm != testMessage);
        }
        receivedMessages.clear();
        setChanged();
        TCommand command = new TCommand();
        command.shutdown = true;
        notifyObservers(command);
    }

    @Override
    public synchronized void update(Observable o, Object arg) {
        if(arg instanceof SimpleMessage) {
            SimpleMessage sm = (SimpleMessage)arg;
            receivedMessages.add(sm);
        } else if(arg instanceof TError) {
            TError te = (TError)arg;
            throw new RuntimeException(te.toString());
        }
    }
}
