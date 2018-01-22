package net.ladenthin.btcdetector;

import net.ladenthin.btcdetector.configuration.ProbeAddresses;
import net.ladenthin.javacommons.StreamHelper;
import org.bitcoinj.core.Address;
import org.bitcoinj.core.AddressFormatException;
import org.bitcoinj.core.NetworkParameters;
import org.bitcoinj.params.MainNetParams;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.File;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.util.HashSet;
import java.util.Set;
import java.util.Timer;
import java.util.TimerTask;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

public abstract class Prober implements Runnable {
    public final static String CSV_SEPARATOR = ",";

    protected final Logger logger = LoggerFactory.getLogger(this.getClass());
    protected final Set<ByteBuffer> addresses = new HashSet<>();

    protected final NetworkParameters networkParameters = MainNetParams.get();
    protected final AtomicLong generatedPrivateKeys = new AtomicLong();
    protected final AtomicLong hits = new AtomicLong();
    protected final long startTime = System.currentTimeMillis();

    protected final AtomicBoolean shouldRun = new AtomicBoolean(true);

    protected final Object synchroizedWrite = new Object();

    protected final static String selftestPrivateKeyAsWiF = "L3ij9REA2R8UQcVb7Vb8muLGN9J2N6TnDcCFgMRLT1ePCcDqqXnz";
    protected final static String selftestPublicBase58 = "1CG6T3YWT2QmWY5DUcK8Stv2xbWu9Umiep";

    protected final ProbeAddresses probeAddresses;

    protected Prober(ProbeAddresses probeAddresses) {
        this.probeAddresses = probeAddresses;
    }

    protected void readAdresses() {
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

    protected ByteBuffer getHash160ByteBufferFromBase58String(String base58) {
        return hash160ToByteBuffer(Address.fromBase58(networkParameters, base58).getHash160());
    }

    protected ByteBuffer hash160ToByteBuffer(byte[] hash160) {
        // wrap() delivers a buffer which is already flipped
        ByteBuffer wrap = ByteBuffer.wrap(hash160);
        return wrap;
    }

    protected void startStatisticsTimer() {
        Timer timer = new Timer();
        int period = probeAddresses.printStatisticsEveryNSeconds;
        if (period < 1) {
            period = 1;
        }
        timer.scheduleAtFixedRate(new TimerTask() {
            @Override
            public void run() {
                long uptime = System.currentTimeMillis() - startTime;
                long keys = generatedPrivateKeys.get();
                // prevent division by zero in the statistics log
                long uptimeInSeconds = Math.max(uptime/1000, 1);
                logger.info("Statistics: Generated " + keys + " keys in " + uptimeInSeconds + " seconds. " + keys/uptimeInSeconds + " keys/second. " + hits.get() + " hits.");
            }
        }, 0, period * 1000);
    }

    protected void addSchutdownHook() {
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            shouldRun.set(false);
            logger.info("Shut down.");
        }));
    }
}