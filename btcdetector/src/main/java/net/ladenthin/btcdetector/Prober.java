package net.ladenthin.btcdetector;

import net.ladenthin.btcdetector.configuration.ProbeAddresses;
import org.bitcoinj.core.NetworkParameters;
import org.bitcoinj.params.MainNetParams;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Timer;
import java.util.TimerTask;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;
import net.ladenthin.btcdetector.persistence.Persistence;
import net.ladenthin.btcdetector.persistence.PersistenceUtils;
import net.ladenthin.btcdetector.persistence.lmdb.LMDBPersistence;

public abstract class Prober implements Runnable {

    private static final int ONE_SECOND_IN_MILLISECONDS = 1000;
    public static final String MISS_PREFIX = "miss: Could not find the address: ";
    public static final String HIT_PREFIX = "hit: Found the address: ";

    protected Logger logger = LoggerFactory.getLogger(this.getClass());

    protected final NetworkParameters networkParameters = MainNetParams.get();
    protected final KeyUtility keyUtility = new KeyUtility(networkParameters, new ByteBufferUtility(false));
    protected final AtomicLong checkedKeys = new AtomicLong();
    protected final AtomicLong emptyConsumer = new AtomicLong();
    protected final AtomicLong hits = new AtomicLong();
    protected long startTime;

    protected final AtomicBoolean shouldRun = new AtomicBoolean(true);

    protected final ProbeAddresses probeAddresses;
    protected final Timer timer = new Timer();

    protected Persistence persistence;

    protected Prober(ProbeAddresses probeAddresses) {
        this.probeAddresses = probeAddresses;
    }

    void setLogger(Logger logger) {
        this.logger = logger;
    }

    protected void initLMDB() {
        PersistenceUtils persistenceUtils = new PersistenceUtils(networkParameters);
        persistence = new LMDBPersistence(probeAddresses.lmdbConfigurationReadOnly, persistenceUtils);
        persistence.init();
    }

    protected void startStatisticsTimer() {
        long period = probeAddresses.printStatisticsEveryNSeconds * ONE_SECOND_IN_MILLISECONDS;
        if (period <= 0) {
            throw new IllegalArgumentException("period must be greater than 0.");
        }
        startTime = System.currentTimeMillis();

        timer.scheduleAtFixedRate(new TimerTask() {
            @Override
            public void run() {
                // get transient information
                long uptime = System.currentTimeMillis() - startTime;
                long keys = checkedKeys.get();
                
                // calculate uptime
                long uptimeInSeconds = uptime / (long) ONE_SECOND_IN_MILLISECONDS;
                long uptimeInMinutes = uptimeInSeconds / 60;
                
                // calculate per time, prevent division by zero with Math.max
                long keysPerSecond = keys / Math.max(uptimeInSeconds, 1);
                long keysPerMinute = keys / Math.max(uptimeInMinutes, 1);
                
                // log the information
                logger.info("Statistics: Checked " + (keys / 1_000_000L) + "M keys in " + uptimeInMinutes + " minutes. [" + keysPerSecond + " keys/second] [" + keysPerMinute + " keys/minute]. " + emptyConsumer.get() + " times an empty consumer. " + hits.get() + " hits.");
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
