/*
 * To change this license header, choose License Headers in Project Properties.
 * To change this template file, choose Tools | Templates
 * and open the template in the editor.
 */
package net.ladenthin.btcdetector;

import java.nio.ByteBuffer;
import java.util.concurrent.Semaphore;
import static net.ladenthin.btcdetector.ProbeAddressesOpenCLTest.reverse;
import org.apache.commons.codec.digest.DigestUtils;
import org.bitcoinj.core.Sha256Hash;
import org.bitcoinj.core.Utils;
import org.bouncycastle.crypto.digests.RIPEMD160Digest;
import static org.jocl.CL.CL_MEM_COPY_HOST_PTR;
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

/**
 *
 * @author Bernard
 */
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
    private final ByteBuffer dstByteBuffer;
    private final Pointer srcPointer;
    private final Pointer dstPointer;

    private final cl_mem srcMem;
    private final cl_mem dstMem;

    // Only available after init
    public OpenClTask(cl_context context, int bits) {
        if (bits > MAX_BITS) {
            throw new IllegalArgumentException("Bit size must be lower or equal than " + MAX_BITS + ".");
        }

        this.context = context;
        this.bits = bits;

        srcByteBuffer = ByteBuffer.allocateDirect(getSrcSizeInBytes());
        dstByteBuffer = ByteBuffer.allocateDirect(getDstSizeInBytes());
        
        srcPointer = Pointer.to(srcByteBuffer);
        dstPointer = Pointer.to(dstByteBuffer);

        srcMem = clCreateBuffer(
                context,
                CL_MEM_READ_ONLY ,
                getSrcSizeInBytes(),
                srcPointer,
                null
        );

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

    public PublicKeyBytes[] executeKernel(cl_kernel kernel, cl_command_queue commandQueue, Object clLock) {

        synchronized (clLock) {
            // Set the arguments for the kernel
            int a = 0;
            clSetKernelArg(kernel, a++, Sizeof.cl_mem, Pointer.to(dstMem));
            clSetKernelArg(kernel, a++, Sizeof.cl_mem, Pointer.to(srcMem));

            // Set the work-item dimensions
            long global_work_size[] = new long[]{getWorkSize()};
            long localWorkSize[] = new long[]{1};
            localWorkSize = null;
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
                        localWorkSize, // local_work_size, enabling the system to choose the work-group size.
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
                
                long afterRead = System.currentTimeMillis();
                System.out.println("... read in: " + (afterRead - beforeRead) + "ms");
            }
        }
        
        System.out.println("transform ByteBuffer to keys ...");
        PublicKeyBytes[] publicKeys = new PublicKeyBytes[getWorkSize()];
        long beforeTransform = System.currentTimeMillis();
        for (int i = 0; i < getWorkSize(); i++) {
            PublicKeyBytes publicKeyBytes = getPublicKeyFromByteBufferXY(dstByteBuffer, i);
            // int pubKeyInts[] = new int[PUBLIC_KEY_LENGTH_WITH_PARITY_U32Array];
            // System.arraycopy(dst_r, i*PUBLIC_KEY_LENGTH_WITH_PARITY_U32Array , pubKeyInts, 0, PUBLIC_KEY_LENGTH_WITH_PARITY_U32Array);
            // byte[] pubKeyBytes = KeyUtility.publicKeyByteArrayFromIntArray(pubKeyInts);
            publicKeys[i] = publicKeyBytes;
        }
        long afterTransform = System.currentTimeMillis();
        System.out.println("... transformed in "+ (afterTransform-beforeTransform) + "ms");
        
        return publicKeys;
    }
    
    public void releaseCl() { 
        clReleaseMemObject(srcMem);
        clReleaseMemObject(dstMem);
    }
    
    public static class PublicKeyBytes {
        
        public static final int ONE_COORDINATE_BYTE_LENGTH = 32;
        public static final int TWO_COORDINATES_BYTES_LENGTH = ONE_COORDINATE_BYTE_LENGTH * 2;
        public static final int PARITY_BYTES_LENGTH = 1;
        
        // add one byte for format sign
        final byte[] compressed = new byte[ONE_COORDINATE_BYTE_LENGTH+PARITY_BYTES_LENGTH];
        final byte[] uncompressed = new byte[TWO_COORDINATES_BYTES_LENGTH+PARITY_BYTES_LENGTH];
        
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
     * Calculates RIPEMD160(SHA256(input)). This is used in Address calculations.
     * Same as {@link Utils#sha256hash160(byte[])} but using {@link DigestUtils}.
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
    
    /**
     * Read the inner bytes in reverse order. Remove padding bytes to return a clean byte array.
     * TODO: BLDEBUG Hier
     */
    private static final PublicKeyBytes getPublicKeyFromByteBufferXY(ByteBuffer b, int keyNumber) {
        PublicKeyBytes publicKeyBytes = new PublicKeyBytes();
        
        int keyOffsetInByteBuffer = PublicKeyBytes.TWO_COORDINATES_BYTES_LENGTH*keyNumber;
        
        // read ByteBuffer
        byte[] yx = new byte[PublicKeyBytes.TWO_COORDINATES_BYTES_LENGTH];
        for (int i = 0; i < PublicKeyBytes.TWO_COORDINATES_BYTES_LENGTH; i++) {
            yx[yx.length-1-i] = b.get(keyOffsetInByteBuffer+i);
        }
        
        // copy x
        System.arraycopy(yx, PublicKeyBytes.ONE_COORDINATE_BYTE_LENGTH, publicKeyBytes.uncompressed, PublicKeyBytes.PARITY_BYTES_LENGTH, PublicKeyBytes.ONE_COORDINATE_BYTE_LENGTH);
        // copy x
        System.arraycopy(yx, PublicKeyBytes.ONE_COORDINATE_BYTE_LENGTH, publicKeyBytes.compressed, PublicKeyBytes.PARITY_BYTES_LENGTH, PublicKeyBytes.ONE_COORDINATE_BYTE_LENGTH);
        // copy y
        System.arraycopy(yx, 0, publicKeyBytes.uncompressed, PublicKeyBytes.PARITY_BYTES_LENGTH+PublicKeyBytes.ONE_COORDINATE_BYTE_LENGTH, PublicKeyBytes.ONE_COORDINATE_BYTE_LENGTH);
        
        // the first byte is 4 to indicate a public key with x and y coordinate (uncompressed)
        publicKeyBytes.uncompressed[0] = 4;
        
        int indexLastYCoordinateByte = PublicKeyBytes.PARITY_BYTES_LENGTH+PublicKeyBytes.TWO_COORDINATES_BYTES_LENGTH-1;
        boolean even = publicKeyBytes.uncompressed[indexLastYCoordinateByte] % 2 == 0;
        
        if (even) {
            publicKeyBytes.compressed[0] = 2;
        } else {
            publicKeyBytes.compressed[0] = 3;
        }
        
        return publicKeyBytes;
    }
}
