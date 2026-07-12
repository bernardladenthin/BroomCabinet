package de.fraunhofer.fokus.jackpot.connector;

import de.fraunhofer.fokus.jackpot.configuration.CUnixNamedPipeServerConnector;

import java.io.*;

public class UnixNamedPipeServerConnector extends UnixNamedPipeConnector {

    private final CUnixNamedPipeServerConnector configuration;

    public UnixNamedPipeServerConnector(CUnixNamedPipeServerConnector configuration) {
        checkOperatingSystem();
        this.configuration = configuration;
    }

    @Override
    public void connect() throws IOException {
        connect(configuration.requestPipe, configuration.responsePipe);
    }

}
