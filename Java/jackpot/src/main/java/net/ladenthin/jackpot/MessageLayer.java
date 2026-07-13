// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot;

import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

import net.ladenthin.jackpot.configuration.CTransceiverSession;
import net.ladenthin.jackpot.interfaces.MessageIdGenerator;
import net.ladenthin.jackpot.interfaces.ShutdownRunnable;
import net.ladenthin.jackpot.message.TCommand;
import net.ladenthin.jackpot.messageprocessing.*;
import net.ladenthin.jackpot.messageprocessing.ParallelMessageTransmitter;
import net.ladenthin.jackpot.util.BinaryMessage;
import net.ladenthin.jackpot.util.ConcurrentMethod;
import net.ladenthin.jackpot.util.ParentEnsureFairProcessingSequence;
import net.ladenthin.jackpot.util.ParentEnsureSynchronized;

/**
 * 
 * @author VSimRTI developer team <vsimrti@fokus.fraunhofer.de>
 * @author Bernard Ladenthin <bernard.ladenthin@fokus.fraunhofer.de>
 * @param <T> 
 */
public class MessageLayer<T> implements ParallelMessageTransmitter<T>, Runnable, 
        ParallelCommandHandler, SequentialBinaryMessageTransmitter,
        ParallelMessageReceiver<T>, MessageIdGenerator {

    /**
     * The boolean flag to shutdown the transceiver.
     */
    private final AtomicBoolean shutdown = new AtomicBoolean(false);

    /**
     * The Transceiver that created this class and forms the interface to the application
     * using this library.
     */
    private final Transceiver<T> transceiver;

    /**
     * The transceiver session settings.
     */
    private final CTransceiverSession cTransceiverSession;

    private final Thread thread;

    // private final Deque<Long> receivedMesages = new ArrayDeque<>();

    /**
     * The {@link SequentialMessageSorter} instance.
     */
    // private final SequentialMessageSorter<T> interceptor;

    private final SerializeLayer<T> serializeLayer;

    /**
     * The {@link ConnectionLayer}.
     */
    private final ConnectionLayer<T> connectionLayer;

    private final AtomicLong nextMessageId;

    public MessageLayer(final CTransceiverSession cTransceiverSession,
        final Transceiver<T> transceiver) {
        this.cTransceiverSession = cTransceiverSession;
        this.nextMessageId = new AtomicLong(cTransceiverSession.initialMessageId);
        this.transceiver = transceiver;

        // provide error logging facilities for lower layers
        ErrorLayer errorLayer = new ErrorLayer(transceiver);
        connectionLayer = new ConnectionLayer<>(cTransceiverSession, transceiver, errorLayer, this);
        serializeLayer  = new SerializeLayer<>(cTransceiverSession, this, errorLayer, this);

        /*
        interceptor = new SequentialMessageSorter<>(
            messageToTransceiver,
            cTransceiverSession.getTransceiverConfiguration().messageIdLong
        );
        */

        thread = new Thread(this,
            "jackpot-MessageLayer-" + cTransceiverSession.transceiverId);
        thread.start();
    }

    /**
     * {@inheritDoc} <b>This method should only be called from the {@link Transceiver}.</b>
     */
    @Override
    @ConcurrentMethod //OK
    @ParentEnsureSynchronized //OK
    @ParentEnsureFairProcessingSequence //OK
    public void transmitMessage(final T message) {
        /*
        lastTSend.set(
            tm.information.systemMillis = System.currentTimeMillis()
        );
        */
        /**
         * Redirect to the {@link net.ladenthin.jackpot.SerializeLayer}
         */
        serializeLayer.transmitMessage(message);
    }

    /**
     * {@inheritDoc} <b>This method should only be called from the {@link SerializeLayer}.</b>
     */
    @Override
    @ConcurrentMethod
    @ParentEnsureSynchronized
    @ParentEnsureFairProcessingSequence
    public void transmitMessage(final BinaryMessage bm) {
        Transceiver.debugLog("MessageLayer.transmitMessage(final BinaryMessage bm): message serialized, now handle");
        /**
         * Redirect to the {@link net.ladenthin.jackpot.ConnectionLayer}
         */
        connectionLayer.transmitMessage(bm);
    }

    @Override
    @ConcurrentMethod
    public void handleCommand(final TCommand command) {
        if (command.shutdown) {
            shutdown.set(true);
            /**
             * The {@link SerializeLayer} is not owned by the {@link ConnectionLayer}, so it
             * must be shut down here as well — otherwise its loop thread waits on its
             * semaphore forever.
             */
            serializeLayer.shutdownRunnable();
            connectionLayer.shutdownRunnable();
        }
    }

    /**
     * {@inheritDoc} <b>This method should only be called from the {@link ConnectionLayer}.</b>
     */
    @Override
    @ConcurrentMethod
    public void receiveMessage(T tm) {
        // TODO:
        // lastTReceived.set(System.currentTimeMillis());
        /*
        synchronized (receivedMesages) {
            receivedMesages.add(tm.information.messageIdLong);
        }
        interceptor.transmitMessage(tm);
        */
        transceiver.receiveMessage(tm);
    }

    @Override
    public void run() {
        // TODO Auto-generated method stub
    }

    /**
     * The number of written messages not acknowledged by the other side yet.
     *
     * @return the count of retained (unacknowledged) messages
     */
    public long getUnacknowledgedMessageCount() {
        return connectionLayer.getUnacknowledgedMessageCount();
    }

    // TODO: This method should not be there
    @Override
    public long getNextId() {
        final long nextId = nextMessageId.incrementAndGet();
        if (nextId >= cTransceiverSession.lastMessageId) {
            throw new RuntimeException("getLastMessageId reached.");
        }
        return nextId;
    }

}
