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

import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

import de.fraunhofer.fokus.jackpot.configuration.CTransceiverSession;
import de.fraunhofer.fokus.jackpot.interfaces.MessageIdGenerator;
import de.fraunhofer.fokus.jackpot.interfaces.ShutdownRunnable;
import de.fraunhofer.fokus.jackpot.message.TCommand;
import de.fraunhofer.fokus.jackpot.messageprocessing.*;
import de.fraunhofer.fokus.jackpot.messageprocessing.ParallelMessageTransmitter;
import de.fraunhofer.fokus.jackpot.util.BinaryMessage;
import de.fraunhofer.fokus.jackpot.util.ConcurrentMethod;
import de.fraunhofer.fokus.jackpot.util.ParentEnsureFairProcessingSequence;
import de.fraunhofer.fokus.jackpot.util.ParentEnsureSynchronized;

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

        thread = new Thread(this);
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
         * Redirect to the {@link de.fraunhofer.fokus.jackpot.SerializeLayer}
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
         * Redirect to the {@link de.fraunhofer.fokus.jackpot.ConnectionLayer}
         */
        connectionLayer.transmitMessage(bm);
    }

    @Override
    @ConcurrentMethod
    public void handleCommand(final TCommand command) {
        if (command.shutdown) {
            shutdown.set(true);
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
