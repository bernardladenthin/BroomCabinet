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

    public AddressFile(@Nonnull NetworkParameters networkParameters) {
        this.networkParameters = networkParameters;
        keyUtility = new KeyUtility(networkParameters, new ByteBufferUtility(true));
    }

    public void readFromFile(@Nonnull File file, ReadStatistic readStatistic, @Nonnull Consumer<AddressToCoin> addressConsumer) throws IOException {
        try (Scanner sc = new Scanner(new FileInputStream(file))) {

            AddressTxtLine addressTxtLine = new AddressTxtLine();
            while (sc.hasNextLine()) {
                String line = sc.nextLine();
                try {
                    AddressToCoin addressToCoin = addressTxtLine.fromLine(line, keyUtility);
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
