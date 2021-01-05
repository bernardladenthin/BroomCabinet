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
package net.ladenthin.btcdetector.staticaddresses;

import java.math.BigInteger;
import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import net.ladenthin.btcdetector.ByteBufferUtility;
import net.ladenthin.btcdetector.KeyUtility;
import static net.ladenthin.btcdetector.staticaddresses.TestAddresses42.RANDOM_SEED;
import org.bitcoinj.core.ECKey;
import org.bitcoinj.core.LegacyAddress;
import org.bitcoinj.core.NetworkParameters;
import org.bitcoinj.params.MainNetParams;

public abstract class AbstractTestAddresses implements TestAddresses {
    
    public final NetworkParameters networkParameters = MainNetParams.get();

    private final List<ECKey> ecKeys = new ArrayList<>();
    
    public AbstractTestAddresses(int randomSeed, int numberOfAddresses, boolean compressed) {
        Random random = new Random(randomSeed);
        for (int i = 0; i < numberOfAddresses; i++) {
            BigInteger secret = new KeyUtility(null, new ByteBufferUtility(false)).createSecret(KeyUtility.BIT_LENGTH, random);
            ECKey ecKey = ECKey.fromPrivate(secret, compressed);
            ecKeys.add(ecKey);
        }
    }

    @Override
    public List<ECKey> getECKeys() {
        return ecKeys;
    }

    public String getIndexAsBase58String(int index) {
        return LegacyAddress.fromKey(networkParameters, getECKeys().get(index)).toBase58();
    }

    @Override
    public String getAsBase58Strings() {
        StringBuilder sb = new StringBuilder();
        List<String> base58StringList = getAsBase58StringList();
        for (String base58 : base58StringList) {
            sb.append(base58);
            sb.append(System.lineSeparator());
        }
        return sb.toString();
    }

    @Override
    public List<String> getAsBase58StringList() {
        List<String> base58Strings = new ArrayList<>();
        List<ECKey> ecKeys = getECKeys();
        for (ECKey ecKey : ecKeys) {
            LegacyAddress address = LegacyAddress.fromKey(networkParameters, ecKey);
            String base58 = address.toBase58();
            base58Strings.add(base58);
        }
        return base58Strings;
    }
}
