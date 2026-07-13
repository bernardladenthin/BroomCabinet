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
     * The default {@link #connectionTimeout}. Unit: [ms].
     */
    public static final int DEFAULT_CONNECTION_TIMEOUT = 20000;

    /**
     * Connection timeout. If the transceiver reaches this time without any received message,
     * the connection is considered dead and a {@link net.ladenthin.jackpot.message.TError}
     * with the {@code expired} flag set is surfaced to the observers (once per silence
     * period). Unit: [ms].
     */
    public final int connectionTimeout;

    /**
     * The value should always be less than {@link #connectionTimeout}. Calculation example: The
     * maximum time to wait for a transmission is <code>20000 ms</code>. Sending a heartbeat one
     * millisecond before could be dangerous. We don't know the additional latency. For safety
     * reasons we use the half time. If we do not send any message within this time, the
     * transmission fire a heartbeat to keep the connection alive. Unit: [ms]. Default: 10000.
     */
    public final long heartbeatInterval;

    /**
     * Delay before task is to be executed. Unit: [ms].
     */
    public final long heartbeatStartDelay;

    /**
     * Time between heartbeat checks. Unit: [ms].
     */
    public final long heartbeatCheckInterval;

    /**
     * Time after which a written but not yet acknowledged message is resent. Must be
     * comfortably larger than a round trip plus the acknowledgement latency (acknowledgements
     * are batched and sent at most every {@link #heartbeatCheckInterval}). Unit: [ms].
     */
    public final long resendInterval;

    public Heartbeat() {
        this(DEFAULT_CONNECTION_TIMEOUT / 2, DEFAULT_CONNECTION_TIMEOUT);
    }

    /**
     * @param resendInterval see {@link #resendInterval}; every other setting keeps its default
     */
    public Heartbeat(final long resendInterval) {
        this(resendInterval, DEFAULT_CONNECTION_TIMEOUT);
    }

    /**
     * @param resendInterval see {@link #resendInterval}
     * @param connectionTimeout see {@link #connectionTimeout}; the heartbeat intervals are
     * derived from it (interval = half, check interval = a twentieth, at least 1 ms)
     */
    public Heartbeat(final long resendInterval, final int connectionTimeout) {
        this.connectionTimeout = connectionTimeout;
        this.heartbeatInterval = connectionTimeout / 2;
        this.heartbeatStartDelay = heartbeatInterval;
        this.heartbeatCheckInterval = Math.max(1, heartbeatInterval / 10);
        this.resendInterval = resendInterval;
    }
}
