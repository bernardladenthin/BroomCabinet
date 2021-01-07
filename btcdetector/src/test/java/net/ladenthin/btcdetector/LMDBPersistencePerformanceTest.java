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

import ch.qos.logback.classic.Level;
import java.io.File;
import java.io.IOException;
import java.math.BigInteger;
import java.util.concurrent.Executors;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.atomic.AtomicBoolean;
import net.ladenthin.btcdetector.configuration.CConsumerJava;
import net.ladenthin.btcdetector.configuration.CLMDBConfigurationReadOnly;
import net.ladenthin.btcdetector.staticaddresses.TestAddressesFiles;
import net.ladenthin.btcdetector.staticaddresses.TestAddressesLMDB;
import org.bitcoinj.core.ECKey;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

public class LMDBPersistencePerformanceTest {
    
    @Rule
    public TemporaryFolder folder = new TemporaryFolder();
    
    private final static int ARRAY_SIZE = 1024*8;
    private final static BigInteger PRIVATE_KEY = BigInteger.valueOf(1337);
    private final static int CONSUMER_THREADS = 32;
    private final static int TEST_TIME_IN_SECONDS = 15;
    
    private final static int KEYS_QUEUE_SIZE = CONSUMER_THREADS*2;
    private final static int PRODUCER_THREADS = KEYS_QUEUE_SIZE;
    
    @Test
    public void runProber_testAddressGiven_hitExpected() throws IOException, InterruptedException, IllegalArgumentException, NoSuchFieldException, IllegalAccessException {
        TestAddressesLMDB testAddressesLMDB = new TestAddressesLMDB();

        TestAddressesFiles testAddresses = new TestAddressesFiles(false);
        File lmdbFolderPath = testAddressesLMDB.createTestLMDB(folder, testAddresses, true, false);

        CConsumerJava cConsumerJava = new CConsumerJava();
        cConsumerJava.threads = CONSUMER_THREADS;
        cConsumerJava.queueSize = KEYS_QUEUE_SIZE;
        cConsumerJava.printStatisticsEveryNSeconds = 1;
        cConsumerJava.delayEmptyConsumer = 1;
        cConsumerJava.lmdbConfigurationReadOnly = new CLMDBConfigurationReadOnly();
        cConsumerJava.lmdbConfigurationReadOnly.lmdbDirectory = lmdbFolderPath.getAbsolutePath();

        AtomicBoolean shouldRun = new AtomicBoolean(true);
        
        ConsumerJava consumerJava = new ConsumerJava(cConsumerJava, shouldRun);
        ch.qos.logback.classic.Logger logger = (ch.qos.logback.classic.Logger) consumerJava.getLogger();
        logger.setLevel(Level.INFO);
        
        consumerJava.initLMDB();
        
        // create producer
        PublicKeyBytes[] publicKeyByteses = createPublicKeyBytesArray();
        ThreadPoolExecutor threadPoolExecutor = (ThreadPoolExecutor) Executors.newFixedThreadPool(PRODUCER_THREADS);
        createProducerThreads(threadPoolExecutor, shouldRun, consumerJava, publicKeyByteses);
        
        // act
        consumerJava.startConsumer();
        consumerJava.startStatisticsTimer();
        
        Thread.sleep(TEST_TIME_IN_SECONDS * 1000);
    }

    private void createProducerThreads(ThreadPoolExecutor threadPoolExecutor, AtomicBoolean shouldRun, ConsumerJava consumerJava, PublicKeyBytes[] publicKeyByteses) {
        for (int i = 0; i < PRODUCER_THREADS; i++) {
            threadPoolExecutor.submit(() ->{
                while(shouldRun.get()) {
                    try {
                        consumerJava.consumeKeys(publicKeyByteses);
                    } catch (InterruptedException e) {
                        throw new RuntimeException(e);
                    }
                }
            });
        }
    }

    private PublicKeyBytes[] createPublicKeyBytesArray() {
        ECKey ecKey = ECKey.fromPrivate(PRIVATE_KEY, false);
        PublicKeyBytes publicKeyBytes = new PublicKeyBytes(ecKey.getPrivKey(), ecKey.getPubKey());
        PublicKeyBytes[] publicKeyByteses = new PublicKeyBytes[ARRAY_SIZE];
        for (int i = 0; i < publicKeyByteses.length; i++) {
            publicKeyByteses[i] = publicKeyBytes;
        }
        return publicKeyByteses;
    }
}
