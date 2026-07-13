// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.configuration;

import java.io.Serializable;

/**
 * Immutable.
 *
 * @author bernard
 */
public class CClientSocketConnector implements Serializable {

    private static final long serialVersionUID = 5390346636341275100L;

    /**
     * The host.
     */
    public final String host;

    /**
     * The port number.
     */
    public final int port;

    /**
     * The SO_TIMEOUT with the specified timeout. Unit: [ms].
     */
    public final int soTimeout;

    /**
     *
     * @param host The host.
     * @param port The port number.
     */
    public CClientSocketConnector(final String host, final int port) {
        this(host, port, 20000);
    }

    /**
     *
     * @param host The host.
     * @param port The port number.
     * @param soTimeout The SO_TIMEOUT with the specified timeout. Unit: [ms].
     */
    public CClientSocketConnector(final String host, final int port, final int soTimeout) {
        PortValidation.validate(port);
        this.host = host;
        this.port = port;
        this.soTimeout = soTimeout;
    }

    /**
     * 
     */
    public CClientSocketConnector() {
        this("localhost", 12345);
    }
}
