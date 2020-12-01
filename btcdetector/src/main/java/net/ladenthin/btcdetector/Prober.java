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
import net.ladenthin.btcdetector.configuration.ConsumerJava;
import net.ladenthin.btcdetector.persistence.Persistence;
import net.ladenthin.btcdetector.persistence.PersistenceUtils;
import net.ladenthin.btcdetector.persistence.lmdb.LMDBPersistence;
import org.bitcoinj.core.ECKey;

public abstract class Prober implements Runnable {

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

    protected final AtomicBoolean shouldRun = new AtomicBoolean(true);

    protected final ConsumerJava consumerJava;
    protected final Timer timer = new Timer();

    protected Persistence persistence;
    
    private final List<Future<Void>> consumers = new ArrayList<>();
    protected final LinkedBlockingQueue<ECKey> keysQueue;
    private final ByteBufferUtility byteBufferUtility = new ByteBufferUtility(true);

    protected Prober(ConsumerJava consumerJava) {
        this.consumerJava = consumerJava;
        this.keysQueue = new LinkedBlockingQueue<>(consumerJava.queueSize);
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

        String message = "Statistics: [Checked " + (keys / 1_000_000L) + " M keys in " + uptimeInMinutes + " minutes] [" + keysPerSecond + " keys/second] [" + keysPerMinute + " keys/minute] [Times an empty consumer: " + emptyConsumer + "] [Average contains time: " + averageContainsTime + " ms] [Hits: " + hits + "]";
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

    protected void addSchutdownHook() {
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            shouldRun.set(false);
            timer.cancel();
            logger.info("Shut down.");
        }));
    }
    

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
        ECKey key = keysQueue.poll();
        while (key != null) {

            byte[] hash160 = key.getPubKeyHash();
            ByteBuffer hash160AsByteBuffer = byteBufferUtility.byteArrayToByteBuffer(hash160);

            long timeBefore = System.currentTimeMillis();
            if (logger.isDebugEnabled()) {
                logger.debug("Time before persistence.containsAddress: " + timeBefore);
            }

            boolean containsAddress = persistence.containsAddress(hash160AsByteBuffer);
            // Free the buffer immediately, a direct buffer keeps a long time in memory otherwise.
            ByteBufferUtility.freeByteBuffer(hash160AsByteBuffer);

            long timeAfter = System.currentTimeMillis();
            long timeDelta = timeAfter - timeBefore;

            checkedKeys.incrementAndGet();
            checkedKeysSumOfTimeToCheckContains.addAndGet(timeDelta);

            if (logger.isDebugEnabled()) {
                logger.debug("Time after persistence.containsAddress: " + timeAfter);
                logger.debug("Time delta: " + timeDelta);
            }

            if (containsAddress) {
                hits.incrementAndGet();
                String hitMessage = HIT_PREFIX + keyUtility.createKeyDetails(key);
                logger.info(hitMessage);
            } else {
                if (logger.isTraceEnabled()) {
                    String missMessage = MISS_PREFIX + keyUtility.createKeyDetails(key);
                    logger.trace(missMessage);
                }
            }
            key = keysQueue.poll();
        }
    }
}
