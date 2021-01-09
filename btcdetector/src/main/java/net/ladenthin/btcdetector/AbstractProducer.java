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
import net.ladenthin.btcdetector.configuration.CProducer;
import org.apache.commons.codec.binary.Hex;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public abstract class AbstractProducer implements Producer {
    
    private final static int SLEEP_WAIT_TILL_RUNNING = 10;

    protected final static Logger logger = LoggerFactory.getLogger(AbstractProducer.class);
    
    protected final AtomicBoolean running = new AtomicBoolean(false);
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
        running.set(true);
        while (shouldRun.get()) {
            produceKeys();
        }
        running.set(false);
    }
    
    @Override
    public boolean isRunning() {
        return running.get();
    }
    
    /**
     * fromPrivate can throw an {@link IllegalArgumentException}.
     * @param secret the secret to be able to recover the issue
     */
    protected void logErrorInProduceKeys(Exception e, BigInteger secret) {
        logger.error("Error in produceKey for secret " + secret + ".", e);
    }

    @Override
    public void waitTillProducerNotRunning() {
        while(isRunning()) {
            try {
                Thread.sleep(SLEEP_WAIT_TILL_RUNNING);
            } catch (InterruptedException ex) {
            }
        }
    }

    public static BigInteger createSecretBase(CProducer cProducer, BigInteger secret) {
        BigInteger secretBase = cProducer.killBits(secret);
        
        if (logger.isTraceEnabled()) {
            logger.trace("secret: " + secret);
            logger.trace("secret as byte array: " + Hex.encodeHexString(secret.toByteArray()));
            logger.trace("killBits: " + Hex.encodeHexString(cProducer.getKillBits().toByteArray()));
            logger.trace("secretBase: " + secretBase);
            logger.trace("secretBase as byte array: " + Hex.encodeHexString(secretBase.toByteArray()));
        }

        return secretBase;
    }
    
    public static BigInteger calculateSecretKey(BigInteger secretBase, int keyNumber) {
        if (false) {
            // works also but a or might be faster
            return secretBase.add(BigInteger.valueOf(keyNumber));
        }
        return secretBase.or(BigInteger.valueOf(keyNumber));
    }
    
}
