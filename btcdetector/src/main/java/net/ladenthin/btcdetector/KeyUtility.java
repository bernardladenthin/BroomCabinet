package net.ladenthin.btcdetector;

import java.math.BigInteger;
import java.nio.ByteBuffer;
import java.util.Arrays;
import java.util.Random;
import javax.annotation.Nullable;
import org.bitcoinj.core.ECKey;
import org.bitcoinj.core.LegacyAddress;
import org.bitcoinj.core.NetworkParameters;
import org.bouncycastle.util.encoders.Hex;

/**
 * https://stackoverflow.com/questions/5399798/byte-array-and-int-conversion-in-java/11419863
 * https://stackoverflow.com/questions/21087651/how-to-efficiently-change-endianess-of-byte-array-in-java
 * @author Bernard
 */
public class KeyUtility {

    @Nullable
    private final NetworkParameters networkParameters;
    private final ByteBufferUtility byteBufferUtility;

    public static final int BIT_LENGTH = 256;

    public KeyUtility(NetworkParameters networkParameters, ByteBufferUtility byteBufferUtility) {
        this.networkParameters = networkParameters;
        this.byteBufferUtility = byteBufferUtility;
    }

    /**
     * Require networkParameters.
     */
    public ByteBuffer getHash160ByteBufferFromBase58String(String base58) {
        LegacyAddress address = LegacyAddress.fromBase58(networkParameters, base58);
        byte[] hash160 = address.getHash160();
        return byteBufferUtility.byteArrayToByteBuffer(hash160);
    }

    public String toBase58(byte[] hash160) {
        LegacyAddress address = LegacyAddress.fromPubKeyHash(networkParameters, hash160);
        return address.toBase58();
    }

    public BigInteger createSecret(int maximumBitLength, Random random) {
        BigInteger secret = new BigInteger(maximumBitLength, random);
        return secret;
    }

    public ECKey createECKey(BigInteger bi, boolean compressed) {
        return ECKey.fromPrivate(bi, compressed);
    }

    public String createKeyDetails(ECKey key) {
        ByteBufferUtility byteBufferUtility = new ByteBufferUtility(false);

        BigInteger privateKeyBigInteger = key.getPrivKey();
        byte[] privateKeyBytes = key.getPrivKeyBytes();
        String privateKeyHex = key.getPrivateKeyAsHex();
        String privateKeyAsWiF = key.getPrivateKeyAsWiF(networkParameters);

        byte[] hash160 = key.getPubKeyHash();
        ByteBuffer hash160AsByteBuffer = byteBufferUtility.byteArrayToByteBuffer(hash160);
        String publicKeyHash160Hex = Hex.toHexString(hash160);
        String publicKeyHash160Base58 = new KeyUtility(networkParameters, byteBufferUtility).toBase58(hash160);

        String logprivateKeyBigInteger = "privateKeyBigInteger: [" + privateKeyBigInteger + "]";
        String logprivateKeyBytes = "privateKeyBytes: [" + Arrays.toString(privateKeyBytes) + "]";
        String logprivateKeyHex = "privateKeyHex: [" + privateKeyHex + "]";
        String logWiF = "WiF: [" + privateKeyAsWiF + "]";
        String logPublicKeyAsHex = "publicKeyAsHex: [" + key.getPublicKeyAsHex() + "]";
        String logPublicKeyHash160 = "publicKeyHash160Hex: [" + publicKeyHash160Hex + "]";
        String logPublicKeyHash160Base58 = "publicKeyHash160Base58: [" + publicKeyHash160Base58 + "]";
        String logCompressed = "Compressed: [" + key.isCompressed() + "]";

        String space = " ";
        return logprivateKeyBigInteger + space + logprivateKeyBytes + space + logprivateKeyHex + space + logWiF + space + logPublicKeyAsHex + space + logPublicKeyHash160 + space + logPublicKeyHash160Base58 + space + logCompressed;
    }

    // <editor-fold defaultstate="collapsed" desc="ByteBuffer LegacyAddress conversion">
    public ByteBuffer addressToByteBuffer(LegacyAddress address) {
        ByteBuffer byteBuffer = byteBufferUtility.byteArrayToByteBuffer(address.getHash160());
        return byteBuffer;
    }

    /**
     * Require networkParameters.
     */
    public LegacyAddress byteBufferToAddress(ByteBuffer byteBuffer) {
        return new LegacyAddress(networkParameters, byteBufferUtility.byteBufferToBytes(byteBuffer));
    }
    // </editor-fold>

    public static int[] privateKeyIntsFromByteArray(byte[] b) {
        int[] intArray = new int[8];
        byteArrayToIntArray(b, 0, intArray, 0);
        byteArrayToIntArray(b, 4, intArray, 1);
        byteArrayToIntArray(b, 8, intArray, 2);
        byteArrayToIntArray(b, 12, intArray, 3);
        byteArrayToIntArray(b, 16, intArray, 4);
        byteArrayToIntArray(b, 20, intArray, 5);
        byteArrayToIntArray(b, 24, intArray, 6);
        byteArrayToIntArray(b, 28, intArray, 7);
        return intArray;
    }

    public static byte[] publicKeyByteArrayFromIntArray(int[] i) {
        // we need: 1 + 32 bytes
        byte[] b = new byte[33];
        // extraxt the last int and move to the right position, only one byte is needed
        // this prevent an allocation of 36 bytes and got a slice of 33 afterwards
        intToByteArray(i[8], b, 0);
        b[32] = b[0];

        intToByteArray(i[0], b, 0);
        intToByteArray(i[1], b, 4);
        intToByteArray(i[2], b, 8);
        intToByteArray(i[3], b, 12);
        intToByteArray(i[4], b, 16);
        intToByteArray(i[5], b, 20);
        intToByteArray(i[6], b, 24);
        intToByteArray(i[7], b, 28);
        return b;
    }

    public static int byteArrayToInt(byte[] b) {
        return b[3] & 0xFF
                | (b[2] & 0xFF) << 8
                | (b[1] & 0xFF) << 16
                | (b[0] & 0xFF) << 24;
    }

    public static int byteArrayToInt(byte[] b, int offsetByteArray) {
        return b[3 + offsetByteArray] & 0xFF
                | (b[2 + offsetByteArray] & 0xFF) << 8
                | (b[1 + offsetByteArray] & 0xFF) << 16
                | (b[0 + offsetByteArray] & 0xFF) << 24;
    }

    public static void byteArrayToIntArray(byte[] b, int offsetByteArray, int[] i, int offsetIntArray) {
        int newInt = b[3 + offsetByteArray] & 0xFF
                | (b[2 + offsetByteArray] & 0xFF) << 8
                | (b[1 + offsetByteArray] & 0xFF) << 16
                | (b[0 + offsetByteArray] & 0xFF) << 24;
        i[offsetIntArray] = newInt;
    }

    public static byte[] intToByteArray(int a) {
        return new byte[]{
            (byte) ((a >> 24) & 0xFF),
            (byte) ((a >> 16) & 0xFF),
            (byte) ((a >> 8) & 0xFF),
            (byte) (a & 0xFF)
        };
    }

    public static void intToByteArray(int a, byte[] b, int offset) {

        b[0 + offset] = (byte) ((a >> 24) & 0xFF);
        b[1 + offset] = (byte) ((a >> 16) & 0xFF);
        b[2 + offset] = (byte) ((a >> 8) & 0xFF);
        b[3 + offset] = (byte) (a & 0xFF);

    }

    public static void swapIntBytes(byte[] bytes) {
        assert bytes.length % 4 == 0;
        for (int i = 0; i < bytes.length; i += 4) {
            // swap 0 and 3
            byte tmp = bytes[i];
            bytes[i] = bytes[i + 3];
            bytes[i + 3] = tmp;
            // swap 1 and 2
            byte tmp2 = bytes[i + 1];
            bytes[i + 1] = bytes[i + 2];
            bytes[i + 2] = tmp2;
        }
    }

}