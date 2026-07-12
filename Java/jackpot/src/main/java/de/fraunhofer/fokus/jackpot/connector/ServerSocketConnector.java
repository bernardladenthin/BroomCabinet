package de.fraunhofer.fokus.jackpot.connector;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.ServerSocket;
import java.net.Socket;

import de.fraunhofer.fokus.jackpot.configuration.CServerSocketConnector;

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
