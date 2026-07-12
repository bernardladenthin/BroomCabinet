package de.fraunhofer.fokus.jackpot;

import java.util.ArrayDeque;
import java.util.Deque;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.Semaphore;
import java.util.concurrent.atomic.AtomicBoolean;

import de.fraunhofer.fokus.jackpot.configuration.CTransceiverSession;
import de.fraunhofer.fokus.jackpot.interfaces.ShutdownRunnable;
import de.fraunhofer.fokus.jackpot.interfaces.MessageIdGenerator;
import de.fraunhofer.fokus.jackpot.messageprocessing.ParallelMessageTransmitter;
import de.fraunhofer.fokus.jackpot.serializer.SerializeRunnable;
import de.fraunhofer.fokus.jackpot.serializer.SerializerFactory;
import de.fraunhofer.fokus.jackpot.util.BinaryMessage;
import de.fraunhofer.fokus.jackpot.util.ConcurrentMethod;
import de.fraunhofer.fokus.jackpot.util.ParentEnsureFairProcessingSequence;
import de.fraunhofer.fokus.jackpot.util.ParentEnsureSynchronized;
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
    private final ExecutorService serializeExecutor = Executors.newCachedThreadPool();

    /**
     * The {@link Future} serializations.
     */
    private final Deque<Future<BinaryMessage>> serializeFutures = new ArrayDeque<>();

    /**
     * The boolean flag to shutdown the {@link #run()} method.
     */
    private final AtomicBoolean shutdown = new AtomicBoolean(false);

    /**
     * The {@link Semaphore} to run the loop.
     */
    private final Semaphore doRun = new Semaphore(0, true);

    /**
     * The {@link de.fraunhofer.fokus.jackpot.messageprocessing.SequentialBinaryMessageTransmitter} to notify finished serializations in their
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
        thread = new Thread(this);
        thread.start();
    }

    @Override
    @ConcurrentMethod //OK
    @ParentEnsureSynchronized //OK
    @ParentEnsureFairProcessingSequence //OK
    public void transmitMessage(final T message) {
        /**
         * Create a new {@link de.fraunhofer.fokus.jackpot.serializer.SerializeRunnable} to serialize the message.
         */
        final SerializeRunnable<T> task =
            new SerializeRunnable<>(serializerFactory, messageIdGenerator.getNextId(), message,
                cTransceiverSession.transceiverConfiguration.settingsCompression);

        /**
         * Submit the task to the executor service and add the future to the queue.
         */
        synchronized (serializeFutures) {
            serializeFutures.add(serializeExecutor.submit(task));
        }

        /**
         * Release a permit. In future a serialization should be finished.
         * The calling method {@link #de.fraunhofer.fokus.jackpot.Transceiver.update} is encapsulated now.
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
                final Future<BinaryMessage> task;
                synchronized (serializeFutures) {
                    /**
                     * Get the first task from the queue. This task serialized always the first message (FIFO).
                     */
                    task = serializeFutures.pollFirst();
                }

                /**
                 * Waits if necessary for the serialization to complete, and then pass its result to the
                 * {@link messageLayer}. The call of the method {@link #MessageLayer.transmitMessage(BinaryMessage bm)}
                 * will be sequential only.
                 */
                messageLayer.transmitMessage(task.get());
            } catch (InterruptedException e) {
                errorLayer.notifyException(e);
            } catch (ExecutionException e) {
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

        }
    }

    @Override
    @ConcurrentMethod
    public void shutdownRunnable() {
        shutdown.set(true);
        doRun.release();
    }

}
