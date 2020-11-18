package net.ladenthin.btcdetector;

import java.io.File;
import java.io.IOException;
import java.util.List;
import net.ladenthin.btcdetector.configuration.LmdbConfigurationWrite;
import org.junit.rules.TemporaryFolder;

public class TestAddressesLMDB {
    
    public File createTestLMDB(TemporaryFolder folder, boolean compressed) throws IOException {
        net.ladenthin.btcdetector.configuration.AddressFilesToLMDB addressFilesToLMDBConfigurationWrite = new net.ladenthin.btcdetector.configuration.AddressFilesToLMDB();
        TestAddressesFiles testAddresses = new TestAddressesFiles(compressed);
        List<String> addressesFiles = testAddresses.createAddressesFiles(folder);
        addressFilesToLMDBConfigurationWrite.addressesFiles.addAll(addressesFiles);
        addressFilesToLMDBConfigurationWrite.lmdbConfigurationWrite = new LmdbConfigurationWrite();
        File lmdbFolder = folder.newFolder("lmdb");
        String lmdbFolderPath = lmdbFolder.getAbsolutePath();
        addressFilesToLMDBConfigurationWrite.lmdbConfigurationWrite.lmdbDirectory = lmdbFolderPath;
        AddressFilesToLMDB addressFilesToLMDB = new AddressFilesToLMDB(addressFilesToLMDBConfigurationWrite);
        addressFilesToLMDB.run();
        return lmdbFolder;
    }
}