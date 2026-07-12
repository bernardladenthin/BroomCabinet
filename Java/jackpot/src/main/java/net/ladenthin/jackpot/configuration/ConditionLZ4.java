// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.configuration;

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
