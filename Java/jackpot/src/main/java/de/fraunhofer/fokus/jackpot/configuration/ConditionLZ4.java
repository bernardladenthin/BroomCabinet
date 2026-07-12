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

import net.jpountz.lz4.LZ4Compressor;

/**
 * Condition for the LZ4 usage.
 * @see <a href="http://jpountz.github.io/lz4-java/1.2.0/lz4-compression-benchmark/">Cmpression-benchmark</a>
 * @see <a href="http://jpountz.github.io/lz4-java/1.2.0/lz4-decompression-benchmark/">Decompression-benchmark</a>
 *
 * @author VSimRTI developer team <vsimrti@fokus.fraunhofer.de>
 * @author Bernard Ladenthin <bernard.ladenthin@fokus.fraunhofer.de>
 */
public final class ConditionLZ4 extends CompressCondition implements Serializable {

    private static final long serialVersionUID = -7259178019114812462L;

    public final LZ4Compressor compressor;

    public ConditionLZ4(final CLZ4Compressor compressor) {
        this.compressor = CLZ4Compressor.getCompressor(compressor);
    }

    public ConditionLZ4(final CLZ4Compressor compressor, final CompressCondition compressCondition) {
        super(compressCondition);
        this.compressor = CLZ4Compressor.getCompressor(compressor);
    }

    public ConditionLZ4() {
        /*
         * Use the unsafe fast compressor as default.
         */
        this(CLZ4Compressor.unsafeFastCompressor);
    }
}
