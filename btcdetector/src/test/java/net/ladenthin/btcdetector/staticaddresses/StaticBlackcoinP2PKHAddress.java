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

import java.nio.ByteBuffer;
import net.ladenthin.btcdetector.ByteBufferUtility;

/**
 * https://bitinfocharts.com/de/blackcoin/address/BF58Wm7hXSPXxfXm6HwrkWAr45qrZhNHJu
 */
public class StaticBlackcoinP2PKHAddress {

    final public String publicAddress = "BF58Wm7hXSPXxfXm6HwrkWAr45qrZhNHJu";
    final public String publicKeyHash = "7482a6aabd8e0bdb6d56a507a6f1352f7cc872fa";
    
    final public ByteBuffer byteBuffer_publicKeyHash = new ByteBufferUtility(false).getByteBufferFromHex(publicKeyHash);
}
