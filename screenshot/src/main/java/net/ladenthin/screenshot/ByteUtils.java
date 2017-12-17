package net.ladenthin.screenshot;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.IntBuffer;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.logging.Level;
import java.util.logging.Logger;
import java.util.zip.*;

public class ByteUtils {
    private static final Logger logger = Logger.getLogger(ByteUtils.class.getName());

    @Deprecated
    public static byte[] decompressGZIP(byte[] contentBytes){
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buffer = new byte[1024];
        try{

            GZIPInputStream gzis = new GZIPInputStream(new ByteArrayInputStream(contentBytes));

            int len;
            while ((len = gzis.read(buffer)) > 0) {
                out.write(buffer, 0, len);
            }

            gzis.close();
            out.close();
        } catch(IOException e){
            throw new RuntimeException(e);
        }
        return out.toByteArray();
    }

    public static byte[] compressDeflate(byte[] data) throws IOException {
        Deflater deflater = new Deflater();
        deflater.setInput(data);

        ByteArrayOutputStream outputStream = new ByteArrayOutputStream(data.length);

        deflater.finish();
        byte[] buffer = new byte[1024];
        while (!deflater.finished()) {
            int count = deflater.deflate(buffer); // returns the generated code... index
            outputStream.write(buffer, 0, count);
        }
        outputStream.close();
        byte[] output = outputStream.toByteArray();

        deflater.end();

        if (logger.isLoggable(Level.FINEST)) {
            logger.finest("");
            logger.finest("#compressDeflate");
            logger.finest("Original:   " + data.length / 1024 + " Kb");
            logger.finest("Compressed: " + output.length / 1024 + " Kb");
            logger.finest("Ratio:      " + (1.0f * data.length / output.length));
        }
        return output;
    }

    public static byte[] decompressDeflate(byte[] data) throws IOException, DataFormatException {
        Inflater inflater = new Inflater();
        inflater.setInput(data);

        ByteArrayOutputStream outputStream = new ByteArrayOutputStream(data.length);
        byte[] buffer = new byte[1024];
        while (!inflater.finished()) {
            int count = inflater.inflate(buffer);
            outputStream.write(buffer, 0, count);
        }
        outputStream.close();
        byte[] output = outputStream.toByteArray();

        inflater.end();

        return output;
    }

    @Deprecated
    public static byte[] compressGZIP(byte[] data){
        ByteArrayOutputStream byteArrayOutputStream = new ByteArrayOutputStream();
        try{
            /*
            GZIPOutputStream gzipOutputStream = new GZIPOutputStream(byteArrayOutputStream) {
                {
                    this.def.setLevel(Deflater.BEST_COMPRESSION);
                }
            };
            */
            GZIPOutputStream gzipOutputStream = new GZIPOutputStream(byteArrayOutputStream);
            gzipOutputStream.write(data);
            gzipOutputStream.close();
        } catch(IOException e){
            throw new RuntimeException(e);
        }


        byte[] output = byteArrayOutputStream.toByteArray();

        if (logger.isLoggable(Level.FINEST)) {
            logger.finest("");
            logger.finest("#compressGZIP");
            logger.finest("Original:   " + data.length / 1024 + " Kb");
            logger.finest("Compressed: " + output.length / 1024 + " Kb");
            logger.finest("Ratio:      " + (1.0f * data.length / output.length));
        }

        return output;
    }

    // http://stackoverflow.com/questions/14574933/need-help-understanding-int-array-to-byte-array-method-and-little-big-endian-won
    public static byte[] intToByte(int[] input){
        ByteBuffer byteBuffer = ByteBuffer.allocate(input.length * 4);
        IntBuffer intBuffer = byteBuffer.asIntBuffer();
        intBuffer.put(input);
        byte[] array = byteBuffer.array();
        return array;
    }

    // http://stackoverflow.com/questions/14574933/need-help-understanding-int-array-to-byte-array-method-and-little-big-endian-won
    public static int[] byteToInt(byte[] input){
        IntBuffer intBuf = ByteBuffer.wrap(input).order(ByteOrder.BIG_ENDIAN).asIntBuffer();
        int[] array = new int[intBuf.remaining()];
        intBuf.get(array);
        return array;
    }

    public static byte[] getSha256(byte[] raw, byte[] salt) {
        MessageDigest md = null;
        try {
            md = MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException e) {
            throw new RuntimeException(e);
        }
        md.reset();
        md.update(salt);
        return md.digest(raw);
    }

    public static String getSha256String(byte[] raw, byte[] salt) {
        return bytesToHex(getSha256(raw, salt));
    }

    final protected static char[] hexArray = "0123456789ABCDEF".toCharArray();

    // http://stackoverflow.com/questions/9655181/how-to-convert-a-byte-array-to-a-hex-string-in-java
    public static String bytesToHex(byte[] bytes) {
        char[] hexChars = new char[bytes.length * 2];
        for ( int j = 0; j < bytes.length; j++ ) {
            int v = bytes[j] & 0xFF;
            hexChars[j * 2] = hexArray[v >>> 4];
            hexChars[j * 2 + 1] = hexArray[v & 0x0F];
        }
        return new String(hexChars);
    }

    public static short[] bytesToShorts(byte[] bytes) {
        short[] shorts = new short[bytes.length / 2];
        // to turn bytes to shorts as either big endian or little endian.
        ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer().get(shorts);
        return shorts;
    }

    public static byte[] shortsToBytes(short[] value) {
        // to turn shorts back to bytes.
        byte[] bytes = new byte[value.length * 2];
        ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer().put(value);
        return bytes;
    }


}