package net.ladenthin.btcdetector;

import java.nio.ByteBuffer;

/**
 * https://privatekeys.pw/dash/address/XdAUmwtig27HBG6WfYyHAzP8n6XC9jESEw
 */
public class StaticDashP2PKHAddress {

    final public String publicAddress = "XdAUmwtig27HBG6WfYyHAzP8n6XC9jESEw";
    final public String publicKeyHash = "1b2a522cc8d42b0be7ceb8db711416794d50c846";
    
    final public ByteBuffer byteBuffer_publicKeyHash = new ByteBufferUtility(false).getByteBufferFromHex(publicKeyHash);
}
