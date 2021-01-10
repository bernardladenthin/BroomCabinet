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
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import net.ladenthin.btcdetector.AddressTxtLine;
import org.bitcoinj.core.Coin;
import org.junit.rules.TemporaryFolder;

public class TestAddressesFiles implements AddressesFiles {

    public final static Set<String> compressedTestAddressesAsDynamicWidthBase58BitcoinAddressWithAmount = new HashSet<>();
    public final static Set<String> uncompressedTestAddressesAsDynamicWidthBase58BitcoinAddressWithAmount = new HashSet<>();
    public final static Set<String> compressedTestAddressesWithStaticAmountAsDynamicWidthBase58BitcoinAddressWithAmount = new HashSet<>();
    public final static Set<String> uncompressedTestAddressesWithStaticAmountAsDynamicWidthBase58BitcoinAddressWithAmount = new HashSet<>();
    
    public final static Set<String> compressedTestAddressesAsFixedWidthBase58BitcoinAddress = new HashSet<>();
    public final static Set<String> uncompressedTestAddressesAsFixedWidthBase58BitcoinAddress = new HashSet<>();
    public final static Set<String> compressedTestAddressesWithStaticAmountAsFixedWidthBase58BitcoinAddress = new HashSet<>();
    public final static Set<String> uncompressedTestAddressesWithStaticAmountAsFixedWidthBase58BitcoinAddress = new HashSet<>();
    
    public final static Set<String> compressedTestAddressesAsHexHash = new HashSet<>();
    public final static Set<String> uncompressedTestAddressesAsHexHash = new HashSet<>();
    public final static Set<String> compressedTestAddressesWithStaticAmountAsHexHash = new HashSet<>();
    public final static Set<String> uncompressedTestAddressesWithStaticAmountAsHexHash = new HashSet<>();

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

    private final TestAddresses42 testAddresses;

    public TestAddressesFiles(boolean compressed) {
        testAddresses = new TestAddresses42(NUMBER_OF_ADRESSES, compressed);
        TestAddresses42 uc = new TestAddresses42(NUMBER_OF_ADRESSES, false);
        TestAddresses42 co = new TestAddresses42(NUMBER_OF_ADRESSES, true);

        {
            // DynamicWidthBase58BitcoinAddressWithAmount
            {
                uncompressedTestAddressesAsDynamicWidthBase58BitcoinAddressWithAmount.add(uc.getIndexAsBase58String(0)+",5000000000");
                uncompressedTestAddressesAsDynamicWidthBase58BitcoinAddressWithAmount.add(uc.getIndexAsBase58String(1)+",1");
                uncompressedTestAddressesAsDynamicWidthBase58BitcoinAddressWithAmount.add(uc.getIndexAsBase58String(2)+",1");
                uncompressedTestAddressesAsDynamicWidthBase58BitcoinAddressWithAmount.add(uc.getIndexAsBase58String(3)+",1");
                uncompressedTestAddressesAsDynamicWidthBase58BitcoinAddressWithAmount.add(uc.getIndexAsBase58String(4)+",1");
                uncompressedTestAddressesAsDynamicWidthBase58BitcoinAddressWithAmount.add(new StaticBitcoinP2WPKHAddress().publicKeyHashBase58+",1");
            }
            {
                compressedTestAddressesAsDynamicWidthBase58BitcoinAddressWithAmount.add(co.getIndexAsBase58String(0)+",5000000000");
                compressedTestAddressesAsDynamicWidthBase58BitcoinAddressWithAmount.add(co.getIndexAsBase58String(1)+",1");
                compressedTestAddressesAsDynamicWidthBase58BitcoinAddressWithAmount.add(co.getIndexAsBase58String(2)+",1");
                compressedTestAddressesAsDynamicWidthBase58BitcoinAddressWithAmount.add(co.getIndexAsBase58String(3)+",1");
                compressedTestAddressesAsDynamicWidthBase58BitcoinAddressWithAmount.add(co.getIndexAsBase58String(4)+",1");
                compressedTestAddressesAsDynamicWidthBase58BitcoinAddressWithAmount.add(new StaticBitcoinP2WPKHAddress().publicKeyHashBase58+",1");
            }
            {
                uncompressedTestAddressesWithStaticAmountAsDynamicWidthBase58BitcoinAddressWithAmount.add(uc.getIndexAsBase58String(0)+",1");
                uncompressedTestAddressesWithStaticAmountAsDynamicWidthBase58BitcoinAddressWithAmount.add(uc.getIndexAsBase58String(1)+",1");
                uncompressedTestAddressesWithStaticAmountAsDynamicWidthBase58BitcoinAddressWithAmount.add(uc.getIndexAsBase58String(2)+",1");
                uncompressedTestAddressesWithStaticAmountAsDynamicWidthBase58BitcoinAddressWithAmount.add(uc.getIndexAsBase58String(3)+",1");
                uncompressedTestAddressesWithStaticAmountAsDynamicWidthBase58BitcoinAddressWithAmount.add(uc.getIndexAsBase58String(4)+",1");
                uncompressedTestAddressesWithStaticAmountAsDynamicWidthBase58BitcoinAddressWithAmount.add(new StaticBitcoinP2WPKHAddress().publicKeyHashBase58+",1");
            }
            {
                compressedTestAddressesWithStaticAmountAsDynamicWidthBase58BitcoinAddressWithAmount.add(co.getIndexAsBase58String(0)+",1");
                compressedTestAddressesWithStaticAmountAsDynamicWidthBase58BitcoinAddressWithAmount.add(co.getIndexAsBase58String(1)+",1");
                compressedTestAddressesWithStaticAmountAsDynamicWidthBase58BitcoinAddressWithAmount.add(co.getIndexAsBase58String(2)+",1");
                compressedTestAddressesWithStaticAmountAsDynamicWidthBase58BitcoinAddressWithAmount.add(co.getIndexAsBase58String(3)+",1");
                compressedTestAddressesWithStaticAmountAsDynamicWidthBase58BitcoinAddressWithAmount.add(co.getIndexAsBase58String(4)+",1");
                compressedTestAddressesWithStaticAmountAsDynamicWidthBase58BitcoinAddressWithAmount.add(new StaticBitcoinP2WPKHAddress().publicKeyHashBase58 +",1");
            }
        }
        {
            //FixedWidthBase58BitcoinAddress
            {
                uncompressedTestAddressesAsFixedWidthBase58BitcoinAddress.add(uc.getIndexAsBase58String(0));
                uncompressedTestAddressesAsFixedWidthBase58BitcoinAddress.add(uc.getIndexAsBase58String(1));
                uncompressedTestAddressesAsFixedWidthBase58BitcoinAddress.add(uc.getIndexAsBase58String(2));
                uncompressedTestAddressesAsFixedWidthBase58BitcoinAddress.add(uc.getIndexAsBase58String(3));
                uncompressedTestAddressesAsFixedWidthBase58BitcoinAddress.add(uc.getIndexAsBase58String(4));
                uncompressedTestAddressesAsFixedWidthBase58BitcoinAddress.add(new StaticBitcoinP2WPKHAddress().publicKeyHashBase58);
            }
            {
                compressedTestAddressesAsFixedWidthBase58BitcoinAddress.add(co.getIndexAsBase58String(0));
                compressedTestAddressesAsFixedWidthBase58BitcoinAddress.add(co.getIndexAsBase58String(1));
                compressedTestAddressesAsFixedWidthBase58BitcoinAddress.add(co.getIndexAsBase58String(2));
                compressedTestAddressesAsFixedWidthBase58BitcoinAddress.add(co.getIndexAsBase58String(3));
                compressedTestAddressesAsFixedWidthBase58BitcoinAddress.add(co.getIndexAsBase58String(4));
                compressedTestAddressesAsFixedWidthBase58BitcoinAddress.add(new StaticBitcoinP2WPKHAddress().publicKeyHashBase58);
            }
            {
                uncompressedTestAddressesWithStaticAmountAsFixedWidthBase58BitcoinAddress.add(uc.getIndexAsBase58String(0));
                uncompressedTestAddressesWithStaticAmountAsFixedWidthBase58BitcoinAddress.add(uc.getIndexAsBase58String(1));
                uncompressedTestAddressesWithStaticAmountAsFixedWidthBase58BitcoinAddress.add(uc.getIndexAsBase58String(2));
                uncompressedTestAddressesWithStaticAmountAsFixedWidthBase58BitcoinAddress.add(uc.getIndexAsBase58String(3));
                uncompressedTestAddressesWithStaticAmountAsFixedWidthBase58BitcoinAddress.add(uc.getIndexAsBase58String(4));
                uncompressedTestAddressesWithStaticAmountAsFixedWidthBase58BitcoinAddress.add(new StaticBitcoinP2WPKHAddress().publicKeyHashBase58);
            }
            {
                compressedTestAddressesWithStaticAmountAsFixedWidthBase58BitcoinAddress.add(co.getIndexAsBase58String(0));
                compressedTestAddressesWithStaticAmountAsFixedWidthBase58BitcoinAddress.add(co.getIndexAsBase58String(1));
                compressedTestAddressesWithStaticAmountAsFixedWidthBase58BitcoinAddress.add(co.getIndexAsBase58String(2));
                compressedTestAddressesWithStaticAmountAsFixedWidthBase58BitcoinAddress.add(co.getIndexAsBase58String(3));
                compressedTestAddressesWithStaticAmountAsFixedWidthBase58BitcoinAddress.add(co.getIndexAsBase58String(4));
                compressedTestAddressesWithStaticAmountAsFixedWidthBase58BitcoinAddress.add(new StaticBitcoinP2WPKHAddress().publicKeyHashBase58);
            }
        }
        {
            //HexHash
            {
                uncompressedTestAddressesAsHexHash.add(uc.getIndexAsHash160HexEncoded(0));
                uncompressedTestAddressesAsHexHash.add(uc.getIndexAsHash160HexEncoded(1));
                uncompressedTestAddressesAsHexHash.add(uc.getIndexAsHash160HexEncoded(2));
                uncompressedTestAddressesAsHexHash.add(uc.getIndexAsHash160HexEncoded(3));
                uncompressedTestAddressesAsHexHash.add(uc.getIndexAsHash160HexEncoded(4));
                uncompressedTestAddressesAsHexHash.add(new StaticBitcoinP2WPKHAddress().publicKeyHash);
            }
            {
                compressedTestAddressesAsHexHash.add(co.getIndexAsHash160HexEncoded(0));
                compressedTestAddressesAsHexHash.add(co.getIndexAsHash160HexEncoded(1));
                compressedTestAddressesAsHexHash.add(co.getIndexAsHash160HexEncoded(2));
                compressedTestAddressesAsHexHash.add(co.getIndexAsHash160HexEncoded(3));
                compressedTestAddressesAsHexHash.add(co.getIndexAsHash160HexEncoded(4));
                compressedTestAddressesAsHexHash.add(new StaticBitcoinP2WPKHAddress().publicKeyHash);
            }
            {
                uncompressedTestAddressesWithStaticAmountAsHexHash.add(uc.getIndexAsHash160HexEncoded(0));
                uncompressedTestAddressesWithStaticAmountAsHexHash.add(uc.getIndexAsHash160HexEncoded(1));
                uncompressedTestAddressesWithStaticAmountAsHexHash.add(uc.getIndexAsHash160HexEncoded(2));
                uncompressedTestAddressesWithStaticAmountAsHexHash.add(uc.getIndexAsHash160HexEncoded(3));
                uncompressedTestAddressesWithStaticAmountAsHexHash.add(uc.getIndexAsHash160HexEncoded(4));
                uncompressedTestAddressesWithStaticAmountAsHexHash.add(new StaticBitcoinP2WPKHAddress().publicKeyHash);
            }
            {
                compressedTestAddressesWithStaticAmountAsHexHash.add(co.getIndexAsHash160HexEncoded(0));
                compressedTestAddressesWithStaticAmountAsHexHash.add(co.getIndexAsHash160HexEncoded(1));
                compressedTestAddressesWithStaticAmountAsHexHash.add(co.getIndexAsHash160HexEncoded(2));
                compressedTestAddressesWithStaticAmountAsHexHash.add(co.getIndexAsHash160HexEncoded(3));
                compressedTestAddressesWithStaticAmountAsHexHash.add(co.getIndexAsHash160HexEncoded(4));
                compressedTestAddressesWithStaticAmountAsHexHash.add(new StaticBitcoinP2WPKHAddress().publicKeyHash);
            }
        }
    }

    @Override
    public List<String> createAddressesFiles(TemporaryFolder folder, boolean addInvalidAddresses) throws IOException {
        File one = folder.newFile(ADDRESS_FILE_ONE);
        File two = folder.newFile(ADDRESS_FILE_TWO);
        File three = folder.newFile(ADDRESS_FILE_THREE);

        Files.write(one.toPath(), Arrays.asList(
                testAddresses.getIndexAsBase58String(0) + AddressTxtLine.SEPARATOR + amountFirstAddress,
                testAddresses.getIndexAsBase58String(1) + AddressTxtLine.TAB_SPLIT + amountOtherAddresses,
                testAddresses.getIndexAsBase58String(2)
        ));
        Files.write(two.toPath(), Arrays.asList(
                testAddresses.getIndexAsBase58String(3)
        ));
        
        List<String> listThree = new ArrayList<>();
        
        {
            listThree.add("# Test");
            listThree.add("1WrOngAddressFormat");
            listThree.add(new StaticBitcoinP2WPKHAddress().publicAddress);
            listThree.add(testAddresses.getIndexAsBase58String(4));

            if (addInvalidAddresses) {
                // secret : 1
                listThree.add("1EHNa6Q4Jz2uvNExL497mE43ikXhwF6kZm");
                listThree.add("1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH");
            }   
        }
        
        Files.write(three.toPath(), listThree);
        List<String> addresses = new ArrayList<>();
        addresses.add(one.getAbsolutePath());
        addresses.add(two.getAbsolutePath());
        addresses.add(three.getAbsolutePath());
        return addresses;
    }

    @Override
    public TestAddresses getTestAddresses() {
        return testAddresses; 
    }

}
