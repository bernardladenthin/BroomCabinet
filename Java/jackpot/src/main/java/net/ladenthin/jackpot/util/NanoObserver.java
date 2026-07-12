// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.util;

import net.ladenthin.jackpot.message.TError;
import java.util.Observable;
import java.util.Observer;

/**
 *
 * @author bernard
 * @param <T>
 */
public class NanoObserver<T> implements Observer {

    private final Class<T> clazz;
    private final NanoHandler<T> nh;

    public NanoObserver(final Class<T> clazz, final NanoHandler nh) {
        this.clazz = clazz;
        this.nh = nh;
    }

    @Override
    public void update(final Observable o, final Object arg) {
        if (arg == null) {
            return;
        }

        if (clazz.isAssignableFrom(arg.getClass())) {
            T t = (T) arg;
            nh.handleTransmission(t);
        } else if (TError.class.isAssignableFrom(arg.getClass())) {
            TError t = (TError) arg;
            nh.handleError(t);
        }
    }
    
}
