package net.ladenthin.btcdetector;

import java.math.BigInteger;
import java.nio.ByteBuffer;
import java.util.Random;
import javax.annotation.Nullable;
import org.bitcoinj.core.Base58;
import org.bitcoinj.core.ECKey;
import org.bitcoinj.core.LegacyAddress;
import org.bitcoinj.core.NetworkParameters;
import org.bouncycastle.util.encoders.Hex;

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

    public BigInteger createSecret(Random random) {
        BigInteger secret = new BigInteger(KeyUtility.BIT_LENGTH, random);
        return secret;
    }
    
    public ECKey createECKey(BigInteger bi, boolean compressed) {
        return ECKey.fromPrivate(bi, compressed);
    }
    

    public String createKeyDetails( ECKey key) {
        ByteBufferUtility byteBufferUtility = new ByteBufferUtility(false);

        String privateKeyAsWiF = key.getPrivateKeyAsWiF(networkParameters);

        byte[] hash160 = key.getPubKeyHash();
        ByteBuffer hash160AsByteBuffer = byteBufferUtility.byteArrayToByteBuffer(hash160);
        String publicKeyHash160Hex = Hex.toHexString(hash160);
        String publicKeyHash160Base58 = new KeyUtility(networkParameters, byteBufferUtility).toBase58(hash160);

        String logWiF = "WiF: [" + privateKeyAsWiF + "]";
        String logPublicKeyAsHex = " publicKeyAsHex: [" + key.getPublicKeyAsHex() + "]";
        String logPublicKeyHash160 = " publicKeyHash160Hex: [" + publicKeyHash160Hex + "]";
        String logPublicKeyHash160Base58 = " publicKeyHash160Base58: [" + publicKeyHash160Base58 + "]";
        String logCompressed = " Compressed: [" + key.isCompressed() + "]";
        return logWiF + logPublicKeyAsHex + logPublicKeyHash160 + logPublicKeyHash160Base58 + logCompressed;
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

}
