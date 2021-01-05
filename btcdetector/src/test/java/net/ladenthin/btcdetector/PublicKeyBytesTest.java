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

import org.junit.Test;

import java.io.IOException;
import net.ladenthin.btcdetector.staticaddresses.TestAddresses42;
import org.bitcoinj.core.ECKey;
import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.is;

public class PublicKeyBytesTest {

    @Test
    public void createPublicKeyBytes_publicKeyGiven_PublicKeyAndHashesEquals() throws IOException, InterruptedException {
        // arrange
        ECKey keyUncompressed = new TestAddresses42(1, false).getECKeys().get(0);
        ECKey keyCompressed = new TestAddresses42(1, true).getECKeys().get(0);
        
        // act
        PublicKeyBytes publicKeyBytes = new PublicKeyBytes(keyUncompressed.getPrivKey(), keyUncompressed.getPubKey());
        PublicKeyBytes publicKeyBytesGivenCompressed = new PublicKeyBytes(keyUncompressed.getPrivKey(), keyUncompressed.getPubKey(), keyCompressed.getPubKey());
        
        // assert
        assertThat(publicKeyBytes.getCompressed(), is(equalTo(keyCompressed.getPubKey())));
        assertThat(publicKeyBytes.getUncompressed(), is(equalTo(keyUncompressed.getPubKey())));
        
        assertThat(publicKeyBytes.getCompressedKeyHash(), is(equalTo(keyCompressed.getPubKeyHash())));
        assertThat(publicKeyBytes.getCompressedKeyHashFast(), is(equalTo(keyCompressed.getPubKeyHash())));
        
        assertThat(publicKeyBytesGivenCompressed.getCompressedKeyHash(), is(equalTo(keyCompressed.getPubKeyHash())));
        assertThat(publicKeyBytesGivenCompressed.getCompressedKeyHashFast(), is(equalTo(keyCompressed.getPubKeyHash())));
        assertThat(publicKeyBytesGivenCompressed.getUncompressedKeyHash(), is(equalTo(keyUncompressed.getPubKeyHash())));
        assertThat(publicKeyBytesGivenCompressed.getUncompressedKeyHashFast(), is(equalTo(keyUncompressed.getPubKeyHash())));
    }
}
