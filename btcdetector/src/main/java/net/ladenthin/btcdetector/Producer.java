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

import java.util.Random;

public interface Producer {

    /**
     * Start multiple producer threads to procue keys with
     * {@link #produceKeys(int, java.util.Random)} continuously.
     */
    void startProducers();

    /**
     * Create multiple keys for a specific bit length using {@link Random} and
     * push them to the {@link Consumer}.
     *
     * @param bitLength
     * @param random
     */
    void produceKeys(int bitLength, Random random);
}
