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
 * https://privatekeys.pw/litecoin/address/M8T1B2Z97gVdvmfkQcAtYbEepune1tzGua
 */
public class StaticLitecoinP2SHAddress {

    final public String publicAddress = "M8T1B2Z97gVdvmfkQcAtYbEepune1tzGua";
    final public String scriptHash = "0605bfbd71b78f7e9fc815fe9cc90aaeb1d9a728 ";
    
    final public ByteBuffer byteBuffer_scriptHash = new ByteBufferUtility(false).getByteBufferFromHex(scriptHash);
}
