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
import static net.ladenthin.btcdetector.ProbeAddressesOpenCLTest.reverse;
import static net.ladenthin.btcdetector.PublicKeyBytes.PARITY_BYTES_LENGTH;
import static net.ladenthin.btcdetector.PublicKeyBytes.TWO_COORDINATES_BYTES_LENGTH;
import static org.jocl.CL.CL_MEM_READ_ONLY;
import static org.jocl.CL.CL_MEM_USE_HOST_PTR;
import static org.jocl.CL.CL_MEM_WRITE_ONLY;
import static org.jocl.CL.CL_TRUE;
import static org.jocl.CL.clCreateBuffer;
import static org.jocl.CL.clEnqueueNDRangeKernel;
import static org.jocl.CL.clEnqueueReadBuffer;
import static org.jocl.CL.clEnqueueWriteBuffer;
import static org.jocl.CL.clFinish;
import static org.jocl.CL.clReleaseMemObject;
import static org.jocl.CL.clSetKernelArg;
import org.jocl.Pointer;
import org.jocl.Sizeof;
import org.jocl.cl_command_queue;
import org.jocl.cl_context;
import org.jocl.cl_kernel;
import org.jocl.cl_mem;

public class OpenClTask {

    /**
     * I din't know which is better.
     */
    private static final boolean USE_HOST_PTR = false;

    public static final int PRIVATE_KEY_BYTES = 32;
    public static final int PUBLIC_KEY_BYTES = 64;

    public static final int MAX_BITS = 32;
    public static final int BITS_PER_BYTE = 8;

    private final cl_context context;
    private final int bits;
    private final ByteBuffer srcByteBuffer;
    private final Pointer srcPointer;

    private final cl_mem srcMem;

    // Only available after init
    public OpenClTask(cl_context context, int bits) {
        if (bits > MAX_BITS) {
            throw new IllegalArgumentException("Bit size must be lower or equal than " + MAX_BITS + ".");
        }

        this.context = context;
        this.bits = bits;

        srcByteBuffer = ByteBuffer.allocateDirect(getSrcSizeInBytes());
        srcPointer = Pointer.to(srcByteBuffer);
        srcMem = clCreateBuffer(
                context,
                CL_MEM_READ_ONLY ,
                getSrcSizeInBytes(),
                srcPointer,
                null
        );
    }

    public int getWorkSize() {
        return 1 << bits;
    }

    public int getSrcSizeInBytes() {
        return PRIVATE_KEY_BYTES * getWorkSize();
    }

    public int getDstSizeInBytes() {
        return PUBLIC_KEY_BYTES * getWorkSize();
    }

    public void setSrcPrivateKeyChunk(byte[] privateKeyTemplate) {
        byte[] privateKey = privateKeyTemplate.clone();

        unsetLSB(privateKey, bits);

        // put key in reverse order because the ByteBuffer put writes in reverse order, a flip has no effect
        reverse(privateKey);
        srcByteBuffer.clear();
        srcByteBuffer.put(privateKey, 0, privateKey.length);
    }

    static void unsetLSB(byte[] privateKey, int bits) throws IllegalStateException {
        byte[] privateKeyLSB32 = new byte[] {
            privateKey[privateKey.length - 4],
            privateKey[privateKey.length - 3],
            privateKey[privateKey.length - 2],
            privateKey[privateKey.length - 1]
        };

        int privateKeyLSB32AsInt = KeyUtility.byteArrayToInt(privateKeyLSB32);
        // unset bits with shift operator
        privateKeyLSB32AsInt = privateKeyLSB32AsInt >> bits;
        privateKeyLSB32AsInt = privateKeyLSB32AsInt << bits;

        byte[] privateKeyLSB32BitsUnset = KeyUtility.intToByteArray(privateKeyLSB32AsInt);
        privateKey[privateKey.length - 4] = privateKeyLSB32BitsUnset[0];
        privateKey[privateKey.length - 3] = privateKeyLSB32BitsUnset[1];
        privateKey[privateKey.length - 2] = privateKeyLSB32BitsUnset[2];
        privateKey[privateKey.length - 1] = privateKeyLSB32BitsUnset[3];

    }
    
    static void setLSB(byte[] privateKey, int value) {
        byte[] iAsBytes = KeyUtility.intToByteArray(value);
        privateKey[privateKey.length - 4] |= iAsBytes[0];
        privateKey[privateKey.length - 3] |= iAsBytes[1];
        privateKey[privateKey.length - 2] |= iAsBytes[2];
        privateKey[privateKey.length - 1] |= iAsBytes[3];
    }

    public ByteBuffer executeKernel(cl_kernel kernel, cl_command_queue commandQueue) {
        // allocate a new dst buffer that a clone afterwards is not necessary
        final ByteBuffer dstByteBuffer = ByteBuffer.allocateDirect(getDstSizeInBytes());
        final Pointer dstPointer = Pointer.to(dstByteBuffer);
        final cl_mem dstMem;
        if (USE_HOST_PTR) {
            dstMem = clCreateBuffer(
                    context,
                    CL_MEM_USE_HOST_PTR,
                    getDstSizeInBytes(),
                    dstPointer,
                    null
            );
        } else {
            dstMem = clCreateBuffer(
                    context,
                    CL_MEM_WRITE_ONLY,
                    getDstSizeInBytes(),
                    null,
                    null
            );
        }

        // Set the arguments for the kernel
        clSetKernelArg(kernel, 0, Sizeof.cl_mem, Pointer.to(dstMem));
        clSetKernelArg(kernel, 1, Sizeof.cl_mem, Pointer.to(srcMem));

        // Set the work-item dimensions
        long global_work_size[] = new long[]{getWorkSize()};
        long localWorkSize[] = null; // new long[]{1}; // enabling the system to choose the work-group size.
        int workDim = 1;

        {
            // write src buffer
            clEnqueueWriteBuffer(
                    commandQueue,
                    srcMem,
                    CL_TRUE,
                    0,
                    getSrcSizeInBytes(),
                    srcPointer,
                    0,
                    null,
                    null
            );
            clFinish(commandQueue);
        }
        {
            // execute the kernel
            System.out.println("execute kernel ...");
            long beforeExecute = System.currentTimeMillis();
            clEnqueueNDRangeKernel(
                    commandQueue,
                    kernel,
                    workDim,
                    null,
                    global_work_size,
                    localWorkSize,
                    0,
                    null,
                    null
            );
            clFinish(commandQueue);

            long afterExecute = System.currentTimeMillis();
            System.out.println("... executed in: " + (afterExecute - beforeExecute) + "ms");
        }
        {
            // read the dst buffer
            System.out.println("Read the output data: " + ((getDstSizeInBytes() / 1024) / 1024) + "Mb ...");
            long beforeRead = System.currentTimeMillis();

            clEnqueueReadBuffer(
                    commandQueue,
                    dstMem,
                    CL_TRUE,
                    0,
                    getDstSizeInBytes(),
                    dstPointer,
                    0,
                    null,
                    null
            );
            clFinish(commandQueue);
            clReleaseMemObject(dstMem);

            long afterRead = System.currentTimeMillis();
            System.out.println("... read in: " + (afterRead - beforeRead) + "ms");
        }
        return dstByteBuffer;
    }
    
    public static PublicKeyBytes[] transformByteBufferToPublicKeyBytes(ByteBuffer byteBuffer, int workSize, BigInteger secretBase) {
        System.out.println("transform ByteBuffer to keys ...");
        PublicKeyBytes[] publicKeys = new PublicKeyBytes[workSize];
        long beforeTransform = System.currentTimeMillis();
        for (int i = 0; i < workSize; i++) {
            PublicKeyBytes publicKeyBytes = getPublicKeyFromByteBufferXY(byteBuffer, i, secretBase);
            // int pubKeyInts[] = new int[PUBLIC_KEY_LENGTH_WITH_PARITY_U32Array];
            // System.arraycopy(dst_r, i*PUBLIC_KEY_LENGTH_WITH_PARITY_U32Array , pubKeyInts, 0, PUBLIC_KEY_LENGTH_WITH_PARITY_U32Array);
            // byte[] pubKeyBytes = KeyUtility.publicKeyByteArrayFromIntArray(pubKeyInts);
            publicKeys[i] = publicKeyBytes;
        }
        long afterTransform = System.currentTimeMillis();
        System.out.println("... transformed in "+ (afterTransform-beforeTransform) + "ms");
        return publicKeys;
    }
    
    /**
     * https://stackoverflow.com/questions/3366925/deep-copy-duplicate-of-javas-bytebuffer/4074089
     */
    private static ByteBuffer cloneByteBuffer(final ByteBuffer original) {
        // Create clone with same capacity as original.
        final ByteBuffer clone = (original.isDirect())
                ? ByteBuffer.allocateDirect(original.capacity())
                : ByteBuffer.allocate(original.capacity());

        // Create a read-only copy of the original.
        // This allows reading from the original without modifying it.
        final ByteBuffer readOnlyCopy = original.asReadOnlyBuffer();

        // Flip and read from the original.
        readOnlyCopy.flip();
        clone.put(readOnlyCopy);

        return clone;
    }

    public void releaseCl() { 
        clReleaseMemObject(srcMem);
    }
    
    /**
     * Read the inner bytes in reverse order. Remove padding bytes to return a clean byte array.
     * TODO: BLDEBUG Hier
     */
    private static final PublicKeyBytes getPublicKeyFromByteBufferXY(ByteBuffer b, int keyNumber, BigInteger secretBase) {
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
        
        PublicKeyBytes publicKeyBytes = new PublicKeyBytes(secretBase.add(BigInteger.valueOf(keyNumber)), uncompressed);
        return publicKeyBytes;
    }
}
