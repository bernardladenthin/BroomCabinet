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

import com.dyuproject.protostuff.LinkedBuffer;
import com.dyuproject.protostuff.ProtostuffIOUtil;
import com.dyuproject.protostuff.Schema;
import com.dyuproject.protostuff.runtime.RuntimeSchema;

/**
 * Protostuff implementation of a {@link Serializer}.
 *
 * @author VSimRTI developer team <vsimrti@fokus.fraunhofer.de>
 * @author Bernard Ladenthin <bernard.ladenthin@fokus.fraunhofer.de>
 * @param <T>
 * @date 07/20/2013
 */
public class ProtostuffSerializer<T> extends Serializer<T> {

    private final Schema<T> schema;
    private final static int bufferSize = 4096;//2^12
    private final LinkedBuffer buffer = LinkedBuffer.allocate(bufferSize);

    @SuppressWarnings("unchecked")
    public ProtostuffSerializer(final Type messageType, Class<?> messageClass, final T msg) {
        super(messageType, messageClass, msg);
        schema = (Schema<T>) RuntimeSchema.getSchema(messageClass);
    }

    @Override
    public byte[] serialize() throws Exception {
        final byte[] b;
        try {
            b = ProtostuffIOUtil.toByteArray(msg, schema, buffer);
        } finally {
            buffer.clear();
        }

        return b;
    }

}
