// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.serializer;

import java.lang.reflect.Type;

import com.google.gson.Gson;

/**
 * Gson implementation of a {@link Serializer}.
 *
 * @author VSimRTI developer team <vsimrti@fokus.fraunhofer.de>
 * @author Bernard Ladenthin <bernard.ladenthin@fokus.fraunhofer.de>
 * @param <T>
 */
public class GsonSerializer<T> extends Serializer<T> {

    private final Gson gson = new Gson();
    private final static String CHARSET = "UTF-8";

    public GsonSerializer(final Type messageType, Class<?> messageClass, final T msg) {
        super(messageType, messageClass, msg);
    }

    @Override
    public byte[] serialize() throws Exception {
        final String s = gson.toJson(msg, messageType);
        return s.getBytes(CHARSET);
    }

}
