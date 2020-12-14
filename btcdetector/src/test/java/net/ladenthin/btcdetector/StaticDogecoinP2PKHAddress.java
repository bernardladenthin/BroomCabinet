package net.ladenthin.btcdetector;

import java.nio.ByteBuffer;

/**
 * https://privatekeys.pw/dogecoin/address/DH5yaieqoZN36fDVciNyRueRGvGLR3mr7L
 */
public class StaticDogecoinP2PKHAddress {

    final public String publicAddress = "DH5yaieqoZN36fDVciNyRueRGvGLR3mr7L";
    final public String publicKeyHash = "830a7420e63d76244ff7cbd1c248e94c14463259";
    
    final public ByteBuffer byteBuffer_publicKeyHash = new ByteBufferUtility(false).getByteBufferFromHex(publicKeyHash);
}
