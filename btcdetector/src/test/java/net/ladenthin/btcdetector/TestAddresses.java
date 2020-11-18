package net.ladenthin.btcdetector;

import java.io.File;
import java.io.IOException;
import java.math.BigInteger;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Random;
import org.bitcoinj.core.Coin;
import org.bitcoinj.core.ECKey;
import org.bitcoinj.core.LegacyAddress;
import org.bitcoinj.core.NetworkParameters;
import org.bitcoinj.params.MainNetParams;
import org.junit.rules.TemporaryFolder;

public class TestAddresses {

    public final static int RANDOM_SEED = 42;
    
    public final static String[] SEED_42_UNCOMPRESSED_HASH160 = {
        "1BZVqUAK8KBbAL3r7wC3Chq8csTBYYCdZU",
        "1KYinnpkcc4KKNB8C73z9kgXCLpKdzor4V",
        "18DBt2Ght4y9nx69fXT7w8vVq9n5BqfRev",
        "15daqrFSG8d1EMfCWdWZWeZMSDFkqR834t",
        "1AK4RGZoDCsSwjx3zzPwo4nbFzrJapr9m9"
    };
    
    public final static String[] SEED_42_COMPRESSED_HASH160 = {
        "1AcXATyTTvLm12dpBiTxdDxCtHhFyPNS1C",
        "1N2BnKNAqBnNBv4EnmEtjFxoewZ5NBsbVm",
        "1FpKH5GHTwNqJuiHdgL4tJYNvxEMhGzcap",
        "142XRqAwF7Xy5owyHW7u6vCooyGusQYZF4",
        "1NsremZJgQWR4Vx4VARAUv4HLq9NbxPyYi"
    };

    public final NetworkParameters networkParameters = MainNetParams.get();

    public static final String SEGWIT_PUBLIC_ADDRESS = "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq";

    Random random = new Random(RANDOM_SEED);

    private final List<ECKey> ecKeys = new ArrayList<>();

    public TestAddresses(int numberOfAddresses, boolean compressed) {
        for (int i = 0; i < numberOfAddresses; i++) {
            BigInteger secret = new KeyUtility(null, new ByteBufferUtility(false)).createSecret(KeyUtility.BIT_LENGTH, random);
            ECKey ecKey = ECKey.fromPrivate(secret, compressed);
            ecKeys.add(ecKey);
        }
    }

    public List<ECKey> getECKeys() {
        return ecKeys;
    }

    public String getIndexAsBase58String(int index) {
        return LegacyAddress.fromKey(networkParameters, getECKeys().get(index)).toBase58();
    }

    public String getAsBase58Strings() {
        StringBuilder sb = new StringBuilder();
        List<ECKey> ecKeys = getECKeys();
        for (ECKey ecKey : ecKeys) {
            LegacyAddress address = LegacyAddress.fromKey(networkParameters, ecKey);
            String base58 = address.toBase58();
            sb.append(base58);
            sb.append(System.lineSeparator());
        }
        return sb.toString();
    }

}