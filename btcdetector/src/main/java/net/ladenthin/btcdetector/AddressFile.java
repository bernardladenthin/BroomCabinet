package net.ladenthin.btcdetector;

import java.io.File;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.util.Arrays;
import java.util.Deque;
import java.util.HashSet;
import java.util.LinkedList;
import java.util.Set;
import javax.annotation.Nonnull;
import javax.annotation.Nullable;
import net.ladenthin.javacommons.StreamHelper;
import org.bitcoinj.core.AddressFormatException;
import org.bitcoinj.core.ECKey;
import org.bitcoinj.core.LegacyAddress;
import org.bitcoinj.core.NetworkParameters;

public class AddressFile {

    @Nonnull
    private final NetworkParameters networkParameters;

    @Nonnull
    private KeyUtility keyUtility;

    public static final String IGNORE_LINE_PREFIX = "#";
    public final static String SEPARATOR = ",";

    public AddressFile(@Nonnull NetworkParameters networkParameters) {
        this.networkParameters = networkParameters;
        keyUtility = new KeyUtility(networkParameters, new ByteBufferUtility(false));
    }

    @Nonnull
    public final Set<ByteBuffer> readFromFile(@Nonnull File file) throws IOException {
        Set<ByteBuffer> addresses = new HashSet<>();

        String addressesToParse = new StreamHelper().readFullyAsUTF8String(file);
        String[] lines = addressesToParse.split("\\R");
        Deque<String> linesAsDeque = new LinkedList<>(Arrays.asList(lines));

        while (!linesAsDeque.isEmpty()) {
            String line = linesAsDeque.pop();
            ByteBuffer byteBuffer = fromBase58CSVLine(line);
            addresses.add(byteBuffer);
        }
        return addresses;
    }

    /**
     * Returns the hash160.
     */
    @Nullable
    public ByteBuffer fromBase58CSVLine(String line) {
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
            LegacyAddress.fromBase58(networkParameters, base58Address);
            final ByteBuffer hash160ByteBufferFromBase58String = keyUtility.getHash160ByteBufferFromBase58String(base58Address);
            return hash160ByteBufferFromBase58String;
        } catch (AddressFormatException afe) {
            return null;
        }
    }
}
