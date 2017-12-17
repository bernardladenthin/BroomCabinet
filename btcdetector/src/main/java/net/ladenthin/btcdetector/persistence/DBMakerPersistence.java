package net.ladenthin.btcdetector.persistence;

import org.bitcoinj.core.Address;
import org.bitcoinj.core.Coin;
import org.bitcoinj.core.Sha256Hash;

import java.io.File;
import java.io.IOException;
import java.util.List;

public class DBMakerPersistence implements Persistence {

    @Override
    public void init() {
        /*
        // .readOnly()
        DB db = DBMaker.fileDB("Q:/MapDB/btc.db")
                .fileMmapEnable()            // Always enable mmap
                .fileMmapEnableIfSupported() // Only enable mmap on supported platforms
                .fileMmapPreclearDisable()   // Make mmap file faster

                // Unmap (release resources) file when its closed.
                // That can cause JVM crash if file is accessed after it was unmapped
                // (there is possible race condition).
                .cleanerHackEnable()
                .closeOnJvmShutdown()
                //.allocateStartSize( 10 * 1024*1024*1024)  // 10GB
                //.allocateIncrement(512 * 1024*1024)       // 512MB
                .make();
        HTreeMap<byte[], Long> adresses = db.hashMap("h", Serializer.BYTE_ARRAY, Serializer.LONG).createOrOpen();

        //Set<ByteBuffer> adresses2 = new HashSet<>();

        //DB db2 = DBMaker.memoryDirectDB().make();
        //adresses = db2.hashMap("h", Serializer.BYTE_ARRAY, Serializer.LONG).createOrOpen();
        */
    }

    @Override
    public void close() {
        /*
        db.commit();
        db.close();
        */
    }

    @Override
    public Coin getAmount(Address address) {
        return null;
    }

    @Override
    public void putTransaction(Sha256Hash transactionHash, List<Address> addresses) {

    }

    @Override
    public void removeTransaction(Sha256Hash transactionHash) {

    }

    @Override
    public void writeAllAmounts(File file) throws IOException {

    }

    @Override
    public void changeAmount(Address address, Coin amountToChange) {
        //adresses.put(toAddress.getHash160(), 0L);
        //adresses2.add(ByteBuffer.wrap(toAddress.getHash160()).asReadOnlyBuffer());
        //db.commit();
    }

    @Override
    public void putNewAmount(Address address, Coin toWrite) {

    }

    @Override
    public List<Address> getAddressesFromTransaction(Sha256Hash transactionHash) {
        return null;
    }

    @Override
    public Coin getAllAmountsFromAddresses(List<Address> addresses) {
        return null;
    }
}
