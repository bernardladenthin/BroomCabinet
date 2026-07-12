package de.fraunhofer.fokus.jackpot;

import de.fraunhofer.fokus.jackpot.configuration.CTransceiverSession;
import de.fraunhofer.fokus.jackpot.serializer.GsonSerializer;
import de.fraunhofer.fokus.jackpot.serializer.ObjectOutputStreamSerializer;
import de.fraunhofer.fokus.jackpot.serializer.ProtostuffSerializer;
import de.fraunhofer.fokus.jackpot.serializer.Serializer;
import de.fraunhofer.fokus.jackpot.serializer.SerializerFactory;
import de.fraunhofer.fokus.jackpot.util.ConcurrentMethod;

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
