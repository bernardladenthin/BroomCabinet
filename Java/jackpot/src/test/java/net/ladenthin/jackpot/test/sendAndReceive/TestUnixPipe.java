// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.sendAndReceive;

import com.google.gson.reflect.TypeToken;
import net.ladenthin.jackpot.configuration.*;
import org.junit.Ignore;

@Ignore
public class TestUnixPipe extends TestConnector {

    @Override
    final CTransceiverSession getServerTransceiver() {
        CUnixNamedPipeServerConnector cUnixNamedPipeServerConnector = new CUnixNamedPipeServerConnector("request", "response");
        CConnector serverConnector = new CConnector(cUnixNamedPipeServerConnector);
        CTransceiver transceiverConfiguration = new CTransceiver(ConnectionType.UnixNamedPipeServer, serverConnector);

        return new CTransceiverSession(
            "serverTransceiver",
            new TypeToken<SimpleMessage>(){}.getType(),
            SimpleMessage.class,
            transceiverConfiguration
        );
    }

    @Override
    final CTransceiverSession getClientTransceiver() {
        CUnixNamedPipeClientConnector cUnixNamedPipeClientConnector = new CUnixNamedPipeClientConnector("response", "request");
        CConnector clientConnector = new CConnector(cUnixNamedPipeClientConnector);
        CTransceiver transceiverConfiguration = new CTransceiver(ConnectionType.UnixNamedPipeClient, clientConnector);

        return new CTransceiverSession(
            "clientTransceiver",
            new TypeToken<SimpleMessage>(){}.getType(),
            SimpleMessage.class,
            transceiverConfiguration
        );
    }

}
