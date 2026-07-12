/**
 * Copyright 2013 Fraunhofer FOKUS
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *    http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 */
package de.fraunhofer.fokus.jackpot.configuration;

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
