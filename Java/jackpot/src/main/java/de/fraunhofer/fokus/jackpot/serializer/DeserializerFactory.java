package de.fraunhofer.fokus.jackpot.serializer;

import de.fraunhofer.fokus.jackpot.deserializer.Deserializer;

public interface DeserializerFactory<T> {

    Deserializer<T> getDeserializer(byte[] bytes);
}
