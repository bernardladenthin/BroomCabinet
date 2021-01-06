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

import java.nio.ByteBuffer;
import java.util.ArrayList;
import java.util.List;
import org.bitcoinj.core.NetworkParameters;
import org.bitcoinj.params.MainNetParams;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Timer;
import java.util.TimerTask;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;
import net.ladenthin.btcdetector.configuration.CConsumerJava;
import net.ladenthin.btcdetector.persistence.Persistence;
import net.ladenthin.btcdetector.persistence.PersistenceUtils;
import net.ladenthin.btcdetector.persistence.lmdb.LMDBPersistence;
import org.bitcoinj.core.ECKey;

public class ConsumerJava implements Consumer {

    private static final int ONE_SECOND_IN_MILLISECONDS = 1000;
    public static final String MISS_PREFIX = "miss: Could not find the address: ";
    public static final String HIT_PREFIX = "hit: Found the address: ";

    protected Logger logger = LoggerFactory.getLogger(this.getClass());

    protected final NetworkParameters networkParameters = MainNetParams.get();
    protected final KeyUtility keyUtility = new KeyUtility(networkParameters, new ByteBufferUtility(false));
    protected final AtomicLong checkedKeys = new AtomicLong();
    protected final AtomicLong checkedKeysSumOfTimeToCheckContains = new AtomicLong();
    protected final AtomicLong emptyConsumer = new AtomicLong();
    protected final AtomicLong hits = new AtomicLong();
    protected long startTime;

    protected final CConsumerJava consumerJava;
    protected final Timer timer = new Timer();

    protected Persistence persistence;
    
    private final List<Future<Void>> consumers = new ArrayList<>();
    protected final LinkedBlockingQueue<PublicKeyBytes[]> keysQueue;
    private final ByteBufferUtility byteBufferUtility = new ByteBufferUtility(true);
    private final AtomicBoolean shouldRun;

    protected ConsumerJava(CConsumerJava consumerJava, AtomicBoolean shouldRun) {
        this.consumerJava = consumerJava;
        this.keysQueue = new LinkedBlockingQueue<>(consumerJava.queueSize);
        this.shouldRun = shouldRun;
    }

    void setLogger(Logger logger) {
        this.logger = logger;
    }

    protected void initLMDB() {
        PersistenceUtils persistenceUtils = new PersistenceUtils(networkParameters);
        persistence = new LMDBPersistence(consumerJava.lmdbConfigurationReadOnly, persistenceUtils);
        persistence.init();
        logger.info("Stats: " + persistence.getStatsAsString());
    }

    private String createStatisticsMessage(long uptime, long keys, long keysSumOfTimeToCheckContains, long emptyConsumer, long hits) {
        // calculate uptime
        long uptimeInSeconds = uptime / (long) ONE_SECOND_IN_MILLISECONDS;
        long uptimeInMinutes = uptimeInSeconds / 60;
        // calculate per time, prevent division by zero with Math.max
        long keysPerSecond = keys / Math.max(uptimeInSeconds, 1);
        long keysPerMinute = keys / Math.max(uptimeInMinutes, 1);
        // calculate average contains time
        long averageContainsTime = keysSumOfTimeToCheckContains / Math.max(keys, 1);

        String message = "Statistics: [Checked " + (keys / 1_000_000L) + " M keys in " + uptimeInMinutes + " minutes] [" + (keysPerSecond/1_000L) + " k keys/second] [" + (keysPerMinute / 1_000_000L) + " M keys/minute] [Times an empty consumer: " + emptyConsumer + "] [Average contains time: " + averageContainsTime + " ms] [keys queue size: " + keysQueue.size() + "] [Hits: " + hits + "]";
        return message;
    }

    protected void startStatisticsTimer() {
        long period = consumerJava.printStatisticsEveryNSeconds * ONE_SECOND_IN_MILLISECONDS;
        if (period <= 0) {
            throw new IllegalArgumentException("period must be greater than 0.");
        }
        startTime = System.currentTimeMillis();

        timer.scheduleAtFixedRate(new TimerTask() {
            @Override
            public void run() {
                // get transient information
                long uptime = System.currentTimeMillis() - startTime;

                String message = createStatisticsMessage(uptime, checkedKeys.get(), checkedKeysSumOfTimeToCheckContains.get(), emptyConsumer.get(), hits.get());

                // log the information
                logger.info(message);
            }
        }, period, period);
    }

    @Override
    public void startConsumer() {
        ExecutorService executor = Executors.newFixedThreadPool(consumerJava.threads);
        for (int i = 0; i < consumerJava.threads; i++) {
            consumers.add(executor.submit(
                    () -> {
                        consumeKeysRunner();
                        return null;
                    }));
        }
    }
    
    /**
     * This method runs in multiple threads.
     */
    private void consumeKeysRunner() {
        logger.trace("Start consumeKeysRunner.");
        while (shouldRun.get()) {
            if (keysQueue.size() >= consumerJava.queueSize) {
                logger.warn("Attention, queue is full. Please increase queue size.");
            }
            consumeKeys();
            emptyConsumer.incrementAndGet();
            try {
                Thread.sleep(consumerJava.delayEmptyConsumer);
            } catch (InterruptedException e) {
                // we need to catch the exception to not break the thread
                logger.error("Ignore InterruptedException during Thread.sleep.", e);
            }
        }
    }
    
    void consumeKeys() {
        PublicKeyBytes[] publicKeyBytesArray = keysQueue.poll();
        while (publicKeyBytesArray != null) {
            for (PublicKeyBytes publicKeyBytes : publicKeyBytesArray) {
                byte[] hash160Uncompressed = publicKeyBytes.getUncompressedKeyHashFast();
                ByteBuffer hash160UncompressedAsByteBuffer = byteBufferUtility.byteArrayToByteBuffer(hash160Uncompressed);
                boolean containsAddressUncompressed = containsAddress(hash160UncompressedAsByteBuffer);

                byte[] hash160Compressed = publicKeyBytes.getCompressedKeyHashFast();
                ByteBuffer hash160CompressedAsByteBuffer = byteBufferUtility.byteArrayToByteBuffer(hash160Compressed);
                boolean containsAddressCompressed = containsAddress(hash160CompressedAsByteBuffer);
                
                // Free the buffer, a direct buffer keeps a long time in memory otherwise.
                ByteBufferUtility.freeByteBuffer(hash160UncompressedAsByteBuffer);
                ByteBufferUtility.freeByteBuffer(hash160CompressedAsByteBuffer);

                if (containsAddressUncompressed) {
                    hits.incrementAndGet();
                    ECKey ecKeyUncompressed = ECKey.fromPrivateAndPrecalculatedPublic(publicKeyBytes.getSecretKey().toByteArray(), publicKeyBytes.getUncompressed());
                    String hitMessageUncompressed = HIT_PREFIX + keyUtility.createKeyDetails(ecKeyUncompressed);
                    logger.info(hitMessageUncompressed);
                }

                if (containsAddressCompressed) {
                    hits.incrementAndGet();
                    ECKey ecKeyCompressed = ECKey.fromPrivateAndPrecalculatedPublic(publicKeyBytes.getSecretKey().toByteArray(), publicKeyBytes.getCompressed());
                    String hitMessageCompressed = HIT_PREFIX + keyUtility.createKeyDetails(ecKeyCompressed);
                    logger.info(hitMessageCompressed);
                }

                if(!containsAddressUncompressed && !containsAddressCompressed) {
                    if (logger.isTraceEnabled()) {
                        ECKey ecKeyUncompressed = ECKey.fromPrivateAndPrecalculatedPublic(publicKeyBytes.getSecretKey().toByteArray(), publicKeyBytes.getUncompressed());
                        String missMessageUncompressed = MISS_PREFIX + keyUtility.createKeyDetails(ecKeyUncompressed);
                        logger.trace(missMessageUncompressed);

                        ECKey ecKeyCompressed = ECKey.fromPrivateAndPrecalculatedPublic(publicKeyBytes.getSecretKey().toByteArray(), publicKeyBytes.getCompressed());
                        String missMessageCompressed = MISS_PREFIX + keyUtility.createKeyDetails(ecKeyCompressed);
                        logger.trace(missMessageCompressed);
                    }
                }
            }
            publicKeyBytesArray = keysQueue.poll();
        }
    }

    private boolean containsAddress(ByteBuffer hash160AsByteBuffer) {
        long timeBefore = System.currentTimeMillis();
        if (logger.isDebugEnabled()) {
            logger.debug("Time before persistence.containsAddress: " + timeBefore);
        }
        boolean containsAddress = persistence.containsAddress(hash160AsByteBuffer);
        long timeAfter = System.currentTimeMillis();
        long timeDelta = timeAfter - timeBefore;
        checkedKeys.incrementAndGet();
        checkedKeysSumOfTimeToCheckContains.addAndGet(timeDelta);
        if (logger.isDebugEnabled()) {
            logger.debug("Time after persistence.containsAddress: " + timeAfter);
            logger.debug("Time delta: " + timeDelta);
        }
        return containsAddress;
    }

    @Override
    public void consumeKeys(PublicKeyBytes[] publicKeyBytes) throws InterruptedException {
        keysQueue.put(publicKeyBytes);
    }
}
