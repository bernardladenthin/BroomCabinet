package net.ladenthin.btcdetector;

import net.ladenthin.btcdetector.configuration.ProbeAddresses;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

public class ProberTest {

    @Rule
    public TemporaryFolder folder = new TemporaryFolder();

    private List<String> createAddressesFiles() throws IOException {
        File one = folder.newFile("addressesOne.txt");
        File two = folder.newFile("addressesTwo.txt");
        File three = folder.newFile("addressesThree.txt");

        Files.write(one.toPath(), Arrays.asList(
                "1JCe8z4jJVNXSjohjM4i9Hh813dLCNx2Sy" ,
                "3Nxwenay9Z8Lc9JBiywExpnEFiLp6Afp8v" ,
                "3D2oetdNuZUqQHPJmcMDDHYoqkyNVsFk9r"));
        Files.write(two.toPath(), Arrays.asList(
                "1FeexV6bAHb8ybZjqQMjJrcCrHGW9sb6uF"));
        Files.write(three.toPath(), Arrays.asList(
                "# Test",
                "1WrongAddressFormat"));
        List<String> addresses = new ArrayList<>();
        addresses.add(one.getAbsolutePath());
        addresses.add(two.getAbsolutePath());
        addresses.add(three.getAbsolutePath());
        return addresses;
    }

    private String createFoundFile() throws IOException {
        return folder.newFile("foundFile.txt").getAbsolutePath();
    }

    @Test
    public void readAdresses_readAllFromFile_noExceptionThrown() throws IOException {
        ProbeAddresses pa = new ProbeAddresses();
        pa.selftestFirst = false;
        pa.foundFile = createFoundFile();
        pa.addressesFiles = createAddressesFiles();

        ProberTestImpl prober = new ProberTestImpl(pa);
        prober.readAdresses();
    }

    @Test
    public void readAdresses_selftestFirstEnabled_noExceptionThrown() throws IOException {
        ProbeAddresses pa = new ProbeAddresses();
        pa.selftestFirst = true;
        pa.foundFile = createFoundFile();
        pa.addressesFiles = createAddressesFiles();

        ProberTestImpl prober = new ProberTestImpl(pa);
        prober.readAdresses();
    }

    @Test(expected = RuntimeException.class)
    public void readAdresses_addressesFileNotExisting_exceptionThrown() throws IOException {
        ProbeAddresses pa = new ProbeAddresses();
        pa.selftestFirst = true;
        pa.foundFile = createFoundFile();
        pa.addressesFiles = Arrays.asList("notExisting.txt");

        ProberTestImpl prober = new ProberTestImpl(pa);
        prober.readAdresses();
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
}
