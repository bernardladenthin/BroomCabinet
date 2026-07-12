// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.configuration;

import java.io.Serializable;

/**
 * Wrapper class for the actual connection configuration which is separated by client/server
 * and the actuall connection type. Immutable.
 *
 * @author VSimRTI developer team <vsimrti@fokus.fraunhofer.de>
 * @author Bernard Ladenthin <bernard.ladenthin@fokus.fraunhofer.de>
 */
public class CConnector implements Serializable {

    private static final long serialVersionUID = -1;

    public final CClientSocketConnector clientSocketConnector;
    public final CServerSocketConnector serverSocketConnector;
    public final CUnixNamedPipeServerConnector unixNamedPipeServer;
    public final CUnixNamedPipeClientConnector unixNamedPipeClient;
    public final CWindowsNamedPipeServerConnector windowsNamedPipeServer;
    public final CWindowsNamedPipeClientConnector windowsNamedPipeClient;

    private CConnector(
        final CClientSocketConnector clientSocketConnector,
        final CServerSocketConnector serverSocketConnector,
        final CUnixNamedPipeServerConnector unixNamedPipeServer,
        final CUnixNamedPipeClientConnector unixNamedPipeClient,
        final CWindowsNamedPipeServerConnector windowsNamedPipeServer,
        final CWindowsNamedPipeClientConnector windowsNamedPipeClient
        ) {
        this.clientSocketConnector = clientSocketConnector;
        this.serverSocketConnector = serverSocketConnector;
        this.unixNamedPipeServer = unixNamedPipeServer;
        this.unixNamedPipeClient = unixNamedPipeClient;
        this.windowsNamedPipeServer = windowsNamedPipeServer;
        this.windowsNamedPipeClient = windowsNamedPipeClient;
    }

    public CConnector(final CClientSocketConnector clientSocketConnector) {
        this(clientSocketConnector, null, null, null, null, null);
    }

    public CConnector(final CServerSocketConnector serverSocketConnector) {
        this(null, serverSocketConnector, null, null, null, null);
    }

    public CConnector(final CUnixNamedPipeServerConnector unixNamedPipeServer) {
        this(null, null, unixNamedPipeServer, null, null, null);
    }

    public CConnector(final CUnixNamedPipeClientConnector unixNamedPipeClient) {
        this(null, null, null, unixNamedPipeClient, null, null);
    }

    public CConnector(final CWindowsNamedPipeServerConnector windowsNamedPipeServer) {
        this(null, null, null, null, windowsNamedPipeServer, null);
    }

    public CConnector(final CWindowsNamedPipeClientConnector windowsNamedPipeClient) {
        this(null, null, null, null, null, windowsNamedPipeClient);
    }
}
