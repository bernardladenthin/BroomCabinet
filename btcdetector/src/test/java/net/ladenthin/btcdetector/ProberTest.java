package net.ladenthin.btcdetector;

import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

import java.io.IOException;
import net.ladenthin.btcdetector.configuration.ConsumerJava;
import net.ladenthin.btcdetector.configuration.LmdbConfigurationReadOnly;

public class ProberTest {

    @Rule
    public TemporaryFolder folder = new TemporaryFolder();

    @Test(expected = org.lmdbjava.LmdbNativeException.class)
    public void initLMDB_lmdbNotExisting_noExceptionThrown() throws IOException {
        ConsumerJava consumerJava = new ConsumerJava();
        consumerJava.lmdbConfigurationReadOnly = new LmdbConfigurationReadOnly();
        consumerJava.lmdbConfigurationReadOnly.lmdbDirectory = folder.newFolder().getAbsolutePath();

        ProberTestImpl prober = new ProberTestImpl(consumerJava);
        prober.initLMDB();
    }

    @Test
    public void addSchutdownHook_noExceptionThrown() throws IOException {
        ConsumerJava consumerJava = new ConsumerJava();
        ProberTestImpl prober = new ProberTestImpl(consumerJava);
        prober.addSchutdownHook();
    }

    @Test
    public void startStatisticsTimer_noExceptionThrown() throws IOException {
        ConsumerJava consumerJava = new ConsumerJava();
        ProberTestImpl prober = new ProberTestImpl(consumerJava);
        prober.startStatisticsTimer();
    }

    @Test(expected = IllegalArgumentException.class)
    public void startStatisticsTimer_invalidparameter_throwsException() throws IOException {
        ConsumerJava consumerJava = new ConsumerJava();
        consumerJava.printStatisticsEveryNSeconds = 0;
        ProberTestImpl prober = new ProberTestImpl(consumerJava);
        prober.startStatisticsTimer();
    }
}
