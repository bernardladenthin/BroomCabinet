// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.connector;

/**
 * Created by bernard on 13.05.14.
 */
public abstract class WindowsNamedPipeConnector implements Connector {

    protected String pipeName;

    protected void checkOperatingSystem() {
        if (!System.getProperty("os.name").toLowerCase().contains("windows")) {
            throw new UnsupportedOperationException("This method is not supported on this operating system.");
        }
    }

    WindowsNamedPipeConnector(String pipeName) {
        this.pipeName = pipeName;
    }

}
