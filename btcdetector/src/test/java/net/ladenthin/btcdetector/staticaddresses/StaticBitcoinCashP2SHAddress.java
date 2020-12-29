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
 * https://privatekeys.pw/bitcoin-cash/address/prseh0a4aejjcewhc665wjqhppgwrz2lw5txgn666a
 */
public class StaticBitcoinCashP2SHAddress {

    final public String publicAddress = "prseh0a4aejjcewhc665wjqhppgwrz2lw5txgn666a";
    final public String scriptHash = "e19bbfb5ee652c65d7c6b54748170850e1895f75";
    
    final public ByteBuffer byteBuffer_scriptHash = new ByteBufferUtility(false).getByteBufferFromHex(scriptHash);
}
