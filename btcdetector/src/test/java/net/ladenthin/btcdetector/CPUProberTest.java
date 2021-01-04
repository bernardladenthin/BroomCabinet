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
import net.ladenthin.btcdetector.staticaddresses.TestAddresses;
import net.ladenthin.btcdetector.staticaddresses.TestAddressesFiles;
import net.ladenthin.btcdetector.staticaddresses.TestAddressesLMDB;
import org.bitcoinj.core.ECKey;
import org.bitcoinj.params.MainNetParams;
import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.is;
import org.junit.runner.RunWith;
import org.mockito.ArgumentCaptor;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.times;
import org.slf4j.Logger;
import static org.mockito.Mockito.verify;

@RunWith(DataProviderRunner.class)
public class CPUProberTest {

    @Rule
    public TemporaryFolder folder = new TemporaryFolder();

    private ArgumentCaptor<String> logCaptor = ArgumentCaptor.forClass(String.class);

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

        ProducerJava producerJava = new ProducerJava(cProducerJava, shouldRun, consumerJava, consumerJava.keyUtility);

        ECKey key = TestAddresses.getFirstAddressHash160FromTestAddress(compressed);

        Logger logger = mock(Logger.class);
        consumerJava.setLogger(logger);
        Random randomForProducer = new Random(TestAddresses.RANDOM_SEED);
        producerJava.produceKeys(KeyUtility.BIT_LENGTH, randomForProducer);
        consumerJava.consumeKeys();

        KeyUtility keyUtility = new KeyUtility(MainNetParams.get(), new ByteBufferUtility(false));
        String hitMessage = ConsumerJava.HIT_PREFIX + keyUtility.createKeyDetails(key);

        verify(logger, times(1)).info(logCaptor.capture());

        List<String> arguments = logCaptor.getAllValues();

        assertThat(arguments.get(0), is(equalTo(hitMessage)));
    }
}
