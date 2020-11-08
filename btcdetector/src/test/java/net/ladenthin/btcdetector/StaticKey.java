package net.ladenthin.btcdetector;

import java.nio.ByteBuffer;

/**
 * Static strings from a random generated address https://www.bitaddress.org
 */
public class StaticKey {

    final public String privateKeyHex = "68E23530DEB6D5011AB56D8AD9F7B4A3B424F1112F08606357497495929F72DC";
    final public String privateKeyWiFUncompressed = "5JcUh9ET11ZZHnEhSvzEUCg3opTa9WCmsGuCFYGQGhBzKJpgJ39";
    final public String privateKeyWiFCompressed = "KzjbEBLMm3UhX4fTXTHcT4XMPeUHJXty2uBNfAzyiGPVynPeFMeV";

    final public String publicKeyUncompressedHex = "045d99d81d9e731e0d7eebd1c858b1155da7981b1f0a16d322a361f8b589ad2e3bde53dc614e3a84164dab3f5899abde3b09553dca10c9716fa623a5942b9ea420";
    final public String publicKeyCompressedHex = "025d99d81d9e731e0d7eebd1c858b1155da7981b1f0a16d322a361f8b589ad2e3b";
    
    final public String publicKeyUncompressedHash160Hex = "024336956610316605d1051cb9b8e88f82b70b29";
    final public String publicKeyCompressedHash160Hex = "892852a28710e156b07fa7933edd5490cbbcfa4f";
    
    final public String publicKeyUncompressed = "1CxsSWgsWNxoqS1XB5QgchtMpWrzzPCES";
    final public String publicKeyCompressed = "1DWDsxY3mvzjPLHD67nRq15M8vs6VLZaqV";
    
    final public ByteBuffer byteBufferPublicKeyUncompressed = new ByteBufferUtility(false).getByteBufferFromHex(publicKeyUncompressedHash160Hex);
    final public ByteBuffer byteBufferPublicKeyCompressed = new ByteBufferUtility(false).getByteBufferFromHex(publicKeyCompressedHash160Hex);

}
