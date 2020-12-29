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
 * https://privatekeys.pw/dogecoin/address/9tp7THhBG3fNNFka1AJm95DU3E4x3pwQA3
 */
public class StaticDogecoinP2SHXAddress {

    final public String publicAddress = "9tp7THhBG3fNNFka1AJm95DU3E4x3pwQA3";
    final public String scriptHash = "1a11b73ad3dd99d77da9f858cf323205a84dd5da";
    
    final public ByteBuffer byteBuffer_scriptHash = new ByteBufferUtility(false).getByteBufferFromHex(scriptHash);
}
