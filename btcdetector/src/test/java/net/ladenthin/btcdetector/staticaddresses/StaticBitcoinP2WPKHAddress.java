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
 * https://privatekeys.pw/bitcoin/address/bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq
 */
public class StaticBitcoinP2WPKHAddress {

    final public String publicAddress = "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq";
    final public String publicKeyHash = "e8df018c7e326cc253faac7e46cdc51e68542c42";
    
    final public ByteBuffer byteBuffer_publicKeyHash = new ByteBufferUtility(false).getByteBufferFromHex(publicKeyHash);
}
