// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.message;

import java.io.Serializable;

/**
 * Class for a transmitter command.
 *
 * @author VSimRTI developer team <vsimrti@fokus.fraunhofer.de>
 * @author Bernard Ladenthin <bernard.ladenthin@fokus.fraunhofer.de>
 */
public class TCommand implements Serializable {

    private static final long serialVersionUID = 1090777475327447767L;

    /**
     * shutdown can be received from the transceiver if the connection is to be closed.
     */
    public boolean shutdown;

    @Override
    public int hashCode() {
        int hash = 3;
        hash = 59 * hash + (this.shutdown ? 1 : 0);
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
        final TCommand other = (TCommand) obj;
        if (this.shutdown != other.shutdown) {
            return false;
        }
        return true;
    }

    @Override
    public String toString() {
        return "TCommand{" + "shutdown=" + shutdown + '}';
    }

}
