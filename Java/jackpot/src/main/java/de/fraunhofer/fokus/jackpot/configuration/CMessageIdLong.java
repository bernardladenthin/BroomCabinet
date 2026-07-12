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
 * Defines the range message IDs can be taken from. Immutable.
 * 
 * @author VSimRTI developer team <vsimrti@fokus.fraunhofer.de>
 * @author Bernard Ladenthin <bernard.ladenthin@fokus.fraunhofer.de>
 */
public class CMessageIdLong implements Serializable {

    private static final long serialVersionUID = 5800692147733718334L;

    /**
     * The initial messageId. You also can use <code>0</code>. A message with this ID is not sent.
     * This indicates that a message was never received.
     */
    public final long begin;

    /**
     * The last messageId. You also can use a individual value like <code>12345</code>. Note this
     * value must be always higher as {@link #begin}. This number must be sufficiently large. Is it
     * too small, the transceiver can not send more messages.
     */
    public final long end;

    public CMessageIdLong(final long begin, final long end) {
        this.begin = begin;
        this.end = end;
    }

    public CMessageIdLong() {
        this(Long.MIN_VALUE, Long.MAX_VALUE);
    }
}
