package net.ladenthin.persistentsocket.configuration;

import java.io.Serializable;

/**
 * Immutable.
 * 
 * @author bernard
 */
public class ServerSocket implements Serializable {

    private static final long serialVersionUID = -1;

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
    public ServerSocket(final int port) {
        this(port, 20000);
    }

    /**
     * 
     * @param port The port number.
     * @param soTimeout The SO_TIMEOUT with the specified timeout. Unit: [ms].
     */
    public ServerSocket(final int port, final int soTimeout) {
        if (port < 0 || port >= 65535) {
            throw new IllegalArgumentException();
        }
        this.port = port;
        this.soTimeout = soTimeout;
    }

    /**
     * Default constructor.
     */
    public ServerSocket() {
        this(12345);
    }
}
