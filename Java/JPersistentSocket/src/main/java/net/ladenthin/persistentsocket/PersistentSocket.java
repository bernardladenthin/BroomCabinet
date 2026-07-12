// SPDX-FileCopyrightText: 2014 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.persistentsocket;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.Closeable;
import java.io.DataInput;
import java.io.DataInputStream;
import java.io.DataOutput;
import java.io.DataOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.Socket;
import java.util.Deque;
import java.util.LinkedList;
import java.util.Timer;
import java.util.TimerTask;
import java.util.concurrent.Semaphore;
import java.util.concurrent.atomic.AtomicLong;
import net.ladenthin.persistentsocket.configuration.ClientSocket;
import net.ladenthin.persistentsocket.configuration.Configuration;
import net.ladenthin.persistentsocket.configuration.Connection;
import net.ladenthin.streambuffer.StreamBuffer;

/**
 * @author Bernard Ladenthin <bernard.ladenthin@gmail.com>
 */
public class PersistentSocket implements Closeable {
    
    private final static int blockSize = 8129;
    private final static AtomicLong messageId = new AtomicLong();
    private Socket socket;

    private class HeartbeatTask extends TimerTask {

        @Override
        public void run() {
            
        }
    }
    
    // todo: parameter
    private final Configuration configuration;
    
    private final Timer heartbeatTimer = new Timer();
    
    private volatile boolean shutdown = false;
    
    private final StreamBuffer toSocket = new StreamBuffer();
    private final StreamBuffer fromSocket = new StreamBuffer();
    
    private final Semaphore toTransmitSemaphore = new Semaphore(0);
    
    private final Deque<TransmissionBlock> toTransmit = new LinkedList<>();
    private final Deque<TransmissionBlock> transmitted = new LinkedList<>();
    
    private volatile BufferedInputStream bis;
    private volatile DataInputStream dis;
    private volatile BufferedOutputStream bos;
    private volatile DataOutputStream dos;
    
    private volatile DataInput socketDataInput;
    private volatile DataOutput socketDataOutput;
    
    private final Thread fromSocketThread = new Thread(new Runnable() {

        @Override
        public void run() {
            
        }
    }, "fromSocketThread");
    
    private final Thread toSocketThread = new Thread(new Runnable() {

        @Override
        public void run() {
            InputStream is = toSocket.getInputStream();
            for(;;) {
                if (shutdown) {
                    return;
                }
                try {
                    final int available = is.available();
                    
                    if (available > 0) {
                        final int length = available > blockSize ? blockSize : available;
                        
                        byte[] data = new byte[length];
                        if (is.read(data) != data.length) {
                            throw new IOException("Read not enough bytes.");
                        }
                        
                        final long id = messageId.incrementAndGet();
                        // overflow?
                        assert id > 0;
                        
                        TransmissionBlock transmissionBlock = new TransmissionBlock(id, data, null);
                        synchronized (toTransmit) {
                            toTransmit.add(transmissionBlock);
                        }
                        
                        toTransmitSemaphore.release();
                    } else {
                        toSocket.blockDataAvailable();
                    }
                    
                } catch (InterruptedException | IOException | RuntimeException e) {
                    handleException(e);
                }
            }
        }
    }, "toSocketThread");
    
    private final Thread writeThread = new Thread(new Runnable() {

        @Override
        public void run() {
            try {
                toTransmitSemaphore.acquire();
                if (shutdown) {
                    return;
                }
                
                final TransmissionBlock block;
                synchronized (toTransmit) {
                    block = toTransmit.getFirst();
                }
                
                try {
                    block.writeBlock(dos);
                } catch (IOException e) {
                    // todo: wrap connectLoop in a guard so it is only entered once
                    try {
                        connectLoop();
                    } catch (IOException reconnectFailed) {
                        handleException(reconnectFailed);
                    }
                }

            } catch (InterruptedException | RuntimeException e) {
                handleException(e);
            }
        }
    }, "writeThread");
    
    @Override
    public void close() throws IOException {
        throw new UnsupportedOperationException("Not supported yet."); //To change body of generated methods, choose Tools | Templates.
    }
    
    
    public void shutdownBridge() {
        try {
            shutdown = true;
            toTransmitSemaphore.release();
            heartbeatTimer.cancel();
            toSocket.close();
            fromSocket.close();
        } catch (IOException e) {
            throw new RuntimeException(e);
        }
    }
    
    /**
     * This method close all streams and free all resources.
     */
    private void disconnect() {
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
            socket.close();
        } catch (IOException e) {
            socket = null;
        }
    }
    
    private final void connectLoop() throws IOException {

        final ClientSocket clientSocket = configuration.getClientSocket();
        final Connection connection = configuration.getConnection();

        final long startTime = System.currentTimeMillis();
        final long endTime = startTime + connection.getMaximumConnectionTime();

        while(System.currentTimeMillis() <= endTime) {
            try {
                disconnect();
                socket = new Socket(clientSocket.host, clientSocket.port);
                socket.setSoTimeout(clientSocket.soTimeout);

                bis = new BufferedInputStream(
                    socket.getInputStream(),
                    connection.getInputBufferSize()
                );

                dis = new DataInputStream(bis);

                bos = new BufferedOutputStream(
                    socket.getOutputStream(),
                    connection.getOutputBufferSize()
                );

                dos = new DataOutputStream(bos);

                return;
            } catch (IOException e) {
                try {
                    Thread.sleep(connection.getSleepConnectionMillis());
                } catch (InterruptedException ex) {
                    handleException(ex);
                }
            }
        }
        // do not remove this null assignment, we need this for the other thread
        bis = null;
        dis = null;
        bos = null;
        dos = null;
        throw new IOException("No connection possible");
    }

    public PersistentSocket(Configuration configuration) {
        this.configuration = configuration;
        
        final HeartbeatTask heartbeatTask = new HeartbeatTask();
        
        // create the heartbeat task
        heartbeatTimer.scheduleAtFixedRate(
            heartbeatTask,
            configuration.getConnection().getHeartbeatStartDelay(),
            configuration.getConnection().getHeartbeatCheckInterval()
        );
    }
    
    private void handleException(Exception e) {
        
    }

}
