package net.ladenthin.btcdetector;

import net.ladenthin.btcdetector.configuration.ProbeAddressesCPU;
import org.bitcoinj.core.ECKey;
import java.math.BigInteger;
import java.nio.ByteBuffer;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.LinkedBlockingQueue;

public class CPUProber extends Prober {

    private final ProbeAddressesCPU probeAddressesCPU;
    private final ByteBufferUtility byteBufferUtility = new ByteBufferUtility(true);

    private final List<Future<Void>> producers = new ArrayList<>();
    private final List<Future<Void>> consumers = new ArrayList<>();
    private final LinkedBlockingQueue<ECKey> keysQueue;

    public CPUProber(ProbeAddressesCPU probeAddressesCPU) {
        super(probeAddressesCPU);
        this.probeAddressesCPU = probeAddressesCPU;
        this.keysQueue = new LinkedBlockingQueue<>(probeAddressesCPU.queueSize);
    }

    @Override
    public void run() {
        initLMDB();
        addSchutdownHook();
        startConsumer();
        startProducer();
        startStatisticsTimer();
    }

    private void startConsumer() {
        ExecutorService executor = Executors.newFixedThreadPool(probeAddressesCPU.consumerThreads);
        for (int i = 0; i < probeAddressesCPU.consumerThreads; i++) {
            consumers.add(executor.submit(
                    () -> {
                        consumeKeysRunner();
                        return null;
                    }));
        }
    }

    private void startProducer() {
        ExecutorService executor = Executors.newFixedThreadPool(probeAddressesCPU.producerThreads);
        for (int i = 0; i < probeAddressesCPU.producerThreads; i++) {
            producers.add(executor.submit(
                    () -> {
                        SecureRandom secureRandom = new SecureRandom();
                        long secureRandomSeed = secureRandom.nextLong();
                        produceKeysRunner(secureRandomSeed);
                        return null;
                    }));
        }
    }

    /**
     * This method runs in multiple threads.
     */
    private void produceKeysRunner(long seed) throws NoSuchAlgorithmException {
        logger.trace("Start produceKeysRunner.");
        // It is already thread local, no need for {@link java.util.concurrent.ThreadLocalRandom}.
        int bitLength = probeAddressesCPU.bitLength;
        logger.info("Initialize random with seed: " + seed + ", bit length: " + bitLength);
        Random random = SecureRandom.getInstanceStrong();
        random.setSeed(seed);
        while (shouldRun.get()) {
            produceKey(bitLength, random);
        }
    }

    /**
     * This method runs in multiple threads.
     */
    private void consumeKeysRunner() {
        logger.trace("Start consumeKeysRunner.");
        while (shouldRun.get()) {
            if (keysQueue.size() >= probeAddressesCPU.queueSize) {
                logger.warn("Attention, queue is full. Please increase queue size.");
            }
            consumeKeys();
            emptyConsumer.incrementAndGet();
            try {
                Thread.sleep(probeAddressesCPU.delayEmptyConsumer);
            } catch (InterruptedException e) {
                // we need to catch the exception to not break the thread
                logger.error("Ignore InterruptedException during Thread.sleep.", e);
            }
        }
    }

    void produceKey(int bitLength, Random random) {
        BigInteger secret = null;
        try {
            // Specifically, any 256-bit number between 0x1 and 0xFFFF FFFF FFFF FFFF FFFF FFFF FFFF FFFE BAAE DCE6 AF48 A03B BFD2 5E8C D036 4141 is a valid private key.
            secret = keyUtility.createSecret(bitLength, random);
            if (secret.equals(BigInteger.ZERO) || secret.equals(BigInteger.ONE)) {
                // ignore these, prevent an IllegalArgumentException
                return;
            }

            // create uncompressed
            ECKey ecKeyCompressed = ECKey.fromPrivate(secret, true);
            keysQueue.put(ecKeyCompressed);

            // create compressed
            ECKey ecKey = ecKeyCompressed.decompress();
            keysQueue.put(ecKey);
        } catch (Exception e) {
            // fromPrivate can throw an IllegalArgumentException
            // save the secret to be able to recover the issue
            logger.error("Error in produceKey for secret " + secret + ".", e);
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
