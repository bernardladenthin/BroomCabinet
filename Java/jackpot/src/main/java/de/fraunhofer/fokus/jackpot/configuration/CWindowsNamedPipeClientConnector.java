package de.fraunhofer.fokus.jackpot.configuration;

/**
 * Created by bernard on 13.05.14.
 */
public class CWindowsNamedPipeClientConnector extends CBidirectionalPipe {

    private static final long serialVersionUID = -1;

    public CWindowsNamedPipeClientConnector(final String pipeName) {
        super(pipeName);
    }
}
