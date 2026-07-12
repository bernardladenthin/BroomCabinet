// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.serializer;

import java.io.ByteArrayOutputStream;
import java.io.ObjectOutput;
import java.io.ObjectOutputStream;
import java.lang.reflect.Type;

/**
 * Pure java implementation of a {@link Serializer}.
 *
 * @author VSimRTI developer team <vsimrti@fokus.fraunhofer.de>
 * @author Bernard Ladenthin <bernard.ladenthin@fokus.fraunhofer.de>
 * @date 07/20/2013
 */
public class ObjectOutputStreamSerializer<T> extends Serializer<T> {

    public ObjectOutputStreamSerializer(final Type messageType, Class<?> messageClass, final T msg) {
        super(messageType, messageClass, msg);
    }

    @Override
    public byte[] serialize() throws Exception {
        try (ByteArrayOutputStream bos = new ByteArrayOutputStream();
             ObjectOutput out = new ObjectOutputStream(bos) ) {
            out.writeObject(msg);
            return bos.toByteArray();
        }
    }

}
