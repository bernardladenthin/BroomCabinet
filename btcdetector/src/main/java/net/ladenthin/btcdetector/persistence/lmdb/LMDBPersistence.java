package net.ladenthin.btcdetector.persistence.lmdb;

import net.ladenthin.btcdetector.persistence.Persistence;
import net.ladenthin.btcdetector.persistence.PersistenceUtils;
import org.bitcoinj.core.LegacyAddress;
import org.bitcoinj.core.Coin;
import org.lmdbjava.CursorIterable;
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
import java.util.Map;
import net.ladenthin.btcdetector.AddressFile;
import net.ladenthin.btcdetector.ByteBufferUtility;
import net.ladenthin.btcdetector.KeyUtility;
import net.ladenthin.btcdetector.configuration.LmdbConfigurationReadOnly;
import net.ladenthin.btcdetector.configuration.LmdbConfigurationWrite;

import static org.lmdbjava.DbiFlags.MDB_CREATE;
import static org.lmdbjava.Env.create;

public class LMDBPersistence implements Persistence {

    private static final String DB_NAME_HASH160_TO_COINT = "hash160toCoin";
    private static final int DB_COUNT = 2;

    private final PersistenceUtils persistenceUtils;
    private final LmdbConfigurationWrite lmdbConfigurationWrite;
    private final LmdbConfigurationReadOnly lmdbConfigurationReadOnly;
    private final KeyUtility keyUtility;
    private Env<ByteBuffer> env;
    private Dbi<ByteBuffer> lmdb_h160ToAmount;

    public LMDBPersistence(LmdbConfigurationWrite lmdbConfigurationWrite, PersistenceUtils persistenceUtils) {
        this.lmdbConfigurationReadOnly = null;
        this.lmdbConfigurationWrite = lmdbConfigurationWrite;
        this.persistenceUtils = persistenceUtils;
        this.keyUtility = new KeyUtility(persistenceUtils.networkParameters, new ByteBufferUtility(true));
    }

    public LMDBPersistence(LmdbConfigurationReadOnly lmdbConfigurationReadOnly, PersistenceUtils persistenceUtils) {
        this.lmdbConfigurationReadOnly = lmdbConfigurationReadOnly;
        lmdbConfigurationWrite = null;
        this.persistenceUtils = persistenceUtils;
        this.keyUtility = new KeyUtility(persistenceUtils.networkParameters, new ByteBufferUtility(true));
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
            lmdb_h160ToAmount = env.openDbi(DB_NAME_HASH160_TO_COINT, MDB_CREATE);
        } else if (lmdbConfigurationReadOnly != null) {
            env = create().setMaxDbs(DB_COUNT).open(new File(lmdbConfigurationReadOnly.lmdbDirectory), EnvFlags.MDB_RDONLY_ENV);
            lmdb_h160ToAmount = env.openDbi(DB_NAME_HASH160_TO_COINT);
        } else {
            throw new IllegalArgumentException();
        }
    }

    @Override
    public void close() {
        lmdb_h160ToAmount.close();
    }

    @Override
    public Coin getAmount(LegacyAddress address) {
        try (Txn<ByteBuffer> txn = env.txnRead()) {
            ByteBuffer key = keyUtility.addressToByteBuffer(address);
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
    public boolean containsAddress(ByteBuffer hash160) {
        try (Txn<ByteBuffer> txn = env.txnRead()) {
            ByteBuffer byteBuffer = lmdb_h160ToAmount.get(txn, hash160);
            txn.close();
            return byteBuffer != null;
        }
    }
    
    @Override
    public void writeAllAmountsToAddressFile(File file) throws IOException {
        try (Txn<ByteBuffer> txn = env.txnRead()) {
            try (CursorIterable<ByteBuffer> iterable = lmdb_h160ToAmount.iterate(txn, KeyRange.all())) {
                try (FileWriter writer = new FileWriter(file)) {
                    for (final CursorIterable.KeyVal<ByteBuffer> kv : iterable) {
                        ByteBuffer addressAsByteBuffer = kv.key();
                        LegacyAddress address = keyUtility.byteBufferToAddress(addressAsByteBuffer);
                        String line = address.toBase58() + AddressFile.SEPARATOR + kv.val().getLong() + System.lineSeparator();
                        writer.write(line);
                    }
                }
            }
        }
    }
    
    @Override
    public void putAllAmounts(Map<ByteBuffer, Coin> amounts) throws IOException {
        for (Map.Entry<ByteBuffer, Coin> entry : amounts.entrySet()) {
            LegacyAddress address = keyUtility.byteBufferToAddress(entry.getKey());
            putNewAmount(address, entry.getValue());
        }
    }

    @Override
    public void changeAmount(LegacyAddress address, Coin amountToChange) {
        Coin valueInDB = getAmount(address);
        Coin toWrite = valueInDB.add(amountToChange);
        putNewAmount(address, toWrite);
    }

    @Override
    public void putNewAmount(LegacyAddress address, Coin toWrite) {
        ByteBuffer key = keyUtility.addressToByteBuffer(address);
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
    public Coin getAllAmountsFromAddresses(List<LegacyAddress> addresses) {
        Coin allAmounts = Coin.ZERO;
        for (LegacyAddress address : addresses) {
            allAmounts = allAmounts.add(getAmount(address));
        }
        return allAmounts;
    }

    public Stat getStats() {
        return env.stat();
    }
}
