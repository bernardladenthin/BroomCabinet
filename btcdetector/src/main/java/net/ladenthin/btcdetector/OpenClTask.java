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
import java.util.Arrays;
import org.apache.commons.codec.binary.Hex;
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
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class OpenClTask {

    protected Logger logger = LoggerFactory.getLogger(this.getClass());
    
    /**
     * I din't know which is better.
     */
    private static final boolean USE_HOST_PTR = false;

    private final static boolean USE_XOR_SWAP = false;

    public static final int PRIVATE_KEY_BYTES = 32;
    public static final int PUBLIC_KEY_BYTES = 64;

    public static final int MAX_GRID_NUM_BITS = 24;
    public static final int BITS_PER_BYTE = 8;

    private final cl_context context;
    private final int gridNumBits;
    private final BigInteger killBits;
    private final ByteBuffer srcByteBuffer;
    private final Pointer srcPointer;

    private final cl_mem srcMem;

    // Only available after init
    public OpenClTask(cl_context context, int gridNumBits) {
        if (gridNumBits > MAX_GRID_NUM_BITS) {
            throw new IllegalArgumentException("Max grid num bits must be lower or equal than " + MAX_GRID_NUM_BITS + ".");
        }
        killBits = BigInteger.valueOf(2).pow(gridNumBits).subtract(BigInteger.ONE);

        this.context = context;
        this.gridNumBits = gridNumBits;

        srcByteBuffer = ByteBuffer.allocateDirect(getSrcSizeInBytes());
        srcPointer = Pointer.to(srcByteBuffer);
        srcMem = clCreateBuffer(
                context,
                CL_MEM_READ_ONLY,
                getSrcSizeInBytes(),
                srcPointer,
                null
        );
    }

    public int getWorkSize() {
        return 1 << gridNumBits;
    }

    public int getSrcSizeInBytes() {
        return PRIVATE_KEY_BYTES;
    }

    public int getDstSizeInBytes() {
        return PUBLIC_KEY_BYTES * getWorkSize();
    }

    public void setSrcPrivateKeyChunk(BigInteger privateKeyTemplate) {
        BigInteger privateKeyChunk = privateKeyTemplate.andNot(killBits);
        byte[] privateKeyChunkAsByteArray = KeyUtility.bigIntegerToBytes(privateKeyChunk);
        if (logger.isTraceEnabled()) {
            logger.trace("privateKeyTemplate: " + Hex.encodeHexString(privateKeyTemplate.toByteArray()));
            logger.trace("killBits: " + Hex.encodeHexString(killBits.toByteArray()));
            logger.trace("privateKeyChunkAsByteArray: " + Hex.encodeHexString(privateKeyChunk.toByteArray()));
        }

        // put key in reverse order because the ByteBuffer put writes in reverse order, a flip has no effect
        reverse(privateKeyChunkAsByteArray);
        srcByteBuffer.clear();
        srcByteBuffer.put(privateKeyChunkAsByteArray, 0, privateKeyChunkAsByteArray.length);
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
            
            if (logger.isTraceEnabled()) {
                logger.trace("Executed OpenCL kernel in " + (afterExecute - beforeExecute) + "ms");
            }
        }
        {
            // read the dst buffer
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
            if (logger.isTraceEnabled()) {
                logger.trace("Read OpenCL data "+((getDstSizeInBytes() / 1024) / 1024) + "Mb in " + (afterRead - beforeRead) + "ms");
            }
        }
        return dstByteBuffer;
    }

    public void releaseCl() {
        clReleaseMemObject(srcMem);
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

    /**
     * https://stackoverflow.com/questions/12893758/how-to-reverse-the-byte-array-in-java
     */
    public static void reverse(byte[] array) {
        if (array == null) {
            return;
        }
        if (USE_XOR_SWAP) {
            int len = array.length;
            for (int i = 0; i < len / 2; i++) {
                array[i] ^= array[len - i - 1];
                array[len - i - 1] ^= array[i];
                array[i] ^= array[len - i - 1];
            }
        } else {
            int i = 0;
            int j = array.length - 1;
            byte tmp;
            while (j > i) {
                tmp = array[j];
                array[j] = array[i];
                array[i] = tmp;
                j--;
                i++;
            }
        }
    }
}
