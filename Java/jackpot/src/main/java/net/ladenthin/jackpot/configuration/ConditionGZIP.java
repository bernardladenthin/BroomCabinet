// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.configuration;

import java.io.Serializable;
import java.util.zip.Deflater;

/**
 * Condition for the GZIP usage.
 *
 * @author VSimRTI developer team <vsimrti@fokus.fraunhofer.de>
 * @author Bernard Ladenthin <bernard.ladenthin@fokus.fraunhofer.de>
 */
public final class ConditionGZIP extends CompressCondition implements Serializable {

    private static final long serialVersionUID = 969261859454526336L;

    /**
     * Level for the deflating.
     */
    public final int deflaterLevel;

    public ConditionGZIP(final int deflaterLevel) {
        this.deflaterLevel = deflaterLevel;
    }

    public ConditionGZIP(final int deflaterLevel, final CompressCondition compressCondition) {
        super(compressCondition);
        this.deflaterLevel = deflaterLevel;
    }

    public ConditionGZIP() {
        this(Deflater.BEST_SPEED);
    }
}
