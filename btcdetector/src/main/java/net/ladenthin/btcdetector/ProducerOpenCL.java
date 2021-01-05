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
import java.security.SecureRandom;
import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.atomic.AtomicBoolean;
import net.ladenthin.btcdetector.configuration.CProducerOpenCL;

public class ProducerOpenCL extends AbstractProducer {

    private final CProducerOpenCL producerOpenCL;

    private final List<Future<Void>> producers = new ArrayList<>();
    private ThreadPoolExecutor resultReaderThreadPoolExecutor;

    public ProducerOpenCL(CProducerOpenCL producerOpenCL, AtomicBoolean shouldRun, Consumer consumer, KeyUtility keyUtility) {
        super(shouldRun, consumer, keyUtility);
        this.producerOpenCL = producerOpenCL;
    }

    @Override
    public void startProducers() {
        resultReaderThreadPoolExecutor = (ThreadPoolExecutor) Executors.newFixedThreadPool(producerOpenCL.resultReaderThreads);
        if (false) {
            for (int i = 0; i < producerOpenCL.resultReaderThreads; i++) {
                producers.add(resultReaderThreadPoolExecutor.submit(
                        () -> {
                            Random secureRandom = SecureRandom.getInstanceStrong();
                            long secureRandomSeed = secureRandom.nextLong();
                            produceKeysRunner(producerOpenCL.privateKeyBitLength, secureRandomSeed);
                            return null;
                        }));
            }
        }
    }

    @Override
    public void produceKeys(int bitLength, Random random) {
        BigInteger secret = null;
        try {
            // Specifically, any 256-bit number between 0x1 and 0xFFFF FFFF FFFF FFFF FFFF FFFF FFFF FFFE BAAE DCE6 AF48 A03B BFD2 5E8C D036 4141 is a valid private key.
            secret = keyUtility.createSecret(bitLength, random);
            if (secret.equals(BigInteger.ZERO) || secret.equals(BigInteger.ONE)) {
                // ignore these, prevent an IllegalArgumentException
                return;
            }

            // create uncompressed
            ECKey ecKey = ECKey.fromPrivate(secret, false);
            PublicKeyBytes publicKeyBytes = new PublicKeyBytes(ecKey.getPrivKey(), ecKey.getPubKey());
            consumer.consumeKey(publicKeyBytes);
        } catch (Exception e) {
            // fromPrivate can throw an IllegalArgumentException
            // save the secret to be able to recover the issue
            logger.error("Error in produceKey for secret " + secret + ".", e);
        }
    }

}
