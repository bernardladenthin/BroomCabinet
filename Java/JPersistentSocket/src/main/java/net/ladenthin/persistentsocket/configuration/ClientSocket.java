package net.ladenthin.persistentsocket.configuration;

import java.io.Serializable;

/**
 * Immutable.
 *
 * @author bernard
 */
public class ClientSocket implements Serializable {

    private static final long serialVersionUID = -1;

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
    public ClientSocket(final String host, final int port) {
        this(host, port, 20000);
    }

    /**
     * 
     * @param host The host.
     * @param port The port number.
     * @param soTimeout The SO_TIMEOUT with the specified timeout. Unit: [ms].
     */
    public ClientSocket(final String host, final int port, final int soTimeout) {
        if (port < 0 || port >= 65535) {
            throw new IllegalArgumentException();
        }
        this.host = host;
        this.port = port;
        this.soTimeout = soTimeout;
    }

    /**
     * Default constructor.
     */
    public ClientSocket() {
        this("localhost", 12345);
    }
}
