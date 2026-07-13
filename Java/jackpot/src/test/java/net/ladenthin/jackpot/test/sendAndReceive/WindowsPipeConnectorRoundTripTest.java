// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.sendAndReceive;

import com.google.gson.reflect.TypeToken;
import net.ladenthin.jackpot.configuration.*;
import org.junit.jupiter.api.Disabled;

@Disabled("Needs the Windows kernel32 named-pipe API; only runnable on a Windows host.")
public class WindowsPipeConnectorRoundTripTest extends AbstractConnectorRoundTripTest {

    @Override
    final CTransceiverSession getServerTransceiver() {
        CWindowsNamedPipeServerConnector cWindowsNamedPipeServerConnector = new CWindowsNamedPipeServerConnector("testpipe");
        CConnector serverConnector = new CConnector(cWindowsNamedPipeServerConnector);
        CTransceiver transceiverConfiguration = new CTransceiver(ConnectionType.WindowsNamedPipeServer, serverConnector);

        return new CTransceiverSession(
                "serverTransceiver",
                new TypeToken<SimpleMessage>(){}.getType(),
                SimpleMessage.class,
                transceiverConfiguration
        );
    }

    @Override
    final CTransceiverSession getClientTransceiver() {
        CWindowsNamedPipeClientConnector cWindowsNamedPipeClientConnector = new CWindowsNamedPipeClientConnector("testpipe");
        CConnector clientConnector = new CConnector(cWindowsNamedPipeClientConnector);
        CTransceiver transceiverConfiguration = new CTransceiver(ConnectionType.WindowsNamedPipeClient, clientConnector);

        return new CTransceiverSession(
                "clientTransceiver",
                new TypeToken<SimpleMessage>(){}.getType(),
                SimpleMessage.class,
                transceiverConfiguration
        );
    }

}
