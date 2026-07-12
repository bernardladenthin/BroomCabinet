package de.fraunhofer.fokus.jackpot.connector;

import de.fraunhofer.fokus.jackpot.configuration.CUnixNamedPipeClientConnector;

import java.io.*;

public class UnixNamedPipeClientConnector extends UnixNamedPipeConnector {

    private final CUnixNamedPipeClientConnector configuration;

    public UnixNamedPipeClientConnector(CUnixNamedPipeClientConnector configuration) {
        checkOperatingSystem();
        this.configuration = configuration;
    }

    @Override
    public void connect() throws IOException {
        connect(configuration.requestPipe, configuration.responsePipe);
    }

}
