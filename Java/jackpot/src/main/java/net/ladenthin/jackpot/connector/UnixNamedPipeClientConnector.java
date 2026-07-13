// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.connector;

import net.ladenthin.jackpot.configuration.CUnixNamedPipeClientConnector;

import java.io.*;

public class UnixNamedPipeClientConnector extends UnixNamedPipeConnector {

    private final CUnixNamedPipeClientConnector configuration;

    public UnixNamedPipeClientConnector(CUnixNamedPipeClientConnector configuration) {
        checkOperatingSystem();
        this.configuration = configuration;
    }

    @Override
    public void connect() throws IOException {
        connect(configuration.requestPipe, configuration.responsePipe, /* openInputFirst: the client side opens write-first */ false);
    }

}
