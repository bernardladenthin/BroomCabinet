// @formatter:off
/**
 * Copyright 2020 Bernard Ladenthin bernard.ladenthin@gmail.com
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *    http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 */
// @formatter:on
package net.ladenthin.btcdetector;

import java.io.IOException;
import net.ladenthin.btcdetector.staticaddresses.*;
import net.ladenthin.btcdetector.staticaddresses.StaticKey;
import net.ladenthin.btcdetector.staticaddresses.TestAddresses;
import org.bitcoinj.core.Coin;
import org.junit.Before;
import org.junit.Test;
import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.*;

public class AddressTxtLineTest {

    private static final TestAddresses testAddresses = new TestAddresses(0, false);

    StaticKey staticKey = new StaticKey();

    KeyUtility keyUtility = new KeyUtility(testAddresses.networkParameters, new ByteBufferUtility(false));

    @Before
    public void init() throws IOException {
    }
    
    private void assertThatDefaultCoinIsSet(AddressToCoin addressToCoin) {
        assertThat(addressToCoin.getCoin(), is(equalTo(AddressTxtLine.DEFAULT_COIN)));
    }

    @Test
    public void fromLine_addressLineIsEmpty_returnNull() throws IOException {
        // act
        AddressToCoin addressToCoin = new AddressTxtLine().fromLine("", keyUtility);

        // assert
        assertThat(addressToCoin, is(nullValue()));
    }

    @Test
    public void fromLine_addressLineStartsWithIgnoreLineSign_returnNull() throws IOException {
        // act
        AddressToCoin addressToCoin = new AddressTxtLine().fromLine(AddressTxtLine.IGNORE_LINE_PREFIX + " test", keyUtility);

        // assert
        assertThat(addressToCoin, is(nullValue()));
    }

    @Test
    public void fromLine_uncompressedBitcoinAddressGiven_ReturnHash160AndDefaultCoin() throws IOException {
        // act
        AddressToCoin addressToCoin = new AddressTxtLine().fromLine(staticKey.publicKeyUncompressed, keyUtility);

        // assert
        assertThat(addressToCoin.getHash160(), is(equalTo(staticKey.byteBufferPublicKeyUncompressed)));
        assertThatDefaultCoinIsSet(addressToCoin);
    }

    @Test
    public void fromLine_compressedBitcoinAddressGiven_ReturnHash160AndDefaultCoin() throws IOException {
        // act
        AddressToCoin addressToCoin = new AddressTxtLine().fromLine(staticKey.publicKeyCompressed, keyUtility);

        // assert
        assertThat(addressToCoin.getHash160(), is(equalTo(staticKey.byteBufferPublicKeyCompressed)));
        assertThatDefaultCoinIsSet(addressToCoin);
    }

    @Test
    public void fromLine_uncompressedBitcoinAddressGivenWithValidAmount_ReturnHash160AndDefaultCoin() throws IOException {
        // arrange
        String coin = "123987";
        // act
        AddressToCoin addressToCoin = new AddressTxtLine().fromLine(staticKey.publicKeyUncompressed + AddressTxtLine.SEPARATOR + coin, keyUtility);

        // assert
        assertThat(addressToCoin.getHash160(), is(equalTo(staticKey.byteBufferPublicKeyUncompressed)));
        assertThat(addressToCoin.getCoin(), is(equalTo(Coin.valueOf(Long.valueOf(coin)))));
    }

    @Test
    public void fromLine_uncompressedBitcoinAddressGivenWithInvalidAmount_ReturnHash160AndDefaultCoin() throws IOException {
        // act
        AddressToCoin addressToCoin = new AddressTxtLine().fromLine(staticKey.publicKeyUncompressed + AddressTxtLine.SEPARATOR + "XYZ", keyUtility);

        // assert
        assertThat(addressToCoin.getHash160(), is(equalTo(staticKey.byteBufferPublicKeyUncompressed)));
        assertThatDefaultCoinIsSet(addressToCoin);
    }

    @Test
    public void fromLine_addressLineStartsWithAddressHeader_returnNull() throws IOException {
        // act
        AddressToCoin addressToCoin = new AddressTxtLine().fromLine(AddressTxtLine.ADDRESS_HEADER, keyUtility);

        // assert
        assertThat(addressToCoin, is(nullValue()));
    }

    @Test
    public void fromLine_StaticBitcoinP2WPKHAddress_returnPublicKeyHash() throws IOException {
        // act
        StaticBitcoinP2WPKHAddress staticBitcoinP2WPKHAddress = new StaticBitcoinP2WPKHAddress();
        AddressToCoin addressToCoin = new AddressTxtLine().fromLine(staticBitcoinP2WPKHAddress.publicAddress, keyUtility);

        // assert
        assertThat(addressToCoin.getHash160(), is(equalTo(staticBitcoinP2WPKHAddress.byteBuffer_publicKeyHash)));
        assertThatDefaultCoinIsSet(addressToCoin);
    }

    @Test
    public void fromLine_StaticBitcoinP2WSHAddress_returnPublicKeyHash() throws IOException {
        // act
        StaticBitcoinP2WSHAddress staticBitcoinP2WSHAddress = new StaticBitcoinP2WSHAddress();
        AddressToCoin addressToCoin = new AddressTxtLine().fromLine(staticBitcoinP2WSHAddress.publicAddress, keyUtility);

        // assert
        assertThat(addressToCoin, is(nullValue()));
    }

    @Test
    public void fromLine_StaticDashP2SHAddress_returnNull() throws IOException {
        // act
        StaticDashP2SHAddress staticDashP2SHAddress = new StaticDashP2SHAddress();
        AddressToCoin addressToCoin = new AddressTxtLine().fromLine(staticDashP2SHAddress.publicAddress, keyUtility);

        // assert
        assertThat(addressToCoin, is(nullValue()));
    }

    @Test
    public void fromLine_StaticDashP2PKHAddress_returnPublicKeyHash() throws IOException {
        // act
        StaticDashP2PKHAddress staticDashP2PKHAddress = new StaticDashP2PKHAddress();
        AddressToCoin addressToCoin = new AddressTxtLine().fromLine(staticDashP2PKHAddress.publicAddress, keyUtility);

        // assert
        assertThat(addressToCoin.getHash160(), is(equalTo(staticDashP2PKHAddress.byteBuffer_publicKeyHash)));
        assertThatDefaultCoinIsSet(addressToCoin);
    }

    @Test
    public void fromLine_StaticDogecoinP2SHAddress_returnNull() throws IOException {
        // act
        StaticDogecoinP2SHAddress staticDogecoinP2SHAddress = new StaticDogecoinP2SHAddress();
        AddressToCoin addressToCoin = new AddressTxtLine().fromLine(staticDogecoinP2SHAddress.publicAddress, keyUtility);

        // assert
        assertThat(addressToCoin, is(nullValue()));
    }

    @Test
    public void fromLine_StaticDogecoinP2SHXAddress_returnNull() throws IOException {
        // act
        StaticDogecoinP2SHXAddress staticDogecoinP2SHXAddress = new StaticDogecoinP2SHXAddress();
        AddressToCoin addressToCoin = new AddressTxtLine().fromLine(staticDogecoinP2SHXAddress.publicAddress, keyUtility);

        // assert
        assertThat(addressToCoin, is(nullValue()));
    }

    @Test
    public void fromLine_StaticDogecoinP2PKHAddress_returnPublicKeyHash() throws IOException {
        // act
        StaticDogecoinP2PKHAddress staticDogecoinP2PKHAddress = new StaticDogecoinP2PKHAddress();
        AddressToCoin addressToCoin = new AddressTxtLine().fromLine(staticDogecoinP2PKHAddress.publicAddress, keyUtility);

        // assert
        assertThat(addressToCoin.getHash160(), is(equalTo(staticDogecoinP2PKHAddress.byteBuffer_publicKeyHash)));
        assertThatDefaultCoinIsSet(addressToCoin);
    }

    @Test
    public void fromLine_StaticLitecoinP2SHAddress_returnNull() throws IOException {
        // act
        StaticLitecoinP2SHAddress staticLitecoinP2SHAddress = new StaticLitecoinP2SHAddress();
        AddressToCoin addressToCoin = new AddressTxtLine().fromLine(staticLitecoinP2SHAddress.publicAddress, keyUtility);

        // assert
        assertThat(addressToCoin, is(nullValue()));
    }

    @Test
    public void fromLine_StaticLitecoinP2PKHAddress_returnPublicKeyHash() throws IOException {
        // act
        StaticLitecoinP2PKHAddress staticLitecoinP2PKHAddress = new StaticLitecoinP2PKHAddress();
        AddressToCoin addressToCoin = new AddressTxtLine().fromLine(staticLitecoinP2PKHAddress.publicAddress, keyUtility);

        // assert
        assertThat(addressToCoin.getHash160(), is(equalTo(staticLitecoinP2PKHAddress.byteBuffer_publicKeyHash)));
        assertThatDefaultCoinIsSet(addressToCoin);
    }

    @Test
    public void fromLine_StaticBitcoinCashP2SHAddress_returnNull() throws IOException {
        // act
        StaticBitcoinCashP2SHAddress staticBitcoinCashP2SHAddress = new StaticBitcoinCashP2SHAddress();
        AddressToCoin addressToCoin = new AddressTxtLine().fromLine(staticBitcoinCashP2SHAddress.publicAddress, keyUtility);

        // assert
        assertThat(addressToCoin, is(nullValue()));
    }

    @Test
    public void fromLine_StaticBitcoinCashP2PKHAddress_returnPublicKeyHash() throws IOException {
        // act
        StaticBitcoinCashP2PKHAddress staticBitcoinCashP2PKHAddress = new StaticBitcoinCashP2PKHAddress();
        AddressToCoin addressToCoin = new AddressTxtLine().fromLine(staticBitcoinCashP2PKHAddress.publicAddress, keyUtility);

        // assert
        assertThat(addressToCoin.getHash160(), is(equalTo(staticBitcoinCashP2PKHAddress.byteBuffer_publicKeyHash)));
        assertThatDefaultCoinIsSet(addressToCoin);
    }

    @Test
    public void fromLine_StaticBitcoinP2MSAddress_returnPublicKeyHash() throws IOException {
        // act
        StaticBitcoinP2MSAddress staticBitcoinP2MSAddress = new StaticBitcoinP2MSAddress();
        AddressToCoin addressToCoin = new AddressTxtLine().fromLine(staticBitcoinP2MSAddress.publicAddress, keyUtility);

        // assert
        assertThat(addressToCoin, is(nullValue()));
    }

    @Test
    public void fromLine_StaticBitcoinCashP2MSAddress_returnPublicKeyHash() throws IOException {
        // act
        StaticBitcoinCashP2MSAddress staticBitcoinCashP2MSAddress = new StaticBitcoinCashP2MSAddress();
        AddressToCoin addressToCoin = new AddressTxtLine().fromLine(staticBitcoinCashP2MSAddress.publicAddress, keyUtility);

        // assert
        assertThat(addressToCoin, is(nullValue()));
    }

    @Test
    public void fromLine_StaticBitcoinCashP2MSXAddress_returnPublicKeyHash() throws IOException {
        // act
        StaticBitcoinCashP2MSXAddress staticBitcoinCashP2MSXAddress = new StaticBitcoinCashP2MSXAddress();
        AddressToCoin addressToCoin = new AddressTxtLine().fromLine(staticBitcoinCashP2MSXAddress.publicAddress, keyUtility);

        // assert
        assertThat(addressToCoin, is(nullValue()));
    }

    @Test(expected = java.lang.IllegalStateException.class)
    public void fromLine_InvalidP2WPKHAddressGive_exceptionExpected() throws IOException {
        // act
        AddressToCoin addressToCoin = new AddressTxtLine().fromLine("bc1pmfr3p9j00pfxjh0zmgp99y8zftmd3s5pmedqhyptwy6lm87hf5ss52r5n8", keyUtility);

        // assert
        assertThat(addressToCoin, is(nullValue()));
    }

}
