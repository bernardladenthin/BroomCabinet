// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot;

import net.ladenthin.jackpot.configuration.CTransceiverSession;
import net.ladenthin.jackpot.deserializer.Deserializer;
import net.ladenthin.jackpot.deserializer.GsonDeserializer;
import net.ladenthin.jackpot.deserializer.ObjectOutputStreamDeserializer;
import net.ladenthin.jackpot.deserializer.ProtostuffDeserializer;
import net.ladenthin.jackpot.serializer.DeserializerFactory;

public class DeserializerFactoryImpl<T> extends SerializationFactory implements
    DeserializerFactory<T> {

    public DeserializerFactoryImpl(final CTransceiverSession cTransceiverSession) {
        super(cTransceiverSession);
    }

    @Override
    public Deserializer<T> getDeserializer(final byte[] bytes) {
        switch (getTransmissionType()) {
        case ProtostuffSerialization:
            return new ProtostuffDeserializer<>(getMessageType(), getMessageClass(), bytes);
        case GsonSerialization:
            return new GsonDeserializer<>(getMessageType(), getMessageClass(), bytes);
        default:
        case ObjectOutputStreamSerialization:
            return new ObjectOutputStreamDeserializer<>(getMessageType(), getMessageClass(), bytes);
        }
    }

}
