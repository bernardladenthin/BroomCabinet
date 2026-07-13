// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot;

import net.ladenthin.jackpot.configuration.Heartbeat;
import net.ladenthin.jackpot.interfaces.ShutdownRunnable;
import net.ladenthin.jackpot.interfaces.WriteManagement;
import net.ladenthin.jackpot.util.*;

import java.util.*;
import java.util.concurrent.Semaphore;
import java.util.concurrent.atomic.AtomicBoolean;

public final class WriteLayer implements Runnable, WriteManagement, ShutdownRunnable {

    private final ErrorLayer errorLayer;

    /**
     * One written but not yet acknowledged message together with its last write time, so the
     * resend sweep can find overdue messages.
     */
    private static final class UnacknowledgedMessage {

        private final BinaryMessage message;

        /**
         * When the message was (last) written to the stream. Unit: [ms since epoch].
         */
        private final long writtenAt;

        private UnacknowledgedMessage(final BinaryMessage message, final long writtenAt) {
            this.message = message;
            this.writtenAt = writtenAt;
        }
    }

    private final NavigableSet<BinaryMessage> toWrite = new TreeSet<>();

    /**
     * Every written message is retained here until the other side acknowledges it (see
     * {@link #deleteId(long)}); messages unacknowledged for longer than
     * {@link Heartbeat#resendInterval} are resent (see {@link #resendOverdueMessages()}).
     */
    private final NavigableMap<Long, UnacknowledgedMessage> written = new TreeMap<>();

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
    
    private final Timer timer;
    private final HeartbeatTask heartbeatTask = new HeartbeatTask(this);

    public WriteLayer(final ErrorLayer errorLayer, final ConnectionLayer<?> connectionLayer) {
        this.errorLayer = errorLayer;
        this.connectionLayer = connectionLayer;
        heartbeat = connectionLayer.getTransceiverSession().transceiverConfiguration.heartbeat;
        currentWritingLock = new CurrentWritingLock(errorLayer);
        this.timer = new Timer(
            "jackpot-WriteLayer-Timer-" + connectionLayer.getTransceiverSession().transceiverId);
        this.thread = new Thread(this,
            "jackpot-WriteLayer-" + connectionLayer.getTransceiverSession().transceiverId);
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

                /**
                 * Dead-connection detection, driven by the heartbeat timer ticks that keep
                 * this loop running even when idle.
                 */
                connectionLayer.checkConnectionExpired();

                final BinaryMessage message;

                /**
                 * Pending acknowledgements are sent with priority: the other side retains
                 * every written message until it is acknowledged, so a delayed
                 * acknowledgement means retained memory and, eventually, an unnecessary
                 * resend over there. Draining returns the whole batch as one message.
                 */
                final List<Long> acknowledgements = connectionLayer.drainPendingAcknowledgements();
                if (!acknowledgements.isEmpty()) {
                    message = BinaryMessage.createAcknowledged(
                        connectionLayer.getMessageIdGenerator().getNextId(), acknowledgements);
                } else {
                    final BinaryMessage pending;
                    synchronized (toWrite) {
                        /**
                         * Get the first message ordered by the message id from the set.
                         */
                        pending = toWrite.pollFirst();
                    }
                    if (pending != null) {
                        message = pending;
                    } else {
                        /**
                         * Idle tick (timerTask): first give overdue unacknowledged messages
                         * another chance — a message lost on the wire wedges the receiver
                         * (it processes ids strictly in order), and only this resend can
                         * unwedge it. The resent messages re-enter {@link #toWrite} and are
                         * written on the next permits.
                         */
                        resendOverdueMessages();
                        if (lastMessageSent + heartbeat.heartbeatInterval > System.currentTimeMillis()) {
                            // no need to create a heartbeat
                            continue;
                        }
                        message = BinaryMessage.createHeartbeat(connectionLayer.getMessageIdGenerator().getNextId());
                    }
                }

                /**
                 * Set the current message id to the {@link currentWritingLock} to remember this thread is writing the specific message
                 * to the stream now.
                 */
                currentWritingLock.setLock(message.getId());

                /**
                 * The {@link currentWritingLock} must be released even when the write throws
                 * (e.g. {@link NoConnectionPossible}). A leaked lock would let a later
                 * {@link #resendId(long)}/{@link #deleteId(long)} for the same id spin in
                 * {@link CurrentWritingLock#blockUntilCurrentWriting(long)} forever.
                 */
                try {
                    Transceiver.debugLog("WriteLayer.run().now going to streamWriter");

                    /**
                     * Retain the message BEFORE writing: if the write fails (e.g. the
                     * connection is gone), the message stays in the retain buffer and the
                     * resend sweep delivers it after the reconnect — otherwise it would be
                     * lost and the receiver would wait for its id forever.
                     */
                    synchronized (written) {
                        written.put(message.getId(),
                            new UnacknowledgedMessage(message, System.currentTimeMillis()));
                    }

                    /**
                     * Write the message to the stream now. At this point only one critical error should occur, the
                     * streamWriter is not be able to create a stable stream to write the message successfully.
                     * If the message could not be written a NoConnectionPossible will be fired.
                     */
                    connectionLayer.writeBoxedSendableByteMessage(message);

                    lastMessageSent = System.currentTimeMillis();
                } finally {
                    /**
                     * Release the {@link currentWritingLock}.
                     */
                    currentWritingLock.releaseLock();
                }

            } catch (InterruptedException | NoConnectionPossible e) {
                /**
                 * During shutdown a failed write is expected (the streams were closed on
                 * purpose) and must not be reported; the loop continues and terminates on
                 * the shutdown permit.
                 */
                if (!shutdown.get()) {
                    errorLayer.notifyException(e);
                }
            } catch (RuntimeException e) {
                /**
                 * An unexpected RuntimeException (e.g. message id range exhaustion in the id
                 * generator) must never kill the loop thread — a dead writer hangs the whole
                 * transceiver silently. Surface it and keep the loop alive.
                 */
                if (!shutdown.get()) {
                    errorLayer.notifyException(e);
                }
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
         * The calling method {@link #net.ladenthin.jackpot.SerializeLayer.run} is encapsulated now.
         */
        doRun.release();
    }

    /**
     * Move every message that stayed unacknowledged for longer than
     * {@link Heartbeat#resendInterval} back into the write queue. Called from the run loop on
     * idle ticks; the ids are collected first so {@link #resendId(long)} is never invoked
     * while holding the {@code written} monitor (it takes {@code toWrite} before
     * {@code written}, and that lock order must stay consistent).
     */
    private void resendOverdueMessages() {
        final long overdueBefore = System.currentTimeMillis() - heartbeat.resendInterval;
        final List<Long> overdueIds = new ArrayList<>();
        synchronized (written) {
            for (final Map.Entry<Long, UnacknowledgedMessage> entry : written.entrySet()) {
                if (entry.getValue().writtenAt <= overdueBefore) {
                    overdueIds.add(entry.getKey());
                }
            }
        }
        for (final long id : overdueIds) {
            resendId(id);
        }
    }

    @Override
    @ConcurrentMethod
    public void resendId(long id) {
        currentWritingLock.blockUntilCurrentWriting(id);
        synchronized (toWrite) {
            synchronized (written) {
                // swap; tolerant: the id may have been acknowledged (deleted) meanwhile
                final UnacknowledgedMessage unacknowledged = written.remove(id);
                if (unacknowledged == null) {
                    return;
                }
                transmitMessage(unacknowledged.message);
            }
        }
    }

    @Override
    public void deleteId(long id) {
        currentWritingLock.blockUntilCurrentWriting(id);
        synchronized (written) {
            /**
             * Tolerant remove: an acknowledgement may arrive more than once for the same id
             * (the receiver re-acknowledges discarded duplicates in case the first
             * acknowledgement was lost), so an absent id is a valid no-op.
             */
            written.remove(id);
        }
    }

    /**
     * The number of written messages that were not acknowledged by the other side yet.
     *
     * @return the count of retained (unacknowledged) messages
     */
    public long getUnacknowledgedMessageCount() {
        synchronized (written) {
            return written.size();
        }
    }

}
