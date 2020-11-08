package net.ladenthin.btcdetector;

import java.io.IOException;
import java.nio.ByteBuffer;
import org.junit.Before;
import org.junit.Test;
import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.*;

public class AddressFileTest {

    private static final TestAddresses testAddresses = new TestAddresses(0, false);

    StaticKey staticKey = new StaticKey();
    
    
    KeyUtility keyUtility =     new KeyUtility(testAddresses.networkParameters, new ByteBufferUtility(false));

    @Before
    public void init() throws IOException {
    }

    @Test
    public void fromBase58CSVLine_TestUncompressed() throws IOException {
        // act
        AddressToCoin addressToCoin = AddressToCoin.fromBase58CSVLine(staticKey.publicKeyUncompressed,keyUtility );

        // assert
        assertThat(addressToCoin.getHash160(), is(equalTo(staticKey.byteBufferPublicKeyUncompressed)));
    }

    @Test
    public void fromBase58CSVLine_TestCompressed() throws IOException {
        // act
        AddressToCoin addressToCoin = AddressToCoin.fromBase58CSVLine(staticKey.publicKeyCompressed, keyUtility);

        // assert
        assertThat(addressToCoin.getHash160(), is(equalTo(staticKey.byteBufferPublicKeyCompressed)));
    }

    @Test
    public void fromBase58CSVLine_addressLineIsEmpty_returnNull() throws IOException {
        // act
        AddressToCoin addressToCoin = AddressToCoin.fromBase58CSVLine("", keyUtility);

        // assert
        assertThat(addressToCoin, is(nullValue()));
    }

    @Test
    public void fromBase58CSVLine_addressLineStartsWithIgnoreLineSign_returnNull() throws IOException {
        // act
        AddressToCoin addressToCoin = AddressToCoin.fromBase58CSVLine(AddressFile.IGNORE_LINE_PREFIX + " test", keyUtility);

        // assert
        assertThat(addressToCoin, is(nullValue()));
    }

    @Test
    public void fromBase58CSVLine_addressStartsWithbc1_returnNull() throws IOException {
        // act
        AddressToCoin addressToCoin = AddressToCoin.fromBase58CSVLine(TestAddresses.SEGWIT_PUBLIC_ADDRESS, keyUtility);

        // assert
        assertThat(addressToCoin, is(nullValue()));
    }

}
