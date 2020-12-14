package net.ladenthin.btcdetector;

import java.nio.ByteBuffer;

/**
 * https://privatekeys.pw/bitcoin/address/bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq
 */
public class StaticSegwitAddress {

    final public String publicAddress = "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq";
    final public String publicKeyHash = "e8df018c7e326cc253faac7e46cdc51e68542c42";
    
    final public ByteBuffer byteBuffer_publicKeyHash = new ByteBufferUtility(false).getByteBufferFromHex(publicKeyHash);
}
