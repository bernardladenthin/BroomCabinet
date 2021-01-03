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

import java.util.concurrent.atomic.AtomicBoolean;
import net.ladenthin.btcdetector.configuration.CSniffing;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class Sniffer implements Runnable  {

    protected Logger logger = LoggerFactory.getLogger(this.getClass());
    
    private final CSniffing sniffing;

    protected final AtomicBoolean shouldRun = new AtomicBoolean(true);
    
    private ConsumerJava consumerJava;
    private ProducerJava producerJava;

    public Sniffer(CSniffing sniffing) {
        this.sniffing = sniffing;
    }

    @Override
    public void run() {
        
        addSchutdownHook();
            
        if (sniffing.consumerJava != null) {
            consumerJava = new ConsumerJava(sniffing.consumerJava, shouldRun);
            consumerJava.initLMDB();
            consumerJava.startConsumer();
            consumerJava.startStatisticsTimer();
        }
        
        if (sniffing.producerJava != null) {
            producerJava = new ProducerJava(sniffing.producerJava, shouldRun, consumerJava, consumerJava.keyUtility);
            producerJava.startProducer();
        }
        
    }
    
    protected void addSchutdownHook() {
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            shouldRun.set(false);
            consumerJava.timer.cancel();
            logger.info("Shut down.");
        }));
    }

}
