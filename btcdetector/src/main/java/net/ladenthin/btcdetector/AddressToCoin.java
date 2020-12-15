package net.ladenthin.btcdetector;

import com.github.kiulian.converter.AddressConverter;
import java.nio.ByteBuffer;
import java.util.Arrays;
import javax.annotation.Nullable;
import static net.ladenthin.btcdetector.AddressFile.IGNORE_LINE_PREFIX;
import static net.ladenthin.btcdetector.AddressFile.ADDRESS_HEADER;
import static net.ladenthin.btcdetector.AddressFile.SEPARATOR;
import org.bitcoinj.core.AddressFormatException;
import org.bitcoinj.core.Base58;
import static org.bitcoinj.core.Base58.decode;
import org.bitcoinj.core.Bech32;
import org.bitcoinj.core.Coin;
import org.bitcoinj.core.SegwitAddress;
import org.bitcoinj.core.Sha256Hash;
import org.bitcoinj.script.Script;
import org.bouncycastle.util.encoders.Hex;

public class AddressToCoin {

    private final ByteBuffer hash160;
    private final Coin coin;

    public static String TAB_SPLIT = "\t";

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

    @Override
    public String toString() {
        return new ByteBufferUtility(false).getHexFromByteBuffer(hash160);
    }

    @Nullable
    public static AddressToCoin fromBase58CSVLine(String line, KeyUtility keyUtility) {
        String[] lineSplitted = line.split(SEPARATOR + "|" + TAB_SPLIT);
        String address = lineSplitted[0];
        address = address.trim();
        if (address.isEmpty() || address.startsWith(IGNORE_LINE_PREFIX) || address.startsWith(ADDRESS_HEADER)) {
            return null;
        }
        
        if( address.startsWith("q")) {
            // q: bitcoin cash Base58 (P2PKH)
            // convert to legacy address
            address = AddressConverter.toLegacyAddress(address);
        }
        
        if (address.startsWith("d-") || address.startsWith("m-") || address.startsWith("s-")) {
            // blockchair format for Bitcoin (d-) and Bitcoin Cash (m-) and (s-) (P2MS)
            return null;
        } else if (address.startsWith("bc1")) {
            // bitcoin Bech32 (P2WPKH) or bitcoin Bech32 (P2WSH)
            Coin amount = getCoinIfExists(lineSplitted);
            SegwitAddress segwitAddress = SegwitAddress.fromBech32(keyUtility.networkParameters, address);
            if (segwitAddress.getOutputScriptType() == Script.ScriptType.P2WSH) {
                return null;
            }
            byte[] hash = segwitAddress.getHash();
            ByteBuffer hash160 = keyUtility.byteBufferUtility.byteArrayToByteBuffer(hash);
            return new AddressToCoin(hash160, amount);
        } else if (address.startsWith("ltc")) {
            // litecoin Bech32 (P2WPKH)
            //https://privatekeys.pw/litecoin/address/ltc1qd5wm03t5kcdupjuyq5jffpuacnaqahvfsdu8smf8z0u0pqdqpatqsdrn8h
            return null;
        } else if (address.startsWith("7") || address.startsWith("A") || address.startsWith("9") || address.startsWith("M") || address.startsWith("p")  ) {
            // 7: dash Base58 (P2SH)
            // A: dogecoin Base58 (P2SH)
            // 9: dogecoin Base58 (P2SH)
            // M: litecoin Base58 (P2SH)
            // p: bitcoin cash Base58 (P2SH)
            // it's a multisig dash address Base58 (P2SH) and we can't use script hash
            return null;
        } else if(address.startsWith("X") || address.startsWith("D")|| address.startsWith("L") ){
            // X: dash Base58 (P2PKH)
            // D: dogecoin Base58 (P2PKH)
            // L: litecoin Base58 (P2PKH)
            byte[] hash160 = getHash160fromBase58AddressUnchecked(address);
            ByteBuffer hash160AsByteBuffer = keyUtility.byteBufferUtility.byteArrayToByteBuffer(hash160);
            
            Coin amount = getCoinIfExists(lineSplitted);
            return new AddressToCoin(hash160AsByteBuffer, amount);
        } else {
            // bitcoin Base58 (P2PKH)
            ByteBuffer hash160 = keyUtility.getHash160ByteBufferFromBase58String(address);
            Coin amount = getCoinIfExists(lineSplitted);
            return new AddressToCoin(hash160, amount);

        }
    }
    
    public static byte[] getHash160fromBase58AddressUnchecked(String base58) {
        byte[] decoded = Base58.decode(base58);
        byte[] hash160 = new byte[20];
        System.arraycopy(decoded, 1, hash160, 0, hash160.length);
        return hash160;
    }

    private static Coin getCoinIfExists(String[] lineSplitted) throws NumberFormatException {
        Coin amount = Coin.SATOSHI;
        if (lineSplitted.length > 1) {
            String amountString = lineSplitted[1];
            amount = Coin.valueOf(Long.valueOf(amountString));
        }
        return amount;
    }

}
