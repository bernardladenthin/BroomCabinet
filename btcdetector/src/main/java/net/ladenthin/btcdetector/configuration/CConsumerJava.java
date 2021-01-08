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
package net.ladenthin.btcdetector.configuration;

public class CConsumerJava {
    public CLMDBConfigurationReadOnly lmdbConfigurationReadOnly;
    public int printStatisticsEveryNSeconds = 60;
    public int threads = 1;
    /**
     * in ms.
     */
    public long delayEmptyConsumer = 10;
    public int queueSize = 100000;
    
    /**
     * Test during runtime if the key calculation is correct. Decreases massive the performance. Usefull if an OpenCL producer is used.
     */
    public boolean runtimePublicKeyCalculationCheck;
}
