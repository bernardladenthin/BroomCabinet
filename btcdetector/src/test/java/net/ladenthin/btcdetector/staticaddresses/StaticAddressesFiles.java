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
import org.bitcoinj.core.Coin;
import org.junit.rules.TemporaryFolder;

public class StaticAddressesFiles implements AddressesFiles {

    private final static String ADDRESS_FILE_ONE = "staticAddressesFile.txt";
    
    public static final Coin amountOtherAddresses = Coin.SATOSHI;

    public StaticAddressesFiles() {
    }

    @Override
    public List<String> createAddressesFiles(TemporaryFolder folder, boolean addInvalidAddresses) throws IOException {
        File one = folder.newFile(ADDRESS_FILE_ONE);

        Files.write(one.toPath(), Arrays.asList(
                new StaticBitcoinCashP2MSAddress().publicAddress,
                new StaticBitcoinCashP2MSXAddress().publicAddress,
                new StaticBitcoinCashP2PKHAddress().publicAddress,
                new StaticBitcoinCashP2SHAddress().publicAddress,
                new StaticBitcoinP2MSAddress().publicAddress,
                new StaticBitcoinP2WPKHAddress().publicAddress,
                new StaticBitcoinP2WSHAddress().publicAddress,
                new StaticDashP2PKHAddress().publicAddress,
                new StaticDashP2SHAddress().publicAddress,
                new StaticDogecoinP2PKHAddress().publicAddress,
                new StaticDogecoinP2SHAddress().publicAddress,
                new StaticDogecoinP2SHXAddress().publicAddress,
                new StaticLitecoinP2PKHAddress().publicAddress,
                new StaticLitecoinP2SHAddress().publicAddress
        ));
        List<String> addresses = new ArrayList<>();
        addresses.add(one.getAbsolutePath());
        return addresses;
    }

    @Override
    public TestAddresses getTestAddresses() {
        throw new UnsupportedOperationException("Not supported yet.");
    }

}
