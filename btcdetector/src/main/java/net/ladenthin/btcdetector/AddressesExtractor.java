package net.ladenthin.btcdetector;

import net.ladenthin.btcdetector.configuration.ExtractAddresses;
import net.ladenthin.btcdetector.persistence.PersistenceUtils;
import net.ladenthin.btcdetector.persistence.lmdb.LMDBPersistence;
import org.bitcoinj.core.Context;
import org.bitcoinj.core.NetworkParameters;
import org.bitcoinj.params.MainNetParams;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.File;
import java.io.IOException;

public class AddressesExtractor implements Runnable {

    private final Logger logger = LoggerFactory.getLogger(AddressesExtractor.class);

    private final ExtractAddresses extractAddresses;

    private NetworkParameters networkParameters;

    private LMDBPersistence persistence;

    public AddressesExtractor(ExtractAddresses extractAddresses) {
        this.extractAddresses = extractAddresses;
    }

    @Override
    public void run() {
        createNetworkParameter();
        PersistenceUtils persistenceUtils = new PersistenceUtils(networkParameters);
        persistence = new LMDBPersistence(extractAddresses.lmdbConfigurationReadOnly, persistenceUtils);
        persistence.init();
        try {
            logger.info("writeAllAmounts ...");
            File addressesFile = new File(extractAddresses.addressesFile);
            // delete before write all addresses
            addressesFile.delete();
            persistence.writeAllAmountsToAddressFile(addressesFile);
            logger.info("writeAllAmounts done");
        } catch (IOException e) {
            throw new RuntimeException(e);
        } finally {
            persistence.close();
        }
    }

    private void createNetworkParameter() {
        networkParameters = MainNetParams.get();
        Context.getOrCreate(networkParameters);
    }
}
