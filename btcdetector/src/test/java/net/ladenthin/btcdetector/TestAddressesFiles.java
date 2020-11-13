package net.ladenthin.btcdetector;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import static net.ladenthin.btcdetector.TestAddresses.SEGWIT_PUBLIC_ADDRESS;
import org.bitcoinj.core.Coin;
import org.junit.rules.TemporaryFolder;

public class TestAddressesFiles {

    private final static String ADDRESS_FILE_ONE = "addressesOne.txt";
    private final static String ADDRESS_FILE_TWO = "addressesTwo.txt";
    private final static String ADDRESS_FILE_THREE = "addressesThree.txt";
    public final static int NUMBER_OF_ADRESSES = 5;

    public static final Coin amountFirstAddress = Coin.FIFTY_COINS;
    public static final Coin amountOtherAddresses = Coin.SATOSHI;

    public final static Coin[] AMOUNTS = {
        amountFirstAddress,
        amountOtherAddresses,
        amountOtherAddresses,
        amountOtherAddresses,
        amountOtherAddresses
    };

    private final boolean compressed;
    private final TestAddresses testAddresses;

    public TestAddressesFiles(boolean compressed) {
        this.compressed = compressed;
        testAddresses = new TestAddresses(NUMBER_OF_ADRESSES, compressed);
    }

    public List<String> createAddressesFiles(TemporaryFolder folder) throws IOException {
        File one = folder.newFile(ADDRESS_FILE_ONE);
        File two = folder.newFile(ADDRESS_FILE_TWO);
        File three = folder.newFile(ADDRESS_FILE_THREE);

        Files.write(one.toPath(), Arrays.asList(
                testAddresses.getIndexAsBase58String(0) + AddressFile.SEPARATOR + amountFirstAddress,
                testAddresses.getIndexAsBase58String(1) + AddressToCoin.TAB_SPLIT + amountOtherAddresses,
                testAddresses.getIndexAsBase58String(2)
        ));
        Files.write(two.toPath(), Arrays.asList(
                testAddresses.getIndexAsBase58String(3)
        ));
        Files.write(three.toPath(), Arrays.asList(
                "# Test",
                "1WrongAddressFormat",
                SEGWIT_PUBLIC_ADDRESS,
                testAddresses.getIndexAsBase58String(4)
        ));
        List<String> addresses = new ArrayList<>();
        addresses.add(one.getAbsolutePath());
        addresses.add(two.getAbsolutePath());
        addresses.add(three.getAbsolutePath());
        return addresses;
    }

}
