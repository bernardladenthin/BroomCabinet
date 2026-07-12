// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.deserializer;

import java.lang.reflect.Type;

import com.dyuproject.protostuff.ProtostuffIOUtil;
import com.dyuproject.protostuff.Schema;
import com.dyuproject.protostuff.runtime.RuntimeSchema;

/**
 * Protostuff implementation of a {@link Deserializer}.
 *
 * @author VSimRTI developer team <vsimrti@fokus.fraunhofer.de>
 * @author Bernard Ladenthin <bernard.ladenthin@fokus.fraunhofer.de>
 * @param <T>
 */
public class ProtostuffDeserializer<T> extends Deserializer<T> {

    private final Schema<T> schema;

    @SuppressWarnings("unchecked")
    public ProtostuffDeserializer(final Type messageType, Class<?> messageClass, final byte[] bytes) {
        super(messageType, messageClass, bytes);
        schema = (Schema<T>) RuntimeSchema.getSchema(messageClass);
    }

    @Override
    public T deserialize() throws Exception {
        @SuppressWarnings("unchecked")
        
        T object = schema.newMessage();
        ProtostuffIOUtil.mergeFrom(bytes, object, schema);
        return object;
    }

}
