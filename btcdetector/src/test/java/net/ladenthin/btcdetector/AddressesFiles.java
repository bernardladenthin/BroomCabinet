package net.ladenthin.btcdetector;

import java.io.IOException;
import java.util.List;
import org.junit.rules.TemporaryFolder;

public interface AddressesFiles {
    
    List<String> createAddressesFiles(TemporaryFolder folder) throws IOException;
}
