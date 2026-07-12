// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.configuration;

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
