// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.deserializer;

import java.io.ByteArrayInputStream;
import java.io.ObjectInput;
import java.io.ObjectInputStream;
import java.lang.reflect.Type;
import java.util.Objects;

/**
 * Pure java implementation of a {@link Deserializer}.
 *
 * @author VSimRTI developer team <vsimrti@fokus.fraunhofer.de>
 * @author Bernard Ladenthin <bernard.ladenthin@fokus.fraunhofer.de>
 * @param <T>
 */
public class ObjectOutputStreamDeserializer<T> extends Deserializer<T> {

    public ObjectOutputStreamDeserializer(final Type messageType, Class<?> messageClass, final byte[] bytes) {
        super(messageType, messageClass, bytes);
    }

    @SuppressWarnings("unchecked")
    @Override
    public T deserialize() throws Exception {
        final Object readObject;

        try (ObjectInput in = new ObjectInputStream(new ByteArrayInputStream(bytes))) {
            readObject = Objects.requireNonNull(in.readObject());
        }
        
        if (messageClass.isInstance(readObject)) {
            return (T) readObject;
        } else {
            throw new IllegalArgumentException();
        }
    }

}
