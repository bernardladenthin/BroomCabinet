// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.connector;

import net.ladenthin.jackpot.configuration.CUnixNamedPipeServerConnector;

import java.io.*;

public class UnixNamedPipeServerConnector extends UnixNamedPipeConnector {

    private final CUnixNamedPipeServerConnector configuration;

    public UnixNamedPipeServerConnector(CUnixNamedPipeServerConnector configuration) {
        checkOperatingSystem();
        this.configuration = configuration;
    }

    @Override
    public void connect() throws IOException {
        connect(configuration.requestPipe, configuration.responsePipe, /* openInputFirst: the server side opens read-first */ true);
    }

}
