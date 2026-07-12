// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.configuration;

import net.jpountz.lz4.LZ4Factory;
import net.jpountz.lz4.LZ4FastDecompressor;
import net.jpountz.lz4.LZ4SafeDecompressor;

/**
 * ?
 *
 * @author VSimRTI developer team <vsimrti@fokus.fraunhofer.de>
 * @author Bernard Ladenthin <bernard.ladenthin@fokus.fraunhofer.de>
 */
public enum CLZ4Decompressor {
    nativeFastDecompressor, nativeSaveDecompressor, safeFastDecompressor, safeSaveDecompressor,
    unsafeFastDecompressor, unsafeSaveDecompressor;

    public final static boolean isFastDecompressor(CLZ4Decompressor decompressor) {
        switch (decompressor) {
        case nativeFastDecompressor:
        case safeFastDecompressor:
        case unsafeFastDecompressor:
            return true;
        default:
            return false;
        }
    }

    public final static boolean isSafeDecompressor(CLZ4Decompressor decompressor) {
        switch (decompressor) {
        case nativeSaveDecompressor:
        case safeSaveDecompressor:
        case unsafeSaveDecompressor:
            return true;
        default:
            return false;
        }
    }

    public final static LZ4FastDecompressor getFastDecompressor(CLZ4Decompressor decompressor) {
        switch (decompressor) {
        case nativeFastDecompressor:
            return LZ4Factory.nativeInstance().fastDecompressor();
        case safeFastDecompressor:
            return LZ4Factory.safeInstance().fastDecompressor();
        case unsafeFastDecompressor:
            return LZ4Factory.unsafeInstance().fastDecompressor();
        default:
            throw new IllegalArgumentException();
        }
    }

    public final static LZ4SafeDecompressor getSafeDecompressor(CLZ4Decompressor decompressor) {
        switch (decompressor) {
        case nativeSaveDecompressor:
            return LZ4Factory.nativeInstance().safeDecompressor();
        case safeSaveDecompressor:
            return LZ4Factory.safeInstance().safeDecompressor();
        case unsafeSaveDecompressor:
            return LZ4Factory.unsafeInstance().safeDecompressor();
        default:
            throw new IllegalArgumentException();
        }
    }
}
