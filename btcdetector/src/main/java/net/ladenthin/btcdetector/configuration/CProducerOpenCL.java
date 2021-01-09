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
package net.ladenthin.btcdetector.configuration;

import static org.jocl.CL.CL_DEVICE_TYPE_ALL;

public class CProducerOpenCL extends CProducer {

    public int platformIndex = 0;
    public long deviceType = CL_DEVICE_TYPE_ALL;
    public int deviceIndex = 0;
    
    public int maxResultReaderThreads = 4;
    /**
     * in ms.
     */
    public int delayBlockedReader = 2000;
}
