// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.util;

import net.ladenthin.jackpot.message.TError;

/**
 *
 * @author bernard
 * @param <T>
 */
public interface NanoHandler<T> {

    /**
     *
     * @param transmission
     */
    public void handleTransmission(T transmission);

    /**
     *
     * @param t
     */
    public void handleError(TError t);
}
