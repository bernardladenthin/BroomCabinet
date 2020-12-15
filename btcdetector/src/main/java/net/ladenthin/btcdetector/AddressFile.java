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
    public static final String ADDRESS_HEADER = "address";
    public final static String SEPARATOR = ",";

    public AddressFile(@Nonnull NetworkParameters networkParameters) {
        this.networkParameters = networkParameters;
        keyUtility = new KeyUtility(networkParameters, new ByteBufferUtility(true));
    }
    
    public void readFromFile(@Nonnull File file, ReadStatistic readStatistic, @Nonnull Consumer<AddressToCoin> addressConsumer) throws IOException {
        try (Scanner sc = new Scanner(new FileInputStream(file))) {

            while (sc.hasNextLine()) {
                String line = sc.nextLine();
                try {
                    AddressToCoin addressToCoin = AddressToCoin.fromBase58CSVLine(line, keyUtility);
                    if (addressToCoin != null) {
                        addressConsumer.accept(addressToCoin);
                        readStatistic.successful++;
                    } else {
                        readStatistic.unsupported++;
                    }
                } catch (Exception e) {
                    System.err.println("Error in line: " + line);
                    e.printStackTrace();
                    readStatistic.errors.add(line);
                }
            }
            sc.close();
        }
    }
}
