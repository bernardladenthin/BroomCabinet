package net.ladenthin.btcdetector;

import java.nio.ByteBuffer;
import javax.annotation.Nullable;
import static net.ladenthin.btcdetector.AddressFile.IGNORE_LINE_PREFIX;
import static net.ladenthin.btcdetector.AddressFile.SEPARATOR;
import org.bitcoinj.core.AddressFormatException;
import org.bitcoinj.core.Coin;

public class AddressToCoin {
    private final ByteBuffer hash160;
    private final Coin coin;

    public AddressToCoin(ByteBuffer hash160, Coin coin) {
        this.hash160 = hash160;
        this.coin = coin;
    }

    public Coin getCoin() {
        return coin;
    }

    public ByteBuffer getHash160() {
        return hash160;
    }
    
    @Nullable
    public static AddressToCoin fromBase58CSVLine(String line, KeyUtility keyUtility) {
        String[] lineSplitted = line.split(SEPARATOR);
        String base58Address = lineSplitted[0];
        base58Address = base58Address.trim();
        if (base58Address.isEmpty() || base58Address.startsWith(IGNORE_LINE_PREFIX)) {
            return null;
        }
        if (base58Address.startsWith("bc1")) {
            return null;
        }
        try {
            final ByteBuffer hash160ByteBufferFromBase58String = keyUtility.getHash160ByteBufferFromBase58String(base58Address);

            Coin amount = Coin.SATOSHI;
            if (lineSplitted.length > 1) {
                String amountString = lineSplitted[1];
                amount = Coin.valueOf(Long.valueOf(amountString));
            }
            return new AddressToCoin(hash160ByteBufferFromBase58String, amount);
        } catch (AddressFormatException afe) {
            return null;
        }
    }
    
}
