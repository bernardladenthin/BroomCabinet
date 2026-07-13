// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.connector;

import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.instanceOf;
import static org.hamcrest.Matchers.is;

import com.google.gson.reflect.TypeToken;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.DisabledOnOs;
import org.junit.jupiter.api.condition.OS;

import net.ladenthin.jackpot.ConnectorFactoryImpl;
import net.ladenthin.jackpot.configuration.CClientSocketConnector;
import net.ladenthin.jackpot.configuration.CConnector;
import net.ladenthin.jackpot.configuration.CServerSocketConnector;
import net.ladenthin.jackpot.configuration.CTransceiverSession;
import net.ladenthin.jackpot.configuration.CTransceiver;
import net.ladenthin.jackpot.configuration.CUnixNamedPipeClientConnector;
import net.ladenthin.jackpot.configuration.CUnixNamedPipeServerConnector;
import net.ladenthin.jackpot.configuration.ConnectionType;
import net.ladenthin.jackpot.connector.ClientSocketConnector;
import net.ladenthin.jackpot.connector.Connector;
import net.ladenthin.jackpot.connector.ServerSocketConnector;
import net.ladenthin.jackpot.connector.UnixNamedPipeClientConnector;
import net.ladenthin.jackpot.connector.UnixNamedPipeServerConnector;
import net.ladenthin.jackpot.test.sendAndReceive.SimpleMessage;

/**
 * The {@link ConnectorFactoryImpl} switch must return the connector implementation matching
 * the configured {@link ConnectionType}. Construction only — nothing is connected.
 */
public class ConnectorFactoryImplTest {

    private CTransceiverSession sessionFor(ConnectionType connectionType, CConnector connector) {
        return new CTransceiverSession(
            "connectorFactoryTest",
            new TypeToken<SimpleMessage>() {}.getType(),
            SimpleMessage.class,
            new CTransceiver(connectionType, connector)
        );
    }

    // <editor-fold defaultstate="collapsed" desc="socket connectors">
    @Test
    public void getConnector_serverSocketConnectionConfigured_returnsServerSocketConnector() {
        // arrange
        final ConnectorFactoryImpl factory = new ConnectorFactoryImpl(sessionFor(
            ConnectionType.ServerSocketConnection,
            new CConnector(new CServerSocketConnector(12345))));

        // act
        final Connector connector = factory.getConnector();

        // assert
        assertThat(connector, is(instanceOf(ServerSocketConnector.class)));
    }

    @Test
    public void getConnector_clientSocketConnectionConfigured_returnsClientSocketConnector() {
        // arrange
        final ConnectorFactoryImpl factory = new ConnectorFactoryImpl(sessionFor(
            ConnectionType.ClientSocketConnection,
            new CConnector(new CClientSocketConnector("localhost", 12345))));

        // act
        final Connector connector = factory.getConnector();

        // assert
        assertThat(connector, is(instanceOf(ClientSocketConnector.class)));
    }
    // </editor-fold>

    // <editor-fold defaultstate="collapsed" desc="unix pipe connectors">
    @Test
    @DisabledOnOs(value = OS.WINDOWS, disabledReason = "The unix pipe connectors refuse to construct on Windows.")
    public void getConnector_unixNamedPipeServerConfigured_returnsUnixNamedPipeServerConnector() {
        // arrange
        final ConnectorFactoryImpl factory = new ConnectorFactoryImpl(sessionFor(
            ConnectionType.UnixNamedPipeServer,
            new CConnector(new CUnixNamedPipeServerConnector("target/factory-req", "target/factory-res"))));

        // act
        final Connector connector = factory.getConnector();

        // assert
        assertThat(connector, is(instanceOf(UnixNamedPipeServerConnector.class)));
    }

    @Test
    @DisabledOnOs(value = OS.WINDOWS, disabledReason = "The unix pipe connectors refuse to construct on Windows.")
    public void getConnector_unixNamedPipeClientConfigured_returnsUnixNamedPipeClientConnector() {
        // arrange
        final ConnectorFactoryImpl factory = new ConnectorFactoryImpl(sessionFor(
            ConnectionType.UnixNamedPipeClient,
            new CConnector(new CUnixNamedPipeClientConnector("target/factory-res", "target/factory-req"))));

        // act
        final Connector connector = factory.getConnector();

        // assert
        assertThat(connector, is(instanceOf(UnixNamedPipeClientConnector.class)));
    }
    // </editor-fold>
}
