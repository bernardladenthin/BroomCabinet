package net.ladenthin.btcdetector;

import java.nio.ByteBuffer;

/**
 * https://privatekeys.pw/bitcoin-cash/address/qz7xc0vl85nck65ffrsx5wvewjznp9lflgktxc5878
 */
public class StaticBitcoinCashP2PKHAddress {

    final public String publicAddress = "qz7xc0vl85nck65ffrsx5wvewjznp9lflgktxc5878";
    final public String publicKeyHash = "bc6c3d9f3d278b6a8948e06a399974853097e9fa";
    
    final public ByteBuffer byteBuffer_publicKeyHash = new ByteBufferUtility(false).getByteBufferFromHex(publicKeyHash);
}
