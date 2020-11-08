package net.ladenthin.btcdetector;

import net.ladenthin.btcdetector.configuration.ProbeAddresses;
import net.ladenthin.javacommons.StreamHelper;
import org.bitcoinj.core.NetworkParameters;
import org.bitcoinj.params.MainNetParams;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.File;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.util.Arrays;
import java.util.Deque;
import java.util.HashSet;
import java.util.LinkedList;
import java.util.Set;
import java.util.Timer;
import java.util.TimerTask;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;
import org.bitcoinj.core.ECKey;
import org.bouncycastle.util.encoders.Hex;

public abstract class Prober implements Runnable {

    private static final int MILLISECONDS_TO_SECONDS = 1000;
    public static final String MISS_PREFIX = "miss: Could not find the address: ";
    public static final String HIT_PREFIX = "hit: Found the address: ";

    protected Logger logger = LoggerFactory.getLogger(this.getClass());
    protected final Set<ByteBuffer> addresses = new HashSet<>();

    protected final NetworkParameters networkParameters = MainNetParams.get();
    protected final KeyUtility keyUtility = new KeyUtility(networkParameters, new ByteBufferUtility(false));
    protected final AtomicLong checkedKeys = new AtomicLong();
    protected final AtomicLong emptyConsumer = new AtomicLong();
    protected final AtomicLong hits = new AtomicLong();
    protected long startTime;

    protected final AtomicBoolean shouldRun = new AtomicBoolean(true);

    protected final ProbeAddresses probeAddresses;
    protected final Timer timer = new Timer();

    protected Prober(ProbeAddresses probeAddresses) {
        this.probeAddresses = probeAddresses;
    }

    public Set<ByteBuffer> getAddresses() {
        return addresses;
    }

    void setLogger(Logger logger) {
        this.logger = logger;
    }

    protected void readAdresses() {
        for (String addressFilePath : probeAddresses.addressesFiles) {
            File addressFile = new File(addressFilePath);
            logger.info("Read address file: " + addressFile + " into memory.");
            try {
                String addressesToParse = new StreamHelper().readFullyAsUTF8String(addressFile);
                logger.info("Split address file: " + addressFile + " in memory.");
                String[] lines = addressesToParse.split("\\R");
                Deque<String> linesAsDeque = new LinkedList<>(Arrays.asList(lines));
                logger.info("Read address file: " + addressFile + " from memory. Parse now.");
                // do not booth, its not memory efficient
                addressesToParse = null;
                lines = null;
                while (!linesAsDeque.isEmpty()) {
                    String line = linesAsDeque.pop();
                    ByteBuffer byteBuffer = new AddressFile(networkParameters).fromBase58CSVLine(line);
                    addresses.add(byteBuffer);
                }
                logger.info("Currently " + addresses.size() + " unique addresses.");
            } catch (IOException e) {
                throw new RuntimeException(e);
            }
        }
    }

    protected void startStatisticsTimer() {
        long period = probeAddresses.printStatisticsEveryNSeconds * MILLISECONDS_TO_SECONDS;
        if (period < 1) {
            period = 60 * MILLISECONDS_TO_SECONDS;
        }
        startTime = System.currentTimeMillis();

        timer.scheduleAtFixedRate(new TimerTask() {
            @Override
            public void run() {
                long uptime = System.currentTimeMillis() - startTime;
                long keys = checkedKeys.get();
                // prevent division by zero in the statistics log
                long uptimeInSeconds = Math.max(uptime / (long) MILLISECONDS_TO_SECONDS, 1);
                long uptimeInMinutes = uptimeInSeconds / 60;
                logger.info("Statistics: Checked " + (keys / 1_000_000L) + "M keys in " + uptimeInMinutes + " minutes. [" + keys / uptimeInSeconds + " keys/second] ["+keys / uptimeInMinutes+" keys/minute]. " +emptyConsumer.get() + " times an empty consumer."+ hits.get() + " hits.");
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
}
