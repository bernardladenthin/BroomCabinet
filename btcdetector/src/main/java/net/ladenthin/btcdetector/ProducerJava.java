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

import org.bitcoinj.core.ECKey;
import java.math.BigInteger;
import java.util.Random;
import java.util.concurrent.atomic.AtomicBoolean;
import net.ladenthin.btcdetector.configuration.CProducerJava;

public class ProducerJava extends AbstractProducer {

    private final CProducerJava producerJava;

    public ProducerJava(CProducerJava producerJava, AtomicBoolean shouldRun, Consumer consumer, KeyUtility keyUtility, Random random) {
        super(shouldRun, consumer, keyUtility, random);
        this.producerJava = producerJava;
    }

    @Override
    public void initProducers() {
    }

    @Override
    public void produceKeys() {
        BigInteger secret = null;
        try {
            secret = keyUtility.createSecret(producerJava.privateKeyMaxNumBits, random);
            if (secret.equals(BigInteger.ZERO) || secret.equals(BigInteger.ONE)) {
                // ignore these, prevent an IllegalArgumentException
                return;
            }

            // create uncompressed
            ECKey ecKey = ECKey.fromPrivate(secret, false);
            PublicKeyBytes publicKeyBytes = new PublicKeyBytes(ecKey.getPrivKey(), ecKey.getPubKey());
            consumer.consumeKey(publicKeyBytes);
        } catch (Exception e) {
            logErrorInProduceKeys(e, secret);
        }
    }

}
