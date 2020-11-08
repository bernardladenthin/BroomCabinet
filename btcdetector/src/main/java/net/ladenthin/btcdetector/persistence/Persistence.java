package net.ladenthin.btcdetector.persistence;

import org.bitcoinj.core.LegacyAddress;
import org.bitcoinj.core.Coin;

import java.io.File;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.util.List;
import java.util.Map;

public interface Persistence {

    void init();
    void close();
    Coin getAmount(LegacyAddress address);
    boolean containsAddress(ByteBuffer hash160);

    void writeAllAmountsToAddressFile(File file) throws IOException;

    /**
     * @param amountToChange positive means add, negative means substract the amount
     */
    void changeAmount(LegacyAddress address, Coin amountToChange);

    void putNewAmount(LegacyAddress address, Coin toWrite);
    void putAllAmounts(Map<ByteBuffer, Coin> amounts) throws IOException;

    Coin getAllAmountsFromAddresses(List<LegacyAddress> addresses);
}
