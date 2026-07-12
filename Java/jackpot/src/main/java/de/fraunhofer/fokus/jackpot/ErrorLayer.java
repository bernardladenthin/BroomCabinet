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
package de.fraunhofer.fokus.jackpot;

import de.fraunhofer.fokus.jackpot.interfaces.NotifyException;
import de.fraunhofer.fokus.jackpot.message.TError;
import de.fraunhofer.fokus.jackpot.messageprocessing.ParallelErrorInformant;

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
