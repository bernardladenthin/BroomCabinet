package net.ladenthin.btcdetector;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.util.Scanner;
import java.util.function.Consumer;
import javax.annotation.Nonnull;
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

    public final void readFromFile(@Nonnull File file, @Nonnull Consumer<AddressToCoin> addressConsumer) throws IOException {
        try (Scanner sc = new Scanner(new FileInputStream(file))) {

            while (sc.hasNextLine()) {
                String line = sc.nextLine();
                AddressToCoin addressToCoin = AddressToCoin.fromBase58CSVLine(line, keyUtility);
                if (addressToCoin != null) {
                    addressConsumer.accept(addressToCoin);
                }
            }
            sc.close();
        }
    }
}
