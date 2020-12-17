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
 * https://privatekeys.pw/dash/address/XdAUmwtig27HBG6WfYyHAzP8n6XC9jESEw
 */
public class StaticDashP2PKHAddress {

    final public String publicAddress = "XdAUmwtig27HBG6WfYyHAzP8n6XC9jESEw";
    final public String publicKeyHash = "1b2a522cc8d42b0be7ceb8db711416794d50c846";
    
    final public ByteBuffer byteBuffer_publicKeyHash = new ByteBufferUtility(false).getByteBufferFromHex(publicKeyHash);
}
