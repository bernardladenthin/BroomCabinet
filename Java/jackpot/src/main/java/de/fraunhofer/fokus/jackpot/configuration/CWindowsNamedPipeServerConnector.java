package de.fraunhofer.fokus.jackpot.configuration;

/**
 * Created by bernard on 13.05.14.
 */
public class CWindowsNamedPipeServerConnector extends CBidirectionalPipe {

    private static final long serialVersionUID = -1;

    public CWindowsNamedPipeServerConnector(final String pipeName) {
        super(pipeName);
    }
}
