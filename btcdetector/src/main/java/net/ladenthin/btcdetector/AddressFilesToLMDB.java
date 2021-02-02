// @formatter:off
/**
 * Copyright 2020 Bernard Ladenthin bernard.ladenthin@gmail.com
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *    http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 */
// @formatter:on
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
import net.ladenthin.btcdetector.configuration.CAddressFilesToLMDB;
import net.ladenthin.btcdetector.persistence.lmdb.LMDBPersistence;

public class AddressFilesToLMDB implements Runnable {

    private final Logger logger = LoggerFactory.getLogger(AddressFilesToLMDB.class);

    private final CAddressFilesToLMDB addressFilesToLMDB;

    private NetworkParameters networkParameters;

    private LMDBPersistence persistence;

    private final AtomicLong addressCounter = new AtomicLong();

    private final ReadStatistic readStatistic = new ReadStatistic();

    public AddressFilesToLMDB(CAddressFilesToLMDB addressFilesToLMDB) {
        this.addressFilesToLMDB = addressFilesToLMDB;
    }

    @Override
    public void run() {
        createNetworkParameter();

        PersistenceUtils persistenceUtils = new PersistenceUtils(networkParameters);
        persistence = new LMDBPersistence(addressFilesToLMDB.lmdbConfigurationWrite, persistenceUtils);
        persistence.init();
        try {
            logger.info("check if all configured address files exists");
            for (String addressesFilePath : addressFilesToLMDB.addressesFiles) {
                File addressesFile = new File(addressesFilePath);
                if (!addressesFile.exists()) {
                    throw new IllegalArgumentException("The address file does not exists: " + addressesFile.getAbsolutePath());
                }
                logger.info("address files exists: " + addressesFile.getAbsolutePath());
            }
            
            logger.info("writeAllAmounts ...");
            for (String addressesFilePath : addressFilesToLMDB.addressesFiles) {
                File addressesFile = new File(addressesFilePath);
                AddressFile addressFile = new AddressFile(networkParameters);
                logger.info("process " + addressesFilePath);
                addressFile.readFromFile(addressesFile, readStatistic, addressToCoin -> {

                    ByteBuffer hash160 = addressToCoin.getHash160();
                    persistence.putNewAmount(hash160, addressToCoin.getCoin());
                    addressCounter.incrementAndGet();

                    if (addressCounter.get() % 1_000_000 == 0) {
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
            
            long count = persistence.count();
            logger.info("LMDB contains " + count + " unique entries.");

        } catch (IOException e) {
            throw new RuntimeException(e);
        } finally {
            persistence.close();
        }
    }

    private void logProgress() {
        logger.info("Progress: " + addressCounter.get() + " addresses. Unsupported: " + readStatistic.unsupported + " Errors: " + readStatistic.errors.size());
    }

    private void createNetworkParameter() {
        networkParameters = MainNetParams.get();
        Context.getOrCreate(networkParameters);
    }
}
