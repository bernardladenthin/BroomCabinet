package de.fraunhofer.fokus.jackpot;

import de.fraunhofer.fokus.jackpot.configuration.Heartbeat;
import de.fraunhofer.fokus.jackpot.interfaces.ShutdownRunnable;
import de.fraunhofer.fokus.jackpot.interfaces.WriteManagement;
import de.fraunhofer.fokus.jackpot.util.*;

import java.util.*;
import java.util.concurrent.Semaphore;
import java.util.concurrent.atomic.AtomicBoolean;

public final class WriteLayer implements Runnable, WriteManagement, ShutdownRunnable {

    private final ErrorLayer errorLayer;

    private final NavigableSet<BinaryMessage> toWrite = new TreeSet<>();
    private final NavigableMap<Long, BinaryMessage> written = new TreeMap<>();

    /**
     * The boolean flag to shutdown the {@link #run()} method.
     */
    private final AtomicBoolean shutdown = new AtomicBoolean(false);

    /**
     * Semaphore to run the loop.
     */
    protected final Semaphore doRun = new Semaphore(0, true);

    private final Thread thread;

    private final ConnectionLayer<?> connectionLayer;

    private final CurrentWritingLock currentWritingLock;

    private final Heartbeat heartbeat;

    /**
     * A continuous signal to wake up the loop.
     */
    public final void heartbeatSignal() {
        doRun.release();
    }
    
    private final Timer timer = new Timer();
    private final HeartbeatTask heartbeatTask = new HeartbeatTask(this);

    public WriteLayer(final ErrorLayer errorLayer, final ConnectionLayer<?> connectionLayer) {
        this.errorLayer = errorLayer;
        this.connectionLayer = connectionLayer;
        heartbeat = connectionLayer.getTransceiverSession().transceiverConfiguration.heartbeat;
        currentWritingLock = new CurrentWritingLock(errorLayer);
        this.thread = new Thread(this);
        thread.start();

        //TODO: fix the times
        //Creating timer which executes once after five seconds
        timer.scheduleAtFixedRate(
                heartbeatTask,
                heartbeat.heartbeatStartDelay,
                heartbeat.heartbeatCheckInterval);
    }

    @Override
    public void run() {
        long lastMessageSent = 0;
        for (;;) {
            try {
                /**
                 * A permit exist?
                 */
                doRun.acquire();

                Transceiver.debugLog("WriteLayer.run(): acquired");

                /**
                 * A shutdown permit. Terminate the thread.
                 */
                if (shutdown.get()) {
                    Transceiver.debugLog("WriteLayer.run(): shutdown, bye...");
                    timer.cancel();
                    return;
                }
                final BinaryMessage message;
                synchronized (toWrite) {
                    if (toWrite.isEmpty()) {
                        //timerTask
                        if (lastMessageSent + heartbeat.heartbeatInterval > System.currentTimeMillis()) {
                            // no need to create a heartbeat
                            continue;
                        }
                        message = BinaryMessage.createHeartbeat(connectionLayer.getMessageIdGenerator().getNextId());
                    } else {
                        /**
                         * Get the first message ordered by the message id from the set.
                         */
                        message = toWrite.pollFirst();
                    }
                }

                /**
                 * Set the current message id to the {@link currentWritingLock} to remember this thread is writing the specific message
                 * to the stream now.
                 */
                currentWritingLock.setLock(message.getId());

                Transceiver.debugLog("WriteLayer.run().now going to streamWriter");

                /**
                 * Write the message to the stream now. At this point only one critical error should occur, the
                 * streamWriter is not be able to create a stable stream to write the message successfully.
                 * If the message could not be written a NoConnectionPossible will be fired.
                 */
                connectionLayer.writeBoxedSendableByteMessage(message);

                lastMessageSent = System.currentTimeMillis();

                /**
                 * Add the probably written message to the written map.
                 * The message was written to the buffer of the stream.
                 * At this point the message was written successfully to
                 * a stream, but we do not know if it were received.
                 */
                synchronized (written) {
                    written.put(message.getId(), message);
                }

                /**
                 * Release the {@link currentWritingLock}.
                 */
                currentWritingLock.releaseLock();

            } catch (InterruptedException | NoConnectionPossible e) {
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

    @Override
    @ConcurrentMethod
    @ParentEnsureSynchronized
    @ParentEnsureFairProcessingSequence
    public void transmitMessage(final BinaryMessage bm) {
        synchronized (toWrite) {
            /**
             * Not possible. Only to debug.
             */
            assert (!toWrite.contains(bm)) : "toWrite already contains the message";

            Transceiver.debugLog("WriteLayer.transmitMessage(final BinaryMessage bm): message now in list");

            toWrite.add(bm);
        }

        /**
         * Release a permit. In future a transmit (write) should be finished.
         * The calling method {@link #de.fraunhofer.fokus.jackpot.SerializeLayer.run} is encapsulated now.
         */
        doRun.release();
    }

    @Override
    @ConcurrentMethod
    public void resendId(long id) {
        currentWritingLock.blockUntilCurrentWriting(id);
        synchronized (toWrite) {
            synchronized (written) {
                assert (written.containsKey(id)) : "written does not contains the key " + id;

                // swap
                final BinaryMessage bm = written.get(id);
                written.remove(id);
                transmitMessage(bm);
            }
        }
    }

    @Override
    public void deleteId(long id) {
        currentWritingLock.blockUntilCurrentWriting(id);
        synchronized (written) {
            assert (written.containsKey(id)) : "written does not contains the key " + id;

            written.remove(id);
        }
    }

}
