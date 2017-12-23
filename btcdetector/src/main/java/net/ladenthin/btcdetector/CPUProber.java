package net.ladenthin.btcdetector;

import net.ladenthin.btcdetector.configuration.ProbeAddressesCPU;
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

public class CPUProber extends Prober {

    private final ProbeAddressesCPU probeAddressesCPU;

    private final List<Future<Void>> futures = new ArrayList<>();

    public CPUProber(ProbeAddressesCPU probeAddressesCPU) {
        super(probeAddressesCPU);
        this.probeAddressesCPU = probeAddressesCPU;
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
        if (probeAddressesCPU.selftestFirst) {
            checkPrivateKey(DumpedPrivateKey.fromBase58(networkParameters, selftestPrivateKeyAsWiF).getKey());
        }
    }

    private void startThreads() {
        ExecutorService executor = Executors.newFixedThreadPool(probeAddressesCPU.nThreads);
        for (int i = 0; i < probeAddressesCPU.nThreads; i++) {
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
                    Files.write(Paths.get(probeAddressesCPU.foundFile), (privateKeyAsWiF + "\n").getBytes(), StandardOpenOption.APPEND, StandardOpenOption.CREATE);
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


}
