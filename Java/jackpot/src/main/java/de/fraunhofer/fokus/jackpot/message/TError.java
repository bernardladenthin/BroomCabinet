package de.fraunhofer.fokus.jackpot.message;

import java.io.PrintWriter;
import java.io.Serializable;
import java.io.StringWriter;
import java.util.Objects;

public class TError implements Serializable {

    private static final long serialVersionUID = -8461653841359240757L;

    /**
     * noInAvailable is fired from the transceiver when the maximum waiting time has been reached.
     */
    public boolean noInAvailable;

    /**
     * expired is fired from the transceiver when the connection suddenly lost or safely closed.
     */
    public boolean expired;

    /**
     * Throwable (i.e. an exception) contain all thrown exceptions from the transceiver.
     */
    public String throwableError;

    public boolean noConnectionPossible;

    public static TError fromThrowable(Throwable t) {
        StringWriter sw = new StringWriter();
        PrintWriter pw = new PrintWriter(sw);
        t.printStackTrace(pw);
        TError error = new TError();
        error.throwableError = sw.toString();
        return error;
    }

    @Override
    public int hashCode() {
        int hash = 3;
        hash = 37 * hash + (this.noInAvailable ? 1 : 0);
        hash = 37 * hash + (this.expired ? 1 : 0);
        hash = 37 * hash + Objects.hashCode(this.throwableError);
        hash = 37 * hash + (this.noConnectionPossible ? 1 : 0);
        return hash;
    }

    @Override
    public boolean equals(Object obj) {
        if (obj == null) {
            return false;
        }
        if (getClass() != obj.getClass()) {
            return false;
        }
        final TError other = (TError) obj;
        if (this.noInAvailable != other.noInAvailable) {
            return false;
        }
        if (this.expired != other.expired) {
            return false;
        }
        if (!Objects.equals(this.throwableError, other.throwableError)) {
            return false;
        }
        if (this.noConnectionPossible != other.noConnectionPossible) {
            return false;
        }
        return true;
    }

    @Override
    public String toString() {
        return "TError{" + "noInAvailable=" + noInAvailable + ", expired=" + expired + ", throwableError=" + throwableError + ", noConnectionPossible=" + noConnectionPossible + '}';
    }
    

}
