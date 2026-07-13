// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.sendAndReceive;

import com.google.gson.reflect.TypeToken;
import net.ladenthin.jackpot.configuration.*;

public class SocketConnectorRoundTripTest extends AbstractConnectorRoundTripTest {

    private final static String host = "localhost";
    private final static int port = 12345;

    @Override
    CTransceiverSession getServerTransceiver() {
        CServerSocketConnector cServerSocketConnector = new CServerSocketConnector(port);
        CConnector serverConnector = new CConnector(cServerSocketConnector);
        CTransceiver transceiverConfiguration = new CTransceiver(ConnectionType.ServerSocketConnection, serverConnector);

        return new CTransceiverSession(
            "serverTransceiver",
            new TypeToken<SimpleMessage>(){}.getType(),
            SimpleMessage.class,
            transceiverConfiguration
        );
    }

    @Override
    CTransceiverSession getClientTransceiver() {
        CClientSocketConnector cClientSocketConnector = new CClientSocketConnector(host, port);
        CConnector clientConnector = new CConnector(cClientSocketConnector);
        CTransceiver transceiverConfiguration = new CTransceiver(ConnectionType.ClientSocketConnection, clientConnector);

        return new CTransceiverSession(
            "clientTransceiver",
            new TypeToken<SimpleMessage>(){}.getType(),
            SimpleMessage.class,
            transceiverConfiguration
        );
    }

}
