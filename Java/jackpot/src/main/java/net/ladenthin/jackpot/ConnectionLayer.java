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
import java.util.ArrayDeque;
import java.util.Deque;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;
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
     * A {@link Deque} of messages, which are written to the other side.
     * The order of the ids is very important.
     */
    protected final Deque<Long> writtenMessages = new ArrayDeque<>();
    
    /**
     * A {@link Deque} of messages, which are received acknowledged from the other side.
     * The order of the ids is very important.
     */
    protected final Deque<Long> acknowledgedMesages = new ArrayDeque<>();
    
    /**
     * A {@link Deque} of messages, which are received from the other side.
     * The order of the ids is very important.
     */
    protected final Deque<Long> receivedMesages = new ArrayDeque<>();

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
        /**
         * First of all clean successfull messages and resend lost messages.
         * (Durch den Timer wird diese Funktion zu minimalen Zeitpunkten aufgerufen, idealer weise aber öfter).
         */
        cleanAndCheckMessages();
        for (;;) {
            boolean hasToConnect = false;
            try {
                writeLock.lock();
                /*
                 * It must be ensured that the message can be inserted into
                 * writtenMessages immediately after writing the message.
                 */
                synchronized (writtenMessages) {
                    ensureDataOutputStreamConnected();
                    bm.toDataOutput(dos);
                    dos.flush();
                    Transceiver.debugLog("ConnectionLayer.writeBoxedSendableByteMessage(final BinaryMessage bm): written to stream");
                    writtenMessages.add(bm.getId());
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
                Transceiver.debugLog("ConnectionLayer.readBoxedByteMessage(): now BinaryMessage.readFromDataInput(dis);");
                bm = BinaryMessage.fromDataInputJava8(dis);
                Transceiver.debugLog("ConnectionLayer.readBoxedByteMessage(): FINISHED BinaryMessage.readFromDataInput(dis);");
                break;
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
    
    public final void cleanAndCheckMessages() {
        synchronized (writtenMessages) {
            synchronized (acknowledgedMesages) {
                while(
                       !acknowledgedMesages.isEmpty()
                    && !writtenMessages.isEmpty()
                ) {
                    final long ackId = acknowledgedMesages.getFirst();
                    final long writtenId = writtenMessages.pollFirst();
                    if(ackId == writtenId) {
                        acknowledgedMesages.remove();
                    } else {
                        //out of order; instant resent the missing id
                        writeLayer.resendId(writtenId);
                    }
                }
            }
        }
    }
    
    public final void addAcknowledgedMesages(List<Long> messages) {
        synchronized (acknowledgedMesages) {
            acknowledgedMesages.addAll(messages);
        }
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

    private final void ensureDataOutputStreamConnected() throws NoConnectionPossible {
        Transceiver.debugLog("BLDEBUG: ConnectionLayer.ensureDataOutputStreamConnected");
        if (dos == null) {
            Transceiver.debugLog("BLDEBUG: ConnectionLayer.ensureDataOutputStreamConnected: dos == null; connect");
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

                try {
                    readLock.lock();
                    //FIXME: bis sometimes null, verify this connect
                    ensureDataInputStreamConnected();
                    BinaryMessage bm = readBinaryMessage();
                    /**
                     * After a message has been read, the ID must be added immediately.
                     */
                    synchronized (receivedMesages) {
                        receivedMesages.add(bm.getId());
                    }
                    /**
                     * The message content can now be processed.
                     */
                    readLayer.receiveMessage(bm);
                } finally {
                    readLock.unlock();
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
