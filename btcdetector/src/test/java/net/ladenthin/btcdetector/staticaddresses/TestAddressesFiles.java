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

    public final static Set<String> compressedTestAddressesAsLines = new HashSet<>();
    public final static Set<String> uncompressedTestAddressesAsLines = new HashSet<>();
    public final static Set<String> compressedTestAddressesWithStaticAmountAsLines = new HashSet<>();
    public final static Set<String> uncompressedTestAddressesWithStaticAmountAsLines = new HashSet<>();
    
    public final static Set<String> compressedTestAddressesAsHexLines = new HashSet<>();
    public final static Set<String> uncompressedTestAddressesAsHexLines = new HashSet<>();
    public final static Set<String> compressedTestAddressesWithStaticAmountAsHexLines = new HashSet<>();
    public final static Set<String> uncompressedTestAddressesWithStaticAmountAsHexLines = new HashSet<>();

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

        {
            uncompressedTestAddressesAsLines.add("15daqrFSG8d1EMfCWdWZWeZMSDFkqR834t,1");
            uncompressedTestAddressesAsLines.add("18DBt2Ght4y9nx69fXT7w8vVq9n5BqfRev,1");
            uncompressedTestAddressesAsLines.add("1AK4RGZoDCsSwjx3zzPwo4nbFzrJapr9m9,1");
            uncompressedTestAddressesAsLines.add("1BZVqUAK8KBbAL3r7wC3Chq8csTBYYCdZU,5000000000");
            uncompressedTestAddressesAsLines.add("1KYinnpkcc4KKNB8C73z9kgXCLpKdzor4V,1");
            uncompressedTestAddressesAsLines.add("1NEJvEj6jB7f9aBhT4wXZnBR9uGJrKanhJ,1");
        }
        {
            compressedTestAddressesAsLines.add("142XRqAwF7Xy5owyHW7u6vCooyGusQYZF4,1");
            compressedTestAddressesAsLines.add("1AcXATyTTvLm12dpBiTxdDxCtHhFyPNS1C,5000000000");
            compressedTestAddressesAsLines.add("1FpKH5GHTwNqJuiHdgL4tJYNvxEMhGzcap,1");
            compressedTestAddressesAsLines.add("1N2BnKNAqBnNBv4EnmEtjFxoewZ5NBsbVm,1");
            compressedTestAddressesAsLines.add("1NEJvEj6jB7f9aBhT4wXZnBR9uGJrKanhJ,1");
            compressedTestAddressesAsLines.add("1NsremZJgQWR4Vx4VARAUv4HLq9NbxPyYi,1");
        }
        {
            uncompressedTestAddressesWithStaticAmountAsLines.add("15daqrFSG8d1EMfCWdWZWeZMSDFkqR834t,1");
            uncompressedTestAddressesWithStaticAmountAsLines.add("18DBt2Ght4y9nx69fXT7w8vVq9n5BqfRev,1");
            uncompressedTestAddressesWithStaticAmountAsLines.add("1AK4RGZoDCsSwjx3zzPwo4nbFzrJapr9m9,1");
            uncompressedTestAddressesWithStaticAmountAsLines.add("1BZVqUAK8KBbAL3r7wC3Chq8csTBYYCdZU,1");
            uncompressedTestAddressesWithStaticAmountAsLines.add("1KYinnpkcc4KKNB8C73z9kgXCLpKdzor4V,1");
            uncompressedTestAddressesWithStaticAmountAsLines.add("1NEJvEj6jB7f9aBhT4wXZnBR9uGJrKanhJ,1");
        }
        {
            compressedTestAddressesWithStaticAmountAsLines.add("142XRqAwF7Xy5owyHW7u6vCooyGusQYZF4,1");
            compressedTestAddressesWithStaticAmountAsLines.add("1AcXATyTTvLm12dpBiTxdDxCtHhFyPNS1C,1");
            compressedTestAddressesWithStaticAmountAsLines.add("1FpKH5GHTwNqJuiHdgL4tJYNvxEMhGzcap,1");
            compressedTestAddressesWithStaticAmountAsLines.add("1N2BnKNAqBnNBv4EnmEtjFxoewZ5NBsbVm,1");
            compressedTestAddressesWithStaticAmountAsLines.add("1NEJvEj6jB7f9aBhT4wXZnBR9uGJrKanhJ,1");
            compressedTestAddressesWithStaticAmountAsLines.add("1NsremZJgQWR4Vx4VARAUv4HLq9NbxPyYi,1");
        }
        
        {
            uncompressedTestAddressesAsHexLines.add("15daqrFSG8d1EMfCWdWZWeZMSDFkqR834t");
            uncompressedTestAddressesAsHexLines.add("18DBt2Ght4y9nx69fXT7w8vVq9n5BqfRev");
            uncompressedTestAddressesAsHexLines.add("1AK4RGZoDCsSwjx3zzPwo4nbFzrJapr9m9");
            uncompressedTestAddressesAsHexLines.add("1BZVqUAK8KBbAL3r7wC3Chq8csTBYYCdZU");
            uncompressedTestAddressesAsHexLines.add("1KYinnpkcc4KKNB8C73z9kgXCLpKdzor4V");
            uncompressedTestAddressesAsHexLines.add("1NEJvEj6jB7f9aBhT4wXZnBR9uGJrKanhJ");
        }
        {
            compressedTestAddressesAsHexLines.add("142XRqAwF7Xy5owyHW7u6vCooyGusQYZF4");
            compressedTestAddressesAsHexLines.add("1AcXATyTTvLm12dpBiTxdDxCtHhFyPNS1C");
            compressedTestAddressesAsHexLines.add("1FpKH5GHTwNqJuiHdgL4tJYNvxEMhGzcap");
            compressedTestAddressesAsHexLines.add("1N2BnKNAqBnNBv4EnmEtjFxoewZ5NBsbVm");
            compressedTestAddressesAsHexLines.add("1NEJvEj6jB7f9aBhT4wXZnBR9uGJrKanhJ");
            compressedTestAddressesAsHexLines.add("1NsremZJgQWR4Vx4VARAUv4HLq9NbxPyYi");
        }
        {
            uncompressedTestAddressesWithStaticAmountAsHexLines.add("15daqrFSG8d1EMfCWdWZWeZMSDFkqR834t");
            uncompressedTestAddressesWithStaticAmountAsHexLines.add("18DBt2Ght4y9nx69fXT7w8vVq9n5BqfRev");
            uncompressedTestAddressesWithStaticAmountAsHexLines.add("1AK4RGZoDCsSwjx3zzPwo4nbFzrJapr9m9");
            uncompressedTestAddressesWithStaticAmountAsHexLines.add("1BZVqUAK8KBbAL3r7wC3Chq8csTBYYCdZU");
            uncompressedTestAddressesWithStaticAmountAsHexLines.add("1KYinnpkcc4KKNB8C73z9kgXCLpKdzor4V");
            uncompressedTestAddressesWithStaticAmountAsHexLines.add("1NEJvEj6jB7f9aBhT4wXZnBR9uGJrKanhJ");
        }
        {
            compressedTestAddressesWithStaticAmountAsHexLines.add("142XRqAwF7Xy5owyHW7u6vCooyGusQYZF4");
            compressedTestAddressesWithStaticAmountAsHexLines.add("1AcXATyTTvLm12dpBiTxdDxCtHhFyPNS1C");
            compressedTestAddressesWithStaticAmountAsHexLines.add("1FpKH5GHTwNqJuiHdgL4tJYNvxEMhGzcap");
            compressedTestAddressesWithStaticAmountAsHexLines.add("1N2BnKNAqBnNBv4EnmEtjFxoewZ5NBsbVm");
            compressedTestAddressesWithStaticAmountAsHexLines.add("1NEJvEj6jB7f9aBhT4wXZnBR9uGJrKanhJ");
            compressedTestAddressesWithStaticAmountAsHexLines.add("1NsremZJgQWR4Vx4VARAUv4HLq9NbxPyYi");
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
