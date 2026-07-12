// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.serializer;

import java.lang.reflect.Type;

/**
 * Abstract Serializer.
 *
 * @author VSimRTI developer team <vsimrti@fokus.fraunhofer.de>
 * @author Bernard Ladenthin <bernard.ladenthin@fokus.fraunhofer.de>
 * @param <T>
 */
public abstract class Serializer<T> {

    protected final Type messageType;
    protected final Class<?> messageClass;
    protected final T msg;

    Serializer(final Type messageType, Class<?> messageClass, final T msg) {
        this.messageType = messageType;
        this.messageClass = messageClass;
        this.msg = msg;
    }

    public abstract byte[] serialize() throws Exception;

}
