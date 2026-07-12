// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.messageprocessing;

import net.ladenthin.jackpot.message.TCommand;

/**
 * Interface for a message handler.
 *
 * @author VSimRTI developer team <vsimrti@fokus.fraunhofer.de>
 * @author Bernard Ladenthin <bernard.ladenthin@fokus.fraunhofer.de>
 */
public interface ParallelCommandHandler {

    /**
     * Handle the given command. <b>The implementation must ensure the sequential processing.</b>
     *
     * @param command
     * The command to handle.
     */
    public void handleCommand(TCommand command);
}
