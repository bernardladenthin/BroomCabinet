// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot;

import net.ladenthin.jackpot.configuration.CTransceiverSession;
import net.ladenthin.jackpot.interfaces.ShutdownRunnable;
import net.ladenthin.jackpot.util.*;
import java.util.ArrayDeque;
import java.util.Deque;
import java.util.Objects;
import java.util.Set;
import java.util.SortedSet;
import java.util.TreeSet;
import java.util.concurrent.Semaphore;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;

public final class ReadLayer<T> implements ShutdownRunnable, Runnable {
    
    /**
     * The boolean flag to shutdown the {@link #run()} method.
     */
    private final AtomicBoolean shutdown = new AtomicBoolean(false);

    /**
     * The {@link CTransceiverSession}.
     */
    private final CTransceiverSession cTransceiverSession;
    
    private final Thread thread;
    
    private final ErrorLayer errorLayer;
    
    private final ConnectionLayer connectionLayer;
    
    private final Transceiver<T> transceiver;

    /**
     * The {@link DeserializeLayer}.
     */
    private final DeserializeLayer<T> deserializeLayer;

    /**
     * The {@link Semaphore} to run the loop.
     */
    private final Semaphore doRun = new Semaphore(0, true);
    
    /**
     * A {@link SortedSet} of {@link BinaryMessage}s, which are received from the other side.
     * The order is ascending.
     */
    private final SortedSet<BinaryMessage> receivedMessages = new TreeSet<>();
    
    private final AtomicLong nextMessageId;
    private final AtomicInteger rejectedPermit = new AtomicInteger();

    private final AtomicLong heartbeatReceivedLastTimestamp = new AtomicLong();
    private final AtomicLong heartbeatReceivedCount = new AtomicLong();
    
    public ReadLayer(
        final CTransceiverSession cTransceiverSession,
        final ConnectionLayer<T> connectionLayer,
        final ErrorLayer errorLayer,
        final Transceiver<T> transceiver
    ) {
        this.cTransceiverSession = cTransceiverSession;
        this.connectionLayer = connectionLayer;
        this.errorLayer = errorLayer;
        this.transceiver = transceiver;
        nextMessageId = new AtomicLong(cTransceiverSession.initialMessageId+1);

        deserializeLayer = new DeserializeLayer<>(
            cTransceiverSession,
            errorLayer,
            transceiver
        );

        this.thread = new Thread(this);
        thread.start();
    }

    @Override
    public final void run() {
        for (;;) {
            try {
                /**
                 * A permit exist?
                 */
                doRun.acquire();
                
                /**
                 * A shutdown permit. Terminate the thread.
                 */
                if (shutdown.get()) {
                    return;
                }
                
                final BinaryMessage bm;
                synchronized (receivedMessages) {
                    bm = receivedMessages.first();
                }
                
                // security check
                Objects.requireNonNull(bm);
                
                // compare the first (lowest) element to the expected messageId
                if (bm.getId() != nextMessageId.get()) {
                    // do not lose this permit, add the value to the counter
                    rejectedPermit.incrementAndGet();
                    // the message is not the expected message, wait for the next message (next permit)
                    continue;
                }
                
                // remove the message from the set
                synchronized (receivedMessages) {
                    receivedMessages.remove(bm);
                }
                // set to the next expected message id
                nextMessageId.incrementAndGet();
                // it is the expected message, release all (maybe previously) rejected permits
                doRun.release(rejectedPermit.getAndSet(0));
                
                if (bm.isStateHeartbeat()) {
                    heartbeatReceivedLastTimestamp.set(System.currentTimeMillis());
                    heartbeatReceivedCount.incrementAndGet();
                } else if (bm.isStateAcknowledged()) {
                    connectionLayer.addAcknowledgedMesages(bm.getAcknowledged());
                } else if (bm.isStateMessage()) {
                    deserializeLayer.dataAvailable(bm);
                } else {
                    throw new IllegalStateException();
                }
                
                connectionLayer.cleanAndCheckMessages();
            } catch (InterruptedException e) {
                errorLayer.notifyException(e);
            }
        }
    }
    
    public final void receiveMessage(BinaryMessage bm) {
        synchronized (receivedMessages) {
            receivedMessages.add(bm);
        }
        doRun.release();
    }

    public final long getHeartbeatReceivedLastTimestamp() {
        return heartbeatReceivedLastTimestamp.get();
    }

    public final long getHeartbeatReceivedCount() {
        return heartbeatReceivedCount.get();
    }

    @Override
    @ConcurrentMethod
    public void shutdownRunnable() {
        deserializeLayer.shutdownRunnable();
        shutdown.set(true);
        doRun.release();
    }

}
