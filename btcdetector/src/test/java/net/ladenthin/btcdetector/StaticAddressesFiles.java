package net.ladenthin.btcdetector;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import org.bitcoinj.core.Coin;
import org.junit.rules.TemporaryFolder;

public class StaticAddressesFiles implements AddressesFiles {

    private final static String ADDRESS_FILE_ONE = "staticAddressesFile.txt";
    
    public static final Coin amountOtherAddresses = Coin.SATOSHI;

    public StaticAddressesFiles() {
    }

    @Override
    public List<String> createAddressesFiles(TemporaryFolder folder) throws IOException {
        File one = folder.newFile(ADDRESS_FILE_ONE);

        Files.write(one.toPath(), Arrays.asList(
                new StaticBitcoinCashP2MSAddress().publicAddress,
                new StaticBitcoinCashP2MSXAddress().publicAddress,
                new StaticBitcoinCashP2PKHAddress().publicAddress,
                new StaticBitcoinCashP2SHAddress().publicAddress,
                new StaticBitcoinP2MSAddress().publicAddress,
                new StaticBitcoinP2WPKHAddress().publicAddress,
                new StaticBitcoinP2WSHAddress().publicAddress,
                new StaticDashP2PKHAddress().publicAddress,
                new StaticDashP2SHAddress().publicAddress,
                new StaticDogecoinP2PKHAddress().publicAddress,
                new StaticDogecoinP2SHAddress().publicAddress,
                new StaticDogecoinP2SHXAddress().publicAddress,
                new StaticLitecoinP2PKHAddress().publicAddress,
                new StaticLitecoinP2SHAddress().publicAddress
        ));
        List<String> addresses = new ArrayList<>();
        addresses.add(one.getAbsolutePath());
        return addresses;
    }

}
