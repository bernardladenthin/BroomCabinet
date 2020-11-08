package net.ladenthin.btcdetector;

import com.tngtech.java.junit.dataprovider.DataProvider;
import com.tngtech.java.junit.dataprovider.DataProviderRunner;
import com.tngtech.java.junit.dataprovider.UseDataProvider;
import java.io.File;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.util.List;
import net.ladenthin.btcdetector.configuration.LmdbConfigurationReadOnly;
import net.ladenthin.btcdetector.configuration.LmdbConfigurationWrite;
import net.ladenthin.btcdetector.persistence.Persistence;
import net.ladenthin.btcdetector.persistence.PersistenceUtils;
import net.ladenthin.btcdetector.persistence.lmdb.LMDBPersistence;
import org.bitcoinj.core.Coin;
import org.bitcoinj.core.Context;
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

    @Before
    public void init() throws IOException {
    }

    @Test
    @UseDataProvider("compressed")
    public void addressFilesToLMDB_createLMDB(boolean compressed) throws IOException {
        TestAddressesLMDB testAddressesLMDB = new TestAddressesLMDB();
        File lmdbFolderPath = testAddressesLMDB.createTestLMDB(folder, compressed);

        // assert
        LmdbConfigurationReadOnly lmdbConfigurationReadOnly = new LmdbConfigurationReadOnly();
        lmdbConfigurationReadOnly.lmdbDirectory = lmdbFolderPath.getAbsolutePath();
        NetworkParameters networkParameters = MainNetParams.get();
        PersistenceUtils persistenceUtils = new PersistenceUtils(networkParameters);
        Persistence persistence = new LMDBPersistence(lmdbConfigurationReadOnly, persistenceUtils);
        persistence.init();

        Coin[] amounts = new Coin[TestAddressesFiles.NUMBER_OF_ADRESSES];
        String[] testAddresses;
        if (compressed) {
            testAddresses = TestAddresses.SEED_42_COMPRESSED_HASH160;
        } else {
            testAddresses = TestAddresses.SEED_42_UNCOMPRESSED_HASH160;
        }
        for (int i = 0; i < amounts.length; i++) {
            amounts[i] = persistence.getAmount(LegacyAddress.fromBase58(networkParameters, testAddresses[i]));
            assertThat(amounts[i], is(equalTo(TestAddressesFiles.AMOUNTS[i])));
        }

        persistence.close();
    }


}
