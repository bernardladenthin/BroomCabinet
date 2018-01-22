package net.ladenthin.btcdetector;

import net.ladenthin.btcdetector.configuration.BlockchainAnalysis;
import net.ladenthin.btcdetector.persistence.PersistenceUtils;
import net.ladenthin.btcdetector.persistence.lmdb.LMDBPersistence;
import net.ladenthin.javacommons.StreamHelper;
import org.bitcoinj.core.Address;
import org.bitcoinj.core.Block;
import org.bitcoinj.core.Coin;
import org.bitcoinj.core.Context;
import org.bitcoinj.core.NetworkParameters;
import org.bitcoinj.core.ScriptException;
import org.bitcoinj.core.Sha256Hash;
import org.bitcoinj.core.Transaction;
import org.bitcoinj.core.TransactionInput;
import org.bitcoinj.core.TransactionOutPoint;
import org.bitcoinj.core.TransactionOutput;
import org.bitcoinj.params.MainNetParams;
import org.bitcoinj.script.Script;
import org.bitcoinj.utils.BlockFileLoader;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.BufferedOutputStream;
import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.HashSet;
import java.util.LinkedList;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.Timer;
import java.util.TimerTask;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;

import static org.bitcoinj.utils.BlockFileLoader.getReferenceClientBlockFileList;

public class Analyser implements Runnable {

    public static final int ONE_SECOND_IN_MILLIS = 1000;
    private final Logger logger = LoggerFactory.getLogger(Analyser.class);

    private final static boolean useReferenceClientBlockFileList = false;

    private final static long zeroCoinValue = Coin.ZERO.getValue();

    // ##################################################
    // iterator for the blockchain
    private BlockIteratorByOrder blockIteratorByOrder;

    // ##################################################
    // parameter
    private final BlockchainAnalysis blockchainAnalysis;

    // ##################################################
    // bitcoinj
    private BlockFileLoader loader;
    private NetworkParameters networkParameters;

    // ##################################################
    // persistence
    private LMDBPersistence persistence;

    // ##################################################
    // statistics
    private final Timer timer = new Timer();
    private final AtomicReference<Statistics> statistics = new AtomicReference<>();
    private long startTime;
    private long endTime;
    private AtomicLong parsedBlocks = new AtomicLong();
    private AtomicLong lastParsedBlocks = new AtomicLong();
    private AtomicLong lastParsedTransactions = new AtomicLong();
    private AtomicLong lastStatisticsTime = new AtomicLong();
    private Block lastProcessedBlock = null;

    public Analyser(BlockchainAnalysis blockchainAnalysis) {
        this.blockchainAnalysis = blockchainAnalysis;
    }

    @Override
    public void run() {
        createNetworkParameter();
        PersistenceUtils persistenceUtils = new PersistenceUtils(networkParameters);
        logger.info("loadBlockchainFiles");
        loadBlockchainFiles();
        logger.info("persistence.init()");
        persistence = new LMDBPersistence(blockchainAnalysis.lmdbConfigurationWrite, persistenceUtils);
        persistence.init();
        startTime = System.currentTimeMillis();
        startStatisticsTimer();
        try {
            logger.info("#processBlocks");
            processBlocks();
        } catch (IOException e) {
            throw new RuntimeException(e);
        } finally {
            if (lastProcessedBlock != null) {
                System.out.println("Last processed block: " + lastProcessedBlock.getHash());
                try {
                    writeLastAnalyzedBlockHash(lastProcessedBlock.getHash());
                } catch (IOException e) {
                    logger.error("Could not write Last processed block.", e);
                }
            }
            logger.info("persistence.close()");
            persistence.close();
            endTime = System.currentTimeMillis();
            long duration = (endTime-startTime)/ONE_SECOND_IN_MILLIS;
            logger.info("Finished after " + duration + " seconds.");
            stopStatisticsTimer();
        }
    }

    private void startStatisticsTimer() {
        lastStatisticsTime.set(System.currentTimeMillis());

        timer.scheduleAtFixedRate(new TimerTask() {
            @Override
            public void run() {
                Statistics statistics = Analyser.this.statistics.get();
                if (statistics != null) {
                    long parsedBlocks = lastParsedBlocks.getAndSet(0);
                    long parsedTransactions = lastParsedTransactions.getAndSet(0);
                    long currentTime = System.currentTimeMillis();
                    long statisticsTime = lastStatisticsTime.getAndSet(currentTime);
                    // Math.max to prevent division by 0
                    long runtimeSinceLastStatisticsPrintInSeconds = Math.max((currentTime - statisticsTime) / ONE_SECOND_IN_MILLIS, 1L);
                    long blocksPerSecond = parsedBlocks / runtimeSinceLastStatisticsPrintInSeconds;
                    long transactionsPerSecond = parsedTransactions / runtimeSinceLastStatisticsPrintInSeconds;
                    logger.info("B/s: " + blocksPerSecond + ". T/s: " + transactionsPerSecond +". " + statistics);
                }
            }
        }, 0, blockchainAnalysis.printStatisticsEveryNSeconds * ONE_SECOND_IN_MILLIS);
    }

    private void stopStatisticsTimer() {
        timer.cancel();
    }

    private Sha256Hash readLastAnalyzedBlockHash() throws IOException {
        String lastAnalyzedBlockHash = new StreamHelper().readFullyAsUTF8String(new File(blockchainAnalysis.lastAnalyzedBlockHashFile));
        return Sha256Hash.wrap(lastAnalyzedBlockHash);
    }

    private void writeLastAnalyzedBlockHash(Sha256Hash hash) throws IOException {
        Files.write(Paths.get(blockchainAnalysis.lastAnalyzedBlockHashFile), hash.toString().getBytes(), StandardOpenOption.WRITE, StandardOpenOption.CREATE);
    }

    private void processBlocks() throws IOException {
        if (new File(blockchainAnalysis.lastAnalyzedBlockHashFile).exists()) {
            logger.debug("blockchainAnalysis.lastAnalyzedBlockHashFile != null");
            Sha256Hash lastAnalyzedBlockHash = readLastAnalyzedBlockHash();
            logger.info("Skip till block with hash: " + lastAnalyzedBlockHash);
            while(blockIteratorByOrder.blocksAvailable()) {
                Block block = blockIteratorByOrder.pop();
                if (lastAnalyzedBlockHash.equals(block.getHash())) {
                    break;
                } else {
                    if (logger.isTraceEnabled()) {
                        logger.trace("Skip block with hash: " + block.getHash());
                    }
                }
            }
            logger.info("Skipped finish.");
        }

        logger.info("iterate over all remaining blocks ...");
        while(blockIteratorByOrder.blocksAvailable()) {
            lastProcessedBlock = blockIteratorByOrder.pop();
            List<Transaction> transactions = lastProcessedBlock.getTransactions();
            for (Transaction transaction : transactions) {
                Sha256Hash hash = transaction.getHash();
                statistics.set(new Statistics(hash, lastProcessedBlock.getTime()));
                debugBreakpointForSomeTransactionHashes(transaction);
                processInputs(hash, transaction.getInputs());
                processOutputs(hash, transaction.getOutputs());
                lastParsedTransactions.incrementAndGet();
            }
            parsedBlocks.incrementAndGet();
            lastParsedBlocks.incrementAndGet();
        }
        logger.info("iterate over all blocks done");
    }

    private void debugBreakpointForSomeTransactionHashes(Transaction transaction) {
        String hash = transaction.getHash().toString();
        if (hash.equals("4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b")) {
            logger.debug("First created coins. Block 0.");
        } else if (hash.equals("f4184fc596403b9d638783cf57adfe4c75c605f6356fbc91338530e9831e9e16")) {
            logger.debug("First transaction.");
        } else if (hash.equals("6f7cf9580f1c2dfb3c4d5d043cdbb128c640e3f20161245aa7372e9666168516")) {
            logger.debug("A normal transaction from one address to two other addresses.");
        } else if( hash.equals("9fa5efd12e4bdba914bf1acd03981c6e31eabaa8a8bd85fc2be36afe5a787c06")) {
            logger.debug("test hash found");
        } else if (hash.equals("7992c1381e5dd6350435ee0cb251a237e19b9e81674e053b1ff1073429591b06")) {
            logger.debug("test hash found");
        } else if (hash.equals("7b998228a004b2d8b2728b01f88fee4bd26f99423e3a72340ca7382451975c00")) {
            logger.debug("test hash found");
        } else if (hash.equals("50cfd3361f7162b3c0c00dacd3d0e4ddf61e8ec0c51bfa54c4ca0e61876810a9")) {
            logger.debug("test hash found");
        } else if (hash.equals("72fff71e772fdba1864f2425dda6c197ed6f8792b5ed164ba4150df7076a53cd")) {
            logger.debug("test hash found");
        } else if(hash.equals("c76185a13474dfa4cc82ec9577960eaf5e6d2380b49ab9f8e30675e237d39923")) {
            logger.debug("A normal transaction from one address to two other addresses.");
        }
    }

    private void processOutputs(Sha256Hash transactionHash, List<TransactionOutput> outputs) {
        List<Address> allOutputAddresses = new ArrayList<>();
        for (TransactionOutput output : outputs) {
            try {
                Script scriptPubKey = output.getScriptPubKey();
                Address toAddress = scriptPubKey.getToAddress(networkParameters, true);
                allOutputAddresses.add(toAddress);
                persistence.changeAmount(toAddress, output.getValue());
            } catch(ScriptException e) {
                // https://blockchain.info/tx/e411dbebd2f7d64dafeef9b14b5c59ec60c36779d43f850e5e347abee1e1a455
                // not able to decode address
            } catch (IllegalArgumentException e) {
                //  https://blockchain.info/tx/b728387a3cf1dfcff1eef13706816327907f79f9366a7098ee48fc0c00ad2726
                // java.lang.IllegalArgumentException: Invalid point encoding 0x-8
                // at org.spongycastle.math.ec.ECCurve.decodePoint(ECCurve.java:396)
                // at org.bitcoinj.core.ECKey.fromPublicOnly(ECKey.java:311)
                // at org.bitcoinj.script.Script.getToAddress(Script.java:366)
            } catch (RuntimeException e) {
                printErrorInTransaction(transactionHash, "#processOutputs");
                e.printStackTrace();
            }
        }
        if (logger.isTraceEnabled()) {
            logger.trace("#putTransactionToAddresses : " + transactionHash + " to: " + allOutputAddresses);
        }
        persistence.putTransaction(transactionHash, allOutputAddresses);
    }

    private void processInputs(Sha256Hash transactionHash, List<TransactionInput> inputs) {
        for (TransactionInput input : inputs) {
            try {
                if (input.isCoinBase()) {
                    // created coins from nothing, no need to substract from an address
                    continue;
                }

                TransactionOutPoint transactionOutPoint = input.getOutpoint();
                if (transactionOutPoint != null) {
                    Sha256Hash transactionOutPointHash = transactionOutPoint.getHash();
                    // gather coins from this out point transaction
                    List<Address> addressesFromTransaction = persistence.getAddressesFromTransaction(transactionOutPointHash);
                    if (false) {
                        // currently not needed
                        Coin allAmountsFromAddresses = persistence.getAllAmountsFromAddresses(addressesFromTransaction);
                    }
                    for (Address address : addressesFromTransaction) {
                        persistence.putNewAmount(address, Coin.ZERO);
                    }
                    // do not delete transaction at this point, the following is possible:
                    // https://blockchain.info/de/address/12cbQLTFMXRnSzktFkuoG3eHoMeFtpTu3S
                }

                if (false) {
                    Coin inputValue = input.getValue();
                    if (inputValue != null) {
                        // TODO: find an transaction similar like this and calculate correct the input: 56336a227949d2b510fd024bf39f3e1c72ea32302db69ed1aa9a8ef61a31387f
                        Address fromAddress = input.getFromAddress();
                        persistence.changeAmount(fromAddress, Coin.valueOf(-inputValue.getValue()));
                    }
                }

            } catch (RuntimeException e) {
                printErrorInTransaction(transactionHash, "#processInputs");
                e.printStackTrace();
            }
        }
    }

    private void printErrorInTransaction(Sha256Hash transactionHash, String msg) {
        logger.error("Error: in transaction: " + transactionHash +  ". " + msg);
    }

    private void writeHash(BufferedOutputStream bos, byte[] hash160) throws IOException {
        bos.write(hash160);
    }

    private void createNetworkParameter() {
        networkParameters = MainNetParams.get();
        Context.getOrCreate(networkParameters);
    }

    private void loadBlockchainFiles() {
        List<File> blockchainFiles;
        if (useReferenceClientBlockFileList) {
            blockchainFiles = getReferenceClientBlockFileList();
        } else {
            blockchainFiles = getBlockFileList(new File(blockchainAnalysis.blockchainDirectory));
        }
        loader = new BlockFileLoader(networkParameters, blockchainFiles);
        blockIteratorByOrder = new BlockIteratorByOrder(loader, stringSetToSha256HashSet(blockchainAnalysis.orphanedBlocks));
    }

    private Set<Sha256Hash> stringSetToSha256HashSet(Set<String> orphanedBlocks) {
        Set<Sha256Hash> orphanedBlocksAsSha256Hash = new HashSet<>();
        for (String orphanedBlock : orphanedBlocks) {
            orphanedBlocksAsSha256Hash.add(Sha256Hash.wrap(orphanedBlock));
        }
        return orphanedBlocksAsSha256Hash;
    }


    private List<File> getBlockFileList(File directory) {
        List<File> list = new LinkedList();
        int i = 0;

        while (true) {
            File file = new File(directory, String.format(Locale.US, "blk%05d.dat", new Object[]{Integer.valueOf(i)}));
            if (!file.exists()) {
                return list;
            }

            list.add(file);
            ++i;
        }
    }

    public static void sortByteArrayArray(byte arr[][]) {
        Comparator<byte[]> comparator = com.google.common.primitives.SignedBytes.lexicographicalComparator();
        Arrays.sort(arr, comparator);
    }

    public static int binSearch(byte arr[][], byte[] key) {
        Comparator<byte[]> comparator = com.google.common.primitives.SignedBytes.lexicographicalComparator();
        return Arrays.binarySearch(arr, key, comparator);
    }
}
