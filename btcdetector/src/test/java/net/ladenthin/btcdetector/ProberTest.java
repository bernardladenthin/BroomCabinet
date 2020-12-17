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
import net.ladenthin.btcdetector.configuration.CConsumerJava;
import net.ladenthin.btcdetector.configuration.CLMDBConfigurationReadOnly;

public class ProberTest {

    @Rule
    public TemporaryFolder folder = new TemporaryFolder();

    @Test(expected = org.lmdbjava.LmdbNativeException.class)
    public void initLMDB_lmdbNotExisting_noExceptionThrown() throws IOException {
        CConsumerJava consumerJava = new CConsumerJava();
        consumerJava.lmdbConfigurationReadOnly = new CLMDBConfigurationReadOnly();
        consumerJava.lmdbConfigurationReadOnly.lmdbDirectory = folder.newFolder().getAbsolutePath();

        ProberTestImpl prober = new ProberTestImpl(consumerJava);
        prober.initLMDB();
    }

    @Test
    public void addSchutdownHook_noExceptionThrown() throws IOException {
        CConsumerJava consumerJava = new CConsumerJava();
        ProberTestImpl prober = new ProberTestImpl(consumerJava);
        prober.addSchutdownHook();
    }

    @Test
    public void startStatisticsTimer_noExceptionThrown() throws IOException {
        CConsumerJava consumerJava = new CConsumerJava();
        ProberTestImpl prober = new ProberTestImpl(consumerJava);
        prober.startStatisticsTimer();
    }

    @Test(expected = IllegalArgumentException.class)
    public void startStatisticsTimer_invalidparameter_throwsException() throws IOException {
        CConsumerJava consumerJava = new CConsumerJava();
        consumerJava.printStatisticsEveryNSeconds = 0;
        ProberTestImpl prober = new ProberTestImpl(consumerJava);
        prober.startStatisticsTimer();
    }
}
