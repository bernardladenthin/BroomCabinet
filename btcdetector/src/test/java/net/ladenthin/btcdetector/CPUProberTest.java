package net.ladenthin.btcdetector;

import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

import java.io.IOException;
import java.util.List;
import java.util.Random;
import net.ladenthin.btcdetector.configuration.ProbeAddressesCPU;
import org.bitcoinj.core.ECKey;
import org.bitcoinj.params.MainNetParams;
import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.is;
import org.mockito.ArgumentCaptor;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.times;
import org.slf4j.Logger;
import static org.mockito.Mockito.verify;

public class CPUProberTest {

    @Rule
    public TemporaryFolder folder = new TemporaryFolder();

    private final StaticKey staticKey = new StaticKey();

    private ArgumentCaptor<String> logCaptor = ArgumentCaptor.forClass(String.class);  ;

    @Test
    public void myTest() throws IOException, InterruptedException {
        ProbeAddressesCPU pa = new ProbeAddressesCPU();
        CPUProber cpuProber = new CPUProber(pa);

        ECKey keyCompressed = getFirstAddressHash160FromTestAddress(true);
        ECKey keyUncompressed = getFirstAddressHash160FromTestAddress(false);

        ByteBufferUtility byteBufferUtility = new ByteBufferUtility(false);
        cpuProber.getAddresses().add(byteBufferUtility.byteArrayToByteBuffer(keyCompressed.getPubKeyHash()));
        cpuProber.getAddresses().add(byteBufferUtility.byteArrayToByteBuffer(keyUncompressed.getPubKeyHash()));

        Logger logger = mock(Logger.class);
        cpuProber.setLogger(logger);
        final Random randomForProducer = new Random(TestAddresses.RANDOM_SEED);
        cpuProber.produceKey(randomForProducer);
        cpuProber.consumeKeys();

        KeyUtility keyUtility = new KeyUtility(MainNetParams.get(), new ByteBufferUtility(false));
        String hitMessageCompressed = CPUProber.HIT_PREFIX + keyUtility.createKeyDetails(keyCompressed);
        String hitMessageUnCompressed = CPUProber.HIT_PREFIX + keyUtility.createKeyDetails(keyUncompressed);
        
        verify(logger, times(2)).info(logCaptor.capture());

        List<String> arguments = logCaptor.getAllValues();

        assertThat(arguments.get(0), is(equalTo(hitMessageCompressed)));
        assertThat(arguments.get(1), is(equalTo(hitMessageUnCompressed)));
    }

    private ECKey getFirstAddressHash160FromTestAddress(boolean compressed) {
        TestAddresses testAddressesCompressed = new TestAddresses(1, compressed);
        ECKey key = testAddressesCompressed.getECKeys().get(0);
        return key;
    }
}
