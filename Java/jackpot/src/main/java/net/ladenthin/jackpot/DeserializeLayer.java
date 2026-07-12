// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot;

import java.util.ArrayDeque;
import java.util.Deque;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.Semaphore;
import java.util.concurrent.atomic.AtomicBoolean;

import net.ladenthin.jackpot.configuration.CTransceiverSession;
import net.ladenthin.jackpot.interfaces.ShutdownRunnable;
import net.ladenthin.jackpot.messageprocessing.SequentialMessageReceiver;
import net.ladenthin.jackpot.serializer.DeserializerRunnable;
import net.ladenthin.jackpot.serializer.DeserializerFactory;
import net.ladenthin.jackpot.serializer.SerializerFactory;
import net.ladenthin.jackpot.util.BinaryMessage;
import net.ladenthin.jackpot.util.ConcurrentMethod;

public class DeserializeLayer<T> implements Runnable, ShutdownRunnable {

    /**
     * The {@link CTransceiverSession}-
     */
    private final CTransceiverSession cTransceiverSession;

    /**
     * The {@link ExecutorService}.
     */
    private final ExecutorService deserializerExecutor = Executors.newCachedThreadPool();

    protected final Deque<Future<T>> deserializerFutures = new ArrayDeque<>();

    /**
     * The {@link SerializerFactory}.
     */
    private final DeserializerFactory<T> deserializerFactory;

    /**
     * The boolean flag to shutdown the {@link #run()} method.
     */
    private final AtomicBoolean shutdown = new AtomicBoolean(false);

    /**
     * Semaphore to run the loop.
     */
    protected final Semaphore doRun = new Semaphore(0, true);

    private final Thread thread;

    /**
     * {@link ConnectionLayer}.
     */
    private final SequentialMessageReceiver<T> receiver;

    private final ErrorLayer errorLayer;

    public DeserializeLayer(final CTransceiverSession cTransceiverSession, final ErrorLayer errorLayer,
        final SequentialMessageReceiver<T> receiver) {
        this.cTransceiverSession = cTransceiverSession;
        this.errorLayer = errorLayer;
        this.receiver = receiver;
        this.deserializerFactory = new DeserializerFactoryImpl<>(cTransceiverSession);
        this.thread = new Thread(this);
        thread.start();
    }
    
    /**
     * Invoke this method to deserialize the {@link BinaryMessage} and
     * submit the result {@link T} to the upper layer.
     * @param bm the binary message to deserialize
     */
    public void dataAvailable(BinaryMessage bm) {
        /**
         * Create a new runnable to deserialize the {@link BinaryMessage}.
         */
        DeserializerRunnable<T> unboxing =
            new DeserializerRunnable<>(deserializerFactory, bm,
                cTransceiverSession.transceiverConfiguration.settingsCompression);
        
        /**
         * Submit the runnable to the {@link ExecutorService}.
         */
        final Future<T> future = deserializerExecutor.submit(unboxing);
        
        /**
         * Add the {@link Future} to the {@link Deque} to get its result later.
         */
        synchronized (deserializerFutures) {
            deserializerFutures.add(future);
        }
        
        /**
         * Releases a permit to receive the deserialization result in the
         * {@link ReadLayer#run()} loop.
         */
        doRun.release();
    }
    
    @Override
    public void run() {
        for (;;) {
            try {
                doRun.acquire();
                
                if (shutdown.get()) {
                    return;
                }
                
                final Future<T> future;
                
                /**
                 * Get the {@link Future} of the next deserialized result.
                 */
                synchronized (deserializerFutures) {
                    future = deserializerFutures.pollFirst();
                }
                
                /**
                 * Get the deserialized result.
                 * Waits if necessary for the computation to complete.
                 */
                final T tm = future.get();
                
                /**
                 * Inform the {@link ConnectionLayer}.
                 */
                receiver.receiveMessage(tm);
            } catch (InterruptedException | ExecutionException e) {
                errorLayer.notifyException(e);
            }
            
        }
    }

    @ConcurrentMethod
    @Override
    public void shutdownRunnable() {
        shutdown.set(true);
        doRun.release();
    }

}
