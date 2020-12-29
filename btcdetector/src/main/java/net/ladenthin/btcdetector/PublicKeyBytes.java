// @formatter:off
/**
 * Copyright 2020 Bernard Ladenthin bernard.ladenthin@gmail.com
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
// @formatter:on
package net.ladenthin.btcdetector;

import org.apache.commons.codec.digest.DigestUtils;
import org.bitcoinj.core.Utils;
import org.bouncycastle.crypto.digests.RIPEMD160Digest;

public class PublicKeyBytes {

    public static final int ONE_COORDINATE_BYTE_LENGTH = 32;
    public static final int TWO_COORDINATES_BYTES_LENGTH = ONE_COORDINATE_BYTE_LENGTH * 2;
    public static final int PARITY_BYTES_LENGTH = 1;

    // add one byte for format sign
    final byte[] compressed = new byte[ONE_COORDINATE_BYTE_LENGTH + PARITY_BYTES_LENGTH];
    final byte[] uncompressed = new byte[TWO_COORDINATES_BYTES_LENGTH + PARITY_BYTES_LENGTH];

    public byte[] getCompressedKeyHash() {
        return Utils.sha256hash160(compressed);
    }

    public byte[] getUncompressedKeyHash() {
        return Utils.sha256hash160(uncompressed);
    }

    public byte[] getCompressedKeyHashFast() {
        return sha256hash160Fast(compressed);
    }

    public byte[] getUncompressedKeyHashFast() {
        return sha256hash160Fast(uncompressed);
    }

    /**
     * Calculates RIPEMD160(SHA256(input)). This is used in Address
     * calculations. Same as {@link Utils#sha256hash160(byte[])} but using
     * {@link DigestUtils}.
     */
    public static byte[] sha256hash160Fast(byte[] input) {
        byte[] sha256 = DigestUtils.sha256(input);
        RIPEMD160Digest digest = new RIPEMD160Digest();
        digest.update(sha256, 0, sha256.length);
        byte[] out = new byte[20];
        digest.doFinal(out, 0);
        return out;
    }

    public String getCompressedKeyHashAsBase58(KeyUtility keyUtility) {
        return keyUtility.toBase58(getCompressedKeyHash());
    }

    public String getUncompressedKeyHashAsBase58(KeyUtility keyUtility) {
        return keyUtility.toBase58(getUncompressedKeyHash());
    }
}
