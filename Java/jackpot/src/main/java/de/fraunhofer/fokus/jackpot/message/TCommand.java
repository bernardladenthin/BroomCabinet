/**
 * Copyright 2013 Fraunhofer FOKUS
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *    http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 */
package de.fraunhofer.fokus.jackpot.message;

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
