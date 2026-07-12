package de.fraunhofer.fokus.jackpot.serializer;

public interface SerializerFactory<T> {

    Serializer<T> getSerializer(T msg);
}
