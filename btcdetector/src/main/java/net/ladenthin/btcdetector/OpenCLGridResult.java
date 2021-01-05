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
import java.nio.ByteBuffer;
import static net.ladenthin.btcdetector.PublicKeyBytes.PARITY_BYTES_LENGTH;
import static net.ladenthin.btcdetector.PublicKeyBytes.TWO_COORDINATES_BYTES_LENGTH;

public class OpenCLGridResult {

    private final BigInteger secretKeyBase;
    private final int workSize;
    private ByteBuffer result;
    
    OpenCLGridResult(BigInteger secretKeyBase, int workSize, ByteBuffer result) {
        this.secretKeyBase = secretKeyBase;
        this.workSize = workSize;
        this.result = result;
    }

    public BigInteger getSecretKeyBase() {
        return secretKeyBase;
    }

    public int getWorkSize() {
        return workSize;
    }

    public ByteBuffer getResult() {
        return result;
    }
    
    public void freeResult() {
        // free and do not use anymore
        ByteBufferUtility.freeByteBuffer(result);
        result = null;
    }
    
    /**
     * Time consuming.
     */
    public PublicKeyBytes[] getPublicKeyBytes() {
        PublicKeyBytes[] publicKeys = new PublicKeyBytes[workSize];
        for (int i = 0; i < workSize; i++) {
            PublicKeyBytes publicKeyBytes = getPublicKeyFromByteBufferXY(result, i, secretKeyBase);
            publicKeys[i] = publicKeyBytes;
        }
        return publicKeys;
    }
    
    /**
     * Read the inner bytes in reverse order.
     */
    private static final PublicKeyBytes getPublicKeyFromByteBufferXY(ByteBuffer b, int keyNumber, BigInteger secretKeyBase) {
        byte[] uncompressed = new byte[PARITY_BYTES_LENGTH + TWO_COORDINATES_BYTES_LENGTH];
        uncompressed[0] = PublicKeyBytes.PARITY_UNCOMPRESSED;
        
        int keyOffsetInByteBuffer = PublicKeyBytes.TWO_COORDINATES_BYTES_LENGTH*keyNumber;
        
        // read ByteBuffer
        byte[] yx = new byte[PublicKeyBytes.TWO_COORDINATES_BYTES_LENGTH];
        for (int i = 0; i < PublicKeyBytes.TWO_COORDINATES_BYTES_LENGTH; i++) {
            yx[yx.length-1-i] = b.get(keyOffsetInByteBuffer+i);
        }
        
        // copy x
        System.arraycopy(yx, PublicKeyBytes.ONE_COORDINATE_BYTE_LENGTH, uncompressed, PublicKeyBytes.PARITY_BYTES_LENGTH, PublicKeyBytes.ONE_COORDINATE_BYTE_LENGTH);
        // copy y
        System.arraycopy(yx, 0, uncompressed, PublicKeyBytes.PARITY_BYTES_LENGTH+PublicKeyBytes.ONE_COORDINATE_BYTE_LENGTH, PublicKeyBytes.ONE_COORDINATE_BYTE_LENGTH);
        
        PublicKeyBytes publicKeyBytes = new PublicKeyBytes(secretKeyBase.add(BigInteger.valueOf(keyNumber)), uncompressed);
        return publicKeyBytes;
    }
    
}
