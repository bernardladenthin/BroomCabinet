// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.util;

import java.io.DataInput;
import java.io.DataOutput;
import java.io.IOException;

/**
 * Read an object from a {@link DataOutput}. TODO: Please add static modifier to static function to
 * use them without an object.
 *
 * @author VSimRTI developer team <vsimrti@fokus.fraunhofer.de>
 * @author Bernard Ladenthin <bernard.ladenthin@fokus.fraunhofer.de>
 */
public interface FromDataInput<T> {

    /**
     * Read an object from a {@link DataOutput}.
     *
     * @param dIn
     * the {@link DataInput}.
     * @throws IOException
     */
    public T fromDataInput(DataInput dIn) throws IOException;
}
