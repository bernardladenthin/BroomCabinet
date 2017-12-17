package net.ladenthin.btcdetector.persistence;

import org.bitcoinj.core.Address;
import org.bitcoinj.core.Coin;
import org.bitcoinj.core.Sha256Hash;

import java.io.File;
import java.io.IOException;
import java.util.List;

public interface Persistence {

    void init();
    void close();
    Coin getAmount(Address address);

    void putTransaction(Sha256Hash transactionHash, List<Address> addresses);
    void removeTransaction(Sha256Hash transactionHash);

    void writeAllAmounts(File file) throws IOException;

    /**
     * @param amountToChange positive means add, negative means substract the amount
     */
    void changeAmount(Address address, Coin amountToChange);

    void putNewAmount(Address address, Coin toWrite);

    List<Address> getAddressesFromTransaction(Sha256Hash transactionHash);

    Coin getAllAmountsFromAddresses(List<Address> addresses);
}
