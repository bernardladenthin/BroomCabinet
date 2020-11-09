package net.ladenthin.btcdetector;

import net.ladenthin.btcdetector.configuration.ProbeAddresses;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

import java.io.IOException;
import net.ladenthin.btcdetector.configuration.LmdbConfigurationReadOnly;

public class ProberTest {

    @Rule
    public TemporaryFolder folder = new TemporaryFolder();

    @Test(expected = org.lmdbjava.LmdbNativeException.class)
    public void initLMDB_lmdbNotExisting_noExceptionThrown() throws IOException {
        ProbeAddresses pa = new ProbeAddresses();
        pa.lmdbConfigurationReadOnly = new LmdbConfigurationReadOnly();
        pa.lmdbConfigurationReadOnly.lmdbDirectory = folder.newFolder().getAbsolutePath();

        ProberTestImpl prober = new ProberTestImpl(pa);
        prober.initLMDB();
    }

    @Test
    public void addSchutdownHook_noExceptionThrown() throws IOException {
        ProbeAddresses pa = new ProbeAddresses();
        ProberTestImpl prober = new ProberTestImpl(pa);
        prober.addSchutdownHook();
    }

    @Test
    public void startStatisticsTimer_noExceptionThrown() throws IOException {
        ProbeAddresses pa = new ProbeAddresses();
        ProberTestImpl prober = new ProberTestImpl(pa);
        prober.startStatisticsTimer();
    }

    @Test(expected = IllegalArgumentException.class)
    public void startStatisticsTimer_invalidparameter_throwsException() throws IOException {
        ProbeAddresses pa = new ProbeAddresses();
        pa.printStatisticsEveryNSeconds = 0;
        ProberTestImpl prober = new ProberTestImpl(pa);
        prober.startStatisticsTimer();
    }
}
