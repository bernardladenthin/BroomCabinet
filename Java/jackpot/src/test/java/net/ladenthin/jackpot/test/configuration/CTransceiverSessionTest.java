// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.configuration;

import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.is;

import com.google.gson.reflect.TypeToken;

import org.junit.jupiter.api.Test;

import net.ladenthin.jackpot.configuration.CClientSocketConnector;
import net.ladenthin.jackpot.configuration.CConnector;
import net.ladenthin.jackpot.configuration.CMessageIdLong;
import net.ladenthin.jackpot.configuration.CTransceiver;
import net.ladenthin.jackpot.configuration.CTransceiverSession;
import net.ladenthin.jackpot.configuration.ConnectionType;
import net.ladenthin.jackpot.configuration.Heartbeat;
import net.ladenthin.jackpot.configuration.SerializationType;
import net.ladenthin.jackpot.configuration.SettingsCompression;
import net.ladenthin.jackpot.test.sendAndReceive.SimpleMessage;

/**
 * {@link CTransceiverSession} must respect the configured {@link CMessageIdLong} id range —
 * historically the range was hardcoded to {@code Long.MIN_VALUE}/{@code Long.MAX_VALUE} and
 * the configuration was silently ignored.
 */
public class CTransceiverSessionTest {

    // <editor-fold defaultstate="collapsed" desc="message id range">
    @Test
    public void constructor_customMessageIdRangeConfigured_rangeIsRespected() {
        // arrange
        final long begin = 100;
        final long end = 200;
        final CTransceiver transceiverConfiguration = new CTransceiver(
            SerializationType.ObjectOutputStreamSerialization,
            SerializationType.ObjectOutputStreamSerialization,
            ConnectionType.ClientSocketConnection,
            new SettingsCompression(),
            new CConnector(new CClientSocketConnector("localhost", 1)),
            new Heartbeat(),
            new CMessageIdLong(begin, end)
        );

        // act
        final CTransceiverSession session = new CTransceiverSession(
            "customIdRange",
            new TypeToken<SimpleMessage>() {}.getType(),
            SimpleMessage.class,
            transceiverConfiguration
        );

        // assert
        assertThat(session.initialMessageId, is(equalTo(begin)));
        assertThat(session.lastMessageId, is(equalTo(end)));
    }

    @Test
    public void constructor_defaultConfiguration_usesFullLongRange() {
        // arrange
        final CTransceiver transceiverConfiguration = new CTransceiver(
            ConnectionType.ClientSocketConnection,
            new CConnector(new CClientSocketConnector("localhost", 1))
        );

        // act
        final CTransceiverSession session = new CTransceiverSession(
            "defaultIdRange",
            new TypeToken<SimpleMessage>() {}.getType(),
            SimpleMessage.class,
            transceiverConfiguration
        );

        // assert
        assertThat(session.initialMessageId, is(equalTo(Long.MIN_VALUE)));
        assertThat(session.lastMessageId, is(equalTo(Long.MAX_VALUE)));
    }
    // </editor-fold>
}
