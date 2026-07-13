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
import net.ladenthin.jackpot.interfaces.MessageIdGenerator;
import net.ladenthin.jackpot.messageprocessing.ParallelMessageTransmitter;
import net.ladenthin.jackpot.serializer.SerializeRunnable;
import net.ladenthin.jackpot.serializer.SerializerFactory;
import net.ladenthin.jackpot.util.BinaryMessage;
import net.ladenthin.jackpot.util.ConcurrentMethod;
import net.ladenthin.jackpot.util.NamedJackpotThreadFactory;
import net.ladenthin.jackpot.util.ParentEnsureFairProcessingSequence;
import net.ladenthin.jackpot.util.ParentEnsureSynchronized;
import java.util.ConcurrentModificationException;

public class SerializeLayer<T> implements ParallelMessageTransmitter<T>, ShutdownRunnable, Runnable {

    /**
     * The {@link CTransceiverSession}-
     */
    private final CTransceiverSession cTransceiverSession;

    /**
     * The {@link ErrorLayer}.
     */
    private final ErrorLayer errorLayer;

    /**
     * The {@link SerializerFactory}.
     */
    private final SerializerFactory<T> serializerFactory;

    /**
     * The {@link ExecutorService}.
     */
    private final ExecutorService serializeExecutor = Executors.newCachedThreadPool(
        new NamedJackpotThreadFactory("jackpot-SerializeLayer-pool"));

    /**
     * A submitted serialization: the pre-allocated wire message id together with its
     * {@link Future} result. The id is needed to repair the wire sequence when the
     * serialization fails (see {@link SerializeLayer#run()}).
     */
    private static final class PendingSerialization {

        private final long id;
        private final Future<BinaryMessage> future;

        private PendingSerialization(final long id, final Future<BinaryMessage> future) {
            this.id = id;
            this.future = future;
        }
    }

    /**
     * The {@link Future} serializations with their pre-allocated wire message ids.
     */
    private final Deque<PendingSerialization> serializeFutures = new ArrayDeque<>();

    /**
     * The boolean flag to shutdown the {@link #run()} method.
     */
    private final AtomicBoolean shutdown = new AtomicBoolean(false);

    /**
     * The {@link Semaphore} to run the loop.
     */
    private final Semaphore doRun = new Semaphore(0, true);

    /**
     * The {@link net.ladenthin.jackpot.messageprocessing.SequentialBinaryMessageTransmitter} to notify finished serializations in their
     * natural order.
     */
    private final MessageLayer<T> messageLayer;

    private final MessageIdGenerator messageIdGenerator;
    private final Thread thread;

    public SerializeLayer(final CTransceiverSession cTransceiverSession,
        final MessageIdGenerator messageIdGenerator, final ErrorLayer errorLayer,
        final MessageLayer<T> messageLayer
    ) {
        this.cTransceiverSession = cTransceiverSession;
        this.messageIdGenerator = messageIdGenerator;
        this.errorLayer = errorLayer;
        this.messageLayer = messageLayer;

        serializerFactory = new SerializerFactoryImpl<>(cTransceiverSession);
        thread = new Thread(this,
            "jackpot-SerializeLayer-" + cTransceiverSession.transceiverId);
        thread.start();
    }

    @Override
    @ConcurrentMethod //OK
    @ParentEnsureSynchronized //OK
    @ParentEnsureFairProcessingSequence //OK
    public void transmitMessage(final T message) {
        /**
         * The wire message id is allocated here, before the serialization runs, to preserve
         * the submission order on the wire.
         */
        final long messageId = messageIdGenerator.getNextId();

        /**
         * Create a new {@link net.ladenthin.jackpot.serializer.SerializeRunnable} to serialize the message.
         */
        final SerializeRunnable<T> task =
            new SerializeRunnable<>(serializerFactory, messageId, message,
                cTransceiverSession.transceiverConfiguration.settingsCompression);

        /**
         * Submit the task to the executor service and add the future to the queue.
         */
        synchronized (serializeFutures) {
            serializeFutures.add(new PendingSerialization(messageId, serializeExecutor.submit(task)));
        }

        /**
         * Release a permit. In future a serialization should be finished.
         * The calling method {@link #net.ladenthin.jackpot.Transceiver.update} is encapsulated now.
         */
        doRun.release();
    }

    @Override
    public void run() {
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

                /**
                 * A task should be finished in future.
                 */
                final PendingSerialization task;
                synchronized (serializeFutures) {
                    /**
                     * Get the first task from the queue. This task serialized always the first message (FIFO).
                     */
                    task = serializeFutures.pollFirst();
                }

                try {
                    /**
                     * Waits if necessary for the serialization to complete, and then pass its result to the
                     * {@link messageLayer}. The call of the method {@link #MessageLayer.transmitMessage(BinaryMessage bm)}
                     * will be sequential only.
                     */
                    messageLayer.transmitMessage(task.future.get());
                } catch (ExecutionException e) {
                    /**
                     * The wire message id was allocated before the serialization ran, so a
                     * failed serialization leaves a hole in the strictly consecutive id
                     * sequence. The receiver processes messages in id order and would wait
                     * for the missing id forever — no later message would ever come through.
                     * Fill the hole with a heartbeat carrying the failed id so the stream
                     * stays consecutive, then surface the failure to the error observers.
                     */
                    messageLayer.transmitMessage(BinaryMessage.createHeartbeat(task.id));

                    Throwable cause = e.getCause();
                    if (cause instanceof ConcurrentModificationException) {
                        ConcurrentModificationException cmeWrap = new ConcurrentModificationException(
                            "Message to serialize was modified while serialization was in process. " +
                            "Make sure your Messages are either immutable or not changed after giving them to the tranceiver!",
                            cause
                        );
                        errorLayer.notifyException(cmeWrap);
                    } else {
                        errorLayer.notifyException(e);
                    }
                }
            } catch (InterruptedException e) {
                errorLayer.notifyException(e);
            }

        }
    }

    @Override
    @ConcurrentMethod
    public void shutdownRunnable() {
        shutdown.set(true);
        doRun.release();
        /**
         * Stop the pool threads as well — idle cached threads would otherwise keep the JVM
         * alive for their keep-alive time (non-daemon threads).
         */
        serializeExecutor.shutdown();
    }

}
