// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.configuration;

/**
 * Created by bernard on 13.05.14.
 */
public class CWindowsNamedPipeClientConnector extends CBidirectionalPipe {

    private static final long serialVersionUID = -1;

    public CWindowsNamedPipeClientConnector(final String pipeName) {
        super(pipeName);
    }
}
