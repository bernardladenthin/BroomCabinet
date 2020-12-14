package net.ladenthin.btcdetector;

import java.io.IOException;
import org.junit.Before;
import org.junit.Test;
import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.*;

public class AddressToCoinTest {

    private static final TestAddresses testAddresses = new TestAddresses(0, false);

    StaticKey staticKey = new StaticKey();

    KeyUtility keyUtility = new KeyUtility(testAddresses.networkParameters, new ByteBufferUtility(false));

    @Before
    public void init() throws IOException {
    }

    @Test
    public void fromBase58CSVLine_TestUncompressed() throws IOException {
        // act
        AddressToCoin addressToCoin = AddressToCoin.fromBase58CSVLine(staticKey.publicKeyUncompressed, keyUtility);

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
    public void fromBase58CSVLine_addressStartsWithbc1_returnPublicKeyHash() throws IOException {
        // act
        StaticSegwitAddress staticSegwitAddress = new StaticSegwitAddress();
        AddressToCoin addressToCoin = AddressToCoin.fromBase58CSVLine(staticSegwitAddress.publicAddress, keyUtility);

        // assert
        assertThat(addressToCoin.getHash160(), is(equalTo(staticSegwitAddress.byteBuffer_publicKeyHash)));
    }

    @Test
    public void fromBase58CSVLine_addressStartsWith7_returnNull() throws IOException {
        // act
        StaticDashP2SHAddress staticDashP2SHAddress = new StaticDashP2SHAddress();
        AddressToCoin addressToCoin = AddressToCoin.fromBase58CSVLine(staticDashP2SHAddress.publicAddress, keyUtility);

        // assert
        assertThat(addressToCoin, is(nullValue()));
    }

    @Test
    public void fromBase58CSVLine_addressStartsWithX_returnPublicKeyHash() throws IOException {
        // act
        StaticDashP2PKHAddress staticDashP2PKHAddress = new StaticDashP2PKHAddress();
        AddressToCoin addressToCoin = AddressToCoin.fromBase58CSVLine(staticDashP2PKHAddress.publicAddress, keyUtility);

        // assert
        assertThat(addressToCoin.getHash160(), is(equalTo(staticDashP2PKHAddress.byteBuffer_publicKeyHash)));
    }

    @Test
    public void fromBase58CSVLine_addressStartsWithA_returnNull() throws IOException {
        // act
        StaticDogecoinP2SHAddress staticDogecoinP2SHAddress = new StaticDogecoinP2SHAddress();
        AddressToCoin addressToCoin = AddressToCoin.fromBase58CSVLine(staticDogecoinP2SHAddress.publicAddress, keyUtility);

        // assert
        assertThat(addressToCoin, is(nullValue()));
    }

    @Test
    public void fromBase58CSVLine_addressStartsWithD_returnPublicKeyHash() throws IOException {
        // act
        StaticDogecoinP2PKHAddress staticDogecoinP2PKHAddress = new StaticDogecoinP2PKHAddress();
        AddressToCoin addressToCoin = AddressToCoin.fromBase58CSVLine(staticDogecoinP2PKHAddress.publicAddress, keyUtility);

        // assert
        assertThat(addressToCoin.getHash160(), is(equalTo(staticDogecoinP2PKHAddress.byteBuffer_publicKeyHash)));
    }

    @Test
    public void fromBase58CSVLine_addressStartsWithM_returnNull() throws IOException {
        // act
        StaticLitecoinP2SHAddress staticLitecoinP2SHAddress = new StaticLitecoinP2SHAddress();
        AddressToCoin addressToCoin = AddressToCoin.fromBase58CSVLine(staticLitecoinP2SHAddress.publicAddress, keyUtility);

        // assert
        assertThat(addressToCoin, is(nullValue()));
    }

    @Test
    public void fromBase58CSVLine_addressStartsWithL_returnPublicKeyHash() throws IOException {
        // act
        StaticLitecoinP2PKHAddress staticLitecoinP2PKHAddress = new StaticLitecoinP2PKHAddress();
        AddressToCoin addressToCoin = AddressToCoin.fromBase58CSVLine(staticLitecoinP2PKHAddress.publicAddress, keyUtility);

        // assert
        assertThat(addressToCoin.getHash160(), is(equalTo(staticLitecoinP2PKHAddress.byteBuffer_publicKeyHash)));
    }

    @Test
    public void fromBase58CSVLine_addressStartsWithp_returnNull() throws IOException {
        // act
        StaticBitcoinCashP2SHAddress staticBitcoinCashP2SHAddress = new StaticBitcoinCashP2SHAddress();
        AddressToCoin addressToCoin = AddressToCoin.fromBase58CSVLine(staticBitcoinCashP2SHAddress.publicAddress, keyUtility);

        // assert
        assertThat(addressToCoin, is(nullValue()));
    }

    @Test
    public void fromBase58CSVLine_addressStartsWithq_returnPublicKeyHash() throws IOException {
        // act
        StaticBitcoinCashP2PKHAddress staticBitcoinCashP2PKHAddress = new StaticBitcoinCashP2PKHAddress();
        AddressToCoin addressToCoin = AddressToCoin.fromBase58CSVLine(staticBitcoinCashP2PKHAddress.publicAddress, keyUtility);

        // assert
        assertThat(addressToCoin.getHash160(), is(equalTo(staticBitcoinCashP2PKHAddress.byteBuffer_publicKeyHash)));
    }

}
