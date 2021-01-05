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

import java.io.IOException;
import java.math.BigInteger;
import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.atomic.AtomicBoolean;
import net.ladenthin.btcdetector.configuration.CProducerOpenCL;

public class ProducerOpenCL extends AbstractProducer {

    private final CProducerOpenCL producerOpenCL;

    private ThreadPoolExecutor resultReaderThreadPoolExecutor;
    private OpenCLContext openCLContext;

    public ProducerOpenCL(CProducerOpenCL producerOpenCL, AtomicBoolean shouldRun, Consumer consumer, KeyUtility keyUtility, Random random) {
        super(shouldRun, consumer, keyUtility, random);
        this.producerOpenCL = producerOpenCL;
    }

    @Override
    public void initProducers() {
        resultReaderThreadPoolExecutor = (ThreadPoolExecutor) Executors.newFixedThreadPool(producerOpenCL.maxResultReaderThreads);
        
        openCLContext = new OpenCLContext(producerOpenCL.platformIndex, producerOpenCL.deviceType, producerOpenCL.deviceIndex, producerOpenCL.gridNumBits);
        try {
            openCLContext.init();
        } catch (IOException e) {
            throw new RuntimeException(e);
        }
    }

    @Override
    public void produceKeys() {
        BigInteger secret = null;
        try {
            secret = keyUtility.createSecret(producerOpenCL.privateKeyMaxNumBits, random);
            if (secret.equals(BigInteger.ZERO) || secret.equals(BigInteger.ONE)) {
                // ignore these, prevent an IllegalArgumentException
                return;
            }

            final BigInteger threadLocalFinalSecret = secret;
            
            waitTillFreeThreadsInPool();
            OpenCLGridResult createKeys = openCLContext.createKeys(threadLocalFinalSecret);
            
            resultReaderThreadPoolExecutor.submit(
                () ->{
                    PublicKeyBytes[] publicKeys = createKeys.getPublicKeyBytes();
                    createKeys.freeResult();
                    for (PublicKeyBytes publicKeyBytes : publicKeys) {
                        try {
                            consumer.consumeKey(publicKeyBytes);
                        } catch (Exception e) {
                            logErrorInProduceKeys(e, threadLocalFinalSecret);
                        }
                    }
                }
            );
        } catch (Exception e) {
            logErrorInProduceKeys(e, secret);
        }
    }
    
    private void waitTillFreeThreadsInPool() throws InterruptedException {
        boolean waitMessageOnce = true;
        while(getFreeThreads() < 1) {
            Thread.sleep(producerOpenCL.delayBlockedReader);
            if (waitMessageOnce) {
                waitMessageOnce = false;
                logger.warn("No possible free threads to read OpenCL results. May increase maxResultReaderThreads.");
            }
        }
    }

    private int getFreeThreads() {
        return resultReaderThreadPoolExecutor.getMaximumPoolSize() - resultReaderThreadPoolExecutor.getActiveCount();
    }

}
