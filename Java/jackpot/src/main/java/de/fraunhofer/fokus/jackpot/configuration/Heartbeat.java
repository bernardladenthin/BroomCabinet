/**
 * Copyright 2013 Fraunhofer FOKUS
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *    http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 */
package de.fraunhofer.fokus.jackpot.configuration;

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

}
