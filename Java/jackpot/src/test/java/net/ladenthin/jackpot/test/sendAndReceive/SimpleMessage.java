// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.sendAndReceive;

import java.io.Serializable;
import java.util.Arrays;

/**
 * Message for testing purpose.
 *
 * @author VSimRTI developer team <vsimrti@fokus.fraunhofer.de>
 * @author Bernard Ladenthin <bernard.ladenthin@fokus.fraunhofer.de>
 */
public class SimpleMessage implements Serializable {

    private static final long serialVersionUID = 3729782123981240566L;

    public final byte[] binaryContent;

    public SimpleMessage(byte[] binaryContent) {
        this.binaryContent = binaryContent;
    }

    @Override
    public int hashCode() {
        final int prime = 31;
        int result = 1;
        result = prime * result + Arrays.hashCode(binaryContent);
        return result;
    }

    @Override
    public boolean equals(Object obj) {
        if (this == obj)
            return true;
        if (obj == null)
            return false;
        if (getClass() != obj.getClass())
            return false;
        SimpleMessage other = (SimpleMessage) obj;
        if (!Arrays.equals(
            binaryContent,
            other.binaryContent))
            return false;
        return true;
    }


}
