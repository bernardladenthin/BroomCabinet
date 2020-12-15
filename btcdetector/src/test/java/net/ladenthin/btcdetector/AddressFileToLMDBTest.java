package net.ladenthin.btcdetector;

import com.tngtech.java.junit.dataprovider.DataProvider;
import com.tngtech.java.junit.dataprovider.DataProviderRunner;
import com.tngtech.java.junit.dataprovider.UseDataProvider;
import java.io.File;
import java.io.IOException;
import java.nio.ByteBuffer;
import net.ladenthin.btcdetector.configuration.LmdbConfigurationReadOnly;
import net.ladenthin.btcdetector.persistence.Persistence;
import net.ladenthin.btcdetector.persistence.PersistenceUtils;
import net.ladenthin.btcdetector.persistence.lmdb.LMDBPersistence;
import org.bitcoinj.core.Coin;
import org.bitcoinj.core.LegacyAddress;
import org.bitcoinj.core.NetworkParameters;
import org.bitcoinj.params.MainNetParams;
import org.junit.Before;
import org.junit.Test;
import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.*;
import org.junit.Rule;
import org.junit.rules.TemporaryFolder;
import org.junit.runner.RunWith;

@RunWith(DataProviderRunner.class)
public class AddressFileToLMDBTest {

    @DataProvider
    public static Object[][] compressed() {
        return new Object[][]{
            {true},
            {false}
        };
    }

    @Rule
    public TemporaryFolder folder = new TemporaryFolder();

    StaticKey staticKey = new StaticKey();

    private final NetworkParameters networkParameters = MainNetParams.get();
    private final KeyUtility keyUtility = new KeyUtility(networkParameters, new ByteBufferUtility(true));

    @Before
    public void init() throws IOException {
    }

    @Test
    @UseDataProvider("compressed")
    public void addressFilesToLMDB_createLMDB_containingTestAddressesHashes(boolean compressed) throws IOException {
        TestAddressesLMDB testAddressesLMDB = new TestAddressesLMDB();

        TestAddressesFiles testAddresses = new TestAddressesFiles(compressed);
        File lmdbFolderPath = testAddressesLMDB.createTestLMDB(folder, testAddresses);

        // assert
        LmdbConfigurationReadOnly lmdbConfigurationReadOnly = new LmdbConfigurationReadOnly();
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
            assertThat(amounts[i], is(equalTo(TestAddressesFiles.AMOUNTS[i])));
        }

        persistence.close();
    }

    @Test
    public void addressFilesToLMDB_createLMDBWithStaticAddresses_containingStaticHashes() throws IOException {
        TestAddressesLMDB testAddressesLMDB = new TestAddressesLMDB();

        StaticAddressesFiles testAddresses = new StaticAddressesFiles();
        File lmdbFolderPath = testAddressesLMDB.createTestLMDB(folder, testAddresses);

        // assert
        LmdbConfigurationReadOnly lmdbConfigurationReadOnly = new LmdbConfigurationReadOnly();
        lmdbConfigurationReadOnly.lmdbDirectory = lmdbFolderPath.getAbsolutePath();
        PersistenceUtils persistenceUtils = new PersistenceUtils(networkParameters);
        Persistence persistence = new LMDBPersistence(lmdbConfigurationReadOnly, persistenceUtils);
        persistence.init();

        String[] hash160s = {
            new StaticDogecoinP2PKHAddress().publicKeyHash,
            new StaticDashP2PKHAddress().publicKeyHash,
            new StaticBitcoinP2WPKHAddress().publicKeyHash,
            new StaticLitecoinP2PKHAddress().publicKeyHash,
            new StaticBitcoinCashP2PKHAddress().publicKeyHash,
        };
        
        for (int i = 0; i < hash160s.length; i++) {
            String hash160 = hash160s[i];
            
            ByteBuffer hash160AsByteBuffer = keyUtility.byteBufferUtility.getByteBufferFromHex(hash160);
            
            boolean contains = persistence.containsAddress(hash160AsByteBuffer);
            assertThat(contains, is(equalTo(Boolean.TRUE)));
        }

        persistence.close();
    }

}
