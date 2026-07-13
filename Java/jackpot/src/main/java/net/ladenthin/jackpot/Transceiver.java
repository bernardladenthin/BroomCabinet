// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot;

import net.ladenthin.jackpot.configuration.CTransceiverSession;
import net.ladenthin.jackpot.message.TCommand;
import net.ladenthin.jackpot.message.TError;
import net.ladenthin.jackpot.messageprocessing.ParallelErrorInformant;
import net.ladenthin.jackpot.messageprocessing.SequentialMessageReceiver;
import net.ladenthin.jackpot.util.ConcurrentMethod;

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
        /**
         * Fail fast with a clear message: without the guard a null argument surfaced as an
         * accidental NullPointerException from arg.getClass().
         */
        if (arg == null) {
            throw new IllegalArgumentException("the message to send must not be null");
        }
        try {
            updateLock.lock();
            if (cTransceiverSession.messageClass.isAssignableFrom(arg.getClass())) {
                Transceiver.debugLog("cTransceiverSession.getMessageClass().isAssignableFrom(arg.getClass())");
                /**
                 * Redirect to the {@link net.ladenthin.jackpot.MessageLayer}
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

    /**
     * The number of transmitted messages the other side has not acknowledged yet. Every
     * message is retained until its acknowledgement arrives (and resent if it does not), so
     * a healthy connection keeps this value near zero.
     *
     * @return the count of retained (unacknowledged) messages
     */
    public long getUnacknowledgedMessageCount() {
        return messageLayer.getUnacknowledgedMessageCount();
    }

}
