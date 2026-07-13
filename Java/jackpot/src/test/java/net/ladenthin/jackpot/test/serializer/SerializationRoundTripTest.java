// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.serializer;

import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.is;
import static org.hamcrest.Matchers.notNullValue;
import static org.junit.jupiter.api.Assertions.assertThrows;

import com.google.gson.reflect.TypeToken;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;

import net.ladenthin.jackpot.DeserializerFactoryImpl;
import net.ladenthin.jackpot.SerializerFactoryImpl;
import net.ladenthin.jackpot.configuration.CClientSocketConnector;
import net.ladenthin.jackpot.configuration.CConnector;
import net.ladenthin.jackpot.configuration.CMessageIdLong;
import net.ladenthin.jackpot.configuration.CTransceiver;
import net.ladenthin.jackpot.configuration.CTransceiverSession;
import net.ladenthin.jackpot.configuration.ConnectionType;
import net.ladenthin.jackpot.configuration.Heartbeat;
import net.ladenthin.jackpot.configuration.SerializationType;
import net.ladenthin.jackpot.configuration.SettingsCompression;
import net.ladenthin.jackpot.deserializer.ObjectOutputStreamDeserializer;
import net.ladenthin.jackpot.serializer.DeserializerFactory;
import net.ladenthin.jackpot.serializer.SerializerFactory;
import net.ladenthin.jackpot.test.sendAndReceive.SimpleMessage;

/**
 * Serialize/deserialize round trips through the factory pair
 * ({@link SerializerFactoryImpl}/{@link DeserializerFactoryImpl}) for every
 * {@link SerializationType}, covering both the factory switch selection and each
 * serializer/deserializer implementation — the core payload transform of the library,
 * previously without any direct test.
 */
public class SerializationRoundTripTest {

    /**
     * Builds a session configured for the given serialization type; the connector part is
     * irrelevant here (no connection is opened by the factories).
     */
    private CTransceiverSession sessionFor(SerializationType serializationType) {
        return new CTransceiverSession(
            "serializationRoundTripTest",
            new TypeToken<SimpleMessage>() {}.getType(),
            SimpleMessage.class,
            new CTransceiver(
                serializationType,
                serializationType,
                ConnectionType.ClientSocketConnection,
                new SettingsCompression(),
                new CConnector(new CClientSocketConnector("localhost", 1)),
                new Heartbeat(),
                new CMessageIdLong()
            )
        );
    }

    // <editor-fold defaultstate="collapsed" desc="round trip per serialization type">
    @ParameterizedTest
    @EnumSource(SerializationType.class)
    public void deserialize_serializedMessageGiven_roundTripPreservesContent(
        SerializationType serializationType) throws Exception {
        // arrange
        final CTransceiverSession session = sessionFor(serializationType);
        final SerializerFactory<SimpleMessage> serializerFactory = new SerializerFactoryImpl<>(session);
        final DeserializerFactory<SimpleMessage> deserializerFactory = new DeserializerFactoryImpl<>(session);
        final SimpleMessage message =
            new SimpleMessage(SerializationRoundTripTest.class.getCanonicalName().getBytes());

        // act
        final byte[] serialized = serializerFactory.getSerializer(message).serialize();
        final SimpleMessage deserialized = deserializerFactory.getDeserializer(serialized).deserialize();

        // pre-assert
        assertThat(serialized, is(notNullValue()));
        assertThat(deserialized, is(notNullValue()));

        // assert
        assertThat(deserialized, is(equalTo(message)));
    }
    // </editor-fold>

    // <editor-fold defaultstate="collapsed" desc="ObjectOutputStreamDeserializer type check">
    @Test
    public void deserialize_bytesOfForeignType_throwsException() throws Exception {
        // arrange: serialize a String, but declare the message class as SimpleMessage
        final CTransceiverSession session = sessionFor(SerializationType.ObjectOutputStreamSerialization);
        final SerializerFactoryImpl<String> stringSerializerFactory = new SerializerFactoryImpl<>(
            new CTransceiverSession(
                "foreignType",
                new TypeToken<String>() {}.getType(),
                String.class,
                session.transceiverConfiguration
            )
        );
        final byte[] foreignBytes = stringSerializerFactory.getSerializer("not a SimpleMessage").serialize();
        final ObjectOutputStreamDeserializer<SimpleMessage> deserializer =
            new ObjectOutputStreamDeserializer<>(
                new TypeToken<SimpleMessage>() {}.getType(), SimpleMessage.class, foreignBytes);

        // act, assert: the deserialized object is not an instance of the declared class
        assertThrows(IllegalArgumentException.class, deserializer::deserialize);
    }
    // </editor-fold>
}
