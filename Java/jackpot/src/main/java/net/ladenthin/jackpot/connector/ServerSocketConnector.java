// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.connector;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.ServerSocket;
import java.net.Socket;

import net.ladenthin.jackpot.configuration.CServerSocketConnector;

public class ServerSocketConnector implements Connector {

    private final CServerSocketConnector configuration;

    private ServerSocket serverSocket;
    private Socket socket;

    public ServerSocketConnector(CServerSocketConnector configuration) {
        this.configuration = configuration;
    }

    public Socket getSocket() {
        return socket;
    }

    @Override
    public OutputStream getOutputStream() throws IOException {
        return socket.getOutputStream();
    }

    @Override
    public InputStream getInputStream() throws IOException {
        return socket.getInputStream();
    }

    @Override
    public void close() throws IOException {
        if (socket != null) {
            socket.close();
        }
        socket = null;
    }

    @Override
    public void connect() throws IOException {
        close();
        serverSocket = new ServerSocket(configuration.port);
        serverSocket.setSoTimeout(configuration.soTimeout);
        socket = serverSocket.accept();
    }

    public int getAssignedPort() {
        return serverSocket.getLocalPort();
    }
}
