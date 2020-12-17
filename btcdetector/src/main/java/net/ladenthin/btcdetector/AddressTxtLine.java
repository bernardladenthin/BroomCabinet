// @formatter:off
/**
 * Copyright 2020 Bernard Ladenthin bernard.ladenthin@gmail.com
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *    http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 */
// @formatter:on
package net.ladenthin.btcdetector;

import com.github.kiulian.converter.AddressConverter;
import java.nio.ByteBuffer;
import javax.annotation.Nullable;
import org.bitcoinj.core.Base58;
import org.bitcoinj.core.Coin;
import org.bitcoinj.core.SegwitAddress;
import org.bitcoinj.script.Script;

/**
 * Most txt files have a common format which uses Base58 address and separated anmount.
 */
public class AddressTxtLine {
    
    /**
     * Should not be {@link Coin#ZERO} because it can't be written to LMDB.
     */
    public static final Coin DEFAULT_COIN = Coin.SATOSHI;

    public static final String IGNORE_LINE_PREFIX = "#";
    public static final String ADDRESS_HEADER = "address";
    public static final String SEPARATOR = ",";
    public static final String TAB_SPLIT = "\t";

    /**
     * If no coins can be found in the line {@link #DEFAULT_COIN} is used.
     * @param line The line to parse.
     * @param keyUtility The {@link KeyUtility}.
     * @return Returns an {@link AddressToCoin} instance.
     */
    @Nullable
    public AddressToCoin fromLine(String line, KeyUtility keyUtility) {
        String[] lineSplitted = line.split(SEPARATOR + "|" + TAB_SPLIT);
        String address = lineSplitted[0];
        Coin amount = getCoinIfPossible(lineSplitted, DEFAULT_COIN);
        address = address.trim();
        if (address.isEmpty() || address.startsWith(IGNORE_LINE_PREFIX) || address.startsWith(ADDRESS_HEADER)) {
            return null;
        }

        if (address.startsWith("q")) {
            // q: bitcoin cash Base58 (P2PKH)
            // convert to legacy address
            address = AddressConverter.toLegacyAddress(address);
        }

        if (address.startsWith("d-") || address.startsWith("m-") || address.startsWith("s-")) {
            // blockchair format for Bitcoin (d-) and Bitcoin Cash (m-) and (s-) (P2MS)
            return null;
        } else if (address.startsWith("bc1")) {
            // bitcoin Bech32 (P2WPKH) or bitcoin Bech32 (P2WSH)
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
        } else if (address.startsWith("7") || address.startsWith("A") || address.startsWith("9") || address.startsWith("M") || address.startsWith("p")) {
            // 7: dash Base58 (P2SH)
            // A: dogecoin Base58 (P2SH)
            // 9: dogecoin Base58 (P2SH)
            // M: litecoin Base58 (P2SH)
            // p: bitcoin cash Base58 (P2SH)
            // it's a multisig dash address Base58 (P2SH) and we can't use script hash
            return null;
        } else if (address.startsWith("X") || address.startsWith("D") || address.startsWith("L")) {
            // X: dash Base58 (P2PKH)
            // D: dogecoin Base58 (P2PKH)
            // L: litecoin Base58 (P2PKH)
            byte[] hash160 = getHash160fromBase58AddressUnchecked(address);
            ByteBuffer hash160AsByteBuffer = keyUtility.byteBufferUtility.byteArrayToByteBuffer(hash160);
            return new AddressToCoin(hash160AsByteBuffer, amount);
        } else {
            // bitcoin Base58 (P2PKH)
            ByteBuffer hash160 = keyUtility.getHash160ByteBufferFromBase58String(address);
            return new AddressToCoin(hash160, amount);

        }
    }

    private byte[] getHash160fromBase58AddressUnchecked(String base58) {
        byte[] decoded = Base58.decode(base58);
        byte[] hash160 = new byte[20];
        System.arraycopy(decoded, 1, hash160, 0, hash160.length);
        return hash160;
    }

    @Nullable
    private Coin getCoinIfPossible(String[] lineSplitted, Coin defaultValue) throws NumberFormatException {
        if (lineSplitted.length > 1) {
            String amountString = lineSplitted[1];
            try {
                return Coin.valueOf(Long.valueOf(amountString));
            } catch (NumberFormatException e) {
                return defaultValue;
            }
        } else {
            return defaultValue;
        }
    }
}
