// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.deserializer;

import java.lang.reflect.Type;

/**
 * Abstract Deserializer.
 *
 * @author VSimRTI developer team <vsimrti@fokus.fraunhofer.de>
 * @author Bernard Ladenthin <bernard.ladenthin@fokus.fraunhofer.de>
 * @param <T>
 */
public abstract class Deserializer<T> {

    protected final Type messageType;
    protected final Class<?> messageClass;
    protected final byte[] bytes;

    // protected final T typeObject = new T();

    Deserializer(final Type messageType, Class<?> messageClass, final byte[] bytes) {
        this.messageType = messageType;
        this.messageClass = messageClass;
        this.bytes = bytes;
    }

    public abstract T deserialize() throws Exception;

}
