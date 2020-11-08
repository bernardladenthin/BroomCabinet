package net.ladenthin.btcdetector;

import net.ladenthin.btcdetector.configuration.ProbeAddressesCPU;
import org.bitcoinj.core.ECKey;
import java.math.BigInteger;
import java.nio.ByteBuffer;
import java.security.SecureRandom;
import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

public class CPUProber extends Prober {

    private final ProbeAddressesCPU probeAddressesCPU;
    private final ByteBufferUtility byteBufferUtility = new ByteBufferUtility(false);

    private final List<Future<Void>> producers = new ArrayList<>();
    private final List<Future<Void>> consumers = new ArrayList<>();
    private final ConcurrentLinkedQueue<ECKey> keysQueue = new ConcurrentLinkedQueue<>();

    public CPUProber(ProbeAddressesCPU probeAddressesCPU) {
        super(probeAddressesCPU);
        this.probeAddressesCPU = probeAddressesCPU;
    }

    @Override
    public void run() {
        readAdresses();
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
    private void produceKeysRunner(long seed) {
        // It is already thread local, no need for {@link java.util.concurrent.ThreadLocalRandom}.
        logger.info("Initialize random with seed: " + seed);
        Random random = new Random(seed);
        while (shouldRun.get()) {
            produceKey(random);
        }
    }

    /**
     * This method runs in multiple threads.
     */
    private void consumeKeysRunner() throws InterruptedException {
        while (shouldRun.get()) {
            if (keysQueue.size() > 100_000) {
                logger.warn("Attention, queue size is above 100000. Please increase consumer threads.");
            }
            consumeKeys();
            emptyConsumer.incrementAndGet();
            Thread.sleep(probeAddressesCPU.delayEmptyConsumer);
        }
    }

    void produceKey(Random random) {
        BigInteger secret = keyUtility.createSecret(random);
        ECKey ecKeyCompressed = ECKey.fromPrivate(secret, true);
        keysQueue.add(ecKeyCompressed);
        ECKey ecKey = ecKeyCompressed.decompress();
        keysQueue.add(ecKey);
    }

    void consumeKeys() {
        ECKey key = keysQueue.poll();
        while (key != null) {

            byte[] hash160 = key.getPubKeyHash();
            ByteBuffer hash160AsByteBuffer = byteBufferUtility.byteArrayToByteBuffer(hash160);
            checkedKeys.incrementAndGet();
            if (addresses.contains(hash160AsByteBuffer)) {
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
