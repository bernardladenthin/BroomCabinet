// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.sendAndReceive;

import com.google.gson.reflect.TypeToken;

import net.ladenthin.jackpot.configuration.CClientSocketConnector;
import net.ladenthin.jackpot.configuration.CConnector;
import net.ladenthin.jackpot.configuration.CMessageIdLong;
import net.ladenthin.jackpot.configuration.CServerSocketConnector;
import net.ladenthin.jackpot.configuration.CTransceiver;
import net.ladenthin.jackpot.configuration.CTransceiverSession;
import net.ladenthin.jackpot.configuration.ConnectionType;
import net.ladenthin.jackpot.configuration.Heartbeat;
import net.ladenthin.jackpot.configuration.SerializationType;
import net.ladenthin.jackpot.test.Common;

/**
 * The full socket round trip with GZIP compression active on both sides — the only automated
 * end-to-end exercise of the compression path (the other integration tests all run
 * uncompressed).
 */
public class GzipCompressedSocketRoundTripTest extends AbstractConnectorRoundTripTest {

    private final static String HOST = "localhost";

    /**
     * A dedicated port, distinct from the other socket integration tests, so the tests can
     * never collide inside one Surefire fork.
     */
    private final static int PORT = 24680;

    private CTransceiver transceiverConfiguration(ConnectionType connectionType, CConnector connector) {
        return new CTransceiver(
            SerializationType.ObjectOutputStreamSerialization,
            SerializationType.ObjectOutputStreamSerialization,
            connectionType,
            // compress every payload >= 1 byte with GZIP
            Common.alwaysGZIPSettingsCompression,
            connector,
            new Heartbeat(),
            new CMessageIdLong()
        );
    }

    @Override
    CTransceiverSession getServerTransceiver() {
        return new CTransceiverSession(
            "gzipRoundTripServer",
            new TypeToken<SimpleMessage>(){}.getType(),
            SimpleMessage.class,
            transceiverConfiguration(
                ConnectionType.ServerSocketConnection,
                new CConnector(new CServerSocketConnector(PORT)))
        );
    }

    @Override
    CTransceiverSession getClientTransceiver() {
        return new CTransceiverSession(
            "gzipRoundTripClient",
            new TypeToken<SimpleMessage>(){}.getType(),
            SimpleMessage.class,
            transceiverConfiguration(
                ConnectionType.ClientSocketConnection,
                new CConnector(new CClientSocketConnector(HOST, PORT)))
        );
    }

}
