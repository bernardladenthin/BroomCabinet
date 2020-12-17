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
package net.ladenthin.btcdetector.staticaddresses;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import net.ladenthin.btcdetector.AddressFile;
import net.ladenthin.btcdetector.AddressToCoin;
import org.bitcoinj.core.Coin;
import org.junit.rules.TemporaryFolder;

public class TestAddressesFiles implements AddressesFiles {

    private final static String ADDRESS_FILE_ONE = "addressesOne.txt";
    private final static String ADDRESS_FILE_TWO = "addressesTwo.txt";
    private final static String ADDRESS_FILE_THREE = "addressesThree.txt";
    public final static int NUMBER_OF_ADRESSES = 5;

    public static final Coin amountFirstAddress = Coin.FIFTY_COINS;
    public static final Coin amountOtherAddresses = Coin.SATOSHI;

    public final static Coin[] AMOUNTS = {
        amountFirstAddress,
        amountOtherAddresses,
        amountOtherAddresses,
        amountOtherAddresses,
        amountOtherAddresses
    };

    private final TestAddresses testAddresses;

    public TestAddressesFiles(boolean compressed) {
        testAddresses = new TestAddresses(NUMBER_OF_ADRESSES, compressed);
    }

    @Override
    public List<String> createAddressesFiles(TemporaryFolder folder) throws IOException {
        File one = folder.newFile(ADDRESS_FILE_ONE);
        File two = folder.newFile(ADDRESS_FILE_TWO);
        File three = folder.newFile(ADDRESS_FILE_THREE);

        Files.write(one.toPath(), Arrays.asList(
                testAddresses.getIndexAsBase58String(0) + AddressFile.SEPARATOR + amountFirstAddress,
                testAddresses.getIndexAsBase58String(1) + AddressToCoin.TAB_SPLIT + amountOtherAddresses,
                testAddresses.getIndexAsBase58String(2)
        ));
        Files.write(two.toPath(), Arrays.asList(
                testAddresses.getIndexAsBase58String(3)
        ));
        Files.write(three.toPath(), Arrays.asList(
                "# Test",
                "1WrongAddressFormat",
                new StaticBitcoinP2WPKHAddress().publicAddress,
                testAddresses.getIndexAsBase58String(4)
        ));
        List<String> addresses = new ArrayList<>();
        addresses.add(one.getAbsolutePath());
        addresses.add(two.getAbsolutePath());
        addresses.add(three.getAbsolutePath());
        return addresses;
    }

}
