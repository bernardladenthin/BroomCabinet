// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.deserializer;

import java.lang.reflect.Type;

import com.google.gson.Gson;

/**
 * Gson implementation of a {@link Deserializer}.
 *
 * @author VSimRTI developer team <vsimrti@fokus.fraunhofer.de>
 * @author Bernard Ladenthin <bernard.ladenthin@fokus.fraunhofer.de>
 * @param <T>
 */
public class GsonDeserializer<T> extends Deserializer<T> {

    private final Gson gson = new Gson();
    private final static String CHARSET = "UTF-8";

    public GsonDeserializer(final Type messageType, Class<?> messageClass, final byte[] bytes) {
        super(messageType, messageClass, bytes);
    }

    @Override
    public T deserialize() throws Exception {
        final String s = new String(bytes, CHARSET);

        final T object = gson.fromJson(s, messageType);
        if (object == null) {
            throw new NullPointerException();
        }
        return object;
    }

}
