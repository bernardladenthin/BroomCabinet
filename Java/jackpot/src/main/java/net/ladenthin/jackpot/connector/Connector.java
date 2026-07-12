// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.connector;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;

public interface Connector {

    public OutputStream getOutputStream() throws IOException;

    public InputStream getInputStream() throws IOException;

    public void close() throws IOException;

    public void connect() throws IOException;
}
