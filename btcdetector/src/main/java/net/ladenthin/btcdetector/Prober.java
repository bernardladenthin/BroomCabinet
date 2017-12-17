package net.ladenthin.btcdetector;

import net.ladenthin.btcdetector.configuration.ProbeAddresses;
import net.ladenthin.javacommons.StreamHelper;
import org.bitcoinj.core.*;
import org.bitcoinj.params.MainNetParams;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.File;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;
import java.util.*;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

public class Prober implements Runnable {

    public final static String CSV_SEPARATOR = ",";

    private final Logger logger = LoggerFactory.getLogger(Prober.class);
    private final Set<ByteBuffer> addresses = new HashSet<>();

    private final NetworkParameters networkParameters = MainNetParams.get();
    private final ProbeAddresses probeAddresses;

    private final AtomicLong generatedPrivateKeys = new AtomicLong();
    private final AtomicLong hits = new AtomicLong();
    private final long startTime = System.currentTimeMillis();
    private final List<Future<Void>> futures = new ArrayList<>();

    private final AtomicBoolean shouldRun = new AtomicBoolean(true);

    private final Object synchroizedWrite = new Object();

    private final static String selftestPrivateKeyAsWiF = "L3ij9REA2R8UQcVb7Vb8muLGN9J2N6TnDcCFgMRLT1ePCcDqqXnz";
    private final static String selftestPublicBase58 = "1CG6T3YWT2QmWY5DUcK8Stv2xbWu9Umiep";

    public Prober(ProbeAddresses probeAddresses) {
        this.probeAddresses = probeAddresses;
    }

    @Override
    public void run() {
        readAdresses();
        selftestFirst();
        addSchutdownHook();
        startThreads();
        startStatisticsTimer();
    }

    private void selftestFirst() {
        if (probeAddresses.selftestFirst) {
            checkPrivateKey(DumpedPrivateKey.fromBase58(networkParameters, selftestPrivateKeyAsWiF).getKey());
        }
    }

    private void addSchutdownHook() {
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            shouldRun.set(false);
            logger.info("Shut down.");
        }));
    }

    private void startStatisticsTimer() {
        Timer timer = new Timer();
        timer.scheduleAtFixedRate(new TimerTask() {
            @Override
            public void run() {
                long uptime = System.currentTimeMillis() - startTime;
                long keys = generatedPrivateKeys.get();
                // prevent division by zero in the statistics log
                long uptimeInSeconds = Math.max(uptime/1000, 1);
                logger.info("Statistics: Generated " + keys + " keys in " + uptimeInSeconds + " seconds. " + keys/uptimeInSeconds + " keys/second. " + hits.get() + " hits.");
            }
        }, 0, probeAddresses.printStatisticsEveryNSeconds * 1000);
    }

    private void startThreads() {
        ExecutorService executor = Executors.newFixedThreadPool(probeAddresses.nThreads);
        for (int i = 0; i < probeAddresses.nThreads; i++) {
            futures.add(executor.submit(
                    () -> {
                        tryToFindPrivateKey();
                        return null;
                    }));
        }
    }

    /**
     * This method runs in multiple threads.
     */
    private void tryToFindPrivateKey() {
        while(shouldRun.get()) {
            checkPrivateKey(new ECKey());
        }
    }

    /**
     * This method runs in multiple threads.
     */
    private void checkPrivateKey(ECKey key) {
        byte[] hash160 = key.getPubKeyHash();
        ByteBuffer hash160AsByteBuffer = hash160ToByteBuffer(hash160);
        generatedPrivateKeys.incrementAndGet();
        if (addresses.contains(hash160AsByteBuffer)) {
            hits.incrementAndGet();
            String privateKeyAsWiF = key.getPrivateKeyAsWiF(networkParameters);
            logger.info("HIT: Found a private key: " + privateKeyAsWiF);
            synchronized (synchroizedWrite) {
                try {
                    Files.write(Paths.get(probeAddresses.foundFile), (privateKeyAsWiF + "\n").getBytes(), StandardOpenOption.APPEND, StandardOpenOption.CREATE);
                } catch (IOException e) {
                    logger.error("Could not write private key to file.", e);
                }
            }
        } else {
            if (logger.isTraceEnabled()) {
                Address address = new Address(networkParameters, hash160);
                String base58 = address.toBase58();
                String privateKeyAsWiF = key.getPrivateKeyAsWiF(networkParameters);
                logger.trace("MISS: not found the public address "+base58+" for the private key: " + privateKeyAsWiF);
            }
        }
    }

    private ByteBuffer hash160ToByteBuffer(byte[] hash160) {
        // wrap() delivers a buffer which is already flipped
        ByteBuffer wrap = ByteBuffer.wrap(hash160);
        return wrap;
    }

    private ByteBuffer getHash160ByteBufferFromBase58String(String base58) {
        return hash160ToByteBuffer(Address.fromBase58(networkParameters, base58).getHash160());
    }

    private void readAdresses() {
        for (String addressFilePath : probeAddresses.addressesFiles ) {
            File addressFile = new File(addressFilePath);
            logger.info("Read address file: " + addressFile);
            try {
                String addressesToParse = new StreamHelper().readFullyAsUTF8String(addressFile);
                String[] lines = addressesToParse.split("\\R");
                for (String line : lines) {
                    String[] lineSplitted = line.split(CSV_SEPARATOR);
                    String address = lineSplitted[0];
                    address = address.trim();
                    if (address.isEmpty() || address.startsWith("#")) {
                        continue;
                    }
                    try {
                        addresses.add(getHash160ByteBufferFromBase58String(address));
                    } catch (AddressFormatException afe) {
                        logger.warn("Ignore address: " + address);
                    }
                }
                if(probeAddresses.selftestFirst) {
                    addresses.add(getHash160ByteBufferFromBase58String(selftestPublicBase58));
                }
                logger.info("Currently " + addresses.size() + " unique addresses.");
            } catch (IOException e) {
                throw new RuntimeException(e);
            }
        }
    }
}
