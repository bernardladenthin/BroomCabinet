// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.persistentsocket.configuration;

import java.io.Serializable;

public class Connection implements Serializable {

    private static final long serialVersionUID = -1;
    private final int maximumConnectionTime;
    
    /**
     * Sleep after each connection try.
     */
    private final int sleepConnectionMillis;
    private final int inputBufferSize;
    private final int outputBufferSize;
    
    
    
    
    /**
     * Sleep time millisecond part. Unit: [ms]
     */
//    public final int sleepMillis = 0;

    /**
     * Sleep time nanosecond part. Range: 0-999999. Unit: [ns]
     */
//    public final int sleepNanos = 10000;

    /**
     * Connection timeout. If the socket reach this time without any received message, it
     * ended. If the timeout reached and no heartbeat from the other side arrived, the process kill
     * themself to prevent a never ending loop. Unit: [ms].
     */
    public final int connectionTimeout = 20000;

    /**
     * The value should always be less than {@link #connectionTimeout}. Calculation example: The
     * maximum time to wait for a transmission is <code>20000 ms</code>. Sending a heartbeat one
     * millisecond before could be dangerous. We don't know the additional latency. For safety
     * reasons we use the half time. If we do not send any message within this time, the
     * transmission fire a heartbeat to keep the connection alive. Unit: [ms]. Current value: 10000.
     */
    public final long heartbeatInterval = (long) (connectionTimeout / 2);

    /**
     * Delay before task is to be executed. Unit: [ms].
     */
    public final long heartbeatStartDelay = heartbeatInterval;

    /**
     * Time between heartbeat checks. Unit: [ms].
     */
    public final long heartbeatCheckInterval = (long) (heartbeatInterval / 10);
    
    /**
     * Constructor using all fields.
     * @param maximumConnectionTime A maximum for each.
     * @param sleepConnectionMillis
     * @param inputBufferSize
     * @param outputBufferSize 
     */
    public Connection(final int maximumConnectionTime, final int sleepConnectionMillis, final int inputBufferSize, final int outputBufferSize) {
        this.maximumConnectionTime = maximumConnectionTime;
        this.sleepConnectionMillis = sleepConnectionMillis;
        this.inputBufferSize = inputBufferSize;
        this.outputBufferSize = outputBufferSize;
    }
    public Connection() {
        this.maximumConnectionTime = 30000;
        this.sleepConnectionMillis = 5000;
        
        //256kb buffer
        this.inputBufferSize = 262144;//2^18;;
        this.outputBufferSize = 262144;//2^18;;
    }

    public int getMaximumConnectionTime() {
        return maximumConnectionTime;
    }

    public int getSleepConnectionMillis() {
        return sleepConnectionMillis;
    }

    public int getInputBufferSize() {
        return inputBufferSize;
    }

    public int getOutputBufferSize() {
        return outputBufferSize;
    }

    public int getConnectionTimeout() {
        return connectionTimeout;
    }

    public long getHeartbeatInterval() {
        return heartbeatInterval;
    }

    public long getHeartbeatStartDelay() {
        return heartbeatStartDelay;
    }

    public long getHeartbeatCheckInterval() {
        return heartbeatCheckInterval;
    }
    
    
}
