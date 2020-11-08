package net.ladenthin.btcdetector;

import java.math.BigInteger;
import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import org.bitcoinj.core.ECKey;
import org.bitcoinj.core.LegacyAddress;
import org.bitcoinj.core.NetworkParameters;
import org.bitcoinj.params.MainNetParams;

public class TestAddresses {
    
    public final static int RANDOM_SEED = 42;

    public final NetworkParameters networkParameters = MainNetParams.get();

    Random random = new Random(RANDOM_SEED);

    private final List<ECKey> ecKeys = new ArrayList<>();

    public TestAddresses(int numberOfAddresses, boolean compressed) {
        for (int i = 0; i < numberOfAddresses; i++) {
            BigInteger secret = new KeyUtility(null, new ByteBufferUtility(false)).createSecret(random);
            ECKey ecKey = ECKey.fromPrivate(secret, compressed);
            ecKeys.add(ecKey);
        }
    }

    public List<ECKey> getECKeys() {
        return ecKeys;
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
