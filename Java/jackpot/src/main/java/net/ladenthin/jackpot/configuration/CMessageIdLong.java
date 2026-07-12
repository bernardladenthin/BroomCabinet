// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.configuration;

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
