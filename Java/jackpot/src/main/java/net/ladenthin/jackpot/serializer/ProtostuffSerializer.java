// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.serializer;

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
