package net.ladenthin.btcdetector;

import net.ladenthin.btcdetector.persistence.PersistenceUtils;
import org.bitcoinj.core.Context;
import org.bitcoinj.core.NetworkParameters;
import org.bitcoinj.params.MainNetParams;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.File;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.util.concurrent.atomic.AtomicLong;
import net.ladenthin.btcdetector.persistence.lmdb.LMDBPersistence;

public class AddressFilesToLMDB implements Runnable {

    private final Logger logger = LoggerFactory.getLogger(AddressFilesToLMDB.class);

    private final net.ladenthin.btcdetector.configuration.AddressFilesToLMDB addressFilesToLMDB;

    private NetworkParameters networkParameters;

    private LMDBPersistence persistence;

    private final AtomicLong addressCounter = new AtomicLong();
    
    private final ReadStatistic readStatistic = new ReadStatistic();

    public AddressFilesToLMDB(net.ladenthin.btcdetector.configuration.AddressFilesToLMDB addressFilesToLMDB) {
        this.addressFilesToLMDB = addressFilesToLMDB;
    }

    @Override
    public void run() {
        createNetworkParameter();

        PersistenceUtils persistenceUtils = new PersistenceUtils(networkParameters);
        persistence = new LMDBPersistence(addressFilesToLMDB.lmdbConfigurationWrite, persistenceUtils);
        persistence.init();
        try {
            logger.info("writeAllAmounts ...");
            for (String addressesFilePath : addressFilesToLMDB.addressesFiles) {
                File addressesFile = new File(addressesFilePath);
                AddressFile addressFile = new AddressFile(networkParameters);
                logger.info("process " + addressesFilePath);
                addressFile.readFromFile(addressesFile, readStatistic, addressToCoin -> {
                    
                    ByteBuffer hash160 = addressToCoin.getHash160();
                    persistence.putNewAmount(hash160, addressToCoin.getCoin());
                    addressCounter.incrementAndGet();

                    if (addressCounter.get() % 100_000 == 0) {
                        logProgress();
                    }
                });
                logProgress();
                logger.info("finished: " + addressesFilePath + " : " + readStatistic);
            }
            logProgress();
            logger.info("writeAllAmounts done");
            
            for (String error : readStatistic.errors) {
            logger.info("Error in line: " + error);
            }
            
        } catch (IOException e) {
            throw new RuntimeException(e);
        } finally {
            persistence.close();
        }
    }

    private void logProgress() {
        logger.info("Progress: " + addressCounter.get() + " addresses. Unsupported: "+ readStatistic.unsupported +" Errors: " + readStatistic.errors.size() );
    }

    private void createNetworkParameter() {
        networkParameters = MainNetParams.get();
        Context.getOrCreate(networkParameters);
    }
}
