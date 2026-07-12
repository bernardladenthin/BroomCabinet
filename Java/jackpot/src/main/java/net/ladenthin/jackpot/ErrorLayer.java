// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot;

import net.ladenthin.jackpot.interfaces.NotifyException;
import net.ladenthin.jackpot.message.TError;
import net.ladenthin.jackpot.messageprocessing.ParallelErrorInformant;

/**
 * This is a centralized way to notify the upper layers of errors in the lower levels.
 * 
 * @author VSimRTI developer team <vsimrti@fokus.fraunhofer.de>
 * @author Bernard Ladenthin <bernard.ladenthin@fokus.fraunhofer.de>
 */
public class ErrorLayer implements NotifyException {

    private final ParallelErrorInformant parallelErrorInformant;

    public ErrorLayer(ParallelErrorInformant parallelErrorInformant) {
        this.parallelErrorInformant = parallelErrorInformant;
    }

    @Override
    public void notifyException(final Exception e) {
        parallelErrorInformant.informError(TError.fromThrowable(e));
    }

    /**
     * Notify the connection expired. This is always the last message.
     */
    public void notifyExpired() {
        final TError error = new TError();
        error.expired = true;
        parallelErrorInformant.informError(error);
    }

    /**
     * Notify there are no more transmissions on the input stream for the maximum waiting time.
     */
    public void notifyNoInAvailable() {
        final TError error = new TError();
        error.noInAvailable = true;
        parallelErrorInformant.informError(error);
    }

    /**
     * Notify
     */
    public void notifyNoConnectionPossible() {
        final TError error = new TError();
        error.noConnectionPossible = true;
        parallelErrorInformant.informError(error);
    }
}
