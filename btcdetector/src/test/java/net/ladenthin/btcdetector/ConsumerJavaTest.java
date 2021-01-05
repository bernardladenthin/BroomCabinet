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

import com.tngtech.java.junit.dataprovider.DataProviderRunner;
import com.tngtech.java.junit.dataprovider.UseDataProvider;
import java.io.File;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

import java.io.IOException;
import java.util.List;
import java.util.Random;
import java.util.concurrent.atomic.AtomicBoolean;
import net.ladenthin.btcdetector.configuration.CConsumerJava;
import net.ladenthin.btcdetector.configuration.CLMDBConfigurationReadOnly;
import net.ladenthin.btcdetector.configuration.CProducerJava;
import net.ladenthin.btcdetector.staticaddresses.TestAddresses1337;
import net.ladenthin.btcdetector.staticaddresses.TestAddresses42;
import net.ladenthin.btcdetector.staticaddresses.TestAddressesFiles;
import net.ladenthin.btcdetector.staticaddresses.TestAddressesLMDB;
import org.bitcoinj.core.ECKey;
import org.bitcoinj.params.MainNetParams;
import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.is;
import org.junit.runner.RunWith;
import org.mockito.ArgumentCaptor;
import static org.mockito.Mockito.atLeast;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import org.slf4j.Logger;

@RunWith(DataProviderRunner.class)
public class ConsumerJavaTest {

    @Rule
    public TemporaryFolder folder = new TemporaryFolder();

    private ArgumentCaptor<String> logCaptor = ArgumentCaptor.forClass(String.class);

    @Test(expected = org.lmdbjava.LmdbNativeException.class)
    public void initLMDB_lmdbNotExisting_noExceptionThrown() throws IOException {
        final AtomicBoolean shouldRun = new AtomicBoolean(true);

        CConsumerJava cConsumerJava = new CConsumerJava();
        cConsumerJava.lmdbConfigurationReadOnly = new CLMDBConfigurationReadOnly();
        cConsumerJava.lmdbConfigurationReadOnly.lmdbDirectory = folder.newFolder().getAbsolutePath();

        ConsumerJava consumerJava = new ConsumerJava(cConsumerJava, shouldRun);
        consumerJava.initLMDB();
    }

    @Test
    public void startStatisticsTimer_noExceptionThrown() throws IOException, InterruptedException {
        final AtomicBoolean shouldRun = new AtomicBoolean(true);

        CConsumerJava cConsumerJava = new CConsumerJava();
        cConsumerJava.printStatisticsEveryNSeconds = 1;
        ConsumerJava consumerJava = new ConsumerJava(cConsumerJava, shouldRun);
        Logger logger = mock(Logger.class);
        consumerJava.setLogger(logger);

        // act
        consumerJava.startStatisticsTimer();

        // assert
        Thread.sleep(3900);
        consumerJava.timer.cancel();

        List<String> arguments = logCaptor.getAllValues();
        verify(logger, atLeast(3)).info(logCaptor.capture());

        assertThat(arguments.get(0), is(equalTo("Statistics: [Checked 0 M keys in 0 minutes] [0 k keys/second] [0 M keys/minute] [Times an empty consumer: 0] [Average contains time: 0 ms] [keys queue size: 0] [Hits: 0]")));
    }

    @Test(expected = IllegalArgumentException.class)
    public void startStatisticsTimer_invalidparameter_throwsException() throws IOException {
        final AtomicBoolean shouldRun = new AtomicBoolean(true);

        CConsumerJava cConsumerJava = new CConsumerJava();
        cConsumerJava.printStatisticsEveryNSeconds = 0;

        ConsumerJava consumerJava = new ConsumerJava(cConsumerJava, shouldRun);
        consumerJava.startStatisticsTimer();
    }

    @Test
    @UseDataProvider(value = CommonDataProvider.DATA_PROVIDER_COMPRESSED_AND_STATIC_AMOUNT, location = CommonDataProvider.class)
    public void runProber_testAddressGiven_hitExpected(boolean compressed, boolean useStaticAmount) throws IOException, InterruptedException {
        TestAddressesLMDB testAddressesLMDB = new TestAddressesLMDB();

        TestAddressesFiles testAddresses = new TestAddressesFiles(compressed);
        File lmdbFolderPath = testAddressesLMDB.createTestLMDB(folder, testAddresses, useStaticAmount);

        CConsumerJava cConsumerJava = new CConsumerJava();
        CProducerJava cProducerJava = new CProducerJava();
        cConsumerJava.lmdbConfigurationReadOnly = new CLMDBConfigurationReadOnly();
        cConsumerJava.lmdbConfigurationReadOnly.lmdbDirectory = lmdbFolderPath.getAbsolutePath();

        AtomicBoolean shouldRun = new AtomicBoolean(true);

        ConsumerJava consumerJava = new ConsumerJava(cConsumerJava, shouldRun);
        consumerJava.initLMDB();

        Random randomForProducer = new Random(TestAddresses42.RANDOM_SEED);
        ProducerJava producerJava = new ProducerJava(cProducerJava, shouldRun, consumerJava, consumerJava.keyUtility, randomForProducer);

        Logger logger = mock(Logger.class);
        consumerJava.setLogger(logger);
        producerJava.produceKeys();
        consumerJava.consumeKeys();

        // assert
        verify(logger, times(1)).info(logCaptor.capture());

        List<String> arguments = logCaptor.getAllValues();

        ECKey key = new TestAddresses42(1, compressed).getECKeys().get(0);
        KeyUtility keyUtility = new KeyUtility(MainNetParams.get(), new ByteBufferUtility(false));
        String hitMessage = ConsumerJava.HIT_PREFIX + keyUtility.createKeyDetails(key);
        assertThat(arguments.get(0), is(equalTo(hitMessage)));
    }

    @Test
    @UseDataProvider(value = CommonDataProvider.DATA_PROVIDER_COMPRESSED_AND_STATIC_AMOUNT, location = CommonDataProvider.class)
    public void runProber_unknownAddressGiven_missExpected(boolean compressed, boolean useStaticAmount) throws IOException, InterruptedException {
        TestAddressesLMDB testAddressesLMDB = new TestAddressesLMDB();

        TestAddressesFiles testAddresses = new TestAddressesFiles(compressed);
        File lmdbFolderPath = testAddressesLMDB.createTestLMDB(folder, testAddresses, useStaticAmount);

        CConsumerJava cConsumerJava = new CConsumerJava();
        CProducerJava cProducerJava = new CProducerJava();
        cConsumerJava.lmdbConfigurationReadOnly = new CLMDBConfigurationReadOnly();
        cConsumerJava.lmdbConfigurationReadOnly.lmdbDirectory = lmdbFolderPath.getAbsolutePath();

        AtomicBoolean shouldRun = new AtomicBoolean(true);

        ConsumerJava consumerJava = new ConsumerJava(cConsumerJava, shouldRun);
        consumerJava.initLMDB();

        Random randomForProducer = new Random(TestAddresses1337.RANDOM_SEED);
        ProducerJava producerJava = new ProducerJava(cProducerJava, shouldRun, consumerJava, consumerJava.keyUtility, randomForProducer);

        Logger logger = mock(Logger.class);
        when(logger.isTraceEnabled()).thenReturn(true);
        consumerJava.setLogger(logger);
        producerJava.produceKeys();
        consumerJava.consumeKeys();

        // assert
        verify(logger, times(2)).trace(logCaptor.capture());

        List<String> arguments = logCaptor.getAllValues();

        ECKey unknownKeyUncompressed = new TestAddresses1337(1, false).getECKeys().get(0);
        ECKey unknownKeyCompressed = new TestAddresses1337(1, true).getECKeys().get(0);
        KeyUtility keyUtility = new KeyUtility(MainNetParams.get(), new ByteBufferUtility(false));
        String missMessageUncompressed = ConsumerJava.MISS_PREFIX + keyUtility.createKeyDetails(unknownKeyUncompressed);
        String missMessageCompressed = ConsumerJava.MISS_PREFIX + keyUtility.createKeyDetails(unknownKeyCompressed);
        assertThat(arguments.get(0), is(equalTo(missMessageUncompressed)));
        assertThat(arguments.get(1), is(equalTo(missMessageCompressed)));
    }
}
