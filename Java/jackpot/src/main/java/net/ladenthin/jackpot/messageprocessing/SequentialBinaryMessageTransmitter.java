// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.messageprocessing;

import net.ladenthin.jackpot.util.BinaryMessage;
import net.ladenthin.jackpot.util.ParentEnsureFairProcessingSequence;

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
