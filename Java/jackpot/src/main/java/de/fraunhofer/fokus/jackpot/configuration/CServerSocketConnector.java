package de.fraunhofer.fokus.jackpot.configuration;

import java.io.Serializable;

/**
 * Immutable.
 * 
 * @author bernard
 */
public class CServerSocketConnector implements Serializable {

    private static final long serialVersionUID = -5288936595318039157L;

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
     * @param port The port number.
     */
    public CServerSocketConnector(final int port) {
        if (port < 0 || port >= 65535) {
            throw new IllegalArgumentException();
        }
        this.port = port;
        this.soTimeout = 20000;
    }

    /**
     * 
     * @param port The port number.
     * @param soTimeout The SO_TIMEOUT with the specified timeout. Unit: [ms].
     */
    public CServerSocketConnector(final int port, final int soTimeout) {
        this.port = port;
        this.soTimeout = soTimeout;
    }

    public CServerSocketConnector() {
        this(12345);
    }
}
