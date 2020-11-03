package net.ladenthin.btcdetector.persistence;

import org.bitcoinj.core.LegacyAddress;
import org.bitcoinj.core.Coin;
import org.bitcoinj.core.Sha256Hash;

import java.io.File;
import java.io.IOException;
import java.util.List;

public interface Persistence {

    void init();
    void close();
    Coin getAmount(LegacyAddress address);

    void putTransaction(Sha256Hash transactionHash, List<LegacyAddress> addresses);
    void removeTransaction(Sha256Hash transactionHash);

    void writeAllAmounts(File file) throws IOException;

    /**
     * @param amountToChange positive means add, negative means substract the amount
     */
    void changeAmount(LegacyAddress address, Coin amountToChange);

    void putNewAmount(LegacyAddress address, Coin toWrite);

    List<LegacyAddress> getAddressesFromTransaction(Sha256Hash transactionHash);

    Coin getAllAmountsFromAddresses(List<LegacyAddress> addresses);
}
