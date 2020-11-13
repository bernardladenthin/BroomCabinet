package net.ladenthin.btcdetector;

import com.tngtech.java.junit.dataprovider.DataProvider;
import com.tngtech.java.junit.dataprovider.DataProviderRunner;
import com.tngtech.java.junit.dataprovider.UseDataProvider;
import java.io.File;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

import java.io.IOException;
import java.util.List;
import java.util.Random;
import net.ladenthin.btcdetector.configuration.LmdbConfigurationReadOnly;
import net.ladenthin.btcdetector.configuration.ProbeAddressesCPU;
import org.bitcoinj.core.ECKey;
import org.bitcoinj.params.MainNetParams;
import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.is;
import org.junit.runner.RunWith;
import org.mockito.ArgumentCaptor;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.times;
import org.slf4j.Logger;
import static org.mockito.Mockito.verify;

@RunWith(DataProviderRunner.class)
public class CPUProberTest {

    @DataProvider
    public static Object[][] compressed() {
        return new Object[][]{
            {true},
            {false}
        };
    }

    @Rule
    public TemporaryFolder folder = new TemporaryFolder();

    private ArgumentCaptor<String> logCaptor = ArgumentCaptor.forClass(String.class);

    ;

    @Test
    @UseDataProvider("compressed")
    public void myTest(boolean compressed) throws IOException, InterruptedException {
        TestAddressesLMDB testAddressesLMDB = new TestAddressesLMDB();
        File lmdbFolderPath = testAddressesLMDB.createTestLMDB(folder, compressed);

        ProbeAddressesCPU pa = new ProbeAddressesCPU();
        pa.lmdbConfigurationReadOnly = new LmdbConfigurationReadOnly();

        pa.lmdbConfigurationReadOnly.lmdbDirectory = lmdbFolderPath.getAbsolutePath();
        CPUProber cpuProber = new CPUProber(pa);
        cpuProber.initLMDB();

        ECKey key = getFirstAddressHash160FromTestAddress(compressed);

        Logger logger = mock(Logger.class);
        cpuProber.setLogger(logger);
        final Random randomForProducer = new Random(TestAddresses.RANDOM_SEED);
        cpuProber.produceKey(randomForProducer);
        cpuProber.consumeKeys();

        KeyUtility keyUtility = new KeyUtility(MainNetParams.get(), new ByteBufferUtility(false));
        String hitMessage = CPUProber.HIT_PREFIX + keyUtility.createKeyDetails(key);

        verify(logger, times(1)).info(logCaptor.capture());

        List<String> arguments = logCaptor.getAllValues();

        assertThat(arguments.get(0), is(equalTo(hitMessage)));
    }

    private ECKey getFirstAddressHash160FromTestAddress(boolean compressed) {
        TestAddresses testAddressesCompressed = new TestAddresses(1, compressed);
        ECKey key = testAddressesCompressed.getECKeys().get(0);
        return key;
    }
}
