/*
 * Copyright 2014 Fraunhofer FOKUS.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package de.fraunhofer.fokus.jackpot.util;

import de.fraunhofer.fokus.jackpot.message.TError;
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
