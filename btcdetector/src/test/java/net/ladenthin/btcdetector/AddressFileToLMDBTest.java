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

import com.tngtech.java.junit.dataprovider.DataProviderRunner;
import com.tngtech.java.junit.dataprovider.UseDataProvider;
import java.io.File;
import java.io.IOException;
import java.nio.ByteBuffer;
import net.ladenthin.btcdetector.configuration.CLMDBConfigurationReadOnly;
import net.ladenthin.btcdetector.persistence.Persistence;
import net.ladenthin.btcdetector.persistence.PersistenceUtils;
import net.ladenthin.btcdetector.persistence.lmdb.LMDBPersistence;
import net.ladenthin.btcdetector.staticaddresses.StaticAddressesFiles;
import net.ladenthin.btcdetector.staticaddresses.StaticKey;
import net.ladenthin.btcdetector.staticaddresses.*;
import net.ladenthin.btcdetector.staticaddresses.TestAddresses;
import net.ladenthin.btcdetector.staticaddresses.TestAddressesFiles;
import net.ladenthin.btcdetector.staticaddresses.TestAddressesLMDB;
import org.bitcoinj.core.Coin;
import org.bitcoinj.core.LegacyAddress;
import org.bitcoinj.core.NetworkParameters;
import org.bitcoinj.params.MainNetParams;
import org.junit.Before;
import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.*;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;
import org.junit.runner.RunWith;

@RunWith(DataProviderRunner.class)
public class AddressFileToLMDBTest {

    @Rule
    public TemporaryFolder folder = new TemporaryFolder();

    StaticKey staticKey = new StaticKey();

    private final NetworkParameters networkParameters = MainNetParams.get();
    private final KeyUtility keyUtility = new KeyUtility(networkParameters, new ByteBufferUtility(true));

    @Before
    public void init() throws IOException {
    }

    @Test
    @UseDataProvider(value = CommonDataProvider.DATA_PROVIDER_COMPRESSED_AND_STATIC_AMOUNT, location = CommonDataProvider.class)
    public void addressFilesToLMDB_createLMDB_containingTestAddressesHashesWithCorrectAmount(boolean compressed, boolean useStaticAmount) throws IOException {
        TestAddressesLMDB testAddressesLMDB = new TestAddressesLMDB();

        TestAddressesFiles testAddresses = new TestAddressesFiles(compressed);
        File lmdbFolderPath = testAddressesLMDB.createTestLMDB(folder, testAddresses, useStaticAmount);

        // assert
        CLMDBConfigurationReadOnly lmdbConfigurationReadOnly = new CLMDBConfigurationReadOnly();
        lmdbConfigurationReadOnly.lmdbDirectory = lmdbFolderPath.getAbsolutePath();
        PersistenceUtils persistenceUtils = new PersistenceUtils(networkParameters);
        Persistence persistence = new LMDBPersistence(lmdbConfigurationReadOnly, persistenceUtils);
        persistence.init();

        Coin[] amounts = new Coin[TestAddressesFiles.NUMBER_OF_ADRESSES];
        String[] base58Adresses;
        if (compressed) {
            base58Adresses = TestAddresses.SEED_42_COMPRESSED_HASH160;
        } else {
            base58Adresses = TestAddresses.SEED_42_UNCOMPRESSED_HASH160;
        }
        for (int i = 0; i < amounts.length; i++) {
            ByteBuffer hash160 = keyUtility.addressToByteBuffer(LegacyAddress.fromBase58(networkParameters, base58Adresses[i]));
            amounts[i] = persistence.getAmount(hash160);
            if (useStaticAmount) {
                assertThat(amounts[i], is(equalTo(Coin.SATOSHI)));
            } else {
                assertThat(amounts[i], is(equalTo(TestAddressesFiles.AMOUNTS[i])));
            }
        }

        persistence.close();
    }

    @Test
    public void addressFilesToLMDB_createLMDBWithStaticAddresses_containingStaticHashes() throws IOException {
        TestAddressesLMDB testAddressesLMDB = new TestAddressesLMDB();

        StaticAddressesFiles testAddresses = new StaticAddressesFiles();
        File lmdbFolderPath = testAddressesLMDB.createTestLMDB(folder, testAddresses, false);

        // assert
        CLMDBConfigurationReadOnly lmdbConfigurationReadOnly = new CLMDBConfigurationReadOnly();
        lmdbConfigurationReadOnly.lmdbDirectory = lmdbFolderPath.getAbsolutePath();
        PersistenceUtils persistenceUtils = new PersistenceUtils(networkParameters);
        Persistence persistence = new LMDBPersistence(lmdbConfigurationReadOnly, persistenceUtils);
        persistence.init();

        String[] hash160s = {
            new StaticDogecoinP2PKHAddress().publicKeyHash,
            new StaticDashP2PKHAddress().publicKeyHash,
            new StaticBitcoinP2WPKHAddress().publicKeyHash,
            new StaticLitecoinP2PKHAddress().publicKeyHash,
            new StaticBitcoinCashP2PKHAddress().publicKeyHash,};

        for (int i = 0; i < hash160s.length; i++) {
            String hash160 = hash160s[i];

            ByteBuffer hash160AsByteBuffer = keyUtility.byteBufferUtility.getByteBufferFromHex(hash160);

            boolean contains = persistence.containsAddress(hash160AsByteBuffer);
            assertThat(contains, is(equalTo(Boolean.TRUE)));
        }

        persistence.close();
    }

}
