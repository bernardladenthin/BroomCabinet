/**
 * Copyright 2013 Fraunhofer FOKUS
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
package de.fraunhofer.fokus.jackpot.messageprocessing;

import de.fraunhofer.fokus.jackpot.util.BinaryMessage;
import de.fraunhofer.fokus.jackpot.util.ParentEnsureFairProcessingSequence;

/**
 * Interface for a {@link BinaryMessage} handler.
 *
 * @author VSimRTI developer team <vsimrti@fokus.fraunhofer.de>
 * @author Bernard Ladenthin <bernard.ladenthin@fokus.fraunhofer.de>
 */
@Deprecated
public interface SequentialBinaryMessageTransmitter {

    /**
     * Handle the message.
     *
     * @param bbm
     * The message to handle.
     */
    @ParentEnsureFairProcessingSequence
    public void transmitMessage(BinaryMessage bbm);
}






























