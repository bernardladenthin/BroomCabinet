// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.messageprocessing;

import net.ladenthin.jackpot.message.TError;

/**
 * Interface for a error informant.
 *
 * @author VSimRTI developer team <vsimrti@fokus.fraunhofer.de>
 * @author Bernard Ladenthin <bernard.ladenthin@fokus.fraunhofer.de>
 */
public interface ParallelErrorInformant {

    /**
     * Informed about the given message. <b>The implementation must ensure the sequential
     * processing.</b>
     *
     * @param error
     * The message to inform.
     */
    public void informError(TError error);
}
