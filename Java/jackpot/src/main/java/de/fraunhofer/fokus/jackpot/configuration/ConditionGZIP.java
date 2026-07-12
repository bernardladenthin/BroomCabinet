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
