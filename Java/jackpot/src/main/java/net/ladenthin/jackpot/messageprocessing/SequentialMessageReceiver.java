// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.messageprocessing;

/**
 * Interface for a message informant.
 *
 * @author VSimRTI developer team <vsimrti@fokus.fraunhofer.de>
 * @author Bernard Ladenthin <bernard.ladenthin@fokus.fraunhofer.de>
 */
public interface SequentialMessageReceiver<T> {

    /**
     * Informed about the given message. <b>The implementation must not ensure the sequential
     * processing.</b> The caller assumes the sequential call.
     *
     * @param tm
     * The message to inform.
     */
    public void receiveMessage(T tm);
}
