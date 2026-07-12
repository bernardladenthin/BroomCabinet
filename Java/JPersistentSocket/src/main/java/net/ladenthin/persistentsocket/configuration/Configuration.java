// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.persistentsocket.configuration;

import java.io.Serializable;

public class Configuration implements Serializable {

    private static final long serialVersionUID = -1;
    
    /**
     * 
     */
    private final ClientSocket clientSocket;
    
    /**
     * 
     */
    private final ServerSocket serverSocket;
    
    /**
     * 
     */
    private final Connection connection;
    
    public Configuration(final ClientSocket clientSocket, final Connection connection) {
        this.clientSocket = clientSocket;
        this.serverSocket = null;
        this.connection = connection;
    }
    
    public Configuration(final ServerSocket serverSocket, final Connection connection) {
        this.clientSocket = null;
        this.serverSocket = serverSocket;
        this.connection = connection;
    }

    public ClientSocket getClientSocket() {
        return clientSocket;
    }

    public ServerSocket getServerSocket() {
        return serverSocket;
    }

    public Connection getConnection() {
        return connection;
    }
    
}
