package net.ladenthin.btcdetector;

import com.google.common.io.Resources;
import java.io.File;
import java.io.IOException;
import java.math.BigInteger;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import net.ladenthin.btcdetector.configuration.ProbeAddressesOpenCL;
import org.apache.commons.io.FileUtils;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

import static org.jocl.CL.*;

import java.util.Arrays;
import org.bitcoinj.core.ECKey;
import org.bitcoinj.params.MainNetParams;
import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.is;
import static org.hamcrest.Matchers.nullValue;

import org.jocl.*;
import org.junit.Ignore;

public class ProbeAddressesOpenCLTest {

    private static final TestAddresses testAddresses = new TestAddresses(1024, false);

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
    @Ignore
    public void run_alive_beep() throws IOException {
        ProbeAddressesOpenCL probeAddressesOpenCL = new ProbeAddressesOpenCL();

        List<String> files = new ArrayList<>();
        files.add(tempAddressesFile.getAbsolutePath());

        OpenCLProber openCLProber = new OpenCLProber(probeAddressesOpenCL);
        openCLProber.run();
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
        int dst_r[] = new int[9*workSize];
        // in:
        int src_k[] = new int[8*workSize];
        
        StaticKey staticKey = new StaticKey();
        int[] staticPrivateKeyAsByteArray = KeyUtility.privateKeyIntsFromByteArray(staticKey.privateKeyBytes);
        System.arraycopy(staticPrivateKeyAsByteArray, 0 , src_k, 0, src_k.length);

        Pointer r = Pointer.to(dst_r);
        Pointer k = Pointer.to(src_k);
        
        long srcMemSize = Sizeof.cl_int8 * dst_r.length;
        long dstMemSize = Sizeof.cl_int8 * src_k.length;
        
        
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

        // Create a context for the selected device
        cl_context context = clCreateContext(
                contextProperties, 1, new cl_device_id[]{device},
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

        // Create the kernel
        cl_kernel kernel = clCreateKernel(program, "generateKeysKernel", null);

        // Set the arguments for the kernel
        int a = 0;
        clSetKernelArg(kernel, a++, Sizeof.cl_mem, Pointer.to(dstMemR));
        clSetKernelArg(kernel, a++, Sizeof.cl_mem, Pointer.to(srcMemK));

        // Set the work-item dimensions
        long global_work_size[] = new long[]{workSize};

        // Execute the kernel
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
        
        ECKey expectedPrivateKey = new ECKey(staticKey.privateKeyBigInteger, null, true);
        byte[] expectedPublicKeyBytes = expectedPrivateKey.getPubKey();
        byte[] windowNaf = windowNaf((byte)4, new StaticKey().privateKeyBigInteger);
        System.out.println("windowNaf: " + Arrays.toString(windowNaf)); // may help to debug OpenCL w-NAF
        
        System.err.println("expectedPublicKeyBytes: " + Arrays.toString(expectedPublicKeyBytes));
        System.out.println("dst_r: " + Arrays.toString(dst_r));
        System.out.println("dst_r_AsByteArray: " + Arrays.toString(dst_r_AsByteArray));
        System.out.println("resultOpenCLPubKey: " + Arrays.toString(resultOpenCLPubKey));
        System.out.println("resultOpenCLPubKeyHash: " + Arrays.toString(resultOpenCLPubKeyHash));
        System.out.println("resultOpenCLPubKeyHashBase58: " + resultOpenCLPubKeyHashBase58);
        
        assertThat(resultOpenCLPubKey, is(equalTo(expectedPublicKeyBytes)));
        assertThat(resultOpenCLPubKeyHashBase58, is(equalTo(staticKey.publicKeyCompressed)));
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


}
