// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot;

import net.ladenthin.jackpot.configuration.CTransceiverSession;
import net.ladenthin.jackpot.serializer.GsonSerializer;
import net.ladenthin.jackpot.serializer.ObjectOutputStreamSerializer;
import net.ladenthin.jackpot.serializer.ProtostuffSerializer;
import net.ladenthin.jackpot.serializer.Serializer;
import net.ladenthin.jackpot.serializer.SerializerFactory;
import net.ladenthin.jackpot.util.ConcurrentMethod;

public class SerializerFactoryImpl<T> extends SerializationFactory implements SerializerFactory<T> {

    public SerializerFactoryImpl(final CTransceiverSession cTransceiverSession) {
        super(cTransceiverSession);
    }

    @Override
    @ConcurrentMethod
    public Serializer<T> getSerializer(final T msg) {
        switch (getTransmissionType()) {
        case ProtostuffSerialization:
            return new ProtostuffSerializer<T>(getMessageType(), getMessageClass(), msg);
        case GsonSerialization:
            return new GsonSerializer<T>(getMessageType(), getMessageClass(), msg);
        default:
        case ObjectOutputStreamSerialization:
            return new ObjectOutputStreamSerializer<T>(getMessageType(), getMessageClass(), msg);
        }
    }

}
