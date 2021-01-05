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

import com.google.common.io.Resources;
import java.io.File;
import java.io.IOException;
import java.math.BigInteger;
import java.net.URL;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.MappedByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.ArrayList;
import java.util.List;
import org.apache.commons.io.FileUtils;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

import static org.jocl.CL.*;

import java.util.Arrays;
import java.util.Random;
import static net.ladenthin.btcdetector.KeyUtility.byteArrayToIntArray;
import static net.ladenthin.btcdetector.OpenClTask.PRIVATE_KEY_BYTES;
import static net.ladenthin.btcdetector.OpenClTask.transformByteBufferToPublicKeyBytes;
import net.ladenthin.btcdetector.staticaddresses.StaticKey;
import net.ladenthin.btcdetector.staticaddresses.TestAddresses;
import net.ladenthin.btcdetector.staticaddresses.TestAddresses42;
import org.bitcoinj.core.ECKey;
import org.bitcoinj.core.Utils;
import org.bitcoinj.params.MainNetParams;
import org.bouncycastle.math.ec.ECPoint;
import org.bouncycastle.util.encoders.Hex;
import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.is;

import org.jocl.*;
import org.junit.Ignore;
import sun.nio.ch.DirectBuffer;

public class ProbeAddressesOpenCLTest {

    private static final TestAddresses42 testAddresses = new TestAddresses42(1024, false);
    
    public final static int BYTES_FOR_INT = 4;
    /**
     * 22:  256Mb: executed in: 1253ms, read in:  74ms
     * 23:  512Mb: executed in: 2346ms, read in: 148ms
     * 24: 1024Mb: executed in: 4622ms, read in: 302ms
    */
    private final static int BITS_FOR_GRID = 20;

    @Rule
    public TemporaryFolder tempFolder = new TemporaryFolder();
    private File tempAddressesFile;

    @Before
    public void init() throws IOException {
        createTemporaryAddressesFile();
    }

    public void fillAddressesFiles(File file) throws IOException {
        FileUtils.writeStringToFile(file, testAddresses.getAsBase58Strings(), StandardCharsets.UTF_8.name());
    }

    public void createTemporaryAddressesFile() throws IOException {
        tempAddressesFile = tempFolder.newFile("addresses.csv");
        fillAddressesFiles(tempAddressesFile);
    }

    @Test
    public void joclTest() {

        /**
         * The source code of the OpenCL program to execute
         */
        String programSource
                = "__kernel void "
                + "sampleKernel(__global const float *a,"
                + "             __global const float *b,"
                + "             __global float *c)"
                + "{"
                + "    int gid = get_global_id(0);"
                + "    c[gid] = a[gid] * b[gid];"
                + "}";

        // Create input- and output data 
        int n = 10;
        float srcArrayA[] = new float[n];
        float srcArrayB[] = new float[n];
        float dstArray[] = new float[n];
        for (int i = 0; i < n; i++) {
            srcArrayA[i] = i;
            srcArrayB[i] = i;
        }
        Pointer srcA = Pointer.to(srcArrayA);
        Pointer srcB = Pointer.to(srcArrayB);
        Pointer dst = Pointer.to(dstArray);

        // The platform, device type and device number
        // that will be used
        final int platformIndex = 0;
        final long deviceType = CL_DEVICE_TYPE_ALL;
        final int deviceIndex = 0;

        // Enable exceptions and subsequently omit error checks in this sample
        CL.setExceptionsEnabled(true);

        // Obtain the number of platforms
        int numPlatformsArray[] = new int[1];
        clGetPlatformIDs(0, null, numPlatformsArray);
        int numPlatforms = numPlatformsArray[0];

        // Obtain a platform ID
        cl_platform_id platforms[] = new cl_platform_id[numPlatforms];
        clGetPlatformIDs(platforms.length, platforms, null);
        cl_platform_id platform = platforms[platformIndex];

        // Initialize the context properties
        cl_context_properties contextProperties = new cl_context_properties();
        contextProperties.addProperty(CL_CONTEXT_PLATFORM, platform);

        // Obtain the number of devices for the platform
        int numDevicesArray[] = new int[1];
        clGetDeviceIDs(platform, deviceType, 0, null, numDevicesArray);
        int numDevices = numDevicesArray[0];

        // Obtain a device ID 
        cl_device_id devices[] = new cl_device_id[numDevices];
        clGetDeviceIDs(platform, deviceType, numDevices, devices, null);
        cl_device_id device = devices[deviceIndex];

        // Create a context for the selected device
        cl_context context = clCreateContext(
                contextProperties, 1, new cl_device_id[]{device},
                null, null, null);

        // Create a command-queue for the selected device
        cl_queue_properties properties = new cl_queue_properties();
        cl_command_queue commandQueue = clCreateCommandQueueWithProperties(
                context, device, properties, null);

        // Allocate the memory objects for the input- and output data
        cl_mem srcMemA = clCreateBuffer(context,
                CL_MEM_READ_ONLY | CL_MEM_COPY_HOST_PTR,
                Sizeof.cl_float * n, srcA, null);
        cl_mem srcMemB = clCreateBuffer(context,
                CL_MEM_READ_ONLY | CL_MEM_COPY_HOST_PTR,
                Sizeof.cl_float * n, srcB, null);
        cl_mem dstMem = clCreateBuffer(context,
                CL_MEM_READ_WRITE,
                Sizeof.cl_float * n, null, null);

        // Create the program from the source code
        cl_program program = clCreateProgramWithSource(context,
                1, new String[]{programSource}, null, null);

        // Build the program
        clBuildProgram(program, 0, null, null, null, null);

        // Create the kernel
        cl_kernel kernel = clCreateKernel(program, "sampleKernel", null);

        // Set the arguments for the kernel
        int a = 0;
        clSetKernelArg(kernel, a++, Sizeof.cl_mem, Pointer.to(srcMemA));
        clSetKernelArg(kernel, a++, Sizeof.cl_mem, Pointer.to(srcMemB));
        clSetKernelArg(kernel, a++, Sizeof.cl_mem, Pointer.to(dstMem));

        // Set the work-item dimensions
        long global_work_size[] = new long[]{n};

        // Execute the kernel
        clEnqueueNDRangeKernel(commandQueue, kernel, 1, null,
                global_work_size, null, 0, null, null);

        // Read the output data
        clEnqueueReadBuffer(commandQueue, dstMem, CL_TRUE, 0,
                n * Sizeof.cl_float, dst, 0, null, null);

        // Release kernel, program, and memory objects
        clReleaseMemObject(srcMemA);
        clReleaseMemObject(srcMemB);
        clReleaseMemObject(dstMem);
        clReleaseKernel(kernel);
        clReleaseProgram(program);
        clReleaseCommandQueue(commandQueue);
        clReleaseContext(context);

        // Verify the result
        boolean passed = true;
        final float epsilon = 1e-7f;
        for (int i = 0; i < n; i++) {
            float x = dstArray[i];
            float y = srcArrayA[i] * srcArrayB[i];
            boolean epsilonEqual = Math.abs(x - y) <= epsilon * Math.abs(x);
            if (!epsilonEqual) {
                passed = false;
                break;
            }
        }
        System.out.println("Test " + (passed ? "PASSED" : "FAILED"));
        if (n <= 10) {
            System.out.println("Result: " + Arrays.toString(dstArray));
        }

        assertThat(passed, is(equalTo(Boolean.TRUE)));
    }

    
    public static int BN_NBITS = 256;
    public static int BN_WSHIFT = 5;
    public static int BN_WBITS = (1 << BN_WSHIFT);
    public static int BN_NWORDS = ((BN_NBITS/8) / 4); // 4 == sizeof(bn_word)

    public static int ACCESS_BUNDLE = 1024;
    public static int ACCESS_STRIDE = (ACCESS_BUNDLE/BN_NWORDS);
    
    @Test
    @Ignore
    public void reverseEngineering_startPoints() {
        int GLOBAL_SIZE = 1024;
        for (int j = 0; j < 1024; j++) {
            for (int k = 0; k < 64; k++) {
                        int i, cell, start;
                        System.out.println("========================================");
                        /* Load the row increment point */
                        i = 2 * j;
                        System.out.println("i: " + i);

                        cell = i;
                        System.out.println("cell: " + cell);
                        start = ((((2 * cell) / ACCESS_STRIDE) * ACCESS_BUNDLE) +
                                 (cell % (ACCESS_STRIDE/2)));
                        System.out.println("start: " + start);

                        int row_in_access_1 = start + (i*ACCESS_STRIDE);
                        System.out.println("row_in_access_1: " + row_in_access_1);

                        start += (ACCESS_STRIDE/2);
                        System.out.println("start: " + start);

                        int row_in_access_2 = start + (i*ACCESS_STRIDE);
                        System.out.println("row_in_access_2: " + row_in_access_2);

                        cell += (k * GLOBAL_SIZE);
                        System.out.println("cell: " + cell);
                        start = (((cell / ACCESS_STRIDE) * ACCESS_BUNDLE) +
                                 (cell % ACCESS_STRIDE));
                        System.out.println("start: " + start);
                        System.out.println("========================================");
            }
        }
    }

    @Test
    @Ignore
    public void calcAddrsFixZeroCl_loadWithoutErrors() throws IOException {
        // ATTENTION: BLDEBUG
        
        
        
        int CELLS = 64;
        int ROW_SIZE = 2; // x1, y1
        int COL_SIZE = 2; // rx, ry
        
        
        String calcAddrsFixZeroClFileName = "calc_addrs.cl";
        URL url = Resources.getResource(calcAddrsFixZeroClFileName);
        String calcAddrsFixZeroCl = Resources.toString(url, StandardCharsets.UTF_8);

        
        // Create input- and output data
        // out:
        int src_points_out[] = new int[ACCESS_BUNDLE];
        int src_z_heap[] = new int[ACCESS_BUNDLE];
        // in:
        int src_row_in[] = new int[ACCESS_BUNDLE * ACCESS_STRIDE * ROW_SIZE];
        int src_col_in[] = new int[ACCESS_BUNDLE * COL_SIZE];

        Pointer pointsOut = Pointer.to(src_points_out);
        Pointer zHeap = Pointer.to(src_z_heap);
        Pointer rowIn = Pointer.to(src_row_in);
        Pointer colIn = Pointer.to(src_col_in);
        
        // The platform, device type and device number
        // that will be used
        final int platformIndex = 0;
        final long deviceType = CL_DEVICE_TYPE_ALL;
        final int deviceIndex = 0;

        // Enable exceptions and subsequently omit error checks in this sample
        CL.setExceptionsEnabled(true);

        // Obtain the number of platforms
        int numPlatformsArray[] = new int[1];
        clGetPlatformIDs(0, null, numPlatformsArray);
        int numPlatforms = numPlatformsArray[0];

        // Obtain a platform ID
        cl_platform_id platforms[] = new cl_platform_id[numPlatforms];
        clGetPlatformIDs(platforms.length, platforms, null);
        cl_platform_id platform = platforms[platformIndex];

        // Initialize the context properties
        cl_context_properties contextProperties = new cl_context_properties();
        contextProperties.addProperty(CL_CONTEXT_PLATFORM, platform);

        // Obtain the number of devices for the platform
        int numDevicesArray[] = new int[1];
        clGetDeviceIDs(platform, deviceType, 0, null, numDevicesArray);
        int numDevices = numDevicesArray[0];

        // Obtain a device ID 
        cl_device_id devices[] = new cl_device_id[numDevices];
        clGetDeviceIDs(platform, deviceType, numDevices, devices, null);
        cl_device_id device = devices[deviceIndex];

        // Create a context for the selected device
        cl_context context = clCreateContext(
                contextProperties, 1, new cl_device_id[]{device},
                null, null, null);

        // Create a command-queue for the selected device
        cl_queue_properties properties = new cl_queue_properties();
        cl_command_queue commandQueue = clCreateCommandQueueWithProperties(
                context, device, properties, null);

        // Allocate the memory objects for the input- and output data
        cl_mem pointsOutMem = clCreateBuffer(context,
                CL_MEM_READ_WRITE,
                Sizeof.cl_int * src_points_out.length,
                pointsOut, null);
        cl_mem zHeapMem = clCreateBuffer(context,
                CL_MEM_READ_WRITE,
                Sizeof.cl_int * src_z_heap.length,
                zHeap, null);
        cl_mem rowInMem = clCreateBuffer(context,
                CL_MEM_READ_ONLY | CL_MEM_COPY_HOST_PTR,
                Sizeof.cl_int * src_row_in.length,
                null, null);
        cl_mem colInMem = clCreateBuffer(context,
                CL_MEM_READ_ONLY | CL_MEM_COPY_HOST_PTR,
                Sizeof.cl_int * src_col_in.length,
                null, null);
        
        // Create the program from the source code
        cl_program program = clCreateProgramWithSource(context,
                1, new String[]{calcAddrsFixZeroCl}, null, null);

        // Build the program
        clBuildProgram(program, 0, null, null, null, null);

        // Create the kernel
        cl_kernel kernel_ec_add_grid = clCreateKernel(program, "ec_add_grid", null);
        cl_kernel kernel_heap_invert = clCreateKernel(program, "heap_invert", null);
        cl_kernel kernel_hash_ec_point_get = clCreateKernel(program, "hash_ec_point_get", null);

        // Set the arguments for the kernel
        int a = 0;
        clSetKernelArg(kernel_ec_add_grid, a++, Sizeof.cl_mem, Pointer.to(pointsOutMem));
        clSetKernelArg(kernel_ec_add_grid, a++, Sizeof.cl_mem, Pointer.to(zHeapMem));
        clSetKernelArg(kernel_ec_add_grid, a++, Sizeof.cl_mem, Pointer.to(rowInMem));
        clSetKernelArg(kernel_ec_add_grid, a++, Sizeof.cl_mem, Pointer.to(colInMem));

        
        
        // Set the work-item dimensions
        long global_work_size[] = new long[]{ACCESS_BUNDLE, };

        // Execute the kernel
        clEnqueueNDRangeKernel(commandQueue, kernel_ec_add_grid, 1, null,
                global_work_size, null, 0, null, null);
    }

    private static List<String> getResourceNamesContent(List<String> resourceNames) throws IOException {
        List<String> contents = new ArrayList<>();
        for (String resourceName : resourceNames) {
            URL url = Resources.getResource(resourceName);
            String content = Resources.toString(url, StandardCharsets.UTF_8);
            contents.add(content);
        }
        return contents;
    }
    
    public final static int PUBLIC_KEY_LENGTH_WITH_PARITY_U32Array = 9;
    public final static int PRIVATE_KEY_LENGTH_U32Array = 8;
    public final static int PUBLIC_KEY_LENGTH_X_Y_WITHOUT_PARITY = 16;
    public final static int SECP256K1_PRE_COMPUTED_XY_SIZE = 12*8;
    
    @Test
    public void hashcatOpenCl() throws IOException {
        ByteBufferUtility byteBufferUtility = new ByteBufferUtility(false);
        KeyUtility keyUtility = new KeyUtility(MainNetParams.get(), byteBufferUtility);
        
        List<String> resourceNames = new ArrayList<>();
        resourceNames.add("inc_defines.h");
        resourceNames.add("inc_vendor.h");
        resourceNames.add("inc_types.h");
        resourceNames.add("inc_platform.h");
        resourceNames.add("inc_platform.cl");
        resourceNames.add("inc_common.h");
        resourceNames.add("inc_common.cl");

        resourceNames.add("inc_ecc_secp256k1.h");
        resourceNames.add("inc_ecc_secp256k1.cl");
        resourceNames.add("inc_ecc_secp256k1custom.cl");
        
        List<String> resourceNamesContent = getResourceNamesContent(resourceNames);
        List<String> resourceNamesContentWithReplacements = new ArrayList<>();
        for (String content : resourceNamesContent) {
            String contentWithReplacements = content;
            contentWithReplacements = contentWithReplacements.replaceAll("#include.*", "");
            contentWithReplacements = contentWithReplacements.replaceAll("GLOBAL_AS const secp256k1_t \\*tmps", "const secp256k1_t \\*tmps");
            resourceNamesContentWithReplacements.add(contentWithReplacements);
        }
        String[] openClPrograms = resourceNamesContentWithReplacements.toArray(new String[0]);
        
        int workSize = 1;
        
        // Create input- and output data
        // out:
        int dst_r[] = new int[PUBLIC_KEY_LENGTH_WITH_PARITY_U32Array*workSize];
        // in:
        int src_k[] = new int[PRIVATE_KEY_LENGTH_U32Array*workSize];
        
        StaticKey staticKey = new StaticKey();
        int[] staticPrivateKeyAsByteArray = KeyUtility.privateKeyIntsFromByteArray(staticKey.privateKeyBytes);
        System.arraycopy(staticPrivateKeyAsByteArray, 0 , src_k, 0, PRIVATE_KEY_LENGTH_U32Array);

        Pointer r = Pointer.to(dst_r);
        Pointer k = Pointer.to(src_k);
        
        long srcMemSize = BYTES_FOR_INT * src_k.length;
        long dstMemSize = BYTES_FOR_INT * dst_r.length;
        
        
        // ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        
        // The platform, device type and device number
        // that will be used
        final int platformIndex = 0;
        final long deviceType = CL_DEVICE_TYPE_ALL;
        final int deviceIndex = 0;

        // Enable exceptions and subsequently omit error checks in this sample
        CL.setExceptionsEnabled(true);

        // Obtain the number of platforms
        int numPlatformsArray[] = new int[1];
        clGetPlatformIDs(0, null, numPlatformsArray);
        int numPlatforms = numPlatformsArray[0];

        // Obtain a platform ID
        cl_platform_id platforms[] = new cl_platform_id[numPlatforms];
        clGetPlatformIDs(platforms.length, platforms, null);
        cl_platform_id platform = platforms[platformIndex];

        // Initialize the context properties
        cl_context_properties contextProperties = new cl_context_properties();
        contextProperties.addProperty(CL_CONTEXT_PLATFORM, platform);

        // Obtain the number of devices for the platform
        int numDevicesArray[] = new int[1];
        clGetDeviceIDs(platform, deviceType, 0, null, numDevicesArray);
        int numDevices = numDevicesArray[0];

        // Obtain a device ID 
        cl_device_id devices[] = new cl_device_id[numDevices];
        clGetDeviceIDs(platform, deviceType, numDevices, devices, null);
        cl_device_id device = devices[deviceIndex];
        final cl_device_id[] cl_device_ids = new cl_device_id[]{device};

        // Create a context for the selected device
        cl_context context = clCreateContext(contextProperties, 1, cl_device_ids,
                null, null, null);

        // Create a command-queue for the selected device
        cl_queue_properties properties = new cl_queue_properties();
        cl_command_queue commandQueue = clCreateCommandQueueWithProperties(
                context, device, properties, null);
        
        // Allocate the memory objects for the input- and output data
        cl_mem srcMemK = clCreateBuffer(context,
                CL_MEM_READ_ONLY | CL_MEM_COPY_HOST_PTR,
                srcMemSize, k, null);
        
        cl_mem dstMemR = clCreateBuffer(context,
                CL_MEM_READ_WRITE,
                dstMemSize, null, null);
        
        // Create the program from the source code
        cl_program program = clCreateProgramWithSource(context,
                openClPrograms.length, openClPrograms, null, null);

        // Build the program
        clBuildProgram(program, 0, null, null, null, null);
        
        // decide between transform/parse public
        final String kernelName;
        if (false) {
            kernelName = "generateKeysKernel_transform_public";
        } else {
            kernelName = "generateKeysKernel_parse_public";
        }
        
        System.out.println(LOG_SEPARATE_LINE);
        System.out.println("Kernel name: " + kernelName );
        System.out.println(LOG_SEPARATE_LINE);

        // Create the kernel
        cl_kernel kernel = clCreateKernel(program, kernelName, null);
        
        
        final long workGroupSize[] = new long[1];
        Pointer workGroupSizePointer = Pointer.to(workGroupSize);
        clGetKernelWorkGroupInfo(kernel, device, CL_KERNEL_WORK_GROUP_SIZE, Sizeof.cl_long, workGroupSizePointer, null);
        System.out.println("CL_KERNEL_WORK_GROUP_SIZE: " + workGroupSize[0]);
        
        final long preferredWorkGroupSizeMultiple[] = new long[1];
        Pointer preferredWorkGroupSizeMultiplePointer = Pointer.to(preferredWorkGroupSizeMultiple);
        clGetKernelWorkGroupInfo(kernel, device, CL_KERNEL_PREFERRED_WORK_GROUP_SIZE_MULTIPLE, Sizeof.cl_long, preferredWorkGroupSizeMultiplePointer, null);
        System.out.println("CL_KERNEL_PREFERRED_WORK_GROUP_SIZE_MULTIPLE: " + preferredWorkGroupSizeMultiple[0]);
        
        final long maxWorkItemDimensions[] = new long[1];
        Pointer maxWorkItemDimensionsPointer = Pointer.to(maxWorkItemDimensions);
        clGetDeviceInfo(device, CL_DEVICE_MAX_WORK_ITEM_DIMENSIONS, Sizeof.cl_long, maxWorkItemDimensionsPointer, null);
        System.out.println("CL_DEVICE_MAX_WORK_ITEM_DIMENSIONS: " + maxWorkItemDimensions[0]);
        
        openClInfo();

        /**
         * The specified 256 work-items in question refers to the total number
         * of work-items in a work-group regardless of whether it is 1-, 2- or 3-dimensions
         * and not the number of work-items in a particular direction.
         * For instance, valid work-group sizes in the format {x, y, z}
         * can be {256, 1, 1} or {16, 16, 1} or {8, 8, 4}.
         * 
         * These examples all sum up to 256 work-items in a work-group.
         * Hope this helps.
         */
        
        
        
        
        
        // Set the arguments for the kernel
        int a = 0;
        clSetKernelArg(kernel, a++, Sizeof.cl_mem, Pointer.to(dstMemR));
        clSetKernelArg(kernel, a++, Sizeof.cl_mem, Pointer.to(srcMemK));

        // Set the work-item dimensions
        long global_work_size[] = new long[]{workSize};

        // Execute the kernel
        System.out.println("execute ...");
        clEnqueueNDRangeKernel(commandQueue, kernel, 1, null,
                global_work_size, null, 0, null, null);
        
        // Read the output data
        clEnqueueReadBuffer(commandQueue, dstMemR, CL_TRUE, 0,
                dstMemSize, r, 0, null, null);
        
        byte[] dst_r_AsByteArray = KeyUtility.publicKeyByteArrayFromIntArray(dst_r);
        ECKey resultOpenCLKey = new ECKey(null, dst_r_AsByteArray);
        byte[] resultOpenCLPubKey = resultOpenCLKey.getPubKey();
        byte[] resultOpenCLPubKeyHash = resultOpenCLKey.getPubKeyHash();
        final String resultOpenCLPubKeyHashBase58 = keyUtility.toBase58(resultOpenCLKey.getPubKeyHash());
        
        // Release kernel, program, and memory objects
        clReleaseMemObject(srcMemK);
        clReleaseMemObject(dstMemR);
        clReleaseKernel(kernel);
        clReleaseProgram(program);
        clReleaseCommandQueue(commandQueue);
        clReleaseContext(context);
        
        ECKey expectedPrivateKey = new ECKey(new StaticKey().privateKeyBigInteger, null, true);
        byte[] expectedPublicKeyBytes = expectedPrivateKey.getPubKey();
        byte[] windowNaf = windowNaf((byte)4, new StaticKey().privateKeyBigInteger);
        System.out.println("windowNaf: " + Arrays.toString(windowNaf)); // may help to debug OpenCL w-NAF
        
        System.out.println("expectedPublicKeyBytes: " + Arrays.toString(expectedPublicKeyBytes));
        System.out.println("dst_r: " + Arrays.toString(dst_r));
        System.out.println("dst_r_AsByteArray: " + Arrays.toString(dst_r_AsByteArray));
        System.out.println("resultOpenCLPubKey: " + Arrays.toString(resultOpenCLPubKey));
        System.out.println("resultOpenCLPubKeyHash: " + Arrays.toString(resultOpenCLPubKeyHash));
        System.out.println("resultOpenCLPubKeyHashBase58: " + resultOpenCLPubKeyHashBase58);
        
        assertThat(resultOpenCLPubKey, is(equalTo(expectedPublicKeyBytes)));
        assertThat(resultOpenCLPubKeyHashBase58, is(equalTo(staticKey.publicKeyCompressed)));
    }
    
    @Test
    public void hashcatOpenClGrid() throws IOException {
        
        final boolean souts = false;
        
        ByteBufferUtility byteBufferUtility = new ByteBufferUtility(false);
        KeyUtility keyUtility = new KeyUtility(MainNetParams.get(), byteBufferUtility);
        
        List<String> resourceNames = new ArrayList<>();
        resourceNames.add("inc_defines.h");
        resourceNames.add("inc_vendor.h");
        resourceNames.add("inc_types.h");
        resourceNames.add("inc_platform.h");
        resourceNames.add("inc_platform.cl");
        resourceNames.add("inc_common.h");
        resourceNames.add("inc_common.cl");

        resourceNames.add("inc_ecc_secp256k1.h");
        resourceNames.add("inc_ecc_secp256k1.cl");
        resourceNames.add("inc_ecc_secp256k1custom.cl");
        
        List<String> resourceNamesContent = getResourceNamesContent(resourceNames);
        List<String> resourceNamesContentWithReplacements = new ArrayList<>();
        for (String content : resourceNamesContent) {
            String contentWithReplacements = content;
            contentWithReplacements = contentWithReplacements.replaceAll("#include.*", "");
            contentWithReplacements = contentWithReplacements.replaceAll("GLOBAL_AS const secp256k1_t \\*tmps", "const secp256k1_t \\*tmps");
            resourceNamesContentWithReplacements.add(contentWithReplacements);
        }
        String[] openClPrograms = resourceNamesContentWithReplacements.toArray(new String[0]);
        
        StaticKey staticKey = new StaticKey();
        
        // ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        
        // The platform, device type and device number
        // that will be used
        final int platformIndex = 0;
        final long deviceType = CL_DEVICE_TYPE_ALL;
        final int deviceIndex = 0;

        // Enable exceptions and subsequently omit error checks in this sample
        CL.setExceptionsEnabled(true);

        // Obtain the number of platforms
        int numPlatformsArray[] = new int[1];
        clGetPlatformIDs(0, null, numPlatformsArray);
        int numPlatforms = numPlatformsArray[0];

        System.out.println("get OpenCL information");
        
        
        System.out.println("Obtain a platform ID");
        // Obtain a platform ID
        cl_platform_id platforms[] = new cl_platform_id[numPlatforms];
        clGetPlatformIDs(platforms.length, platforms, null);
        cl_platform_id platform = platforms[platformIndex];

        System.out.println("Initialize the context properties");
        // Initialize the context properties
        cl_context_properties contextProperties = new cl_context_properties();
        contextProperties.addProperty(CL_CONTEXT_PLATFORM, platform);

        System.out.println("Obtain the number of devices for the platform");
        // Obtain the number of devices for the platform
        int numDevicesArray[] = new int[1];
        clGetDeviceIDs(platform, deviceType, 0, null, numDevicesArray);
        int numDevices = numDevicesArray[0];

        System.out.println("Obtain a device ID");
        // Obtain a device ID 
        cl_device_id devices[] = new cl_device_id[numDevices];
        clGetDeviceIDs(platform, deviceType, numDevices, devices, null);
        cl_device_id device = devices[deviceIndex];
        final cl_device_id[] cl_device_ids = new cl_device_id[]{device};

        // Create a context for the selected device
        cl_context context = clCreateContext(contextProperties, 1, cl_device_ids,
                null, null, null);
        

        // Create a command-queue for the selected device
        cl_queue_properties properties = new cl_queue_properties();
        cl_command_queue commandQueue = clCreateCommandQueueWithProperties(
                context, device, properties, null);
        
        System.out.println("Create the program from the source code");
        // Create the program from the source code
        cl_program program = clCreateProgramWithSource(context,
                openClPrograms.length, openClPrograms, null, null);

        // Build the program
        clBuildProgram(program, 0, null, null, null, null);
        
        final String kernelName  = "generateKeysKernel_grid";
        
        System.out.println(LOG_SEPARATE_LINE);
        System.out.println("Kernel name: " + kernelName );
        System.out.println(LOG_SEPARATE_LINE);

        // Create the kernel
        cl_kernel kernel = clCreateKernel(program, kernelName, null);
        
        if (false) {
        final long workGroupSize[] = new long[1];
        Pointer workGroupSizePointer = Pointer.to(workGroupSize);
        clGetKernelWorkGroupInfo(kernel, device, CL_KERNEL_WORK_GROUP_SIZE, Sizeof.cl_long, workGroupSizePointer, null);
        System.out.println("CL_KERNEL_WORK_GROUP_SIZE: " + workGroupSize[0]);
        
        final long preferredWorkGroupSizeMultiple[] = new long[1];
        Pointer preferredWorkGroupSizeMultiplePointer = Pointer.to(preferredWorkGroupSizeMultiple);
        clGetKernelWorkGroupInfo(kernel, device, CL_KERNEL_PREFERRED_WORK_GROUP_SIZE_MULTIPLE, Sizeof.cl_long, preferredWorkGroupSizeMultiplePointer, null);
        System.out.println("CL_KERNEL_PREFERRED_WORK_GROUP_SIZE_MULTIPLE: " + preferredWorkGroupSizeMultiple[0]);
        
        final long maxWorkItemDimensions[] = new long[1];
        Pointer maxWorkItemDimensionsPointer = Pointer.to(maxWorkItemDimensions);
        clGetDeviceInfo(device, CL_DEVICE_MAX_WORK_ITEM_DIMENSIONS, Sizeof.cl_long, maxWorkItemDimensionsPointer, null);
        System.out.println("CL_DEVICE_MAX_WORK_ITEM_DIMENSIONS: " + maxWorkItemDimensions[0]);
        
        openClInfo();
        }

        OpenClTask openClTask = new OpenClTask(context, BITS_FOR_GRID);
        System.out.println("openClTask.getWorkSize(): " + openClTask.getWorkSize());
        
        Random sr = new SecureRandom();
        BigInteger secretBase = keyUtility.createSecret(64, sr);
        byte[] keyBase = secretBase.toByteArray();
        System.out.println("keyBase: " + Arrays.toString(keyBase));
        openClTask.setSrcPrivateKeyChunk(keyBase);
        
        ByteBuffer clonedDstByteBuffer = openClTask.executeKernel(kernel, commandQueue);
        PublicKeyBytes[] publicKeys = transformByteBufferToPublicKeyBytes(clonedDstByteBuffer, openClTask.getWorkSize(), secretBase);
        {
            // free and do not use anymore
            ByteBufferUtility.freeByteBuffer(clonedDstByteBuffer);
            clonedDstByteBuffer = null;
        }
        
        System.out.println("WARMUP ... ");
        hashPublicKeys(publicKeys, souts);
        hashPublicKeysFast(publicKeys, souts);
        System.out.println("... WARMUP done.");
        hashPublicKeys(publicKeys, souts);
        hashPublicKeysFast(publicKeys, souts);
        
        for (int i = 0; i < openClTask.getWorkSize(); i++) {
            if (i%50000 == 0) {
                System.out.println("check: " + i);
            }
            if (souts) {
            System.out.println("i: " + i);
            System.out.println("1");
            }
            byte[] privateKey = keyBase.clone();
            openClTask.unsetLSB(privateKey, BITS_FOR_GRID);
            OpenClTask.setLSB(privateKey, i);
            
            if(souts) {
                System.out.println("privateKey: " + Arrays.toString(privateKey));
            }
            
            PublicKeyBytes publicKeyBytes = publicKeys[i];
            
            if (souts) {
            System.out.println("2");
            }
            
            ECKey resultOpenCLKeyCompressed = new ECKey(privateKey, publicKeyBytes.getCompressed());
            ECKey resultOpenCLKeyUncompressed = new ECKey(privateKey, publicKeyBytes.getUncompressed());
            
            if (souts) {
            System.out.println("publicKeyBytes.compressed: " + Arrays.toString(publicKeyBytes.getCompressed()));
            System.out.println("publicKeyBytes.uncompressed: " + Arrays.toString(publicKeyBytes.getUncompressed()));
            }
            
            byte[] resultOpenCLKeyCompressedPubKey = resultOpenCLKeyCompressed.getPubKey();
            byte[] resultOpenCLKeyCompressedPubKeyHash = resultOpenCLKeyCompressed.getPubKeyHash();
            byte[] resultOpenCLKeyUncompressedPubKey = resultOpenCLKeyUncompressed.getPubKey();
            byte[] resultOpenCLKeyUncompressedPubKeyHash = resultOpenCLKeyUncompressed.getPubKeyHash();
            
            if (souts) {
            System.out.println("resultOpenCLKeyCompressedPubKey: " + Arrays.toString(resultOpenCLKeyCompressedPubKey));
            System.out.println("resultOpenCLKeyCompressedPubKeyHash: " + Arrays.toString(resultOpenCLKeyCompressedPubKeyHash));
            System.out.println("resultOpenCLKeyUncompressedPubKey: " + Arrays.toString(resultOpenCLKeyUncompressedPubKey));
            System.out.println("resultOpenCLKeyUncompressedPubKeyHash: " + Arrays.toString(resultOpenCLKeyUncompressedPubKeyHash));
            }
            final String resultOpenCLKeyCompressedPubKeyHashBase58 = keyUtility.toBase58(resultOpenCLKeyCompressed.getPubKeyHash());
            final String resultOpenCLKeyUncompressedPubKeyHashBase58 = keyUtility.toBase58(resultOpenCLKeyUncompressed.getPubKeyHash());
            
            if (souts) {
            System.out.println("resultOpenCLKeyCompressedPubKeyHashBase58: " + resultOpenCLKeyCompressedPubKeyHashBase58);
            System.out.println("resultOpenCLKeyUncompressedPubKeyHashBase58: " + resultOpenCLKeyUncompressedPubKeyHashBase58);
            
            System.out.println("publicKeyBytes.getCompressedKeyHash(): " + Arrays.toString(publicKeyBytes.getCompressedKeyHash()));
            System.out.println("publicKeyBytes.getUncompressedKeyHash(): " + Arrays.toString(publicKeyBytes.getUncompressedKeyHash()));
            
            System.out.println("publicKeyBytes.getCompressedKeyHashAsBase58(keyUtility): " + publicKeyBytes.getCompressedKeyHashAsBase58(keyUtility));
            System.out.println("publicKeyBytes.getUncompressedKeyHashAsBase58(keyUtility): " + publicKeyBytes.getUncompressedKeyHashAsBase58(keyUtility));
            }
            ECKey expectedUncompressedKey = new ECKey(privateKey, null);
            BigInteger expectedPrivateKeyBigInteger = expectedUncompressedKey.getPrivKey();
            ECKey expectedCompressedKey = new ECKey( expectedPrivateKeyBigInteger, null, true);
            
            byte[] expectedCompressedPublicKeyBytes = expectedCompressedKey.getPubKey();
            byte[] expectedUncompressedPublicKeyBytes = expectedUncompressedKey.getPubKey();

            if (souts) {
            System.out.println("expectedPrivateKeyBigInteger: " + expectedPrivateKeyBigInteger);
            System.out.println("expectedCompressedPublicKeyBytes: " + Arrays.toString(expectedCompressedPublicKeyBytes));
            System.out.println("expectedUncompressedPublicKeyBytes: " + Arrays.toString(expectedUncompressedPublicKeyBytes));
            }
            
            final String expectedCompressedPublicKeyHashBase58 = keyUtility.toBase58(expectedCompressedKey.getPubKeyHash());
            final String expectedUncompressedPublicKeyHashBase58 = keyUtility.toBase58(expectedUncompressedKey.getPubKeyHash());
            
            if (true) {
                assertThat(resultOpenCLKeyCompressedPubKey, is(equalTo(expectedCompressedPublicKeyBytes)));
                assertThat(resultOpenCLKeyUncompressedPubKey, is(equalTo(expectedUncompressedPublicKeyBytes)));
                
                assertThat(publicKeyBytes.getCompressedKeyHashAsBase58(keyUtility), is(equalTo(expectedCompressedPublicKeyHashBase58)));
                assertThat(publicKeyBytes.getUncompressedKeyHashAsBase58(keyUtility), is(equalTo(expectedUncompressedPublicKeyHashBase58)));
            }
        }
        
        System.out.println("release");
        
        if(true) {
        // Release kernel, program, and memory objects
        openClTask.releaseCl();
        clReleaseKernel(kernel);
        clReleaseProgram(program);
        clReleaseCommandQueue(commandQueue);
        clReleaseContext(context);
        }
    }

    private void hashPublicKeysFast(PublicKeyBytes[] publicKeys, final boolean souts) {
        System.out.println("execute hash fast ...");
        long beforeHash = System.currentTimeMillis();
        for (int i = 0; i < publicKeys.length; i++) {
            byte[] compressedKeyHashFast = publicKeys[i].getCompressedKeyHashFast();
            byte[] uncompressedKeyHashFast = publicKeys[i].getUncompressedKeyHashFast();
            
            //assertThat(compressedKeyHash, is(equalTo(compressedKeyHashFast)));
            //assertThat(uncompressedKeyHash, is(equalTo(uncompressedKeyHashFast)));
            
            if (souts) {
                System.out.println("publicKeys["+i+"].compressedKeyHashFast: " + Arrays.toString(compressedKeyHashFast));
                System.out.println("publicKeys["+i+"].uncompressedKeyHashFast: " + Arrays.toString(uncompressedKeyHashFast));
            }
        }
        long afterHash = System.currentTimeMillis();
        System.out.println("... hashed fast in: " + (afterHash - beforeHash) + "ms");
    }

    private void hashPublicKeys(PublicKeyBytes[] publicKeys, final boolean souts) {
        System.out.println("execute hash ...");
        long beforeHash = System.currentTimeMillis();
        for (int i = 0; i < publicKeys.length; i++) {
            byte[] compressedKeyHash = publicKeys[i].getCompressedKeyHash();
            byte[] uncompressedKeyHash = publicKeys[i].getUncompressedKeyHash();
            
            //assertThat(compressedKeyHash, is(equalTo(compressedKeyHashFast)));
            //assertThat(uncompressedKeyHash, is(equalTo(uncompressedKeyHashFast)));
            
            if (souts) {
                System.out.println("publicKeys["+i+"].compressedKeyHash: " + Arrays.toString(compressedKeyHash));
                System.out.println("publicKeys["+i+"].uncompressedKeyHash: " + Arrays.toString(uncompressedKeyHash));
            }
        }
        long afterHash = System.currentTimeMillis();
        System.out.println("... hashed in: " + (afterHash - beforeHash) + "ms");
    }
    
    /**
     * Read the inner bytes in reverse order. Remove padding bytes to return a clean byte array. Only for x with padding
     */
    private static final byte[] getPublicKeyFromByteBuffer(ByteBuffer b, int keyOffset) {
        int paddingBytes = 3;
        int publicKeyByteLength = PUBLIC_KEY_LENGTH_WITH_PARITY_U32Array * BYTES_FOR_INT;
        byte[] publicKey = new byte[publicKeyByteLength - paddingBytes];
        // its not inverted because the memory was written in OpenCL
        int offset = publicKeyByteLength * keyOffset;
        outer:
        for (int i=0; i<PUBLIC_KEY_LENGTH_WITH_PARITY_U32Array; i++) {
            int x = i*BYTES_FOR_INT;
            for (int j = 0; j < BYTES_FOR_INT; j++) {
                int publicKeyOffset = x+j;
                if (publicKeyOffset == publicKey.length) {
                    // return the public key, read of all bytes finish
                    break outer;
                }
                int y = BYTES_FOR_INT-j-1;
                int byteBufferOffset = offset+x+y;
                publicKey[publicKeyOffset] = b.get(byteBufferOffset);
            }
        }
        return publicKey;
    }
    
    
    
    private static final String LOG_SEPARATE_LINE = "-------------------------------------------------------";

    private void dumpIntArray(String name, int[] intArray) {
        for (int i = 0; i < intArray.length; i++) {
            System.out.println(name + "["+i+"]: " + Integer.toHexString(intArray[i]));
        }
    }
    
    // from https://java-browser.yawk.at/org.bouncycastle/bcprov-jdk15/1.46/org/bouncycastle/math/ec/WNafMultiplier.java
    public byte[] windowNaf(byte width, BigInteger k)
    {
        // The window NAF is at most 1 element longer than the binary
        // representation of the integer k. byte can be used instead of short or
        // int unless the window width is larger than 8. For larger width use
        // short or int. However, a width of more than 8 is not efficient for
        // m = log2(q) smaller than 2305 Bits. Note: Values for m larger than
        // 1000 Bits are currently not used in practice.
        byte[] wnaf = new byte[k.bitLength() + 1];

        // 2^width as short and BigInteger
        short pow2wB = (short)(1 << width);
        BigInteger pow2wBI = BigInteger.valueOf(pow2wB);

        int i = 0;

        // The actual length of the WNAF
        int length = 0;

        // while k >= 1
        while (k.signum() > 0)
        {
            // if k is odd
            if (k.testBit(0))
            {
                // k mod 2^width
                BigInteger remainder = k.mod(pow2wBI);

                // if remainder > 2^(width - 1) - 1
                if (remainder.testBit(width - 1))
                {
                    wnaf[i] = (byte)(remainder.intValue() - pow2wB);
                }
                else
                {
                    wnaf[i] = (byte)remainder.intValue();
                }
                // wnaf[i] is now in [-2^(width-1), 2^(width-1)-1]

                k = k.subtract(BigInteger.valueOf(wnaf[i]));
                length = i;
            }
            else
            {
                wnaf[i] = 0;
            }

            // k = k/2
            k = k.shiftRight(1);
            i++;
        }

        length++;

        // Reduce the WNAF array to its actual length
        byte[] wnafShort = new byte[length];
        System.arraycopy(wnaf, 0, wnafShort, 0, length);
        return wnafShort;
    }

    public static void openClInfo()
    {
        // Obtain the number of platforms
        int numPlatforms[] = new int[1];
        clGetPlatformIDs(0, null, numPlatforms);

        System.out.println("Number of platforms: "+numPlatforms[0]);

        // Obtain the platform IDs
        cl_platform_id platforms[] = new cl_platform_id[numPlatforms[0]];
        clGetPlatformIDs(platforms.length, platforms, null);

        // Collect all devices of all platforms
        List<cl_device_id> devices = new ArrayList<cl_device_id>();
        for (int i=0; i<platforms.length; i++)
        {
            String platformName = getString(platforms[i], CL_PLATFORM_NAME);

            // Obtain the number of devices for the current platform
            int numDevices[] = new int[1];
            clGetDeviceIDs(platforms[i], CL_DEVICE_TYPE_ALL, 0, null, numDevices);

            System.out.println("Number of devices in platform "+platformName+": "+numDevices[0]);

            cl_device_id devicesArray[] = new cl_device_id[numDevices[0]];
            clGetDeviceIDs(platforms[i], CL_DEVICE_TYPE_ALL, numDevices[0], devicesArray, null);

            devices.addAll(Arrays.asList(devicesArray));
        }

        // Print the infos about all devices
        for (cl_device_id device : devices)
        {
            // CL_DEVICE_NAME
            String deviceName = getString(device, CL_DEVICE_NAME);
            System.out.println("--- Info for device "+deviceName+": ---");
            System.out.printf("CL_DEVICE_NAME: \t\t\t%s\n", deviceName);

            // CL_DEVICE_VENDOR
            String deviceVendor = getString(device, CL_DEVICE_VENDOR);
            System.out.printf("CL_DEVICE_VENDOR: \t\t\t%s\n", deviceVendor);

            // CL_DRIVER_VERSION
            String driverVersion = getString(device, CL_DRIVER_VERSION);
            System.out.printf("CL_DRIVER_VERSION: \t\t\t%s\n", driverVersion);

            // CL_DEVICE_TYPE
            long deviceType = getLong(device, CL_DEVICE_TYPE);
            if( (deviceType & CL_DEVICE_TYPE_CPU) != 0)
                System.out.printf("CL_DEVICE_TYPE:\t\t\t\t%s\n", "CL_DEVICE_TYPE_CPU");
            if( (deviceType & CL_DEVICE_TYPE_GPU) != 0)
                System.out.printf("CL_DEVICE_TYPE:\t\t\t\t%s\n", "CL_DEVICE_TYPE_GPU");
            if( (deviceType & CL_DEVICE_TYPE_ACCELERATOR) != 0)
                System.out.printf("CL_DEVICE_TYPE:\t\t\t\t%s\n", "CL_DEVICE_TYPE_ACCELERATOR");
            if( (deviceType & CL_DEVICE_TYPE_DEFAULT) != 0)
                System.out.printf("CL_DEVICE_TYPE:\t\t\t\t%s\n", "CL_DEVICE_TYPE_DEFAULT");

            // CL_DEVICE_MAX_COMPUTE_UNITS
            int maxComputeUnits = getInt(device, CL_DEVICE_MAX_COMPUTE_UNITS);
            System.out.printf("CL_DEVICE_MAX_COMPUTE_UNITS:\t\t%d\n", maxComputeUnits);

            // CL_DEVICE_MAX_WORK_ITEM_DIMENSIONS
            long maxWorkItemDimensions = getLong(device, CL_DEVICE_MAX_WORK_ITEM_DIMENSIONS);
            System.out.printf("CL_DEVICE_MAX_WORK_ITEM_DIMENSIONS:\t%d\n", maxWorkItemDimensions);

            // CL_DEVICE_MAX_WORK_ITEM_SIZES
            long maxWorkItemSizes[] = getSizes(device, CL_DEVICE_MAX_WORK_ITEM_SIZES, 3);
            System.out.printf("CL_DEVICE_MAX_WORK_ITEM_SIZES:\t\t%d / %d / %d \n",
                maxWorkItemSizes[0], maxWorkItemSizes[1], maxWorkItemSizes[2]);

            // CL_DEVICE_MAX_WORK_GROUP_SIZE
            long maxWorkGroupSize = getSize(device, CL_DEVICE_MAX_WORK_GROUP_SIZE);
            System.out.printf("CL_DEVICE_MAX_WORK_GROUP_SIZE:\t\t%d\n", maxWorkGroupSize);

            // CL_DEVICE_MAX_CLOCK_FREQUENCY
            long maxClockFrequency = getLong(device, CL_DEVICE_MAX_CLOCK_FREQUENCY);
            System.out.printf("CL_DEVICE_MAX_CLOCK_FREQUENCY:\t\t%d MHz\n", maxClockFrequency);

            // CL_DEVICE_ADDRESS_BITS
            int addressBits = getInt(device, CL_DEVICE_ADDRESS_BITS);
            System.out.printf("CL_DEVICE_ADDRESS_BITS:\t\t\t%d\n", addressBits);

            // CL_DEVICE_MAX_MEM_ALLOC_SIZE
            long maxMemAllocSize = getLong(device, CL_DEVICE_MAX_MEM_ALLOC_SIZE);
            System.out.printf("CL_DEVICE_MAX_MEM_ALLOC_SIZE:\t\t%d MByte\n", (int)(maxMemAllocSize / (1024 * 1024)));

            // CL_DEVICE_GLOBAL_MEM_SIZE
            long globalMemSize = getLong(device, CL_DEVICE_GLOBAL_MEM_SIZE);
            System.out.printf("CL_DEVICE_GLOBAL_MEM_SIZE:\t\t%d MByte\n", (int)(globalMemSize / (1024 * 1024)));

            // CL_DEVICE_ERROR_CORRECTION_SUPPORT
            int errorCorrectionSupport = getInt(device, CL_DEVICE_ERROR_CORRECTION_SUPPORT);
            System.out.printf("CL_DEVICE_ERROR_CORRECTION_SUPPORT:\t%s\n", errorCorrectionSupport != 0 ? "yes" : "no");

            // CL_DEVICE_LOCAL_MEM_TYPE
            int localMemType = getInt(device, CL_DEVICE_LOCAL_MEM_TYPE);
            System.out.printf("CL_DEVICE_LOCAL_MEM_TYPE:\t\t%s\n", localMemType == 1 ? "local" : "global");

            // CL_DEVICE_LOCAL_MEM_SIZE
            long localMemSize = getLong(device, CL_DEVICE_LOCAL_MEM_SIZE);
            System.out.printf("CL_DEVICE_LOCAL_MEM_SIZE:\t\t%d KByte\n", (int)(localMemSize / 1024));

            // CL_DEVICE_MAX_CONSTANT_BUFFER_SIZE
            long maxConstantBufferSize = getLong(device, CL_DEVICE_MAX_CONSTANT_BUFFER_SIZE);
            System.out.printf("CL_DEVICE_MAX_CONSTANT_BUFFER_SIZE:\t%d KByte\n", (int)(maxConstantBufferSize / 1024));

            // CL_DEVICE_QUEUE_PROPERTIES
            long queueProperties = getLong(device, CL_DEVICE_QUEUE_PROPERTIES);
            if(( queueProperties & CL_QUEUE_OUT_OF_ORDER_EXEC_MODE_ENABLE ) != 0)
                System.out.printf("CL_DEVICE_QUEUE_PROPERTIES:\t\t%s\n", "CL_QUEUE_OUT_OF_ORDER_EXEC_MODE_ENABLE");
            if(( queueProperties & CL_QUEUE_PROFILING_ENABLE ) != 0)
                System.out.printf("CL_DEVICE_QUEUE_PROPERTIES:\t\t%s\n", "CL_QUEUE_PROFILING_ENABLE");

            // CL_DEVICE_IMAGE_SUPPORT
            int imageSupport = getInt(device, CL_DEVICE_IMAGE_SUPPORT);
            System.out.printf("CL_DEVICE_IMAGE_SUPPORT:\t\t%d\n", imageSupport);

            // CL_DEVICE_MAX_READ_IMAGE_ARGS
            int maxReadImageArgs = getInt(device, CL_DEVICE_MAX_READ_IMAGE_ARGS);
            System.out.printf("CL_DEVICE_MAX_READ_IMAGE_ARGS:\t\t%d\n", maxReadImageArgs);

            // CL_DEVICE_MAX_WRITE_IMAGE_ARGS
            int maxWriteImageArgs = getInt(device, CL_DEVICE_MAX_WRITE_IMAGE_ARGS);
            System.out.printf("CL_DEVICE_MAX_WRITE_IMAGE_ARGS:\t\t%d\n", maxWriteImageArgs);

            // CL_DEVICE_SINGLE_FP_CONFIG
            long singleFpConfig = getLong(device, CL_DEVICE_SINGLE_FP_CONFIG);
            System.out.printf("CL_DEVICE_SINGLE_FP_CONFIG:\t\t%s\n",
                stringFor_cl_device_fp_config(singleFpConfig));

            // CL_DEVICE_IMAGE2D_MAX_WIDTH
            long image2dMaxWidth = getSize(device, CL_DEVICE_IMAGE2D_MAX_WIDTH);
            System.out.printf("CL_DEVICE_2D_MAX_WIDTH\t\t\t%d\n", image2dMaxWidth);

            // CL_DEVICE_IMAGE2D_MAX_HEIGHT
            long image2dMaxHeight = getSize(device, CL_DEVICE_IMAGE2D_MAX_HEIGHT);
            System.out.printf("CL_DEVICE_2D_MAX_HEIGHT\t\t\t%d\n", image2dMaxHeight);

            // CL_DEVICE_IMAGE3D_MAX_WIDTH
            long image3dMaxWidth = getSize(device, CL_DEVICE_IMAGE3D_MAX_WIDTH);
            System.out.printf("CL_DEVICE_3D_MAX_WIDTH\t\t\t%d\n", image3dMaxWidth);

            // CL_DEVICE_IMAGE3D_MAX_HEIGHT
            long image3dMaxHeight = getSize(device, CL_DEVICE_IMAGE3D_MAX_HEIGHT);
            System.out.printf("CL_DEVICE_3D_MAX_HEIGHT\t\t\t%d\n", image3dMaxHeight);

            // CL_DEVICE_IMAGE3D_MAX_DEPTH
            long image3dMaxDepth = getSize(device, CL_DEVICE_IMAGE3D_MAX_DEPTH);
            System.out.printf("CL_DEVICE_3D_MAX_DEPTH\t\t\t%d\n", image3dMaxDepth);

            // CL_DEVICE_PREFERRED_VECTOR_WIDTH_<type>
            System.out.printf("CL_DEVICE_PREFERRED_VECTOR_WIDTH_<t>\t");
            int preferredVectorWidthChar = getInt(device, CL_DEVICE_PREFERRED_VECTOR_WIDTH_CHAR);
            int preferredVectorWidthShort = getInt(device, CL_DEVICE_PREFERRED_VECTOR_WIDTH_SHORT);
            int preferredVectorWidthInt = getInt(device, CL_DEVICE_PREFERRED_VECTOR_WIDTH_INT);
            int preferredVectorWidthLong = getInt(device, CL_DEVICE_PREFERRED_VECTOR_WIDTH_LONG);
            int preferredVectorWidthFloat = getInt(device, CL_DEVICE_PREFERRED_VECTOR_WIDTH_FLOAT);
            int preferredVectorWidthDouble = getInt(device, CL_DEVICE_PREFERRED_VECTOR_WIDTH_DOUBLE);
            System.out.printf("CHAR %d, SHORT %d, INT %d, LONG %d, FLOAT %d, DOUBLE %d\n\n\n",
                   preferredVectorWidthChar, preferredVectorWidthShort,
                   preferredVectorWidthInt, preferredVectorWidthLong,
                   preferredVectorWidthFloat, preferredVectorWidthDouble);
        }
    }
        
    /**
     * Returns the value of the device info parameter with the given name
     *
     * @param device The device
     * @param paramName The parameter name
     * @return The value
     */
    private static int getInt(cl_device_id device, int paramName)
    {
        return getInts(device, paramName, 1)[0];
    }

    /**
     * Returns the values of the device info parameter with the given name
     *
     * @param device The device
     * @param paramName The parameter name
     * @param numValues The number of values
     * @return The value
     */
    private static int[] getInts(cl_device_id device, int paramName, int numValues)
    {
        int values[] = new int[numValues];
        clGetDeviceInfo(device, paramName, Sizeof.cl_int * numValues, Pointer.to(values), null);
        return values;
    }

    /**
     * Returns the value of the device info parameter with the given name
     *
     * @param device The device
     * @param paramName The parameter name
     * @return The value
     */
    private static long getLong(cl_device_id device, int paramName)
    {
        return getLongs(device, paramName, 1)[0];
    }

    /**
     * Returns the values of the device info parameter with the given name
     *
     * @param device The device
     * @param paramName The parameter name
     * @param numValues The number of values
     * @return The value
     */
    private static long[] getLongs(cl_device_id device, int paramName, int numValues)
    {
        long values[] = new long[numValues];
        clGetDeviceInfo(device, paramName, Sizeof.cl_long * numValues, Pointer.to(values), null);
        return values;
    }

    /**
     * Returns the value of the device info parameter with the given name
     *
     * @param device The device
     * @param paramName The parameter name
     * @return The value
     */
    private static String getString(cl_device_id device, int paramName)
    {
        // Obtain the length of the string that will be queried
        long size[] = new long[1];
        clGetDeviceInfo(device, paramName, 0, null, size);

        // Create a buffer of the appropriate size and fill it with the info
        byte buffer[] = new byte[(int)size[0]];
        clGetDeviceInfo(device, paramName, buffer.length, Pointer.to(buffer), null);

        // Create a string from the buffer (excluding the trailing \0 byte)
        return new String(buffer, 0, buffer.length-1);
    }

    /**
     * Returns the value of the platform info parameter with the given name
     *
     * @param platform The platform
     * @param paramName The parameter name
     * @return The value
     */
    private static String getString(cl_platform_id platform, int paramName)
    {
        // Obtain the length of the string that will be queried
        long size[] = new long[1];
        clGetPlatformInfo(platform, paramName, 0, null, size);

        // Create a buffer of the appropriate size and fill it with the info
        byte buffer[] = new byte[(int)size[0]];
        clGetPlatformInfo(platform, paramName, buffer.length, Pointer.to(buffer), null);

        // Create a string from the buffer (excluding the trailing \0 byte)
        return new String(buffer, 0, buffer.length-1);
    }
    
    /**
     * Returns the value of the device info parameter with the given name
     *
     * @param device The device
     * @param paramName The parameter name
     * @return The value
     */
    private static long getSize(cl_device_id device, int paramName)
    {
        return getSizes(device, paramName, 1)[0];
    }
    
    /**
     * Returns the values of the device info parameter with the given name
     *
     * @param device The device
     * @param paramName The parameter name
     * @param numValues The number of values
     * @return The value
     */
    static long[] getSizes(cl_device_id device, int paramName, int numValues)
    {
        // The size of the returned data has to depend on 
        // the size of a size_t, which is handled here
        ByteBuffer buffer = ByteBuffer.allocate(
            numValues * Sizeof.size_t).order(ByteOrder.nativeOrder());
        clGetDeviceInfo(device, paramName, Sizeof.size_t * numValues, 
            Pointer.to(buffer), null);
        long values[] = new long[numValues];
        if (Sizeof.size_t == 4)
        {
            for (int i=0; i<numValues; i++)
            {
                values[i] = buffer.getInt(i * Sizeof.size_t);
            }
        }
        else
        {
            for (int i=0; i<numValues; i++)
            {
                values[i] = buffer.getLong(i * Sizeof.size_t);
            }
        }
        return values;
    }
    
}
