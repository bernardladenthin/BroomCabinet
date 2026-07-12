// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.configuration;

import java.io.Serializable;

/**
 * Created by bernard on 13.05.14.
 */
public class CUnixNamedPipeClientConnector implements Serializable {

    private static final long serialVersionUID = -1;

    public final String requestPipe;
    public final String responsePipe;

    public CUnixNamedPipeClientConnector(final String requestPipe, final String responsePipe) {
        this.requestPipe = requestPipe;
        this.responsePipe = responsePipe;
    }
}
