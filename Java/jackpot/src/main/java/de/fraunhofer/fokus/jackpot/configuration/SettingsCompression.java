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
import java.security.InvalidParameterException;
import java.util.List;

import com.google.common.collect.ImmutableList;

//TODO: SPLIT in 2 classes

/**
 * Settings for the GZIP usage.
 *
 * @author VSimRTI developer team <vsimrti@fokus.fraunhofer.de>
 * @author Bernard Ladenthin <bernard.ladenthin@fokus.fraunhofer.de>
 */
public final class SettingsCompression implements Serializable {

    private static final long serialVersionUID = 3082428019699497271L;

    /**
     * List of {@link ConditionGZIP} to compress a byte array.
     */
    public ImmutableList<ConditionGZIP> gzipConditions;

    /**
     * List of {@link ConditionLZ4} to compress a byte array.
     */
    public ImmutableList<ConditionLZ4> lz4Conditions;

    /**
     * Global flag to enable or disable the gzip compression.
     */
    public final boolean enableGZIP;

    /**
     * Global flag to enable or disable the LZ4 compression.
     */
    public final boolean enableLZ4;

    /**
     * GZIP buffer size to uncompress. Unit: [bytes].
     */
    public final int gzipBufferSize;

    /**
     * Use the safe fast decompressor as default.
     */
    public final CLZ4Decompressor decompressor;

    public SettingsCompression(final List<ConditionGZIP> gzipConditions,
        final List<ConditionLZ4> lz4Conditions, final boolean enableGZIP, final boolean enableLZ4,
        final int gzipBufferSize, final CLZ4Decompressor decompressor
    ) {
        if (gzipConditions == null) {
            this.gzipConditions = null;
        } else {
            this.gzipConditions = ImmutableList.copyOf(gzipConditions);
        }

        if (lz4Conditions == null) {
            this.lz4Conditions = null;
        } else {
            this.lz4Conditions = ImmutableList.copyOf(lz4Conditions);
        }

        this.enableGZIP = enableGZIP;
        this.enableLZ4 = enableLZ4;
        this.gzipBufferSize = gzipBufferSize;
        this.decompressor = decompressor;

        if (enableGZIP == true && enableLZ4 == true) {
            throw new InvalidParameterException(
                "illegal flag combination: enableGZIP and enableLZ4 booth true");
        }

        if (enableGZIP == true && gzipConditions == null) {
            throw new InvalidParameterException(
                "illegal parameter combination: enableGZIP and null pointer for gzipConditions");
        }

        if (enableLZ4 == true && lz4Conditions == null) {
            throw new InvalidParameterException(
                "illegal parameter combination: enableLZ4 and null pointer for lz4Conditions");
        }
    }

    public SettingsCompression() {
        this(null, null, false, false, 2048, CLZ4Decompressor.safeFastDecompressor);
    }
}
