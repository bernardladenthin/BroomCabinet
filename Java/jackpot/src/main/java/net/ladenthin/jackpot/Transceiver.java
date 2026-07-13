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

import java.util.List;
import java.util.Observable;
import java.util.Observer;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CopyOnWriteArrayList;
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
     * The registered {@link TransceiverListener}s (the modern alternative to the
     * {@link Observer}s). Copy-on-write: registration is rare, iteration happens per
     * delivered message.
     */
    private final List<TransceiverListener<T>> listeners = new CopyOnWriteArrayList<>();


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
        if (cTransceiverSession.messageClass.isAssignableFrom(arg.getClass())) {
            /**
             * Sender-side backpressure, acquired BEFORE the update lock: a sender blocked on
             * a full pipeline must never hold the lock, otherwise commands (e.g. shutdown)
             * and other senders could not get through. Commands below are deliberately not
             * subject to backpressure.
             */
            messageLayer.acquireSendPermit();
            try {
                updateLock.lock();
                Transceiver.debugLog("cTransceiverSession.getMessageClass().isAssignableFrom(arg.getClass())");
                /**
                 * Redirect to the {@link net.ladenthin.jackpot.MessageLayer}
                 */
                messageLayer.transmitMessage((T) arg);
            } finally {
                updateLock.unlock();
            }
        } else if (arg instanceof TCommand) {
            try {
                updateLock.lock();
                messageLayer.handleCommand((TCommand) arg);
            } finally {
                updateLock.unlock();
            }
        } else {
            throw new IllegalArgumentException("unknown object: " + arg.getClass());
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
        for (final TransceiverListener<T> listener : listeners) {
            try {
                listener.onMessage(tm);
            } catch (RuntimeException e) {
                /**
                 * A misbehaving listener must neither kill the delivering library thread
                 * nor starve the listeners after it. Deliberately swallowed — routing it
                 * into onError would recurse on a listener that also throws there.
                 */
            }
        }
    }

    @Override
    @ConcurrentMethod
    public void informError(final TError error) {
        setChanged();
        notifyObservers(error);
        for (final TransceiverListener<T> listener : listeners) {
            try {
                listener.onError(error);
            } catch (RuntimeException e) {
                // see receiveMessage: listener isolation
            }
        }
    }

    /**
     * Register a typed listener for received messages and errors — the modern alternative
     * to {@link java.util.Observer}. Listeners are invoked on library threads in
     * registration order; a throwing listener never affects the others.
     *
     * @param listener the listener to add; must not be {@code null}
     */
    public void addListener(final TransceiverListener<T> listener) {
        if (listener == null) {
            throw new IllegalArgumentException("the listener must not be null");
        }
        listeners.add(listener);
    }

    /**
     * Remove a previously registered listener.
     *
     * @param listener the listener to remove
     * @return {@code true} when the listener was registered
     */
    public boolean removeListener(final TransceiverListener<T> listener) {
        return listeners.remove(listener);
    }

    /**
     * Send a message — the modern alternative to {@link #update(Observable, Object)}. The
     * returned future completes normally once the other side acknowledged the message
     * (at-least-once on the wire, exactly-once to the receiving application), and
     * exceptionally when the message can never be acknowledged (failed serialization,
     * oversized payload, shutdown while pending). Subject to the same backpressure as
     * {@code update}: the call may block and throws {@link IllegalStateException} after
     * {@code sendTimeout}.
     *
     * @param message the message to send; must not be {@code null}
     * @return a future completed on acknowledgement
     */
    public CompletableFuture<Void> send(final T message) {
        if (message == null) {
            throw new IllegalArgumentException("the message to send must not be null");
        }
        final CompletableFuture<Void> acknowledged = new CompletableFuture<>();
        /**
         * Same discipline as {@link #update}: acquire the backpressure permit BEFORE the
         * update lock, so a blocked sender never blocks commands or other senders.
         */
        messageLayer.acquireSendPermit();
        updateLock.lock();
        try {
            messageLayer.transmitMessage(message, acknowledged);
        } finally {
            updateLock.unlock();
        }
        return acknowledged;
    }

    /**
     * Shut the transceiver down — the modern alternative to sending a
     * {@link TCommand} with {@code shutdown = true}. Terminates every library thread,
     * closes the connector, wakes blocked senders and fails all pending {@link #send}
     * futures.
     */
    public void shutdown() {
        final TCommand command = new TCommand();
        command.shutdown = true;
        update(null, command);
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
