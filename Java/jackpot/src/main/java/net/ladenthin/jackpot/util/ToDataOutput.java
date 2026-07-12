// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.util;

import java.io.DataOutput;
import java.io.IOException;

/**
 * Write this object to a {@link DataOutput}.
 *
 * @author VSimRTI developer team <vsimrti@fokus.fraunhofer.de>
 * @author Bernard Ladenthin <bernard.ladenthin@fokus.fraunhofer.de>
 */
public interface ToDataOutput {

    /**
     * Write this object to a {@link DataOutput}.
     *
     * @param dOut
     * the {@link DataOutput}.
     * @throws IOException
     */
    public void toDataOutput(DataOutput dOut) throws IOException;
}
