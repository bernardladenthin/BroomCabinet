/**
 * Copyright 2013 Fraunhofer FOKUS
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *    http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 */
package de.fraunhofer.fokus.jackpot;

import de.fraunhofer.fokus.jackpot.configuration.CTransceiverSession;
import de.fraunhofer.fokus.jackpot.message.TCommand;
import de.fraunhofer.fokus.jackpot.message.TError;
import de.fraunhofer.fokus.jackpot.messageprocessing.ParallelErrorInformant;
import de.fraunhofer.fokus.jackpot.messageprocessing.SequentialMessageReceiver;
import de.fraunhofer.fokus.jackpot.util.ConcurrentMethod;

import java.util.Observable;
import java.util.Observer;
import java.util.concurrent.locks.ReentrantLock;

/**
 * Transmitter engine.
 *
 * @author VSimRTI developer team <vsimrti@fokus.fraunhofer.de>
 * @author Bernard Ladenthin <bernard.ladenthin@fokus.fraunhofer.de>
 * @param <T> Class is typed against the messages that should be send/received.
 */
public class Transceiver<T> extends Observable implements Observer, SequentialMessageReceiver<T>,
        ParallelErrorInformant {
    // TODO: BLDEBUG: remove this
    public final static boolean enableDebug = false;

    public final static void debugLog(String s) {
        if (enableDebug) {
            System.out.println("BLDEBUG: " + s);
        }
    }

    /**
     * The transceiver session settings.
     */
    private final CTransceiverSession cTransceiverSession;

    /**
     * The layer that actually processes the messages
     */
    private final MessageLayer<T> messageLayer;

    /**
     * The {@link ReentrantLock} for multiple {@link Observable} calls. First come, first serve.
     */
    private final ReentrantLock updateLock = new ReentrantLock(true);


    /**
     * Standard constructor.
     *
     * @param cTransceiverSession
     * The transceiver session settings.
     */
    public Transceiver(final CTransceiverSession cTransceiverSession) {
        this.cTransceiverSession = cTransceiverSession;
        this.messageLayer = new MessageLayer<>(this.cTransceiverSession, this);
    }

    /**
     * This implements the Oberserver part of the Transceiver, waiting for a message to be sent.
     * If this is method is called the contained message is send to the other side of the
     * connection, provided the given object is of the configured message type.
     * @param o the {@link Observable} that calles this method
     * @param arg the message to be send
     */
    @SuppressWarnings("unchecked")
    @Override
    @ConcurrentMethod
    public void update(final Observable o, final Object arg) {
        try {
            updateLock.lock();
            if (cTransceiverSession.messageClass.isAssignableFrom(arg.getClass())) {
                Transceiver.debugLog("cTransceiverSession.getMessageClass().isAssignableFrom(arg.getClass())");
                /**
                 * Redirect to the {@link de.fraunhofer.fokus.jackpot.MessageLayer}
                 */
                messageLayer.transmitMessage((T) arg);
            } else if (arg instanceof TCommand) {
                messageLayer.handleCommand((TCommand) arg);
            } else {
                throw new IllegalArgumentException("unknown object: " + arg.getClass());
            }
        } finally {
            updateLock.unlock();
        }
    }

    /**
     * {@inheritDoc} <b>This method should only be called from {@link MessageLayer}.</b>
     * This informs {@link Observer}s of incomming messages.
     */
    @Override
    public void receiveMessage(final T tm) {
        setChanged();
        notifyObservers(tm);
    }

    @Override
    @ConcurrentMethod
    public void informError(final TError error) {
        setChanged();
        notifyObservers(error);
    }

}
