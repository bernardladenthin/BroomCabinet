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

import java.math.BigInteger;
import java.util.Random;
import java.util.concurrent.atomic.AtomicBoolean;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public abstract class AbstractProducer implements Producer {

    protected Logger logger = LoggerFactory.getLogger(this.getClass());
    protected final AtomicBoolean shouldRun;
    protected final Consumer consumer;
    protected final KeyUtility keyUtility;
    protected final Random random;

    public AbstractProducer(AtomicBoolean shouldRun, Consumer consumer, KeyUtility keyUtility, Random random) {
        this.shouldRun = shouldRun;
        this.consumer = consumer;
        this.keyUtility = keyUtility;
        this.random = random;
    }

    @Override
    public void run() {
        while (shouldRun.get()) {
            produceKeys();
        }
    }
    
    /**
     * fromPrivate can throw an {@link IllegalArgumentException}.
     * @param secret the secret to be able to recover the issue
     */
    protected void logErrorInProduceKeys(Exception e, BigInteger secret) {
        logger.error("Error in produceKey for secret " + secret + ".", e);
    }
}
