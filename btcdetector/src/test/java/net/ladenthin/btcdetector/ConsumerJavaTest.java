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

import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

import java.io.IOException;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;
import net.ladenthin.btcdetector.configuration.CConsumerJava;
import net.ladenthin.btcdetector.configuration.CLMDBConfigurationReadOnly;
import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.is;
import org.mockito.ArgumentCaptor;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.atLeast;
import static org.mockito.Mockito.verify;
import org.slf4j.Logger;

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

        assertThat(arguments.get(0), is(equalTo("Statistics: [Checked 0 M keys in 0 minutes] [0 keys/second] [0 keys/minute] [Times an empty consumer: 0] [Average contains time: 0 ms] [Hits: 0]")));
    }

    @Test(expected = IllegalArgumentException.class)
    public void startStatisticsTimer_invalidparameter_throwsException() throws IOException {
        final AtomicBoolean shouldRun = new AtomicBoolean(true);
        
        CConsumerJava cConsumerJava = new CConsumerJava();
        cConsumerJava.printStatisticsEveryNSeconds = 0;
        
        ConsumerJava consumerJava = new ConsumerJava(cConsumerJava, shouldRun);
        consumerJava.startStatisticsTimer();
    }
}
