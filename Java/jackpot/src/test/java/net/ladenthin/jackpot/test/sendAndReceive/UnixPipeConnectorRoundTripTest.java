// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.sendAndReceive;

import com.google.gson.reflect.TypeToken;
import net.ladenthin.jackpot.configuration.*;
import org.junit.jupiter.api.condition.EnabledOnOs;
import org.junit.jupiter.api.condition.OS;

@EnabledOnOs(value = OS.LINUX, disabledReason = "Needs mkfifo named pipes (POSIX FIFOs).")
public class UnixPipeConnectorRoundTripTest extends AbstractConnectorRoundTripTest {

    /**
     * FIFO paths inside the build directory, so stray files from an aborted run never litter
     * the project root and are cleaned by a regular build.
     */
    private final static String REQUEST_PIPE = "target/unixpipe-roundtrip-request";
    private final static String RESPONSE_PIPE = "target/unixpipe-roundtrip-response";

    @Override
    final CTransceiverSession getServerTransceiver() {
        CUnixNamedPipeServerConnector cUnixNamedPipeServerConnector = new CUnixNamedPipeServerConnector(REQUEST_PIPE, RESPONSE_PIPE);
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
        CUnixNamedPipeClientConnector cUnixNamedPipeClientConnector = new CUnixNamedPipeClientConnector(RESPONSE_PIPE, REQUEST_PIPE);
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
