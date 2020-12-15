package net.ladenthin.btcdetector;

import net.ladenthin.btcdetector.persistence.PersistenceUtils;
import net.ladenthin.btcdetector.persistence.lmdb.LMDBPersistence;
import org.bitcoinj.core.Context;
import org.bitcoinj.core.NetworkParameters;
import org.bitcoinj.params.MainNetParams;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.File;
import java.io.IOException;

public class LMDBToAddressFile implements Runnable {

    private final Logger logger = LoggerFactory.getLogger(LMDBToAddressFile.class);

    private final net.ladenthin.btcdetector.configuration.LMDBToAddressFile lmdbToAddressFile;

    private NetworkParameters networkParameters;

    private LMDBPersistence persistence;

    public LMDBToAddressFile(net.ladenthin.btcdetector.configuration.LMDBToAddressFile lmdbToAddressFile) {
        this.lmdbToAddressFile = lmdbToAddressFile;
    }

    @Override
    public void run() {
        createNetworkParameter();
        PersistenceUtils persistenceUtils = new PersistenceUtils(networkParameters);
        persistence = new LMDBPersistence(lmdbToAddressFile.lmdbConfigurationReadOnly, persistenceUtils);
        persistence.init();
        try {
            logger.info("writeAllAmounts ...");
            File addressesFile = new File(lmdbToAddressFile.addressesFile);
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
