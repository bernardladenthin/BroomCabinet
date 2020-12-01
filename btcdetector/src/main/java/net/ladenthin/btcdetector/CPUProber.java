package net.ladenthin.btcdetector;

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
import net.ladenthin.btcdetector.configuration.ConsumerJava;
import net.ladenthin.btcdetector.configuration.ProducerJava;
import net.ladenthin.btcdetector.configuration.Sniffing;

public class CPUProber extends Prober {

    private final ProducerJava producerJava;
    private final ConsumerJava consumerJava;

    private final List<Future<Void>> producers = new ArrayList<>();

    public CPUProber(Sniffing sniffing) {
        super(sniffing.consumerJava);
        this.producerJava = sniffing.producerJava;
        this.consumerJava = sniffing.consumerJava;
    }

    @Override
    public void run() {
        initLMDB();
        addSchutdownHook();
        startConsumer();
        startProducer();
        startStatisticsTimer();
    }

    private void startProducer() {
        ExecutorService executor = Executors.newFixedThreadPool(producerJava.producerThreads);
        for (int i = 0; i < producerJava.producerThreads; i++) {
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
        int bitLength = producerJava.privateKeyBitLength;
        logger.info("Initialize random with seed: " + seed + ", bit length: " + bitLength);
        Random random = SecureRandom.getInstanceStrong();
        random.setSeed(seed);
        while (shouldRun.get()) {
            produceKey(bitLength, random);
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

}
