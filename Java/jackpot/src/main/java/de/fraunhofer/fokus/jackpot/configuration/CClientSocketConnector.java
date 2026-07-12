package de.fraunhofer.fokus.jackpot.configuration;

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
        if (port < 0 || port >= 65535) {
            throw new IllegalArgumentException();
        }
        this.host = host;
        this.port = port;
        this.soTimeout = 20000;
    }

    /**
     * 
     * @param host The host.
     * @param port The port number.
     * @param soTimeout The SO_TIMEOUT with the specified timeout. Unit: [ms].
     */
    public CClientSocketConnector(final String host, final int port, final int soTimeout) {
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
