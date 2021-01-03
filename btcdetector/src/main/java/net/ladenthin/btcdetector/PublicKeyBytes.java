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

import java.math.BigInteger;
import org.apache.commons.codec.digest.DigestUtils;
import org.bitcoinj.core.Utils;
import org.bouncycastle.crypto.digests.RIPEMD160Digest;

public class PublicKeyBytes {

    public static final int ONE_COORDINATE_BYTE_LENGTH = 32;
    public static final int TWO_COORDINATES_BYTES_LENGTH = ONE_COORDINATE_BYTE_LENGTH * 2;
    public static final int PARITY_BYTES_LENGTH = 1;
    
    public static final int LAST_Y_COORDINATE_BYTE_INDEX = PublicKeyBytes.PARITY_BYTES_LENGTH+PublicKeyBytes.TWO_COORDINATES_BYTES_LENGTH-1;
    
    /**
     * The first byte (parity) is 4 to indicate a public key with x and y coordinate (uncompressed).
     */
    public static final int PARITY_UNCOMPRESSED = 4;
    public static final int PARITY_COMPRESSED_EVEN = 2;
    public static final int PARITY_COMPRESSED_ODD = 3;

    private final byte[] compressed;
    private final byte[] uncompressed;
    private final BigInteger secretKey;
    
    public BigInteger getSecretKey() {
        return secretKey;
    }

    public byte[] getCompressed() {
        return compressed;
    }

    public byte[] getUncompressed() {
        return uncompressed;
    }
    
    public PublicKeyBytes(BigInteger secretKey, byte[] uncompressed) {
        this(secretKey, uncompressed, createCompressedBytes(uncompressed));
    }
    
    public PublicKeyBytes(BigInteger secretKey, byte[] uncompressed, byte[] compressed) {
        this.secretKey = secretKey;
        this.uncompressed = uncompressed;
        this.compressed = compressed;
    }
    
    public static byte[] createCompressedBytes(byte[] uncompressed) {
        // add one byte for format sign
        byte[] compressed = new byte[PARITY_BYTES_LENGTH + ONE_COORDINATE_BYTE_LENGTH];
        
        // copy x
        System.arraycopy(uncompressed, PARITY_BYTES_LENGTH, compressed, PublicKeyBytes.PARITY_BYTES_LENGTH, PublicKeyBytes.ONE_COORDINATE_BYTE_LENGTH);
        
        boolean even = uncompressed[LAST_Y_COORDINATE_BYTE_INDEX] % 2 == 0;
        
        if (even) {
            compressed[0] = PARITY_COMPRESSED_EVEN;
        } else {
            compressed[0] = PARITY_COMPRESSED_ODD;
        }
        return compressed;
    }

    public byte[] getUncompressedKeyHash() {
        return Utils.sha256hash160(uncompressed);
    }

    public byte[] getCompressedKeyHash() {
        return Utils.sha256hash160(compressed);
    }

    public byte[] getUncompressedKeyHashFast() {
        return sha256hash160Fast(uncompressed);
    }

    public byte[] getCompressedKeyHashFast() {
        return sha256hash160Fast(compressed);
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
