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
import java.util.Map;
import java.util.concurrent.atomic.AtomicLong;
import net.ladenthin.btcdetector.persistence.lmdb.LMDBPersistence;
import org.bitcoinj.core.Coin;
import org.bitcoinj.core.LegacyAddress;

public class AddressFilesToLMDB implements Runnable {

    private final Logger logger = LoggerFactory.getLogger(AddressFilesToLMDB.class);

    private final net.ladenthin.btcdetector.configuration.AddressFilesToLMDB addressFilesToLMDB;

    private NetworkParameters networkParameters;

    private LMDBPersistence persistence;

    private final AtomicLong addressCounter = new AtomicLong();

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
                addressFile.readFromFile(addressesFile, addressToCoin -> {
                    LegacyAddress address = new KeyUtility(networkParameters, new ByteBufferUtility(false)).byteBufferToAddress(addressToCoin.getHash160());
                    persistence.putNewAmount(address, addressToCoin.getCoin());
                    addressCounter.incrementAndGet();

                    if (addressCounter.get() % 100_000 == 0) {
                        logProgress();
                    }
                });
                logProgress();
            }
            logProgress();
            logger.info("writeAllAmounts done");
        } catch (IOException e) {
            throw new RuntimeException(e);
        } finally {
            persistence.close();
        }
    }

    private void logProgress() {
        logger.info("Progress: " + addressCounter.get() + " addresses.");
    }

    private void createNetworkParameter() {
        networkParameters = MainNetParams.get();
        Context.getOrCreate(networkParameters);
    }
}
