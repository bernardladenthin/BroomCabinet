package de.fraunhofer.fokus.jackpot.configuration;

import java.io.Serializable;

/**
 * Created by bernard on 13.05.14.
 */
public abstract class CBidirectionalPipe implements Serializable {

    private static final long serialVersionUID = 2259977066655950065L;
    public final String pipeName;

    CBidirectionalPipe(String pipeName) {
        this.pipeName = pipeName;
    }
    
}
