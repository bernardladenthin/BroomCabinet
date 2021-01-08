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
import java.nio.ByteBuffer;
import java.util.ArrayList;
import java.util.Arrays;
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
import org.apache.commons.codec.binary.Hex;
import org.bitcoinj.core.ECKey;

public class ConsumerJava implements Consumer {

    private static final int ONE_SECOND_IN_MILLISECONDS = 1000;
    public static final String MISS_PREFIX = "miss: Could not find the address: ";
    public static final String HIT_PREFIX = "hit: Found the address: ";
    public static final String HIT_SAFE_PREFIX = "hit: safe log: ";

    protected Logger logger = LoggerFactory.getLogger(this.getClass());

    protected final NetworkParameters networkParameters = MainNetParams.get();
    protected final KeyUtility keyUtility = new KeyUtility(networkParameters, new ByteBufferUtility(false));
    protected final AtomicLong checkedKeys = new AtomicLong();
    protected final AtomicLong checkedKeysSumOfTimeToCheckContains = new AtomicLong();
    protected final AtomicLong emptyConsumer = new AtomicLong();
    protected final AtomicLong hits = new AtomicLong();
    protected long startTime = 0;

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

    Logger getLogger() {
        return logger;
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

        timer.scheduleAtFixedRate(new TimerTask() {
            @Override
            public void run() {
                if (startTime == 0) {
                    startTime = System.currentTimeMillis();
                }
                // get transient information
                long uptime = Math.max(System.currentTimeMillis() - startTime,1);

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
        
        ByteBuffer threadLocalReuseableByteBuffer = ByteBuffer.allocateDirect(PublicKeyBytes.HASH160_SIZE);
        
        while (shouldRun.get()) {
            if (keysQueue.size() >= consumerJava.queueSize) {
                logger.warn("Attention, queue is full. Please increase queue size.");
            }
            try {
                consumeKeys(threadLocalReuseableByteBuffer);
                emptyConsumer.incrementAndGet();
                Thread.sleep(consumerJava.delayEmptyConsumer);
            } catch (InterruptedException e) {
                // we need to catch the exception to not break the thread
                logger.error("Ignore InterruptedException during Thread.sleep.", e);
            } catch (Exception e) {
                // log every Exception because it's hard to debug and we do not break down the thread loop
                logger.error("Error in consumeKeysRunner()." , e);
                e.printStackTrace();
            }
        }
        
        if (threadLocalReuseableByteBuffer != null) {
            ByteBufferUtility.freeByteBuffer(threadLocalReuseableByteBuffer);
        }
    }
    
    void consumeKeys(ByteBuffer threadLocalReuseableByteBuffer) {
        PublicKeyBytes[] publicKeyBytesArray = keysQueue.poll();
        while (publicKeyBytesArray != null) {
            for (PublicKeyBytes publicKeyBytes : publicKeyBytesArray) {
                if (publicKeyBytes.isInvalid()) {
                    continue;
                }
                byte[] hash160Uncompressed = publicKeyBytes.getUncompressedKeyHashFast();

                threadLocalReuseableByteBuffer.rewind();
                threadLocalReuseableByteBuffer.put(hash160Uncompressed);
                threadLocalReuseableByteBuffer.flip();

                boolean containsAddressUncompressed = containsAddress(threadLocalReuseableByteBuffer);

                byte[] hash160Compressed = publicKeyBytes.getCompressedKeyHashFast();
                threadLocalReuseableByteBuffer.rewind();
                threadLocalReuseableByteBuffer.put(hash160Compressed);
                threadLocalReuseableByteBuffer.flip();

                boolean containsAddressCompressed = containsAddress(threadLocalReuseableByteBuffer);

                if (consumerJava.runtimePublicKeyCalculationCheck) {
                    ECKey fromPrivateUncompressed = ECKey.fromPrivate(publicKeyBytes.getSecretKey(), false);
                    ECKey fromPrivateCompressed = ECKey.fromPrivate(publicKeyBytes.getSecretKey(), true);
                    if (!Arrays.equals(fromPrivateUncompressed.getPubKeyHash(), hash160Uncompressed)) {
                        throw new IllegalStateException("fromPrivateUncompressed.getPubKeyHash() != hash160Uncompressed");
                    }
                    if (!Arrays.equals(fromPrivateCompressed.getPubKeyHash(), hash160Compressed)) {
                        throw new IllegalStateException("fromPrivateCompressed.getPubKeyHash() != hash160Compressed");
                    }
                }

                if (containsAddressUncompressed) {
                    // immediately log the secret
                    safeLog(publicKeyBytes, hash160Uncompressed, hash160Compressed);
                    hits.incrementAndGet();
                    ECKey ecKeyUncompressed = ECKey.fromPrivateAndPrecalculatedPublic(publicKeyBytes.getSecretKey().toByteArray(), publicKeyBytes.getUncompressed());
                    String hitMessageUncompressed = HIT_PREFIX + keyUtility.createKeyDetails(ecKeyUncompressed);
                    logger.info(hitMessageUncompressed);
                }

                if (containsAddressCompressed) {
                    // immediately log the secret
                    safeLog(publicKeyBytes, hash160Uncompressed, hash160Compressed);
                    hits.incrementAndGet();
                    ECKey ecKeyCompressed = ECKey.fromPrivateAndPrecalculatedPublic(publicKeyBytes.getSecretKey().toByteArray(), publicKeyBytes.getCompressed());
                    String hitMessageCompressed = HIT_PREFIX + keyUtility.createKeyDetails(ecKeyCompressed);
                    logger.info(hitMessageCompressed);
                }

                if (!containsAddressUncompressed && !containsAddressCompressed) {
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
    
    /**
     * Try to log safe informations which may not thrown an exception.
     */
    private void safeLog(PublicKeyBytes publicKeyBytes, byte[] hash160Uncompressed, byte[] hash160Compressed) {
        logger.info(HIT_SAFE_PREFIX +"publicKeyBytes.getSecretKey(): " + publicKeyBytes.getSecretKey());
        logger.info(HIT_SAFE_PREFIX +"publicKeyBytes.getUncompressed(): " + Hex.encodeHexString(publicKeyBytes.getUncompressed()));
        logger.info(HIT_SAFE_PREFIX +"publicKeyBytes.getCompressed(): " + Hex.encodeHexString(publicKeyBytes.getCompressed()));
        logger.info(HIT_SAFE_PREFIX +"hash160Uncompressed: " + Hex.encodeHexString(hash160Uncompressed));
        logger.info(HIT_SAFE_PREFIX +"hash160Compressed: " + Hex.encodeHexString(hash160Compressed));
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
