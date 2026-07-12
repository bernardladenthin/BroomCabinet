package de.fraunhofer.fokus.jackpot.configuration;

import net.jpountz.lz4.LZ4Compressor;
import net.jpountz.lz4.LZ4Factory;

/**
 * ?
 *
 * @author VSimRTI developer team <vsimrti@fokus.fraunhofer.de>
 * @author Bernard Ladenthin <bernard.ladenthin@fokus.fraunhofer.de>
 */
public enum CLZ4Compressor {
    nativeFastCompressor, nativeHighCompressor, safeFastCompressor, safeHighCompressor,
    unsafeFastCompressor, unsafeHighCompressor;

    public final static LZ4Compressor getCompressor(CLZ4Compressor compressor) {
        switch (compressor) {
        case nativeFastCompressor:
            return LZ4Factory.nativeInstance().fastCompressor();
        case nativeHighCompressor:
            return LZ4Factory.nativeInstance().highCompressor();
        case safeFastCompressor:
            return LZ4Factory.safeInstance().fastCompressor();
        case safeHighCompressor:
            return LZ4Factory.safeInstance().highCompressor();
        case unsafeFastCompressor:
            return LZ4Factory.unsafeInstance().fastCompressor();
        case unsafeHighCompressor:
            return LZ4Factory.unsafeInstance().highCompressor();
        default:
            throw new IllegalArgumentException();
        }
    }
}
