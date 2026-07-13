// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot;

import net.ladenthin.jackpot.configuration.CTransceiverSession;
import net.ladenthin.jackpot.connector.Connector;
import net.ladenthin.jackpot.connector.ConnectorFactory;
import net.ladenthin.jackpot.interfaces.MessageIdGenerator;
import net.ladenthin.jackpot.interfaces.ShutdownRunnable;
import net.ladenthin.jackpot.messageprocessing.SequentialBinaryMessageTransmitter;
import net.ladenthin.jackpot.util.*;

import java.io.*;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.locks.ReentrantLock;

public final class ConnectionLayer<T> implements ShutdownRunnable, Runnable,
        SequentialBinaryMessageTransmitter {

    /**
     * The boolean flag to shutdown the {@link #run()} method.
     */
    private final AtomicBoolean shutdown = new AtomicBoolean(false);

    public CTransceiverSession getTransceiverSession() {
        return transceiverSession;
    }

    /**
     * The {@link CTransceiverSession}.
     */
    private final CTransceiverSession transceiverSession;

    /**
     * The buffered stream for input.
     */
    private volatile BufferedInputStream bis;

    /**
     * The {@link DataInputStream} stream.
     */
    private volatile DataInputStream dis;

    /**
     * The {@link BufferedOutputStream}.
     */
    private volatile BufferedOutputStream bos;

    /**
     * The {@link BufferedOutputStream}.
     */
    private volatile DataOutputStream dos;

    private final ErrorLayer errorLayer;

    private final ReentrantLock writeLock = new ReentrantLock(true);
    private final ReentrantLock readLock = new ReentrantLock(true);
    private final ReentrantLock assignLock = new ReentrantLock(true);

    private final Connector connector;

    /**
     * The {@link ConnectorFactory}.
     */
    private final ConnectorFactory connectorFactory;

    /**
     * The {@link WriteLayer}.
     */
    private final WriteLayer writeLayer;

    /**
     * {@link MessageLayer}.
     */
    private final Transceiver<T> transceiver;

    private final Thread thread;

    public MessageIdGenerator getMessageIdGenerator() {
        return messageIdGenerator;
    }

    private final ReadLayer<T> readLayer;
    private final MessageIdGenerator messageIdGenerator;

    public ConnectionLayer(
        final CTransceiverSession cTransceiverSession,
        final Transceiver transceiver,
        final ErrorLayer errorLayer,
        final MessageIdGenerator messageIdGenerator
    ) {
        this.transceiverSession = cTransceiverSession;
        this.transceiver = transceiver;
        this.errorLayer = errorLayer;
        this.messageIdGenerator = messageIdGenerator;

        this.connectorFactory = new ConnectorFactoryImpl(this.transceiverSession);

        connector = connectorFactory.getConnector();

        writeLayer = new WriteLayer(errorLayer, this);
        readLayer = new ReadLayer<>(cTransceiverSession, this, errorLayer, transceiver);

        this.thread = new Thread(this,
            "jackpot-ConnectionLayer-" + cTransceiverSession.transceiverId);
        thread.start();

    }

    /**
     * This method should ensure a write without an Exception. But this method can not guarantee the
     * successful transmission.
     *
     * @param bm
     */
    public final void writeBoxedSendableByteMessage(final BinaryMessage bm) throws NoConnectionPossible {
        Transceiver.debugLog("ConnectionLayer.writeBoxedSendableByteMessage(final BinaryMessage bm)");
        for (;;) {
            boolean hasToConnect = false;
            try {
                writeLock.lock();
                /**
                 * The stream reference is checked INSIDE the lock (connect() swaps the
                 * streams only while holding it) — but connect() itself must never be called
                 * while holding this lock: a thread blocking on the assignLock while owning
                 * a stream lock deadlocks against the connecting thread, which holds the
                 * assignLock and acquires the stream locks.
                 */
                if (dos == null) {
                    hasToConnect = true;
                } else {
                    bm.toDataOutput(dos);
                    dos.flush();
                    Transceiver.debugLog("ConnectionLayer.writeBoxedSendableByteMessage(final BinaryMessage bm): written to stream");
                }
            } catch (IOException e) {
                //unlock first, so the assignStream can assign a new stream.
                Transceiver.debugLog("ConnectionLayer.writeBoxedSendableByteMessage(final BinaryMessage bm): EXCEPTION during write to stream");
                hasToConnect = true;
            } finally {
                writeLock.unlock();
            }

            if (hasToConnect) {
                /**
                 * A failed write during shutdown is expected (the streams were closed on
                 * purpose) — exit instead of trying to reconnect.
                 */
                if (shutdown.get()) {
                    throw new NoConnectionPossible();
                }
                connect();
                continue;
            }

            return;
        }
    }

    /**
     * This is an sequential function
     * @throws NoConnectionPossible
     */
    private final BinaryMessage readBinaryMessage() throws NoConnectionPossible {
        Transceiver.debugLog("ConnectionLayer.readBoxedByteMessage()");
        BinaryMessage bm;
        for (;;) {
            boolean hasToConnect = false;
            try {
                readLock.lock();
                /**
                 * The stream reference is checked INSIDE the lock (connect() swaps the
                 * streams only while holding it) — see the matching comment in
                 * {@link #writeBoxedSendableByteMessage} for why connect() must never be
                 * called while a stream lock is held.
                 */
                if (dis == null) {
                    hasToConnect = true;
                } else {
                    Transceiver.debugLog("ConnectionLayer.readBoxedByteMessage(): now BinaryMessage.readFromDataInput(dis);");
                    bm = BinaryMessage.fromDataInputJava8(dis);
                    Transceiver.debugLog("ConnectionLayer.readBoxedByteMessage(): FINISHED BinaryMessage.readFromDataInput(dis);");
                    break;
                }
            } catch (IOException e) {
                Transceiver.debugLog("ConnectionLayer.readBoxedByteMessage(): EXCEPTION");
                //unlock first, so the assignStream can assign a new stream.
                hasToConnect = true;
            } finally {
                readLock.unlock();
            }

            if (hasToConnect) {
                /**
                 * A failed read during shutdown is expected (the streams were closed on
                 * purpose) — exit instead of trying to reconnect.
                 */
                if (shutdown.get()) {
                    throw new NoConnectionPossible();
                }
                connect();
                continue;
            }
        }
        return bm;
    }

    private final void enforceDisconnect() {
        Transceiver.debugLog("ConnectionLayer.enforceDisconnect()");

        if(dis != null) {
            try {
                dis.close();
            } catch (IOException e) {
            }
            dis = null;
        }

        if(bis != null) {
            try {
                bis.close();
            } catch (IOException e) {
            }
            bis = null;
        }

        if(dos != null) {
            try {
                dos.close();
            } catch (IOException e) {
            }
            dos = null;
        }

        if(bos != null) {
            try {
                bos.close();
            } catch (IOException e) {
            }
            bos = null;
        }

        try {
            connector.close();
        } catch (IOException e) {
        }
    }

    private final void connectLoop() throws NoConnectionPossible {
        Transceiver.debugLog("ConnectionLayer.connectLoop()");
        //TODO: configuration
        int maximumConnectionTime = 30000;
        //sleep after each connection try
        int millis = 5000;
        //256kb buffer
        int inputBufferSize = 262144;//2^18;
        int outputBufferSize = 262144;//2^18;

        final long startTime = System.currentTimeMillis();
        final long endTime = startTime + maximumConnectionTime;

        while(System.currentTimeMillis() <= endTime && !shutdown.get()) {
            try {
                connector.connect();

                bis = new BufferedInputStream(
                    connector.getInputStream(),
                    inputBufferSize
                );
                Transceiver.debugLog("ConnectionLayer.connectLoop().bis: " + bis);

                dis = new DataInputStream(bis);
                Transceiver.debugLog("ConnectionLayer.connectLoop().dis: " + dis);

                bos = new BufferedOutputStream(
                    connector.getOutputStream(),
                    outputBufferSize
                );
                Transceiver.debugLog("ConnectionLayer.connectLoop().bos: " + bos);

                dos = new DataOutputStream(bos);
                Transceiver.debugLog("ConnectionLayer.connectLoop().dos: " + dos);

                return;
            } catch (IOException e) {
                /**
                 * During shutdown a failing connect attempt is expected (the connector was
                 * closed on purpose) — leave immediately instead of sleeping and retrying.
                 */
                if (shutdown.get()) {
                    break;
                }
                try {
                    Thread.sleep(millis);
                } catch (InterruptedException ie) {
                    errorLayer.notifyException(ie);
                }
                Transceiver.debugLog("ConnectionLayer.connectLoop().IOException: continue");
                continue;
            }
        }
        // do not remove this null assignment, we need this for the other thread
        bis = null;
        dis = null;
        bos = null;
        dos = null;
        throw new NoConnectionPossible();
    }

    private final void connect() throws NoConnectionPossible {
        Transceiver.debugLog("ConnectionLayer.connect()");
        //of course the writer and reader invokes this method at the same time
        //one of the them get the lock, the other one knows about the current execution and
        //wait for its finish and return only.
        if(!assignLock.tryLock()) {
            try {
                assignLock.lock();
                // check the successful assignment from other thread, NoConnectionPossible may already thrown
                if( dos == null || bos == null || dis == null || bis == null) {
                    throw new NoConnectionPossibleOtherThread();
                }
                return;
            } finally {
                assignLock.unlock();
            }
        } else {
            try {
                /**
                 * Close the old streams BEFORE acquiring the stream locks: another thread
                 * may sit in a blocking stream read/write while holding its lock — closing
                 * unblocks it with an IOException so it releases the lock this thread is
                 * about to take (the same mechanism the shutdown path uses).
                 */
                enforceDisconnect();
                writeLock.lock();
                readLock.lock();
                //reassign streams
                enforceDisconnect();
                connectLoop();

            } finally {
                readLock.unlock();
                writeLock.unlock();

                assignLock.unlock();
            }
        }
    }
    
    /**
     * Ids of received messages that still have to be acknowledged to the other side. Filled by
     * the {@link ReadLayer}, drained by the {@link WriteLayer} into acknowledgement messages.
     */
    private final List<Long> pendingAcknowledgements = new ArrayList<>();

    /**
     * Timestamp of the last {@link WriteLayer#heartbeatSignal()} nudge caused by a newly
     * enqueued acknowledgement. Unit: [ms since epoch].
     */
    private final AtomicLong lastAcknowledgementNudge = new AtomicLong();

    /**
     * When the last message was successfully read from the other side; the liveness signal
     * for the {@link Heartbeat#connectionTimeout} enforcement. Initialized to the
     * construction time so a fresh connection gets the full timeout before it can expire.
     * Unit: [ms since epoch].
     */
    private volatile long lastReadActivity = System.currentTimeMillis();

    /**
     * Whether the expired error was already surfaced for the current silence period, so it
     * fires once per period instead of on every check tick.
     */
    private final AtomicBoolean expiredNotified = new AtomicBoolean(false);

    /**
     * Surfaces a {@link net.ladenthin.jackpot.message.TError} with the {@code expired} flag
     * when nothing was received for longer than {@link Heartbeat#connectionTimeout} — the
     * other side is transport-alive but dead (or the transport lost messages silently).
     * Driven by the {@link WriteLayer} loop, which is ticked by the heartbeat timer.
     */
    public final void checkConnectionExpired() {
        if (shutdown.get()) {
            return;
        }
        final long silentMillis = System.currentTimeMillis() - lastReadActivity;
        if (silentMillis > transceiverSession.transceiverConfiguration.heartbeat.connectionTimeout) {
            if (expiredNotified.compareAndSet(false, true)) {
                errorLayer.notifyExpired();
            }
        }
    }

    /**
     * Enqueue the id of a received message for acknowledgement to the other side.
     * Nudges the {@link WriteLayer} at most once per
     * {@link net.ladenthin.jackpot.configuration.Heartbeat#heartbeatCheckInterval}, so the
     * mutual acknowledgement-of-acknowledgement exchange stays rate-limited instead of
     * ping-ponging at network speed.
     *
     * @param id the received message id
     */
    public final void enqueueAcknowledgement(final long id) {
        synchronized (pendingAcknowledgements) {
            pendingAcknowledgements.add(id);
        }
        final long now = System.currentTimeMillis();
        final long lastNudge = lastAcknowledgementNudge.get();
        final long nudgeInterval = transceiverSession.transceiverConfiguration.heartbeat.heartbeatCheckInterval;
        if (now - lastNudge >= nudgeInterval && lastAcknowledgementNudge.compareAndSet(lastNudge, now)) {
            writeLayer.heartbeatSignal();
        }
    }

    /**
     * Drain all pending acknowledgements.
     *
     * @return the drained ids (possibly empty, never null)
     */
    public final List<Long> drainPendingAcknowledgements() {
        synchronized (pendingAcknowledgements) {
            if (pendingAcknowledgements.isEmpty()) {
                return Collections.emptyList();
            }
            final List<Long> drained = new ArrayList<>(pendingAcknowledgements);
            pendingAcknowledgements.clear();
            return drained;
        }
    }

    /**
     * Apply acknowledgements received from the other side: every acknowledged message is
     * released from the retained (resend) buffer.
     *
     * @param ids the acknowledged message ids
     */
    public final void applyAcknowledgements(final List<Long> ids) {
        for (final long id : ids) {
            writeLayer.deleteId(id);
        }
    }

    /**
     * The number of written messages not acknowledged by the other side yet.
     *
     * @return the count of retained (unacknowledged) messages
     */
    public final long getUnacknowledgedMessageCount() {
        return writeLayer.getUnacknowledgedMessageCount();
    }

    @Override
    @ConcurrentMethod
    public final void shutdownRunnable() {
        shutdown.set(true);
        writeLayer.shutdownRunnable();
        readLayer.shutdownRunnable();
        /**
         * Close the streams and the connector so the reader thread, which is typically
         * blocked in a stream read, gets an IOException and can observe the shutdown flag.
         * Without this the reader stays blocked forever on a non-daemon thread and the JVM
         * cannot exit.
         */
        enforceDisconnect();
    }

    @Override
    @ConcurrentMethod
    @ParentEnsureSynchronized
    @ParentEnsureFairProcessingSequence
    public final void transmitMessage(BinaryMessage bm) {
        writeLayer.transmitMessage(bm);
    }

    private final void ensureDataInputStreamConnected() throws NoConnectionPossible {
        Transceiver.debugLog("BLDEBUG: ConnectionLayer.ensureDataInputStreamConnected");
        if (dis == null) {
            Transceiver.debugLog("BLDEBUG: ConnectionLayer.ensureDataInputStreamConnected: dis == null; connect");
            connect();
        }
    }

    @Override
    public final void run() {
        try{
            for (;;) {

                if(shutdown.get()) {
                    return;
                }

                /**
                 * Deliberately NOT holding the readLock around this block: readBinaryMessage
                 * locks it internally for the actual stream read and releases it before it
                 * reconnects. Holding it here across the reconnect path deadlocked against a
                 * concurrently reconnecting writer (this thread: owns readLock, blocks on
                 * assignLock — writer: owns assignLock, blocks on readLock). Torn-down
                 * streams are handled by the null checks inside the locked read/write
                 * sections.
                 */
                try {
                    ensureDataInputStreamConnected();
                    BinaryMessage bm = readBinaryMessage();
                    /**
                     * Liveness: a successfully read message proves the other side is alive.
                     */
                    lastReadActivity = System.currentTimeMillis();
                    expiredNotified.set(false);
                    /**
                     * The message content can now be processed. The {@link ReadLayer}
                     * enqueues the acknowledgement once the message is actually processed
                     * (or discarded as a duplicate).
                     */
                    readLayer.receiveMessage(bm);
                } catch (RuntimeException e) {
                    /**
                     * An unexpected RuntimeException must never kill the reader thread — a
                     * dead reader silently stops all inbound traffic. Surface it and keep
                     * reading.
                     */
                    if (!shutdown.get()) {
                        errorLayer.notifyException(e);
                    }
                }
            }
        } catch (NoConnectionPossible e) {
            /**
             * During shutdown the failed connection is expected (the streams were closed on
             * purpose) and must not be reported as an error.
             */
            if (!shutdown.get()) {
                errorLayer.notifyNoConnectionPossible();
            }
        }
    }

}
