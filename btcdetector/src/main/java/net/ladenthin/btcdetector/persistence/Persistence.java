package net.ladenthin.btcdetector.persistence;

import org.bitcoinj.core.Coin;

import java.io.File;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.util.List;
import java.util.Map;

public interface Persistence {

    void init();
    void close();
    Coin getAmount(ByteBuffer hash160);
    boolean containsAddress(ByteBuffer hash160);

    void writeAllAmountsToAddressFile(File file) throws IOException;

    /**
     * @param hash160 the hash160 to change its amount
     * @param amountToChange positive means add, negative means substract the amount
     */
    void changeAmount(ByteBuffer hash160, Coin amountToChange);

    void putNewAmount(ByteBuffer hash160, Coin toWrite);
    void putAllAmounts(Map<ByteBuffer, Coin> amounts) throws IOException;

    Coin getAllAmountsFromAddresses(List<ByteBuffer> hash160s);
    
    String getStatsAsString();
}
