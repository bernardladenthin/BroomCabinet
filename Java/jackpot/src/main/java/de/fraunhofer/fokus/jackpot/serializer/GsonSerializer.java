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
package de.fraunhofer.fokus.jackpot.serializer;

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
