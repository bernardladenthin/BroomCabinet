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

import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.util.Random;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;
import net.ladenthin.btcdetector.configuration.CProducerJava;
import net.ladenthin.btcdetector.configuration.CProducerOpenCL;
import net.ladenthin.btcdetector.configuration.CSniffing;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class Sniffer {

    protected Logger logger = LoggerFactory.getLogger(this.getClass());

    private final CSniffing sniffing;

    protected final AtomicBoolean shouldRun = new AtomicBoolean(true);

    private ConsumerJava consumerJava;

    public Sniffer(CSniffing sniffing) {
        this.sniffing = sniffing;
    }

    public void startRunner() {
        ExecutorService producerExecutorService = Executors.newCachedThreadPool();

        addSchutdownHook();

        if (sniffing.consumerJava != null) {
            consumerJava = new ConsumerJava(sniffing.consumerJava, shouldRun);
            consumerJava.initLMDB();
            consumerJava.startConsumer();
            consumerJava.startStatisticsTimer();
        }

        // It is already thread local, no need for {@link java.util.concurrent.ThreadLocalRandom}.
        final Random random;
        try {
            random = SecureRandom.getInstanceStrong();
        } catch (NoSuchAlgorithmException e) {
            throw new RuntimeException(e);
        }

        if (sniffing.producerJava != null) {
            for (CProducerJava cProducerJava : sniffing.producerJava) {
                ProducerJava producerJava = new ProducerJava(cProducerJava, shouldRun, consumerJava, consumerJava.keyUtility, random);
                producerJava.initProducers();
                producerExecutorService.submit(producerJava);
            }
        }

        if (sniffing.producerOpenCL != null) {
            for (CProducerOpenCL cProducerOpenCL : sniffing.producerOpenCL) {
                ProducerOpenCL producerOpenCL = new ProducerOpenCL(cProducerOpenCL, shouldRun, consumerJava, consumerJava.keyUtility, random);
                producerOpenCL.initProducers();
                producerExecutorService.submit(producerOpenCL);
            }
        }
    }

    protected void addSchutdownHook() {
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            shouldRun.set(false);
            consumerJava.timer.cancel();
            logger.info("Shut down, please wait for remaining tasks.");
        }));
    }

}
