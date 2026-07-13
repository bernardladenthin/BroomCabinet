// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.configuration;

import java.io.Serializable;

/**
 * Heartbeat configuration for the transmission.
 *
 * @author VSimRTI developer team <vsimrti@fokus.fraunhofer.de>
 * @author Bernard Ladenthin <bernard.ladenthin@fokus.fraunhofer.de>
 */
public class Heartbeat implements Serializable {

    private static final long serialVersionUID = 2307516907066951336L;

    /**
     * Sleep time millisecond part. Unit: [ms]
     */
//    public final int sleepMillis = 0;

    /**
     * Sleep time nanosecond part. Range: 0-999999. Unit: [ns]
     */
//    public final int sleepNanos = 10000;

    /**
     * Connection timeout. If the transceiver reach this time without any received message, it
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
     * Time after which a written but not yet acknowledged message is resent. Must be
     * comfortably larger than a round trip plus the acknowledgement latency (acknowledgements
     * are batched and sent at most every {@link #heartbeatCheckInterval}). Unit: [ms].
     */
    public final long resendInterval;

    public Heartbeat() {
        this.resendInterval = heartbeatInterval;
    }

    /**
     * @param resendInterval see {@link #resendInterval}; every other setting keeps its default
     */
    public Heartbeat(final long resendInterval) {
        this.resendInterval = resendInterval;
    }
}
