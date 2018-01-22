package net.ladenthin.btcdetector.persistence.lmdb;

import net.ladenthin.btcdetector.Prober;
import net.ladenthin.btcdetector.configuration.LmdbConfigurationReadOnly;
import net.ladenthin.btcdetector.configuration.LmdbConfigurationWrite;
import net.ladenthin.btcdetector.persistence.Persistence;
import net.ladenthin.btcdetector.persistence.PersistenceUtils;
import org.bitcoinj.core.Address;
import org.bitcoinj.core.Coin;
import org.bitcoinj.core.Sha256Hash;
import org.lmdbjava.CursorIterator;
import org.lmdbjava.Dbi;
import org.lmdbjava.Env;
import org.lmdbjava.EnvFlags;
import org.lmdbjava.KeyRange;
import org.lmdbjava.Stat;
import org.lmdbjava.Txn;

import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.util.List;

import static org.lmdbjava.DbiFlags.MDB_CREATE;
import static org.lmdbjava.Env.create;

public class LMDBPersistence implements Persistence {

    private static final String DB_NAME_h160ToAmount = "h160ToAmount";
    private static final String DB_NAME_transactionHashToAddresses = "transactionHashToAddresses";
    private static final int DB_COUNT = 2;


    private final PersistenceUtils persistenceUtils;
    private final LmdbConfigurationWrite lmdbConfigurationWrite;
    private final LmdbConfigurationReadOnly lmdbConfigurationReadOnly;
    private Env<ByteBuffer> env;
    private Dbi<ByteBuffer> lmdb_h160ToAmount;
    private Dbi<ByteBuffer> lmdb_transactionHashToAddresses;

    public LMDBPersistence(LmdbConfigurationWrite lmdbConfigurationWrite, PersistenceUtils persistenceUtils) {
        this.lmdbConfigurationReadOnly = null;
        this.lmdbConfigurationWrite = lmdbConfigurationWrite;
        this.persistenceUtils = persistenceUtils;
    }

    public LMDBPersistence(LmdbConfigurationReadOnly lmdbConfigurationReadOnly, PersistenceUtils persistenceUtils) {
        this.lmdbConfigurationReadOnly = lmdbConfigurationReadOnly;
        lmdbConfigurationWrite = null;
        this.persistenceUtils = persistenceUtils;
    }

    @Override
    public void init() {
        if (lmdbConfigurationWrite != null) {
            // -Xmx10G -XX:MaxDirectMemorySize=5G
            // We always need an Env. An Env owns a physical on-disk storage file. One
            // Env can store many different databases (ie sorted maps).
            File lmdbDirectory = new File(lmdbConfigurationWrite.lmdbDirectory);
            lmdbDirectory.mkdirs();
            env = create()
                    // LMDB also needs to know how large our DB might be. Over-estimating is OK.
                    .setMapSize(lmdbConfigurationWrite.mapSizeInMiB * 1_024L * 1_024L)
                    // LMDB also needs to know how many DBs (Dbi) we want to store in this Env.
                    .setMaxDbs(DB_COUNT)
                    // Now let's open the Env. The same path can be concurrently opened and
                    // used in different processes, but do not open the same path twice in
                    // the same process at the same time.

                    //https://github.com/kentnl/CHI-Driver-LMDB
                    .open(lmdbDirectory, EnvFlags.MDB_NOSYNC, EnvFlags.MDB_NOMETASYNC, EnvFlags.MDB_WRITEMAP, EnvFlags.MDB_MAPASYNC);
            // We need a Dbi for each DB. A Dbi roughly equates to a sorted map. The
            // MDB_CREATE flag causes the DB to be created if it doesn't already exist.
            lmdb_h160ToAmount = env.openDbi(DB_NAME_h160ToAmount, MDB_CREATE);
            lmdb_transactionHashToAddresses = env.openDbi(DB_NAME_transactionHashToAddresses, MDB_CREATE);
        } else if (lmdbConfigurationReadOnly != null) {
            env = create().setMaxDbs(DB_COUNT).open(new File(lmdbConfigurationReadOnly.lmdbDirectory), EnvFlags.MDB_RDONLY_ENV);
            lmdb_h160ToAmount = env.openDbi(DB_NAME_h160ToAmount);
            lmdb_transactionHashToAddresses = env.openDbi(DB_NAME_transactionHashToAddresses);
        } else {
            throw new IllegalArgumentException();
        }
    }

    @Override
    public void close() {
        lmdb_h160ToAmount.close();
        lmdb_transactionHashToAddresses.close();
    }

    @Override
    public Coin getAmount(Address address) {
        try (Txn<ByteBuffer> txn = env.txnRead()) {
            ByteBuffer key = persistenceUtils.addressToByteBufferDirect(address);
            ByteBuffer byteBuffer = lmdb_h160ToAmount.get(txn, key);
            txn.close();

            Coin valueInDB = Coin.ZERO;
            if (byteBuffer != null) {
                valueInDB = Coin.valueOf(byteBuffer.getLong());
            }
            return valueInDB;
        }
    }

    @Override
    public void putTransaction(Sha256Hash transactionHash, List<Address> addresses) {
        ByteBuffer transactionHashByteBuffer = persistenceUtils.hashToByteBufferDirect(transactionHash);
        ByteBuffer hash160sByteBuffer = persistenceUtils.addressListToByteBufferDirect(addresses);
        try (Txn<ByteBuffer> txn = env.txnWrite()) {
            lmdb_transactionHashToAddresses.put(txn, transactionHashByteBuffer, hash160sByteBuffer);
            txn.commit();
            txn.close();
        }
    }

    @Override
    public void removeTransaction(Sha256Hash transactionHash) {
        ByteBuffer transactionHashByteBuffer = persistenceUtils.hashToByteBufferDirect(transactionHash);
        try (Txn<ByteBuffer> txn = env.txnWrite()) {
            lmdb_transactionHashToAddresses.delete(txn, transactionHashByteBuffer);
            txn.commit();
            txn.close();
        }
    }

    @Override
    public void writeAllAmounts(File file) throws IOException {
        try (Txn<ByteBuffer> txn = env.txnRead()) {
            try (CursorIterator<ByteBuffer> iterate = lmdb_h160ToAmount.iterate(txn, KeyRange.all())) {
                try (FileWriter writer = new FileWriter(file)) {
                    for (final CursorIterator.KeyVal<ByteBuffer> kv : iterate.iterable()) {
                        ByteBuffer addressAsByteBuffer = kv.key();
                        Address address = persistenceUtils.byteBufferToAddress(addressAsByteBuffer);
                        String line = address.toBase58() + Prober.CSV_SEPARATOR + kv.val().getLong() + System.lineSeparator();
                        writer.write(line);
                    }
                }
            }
        }
    }

    @Override
    public void changeAmount(Address address, Coin amountToChange) {
        Coin valueInDB = getAmount(address);
        Coin toWrite = valueInDB.add(amountToChange);
        putNewAmount(address, toWrite);
    }

    @Override
    public void putNewAmount(Address address, Coin toWrite) {
        ByteBuffer key = persistenceUtils.addressToByteBufferDirect(address);
        try (Txn<ByteBuffer> txn = env.txnWrite()) {
            if (lmdbConfigurationWrite.deleteEmptyAddresses && toWrite.isZero()) {
                lmdb_h160ToAmount.delete(txn, key);
            } else {
                lmdb_h160ToAmount.put(txn, key, persistenceUtils.longToByteBufferDirect(toWrite.longValue()));
            }
            txn.commit();
            txn.close();
        }
    }

    @Override
    public List<Address> getAddressesFromTransaction(Sha256Hash transactionHash) {
        ByteBuffer transactionHashByteBuffer = persistenceUtils.hashToByteBufferDirect(transactionHash);
        ByteBuffer hash160sByteBuffer;
        try (Txn<ByteBuffer> txn = env.txnRead()) {
            hash160sByteBuffer = lmdb_transactionHashToAddresses.get(txn, transactionHashByteBuffer);
            txn.close();
        }
        if (hash160sByteBuffer == null) {
            throw new RuntimeException("Transaction is not available: " + transactionHash);
        }
        List<Address> addresses = persistenceUtils.byteBufferToAddressList(hash160sByteBuffer);
        return addresses;
    }

    @Override
    public Coin getAllAmountsFromAddresses(List<Address> addresses) {
        Coin allAmounts = Coin.ZERO;
        for (Address address : addresses) {
            allAmounts = allAmounts.add(getAmount(address));
        }
        return allAmounts;
    }

    public Stat getStats() {
        return env.stat();
    }
}
