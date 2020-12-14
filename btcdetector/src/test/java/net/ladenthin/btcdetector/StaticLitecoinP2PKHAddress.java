package net.ladenthin.btcdetector;

import java.nio.ByteBuffer;

/**
 * https://privatekeys.pw/litecoin/address/LQTpS3VaYTjCr4s9Y1t5zbeY26zevf7Fb3
 */
public class StaticLitecoinP2PKHAddress {

    final public String publicAddress = "LQTpS3VaYTjCr4s9Y1t5zbeY26zevf7Fb3";
    final public String publicKeyHash = "3977ea726e43b1db5c1f3ddd634d56ade26eb0a2";
    
    final public ByteBuffer byteBuffer_publicKeyHash = new ByteBufferUtility(false).getByteBufferFromHex(publicKeyHash);
}
