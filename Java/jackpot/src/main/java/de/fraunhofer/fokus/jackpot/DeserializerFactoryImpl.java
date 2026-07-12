package de.fraunhofer.fokus.jackpot;

import de.fraunhofer.fokus.jackpot.configuration.CTransceiverSession;
import de.fraunhofer.fokus.jackpot.deserializer.Deserializer;
import de.fraunhofer.fokus.jackpot.deserializer.GsonDeserializer;
import de.fraunhofer.fokus.jackpot.deserializer.ObjectOutputStreamDeserializer;
import de.fraunhofer.fokus.jackpot.deserializer.ProtostuffDeserializer;
import de.fraunhofer.fokus.jackpot.serializer.DeserializerFactory;

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
