// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.configuration;

import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.is;
import static org.junit.jupiter.api.Assertions.assertThrows;

import org.junit.jupiter.api.Test;

import net.ladenthin.jackpot.configuration.CClientSocketConnector;
import net.ladenthin.jackpot.configuration.CServerSocketConnector;

/**
 * Port validation of the socket connector configurations. Historically the check was
 * {@code port >= 65535} — an off-by-one rejecting the valid port 65535 — and the
 * {@code soTimeout} constructor overloads skipped validation entirely.
 */
public class SocketConnectorConfigurationTest {

    /**
     * The highest valid TCP port number.
     */
    private static final int MAX_PORT = 65535;

    // <editor-fold defaultstate="collapsed" desc="valid boundary ports">
    @Test
    public void constructor_maximumValidPortGiven_accepted() {
        // act
        final CServerSocketConnector server = new CServerSocketConnector(MAX_PORT);
        final CClientSocketConnector client = new CClientSocketConnector("localhost", MAX_PORT);

        // assert
        assertThat(server.port, is(equalTo(MAX_PORT)));
        assertThat(client.port, is(equalTo(MAX_PORT)));
    }
    // </editor-fold>

    // <editor-fold defaultstate="collapsed" desc="invalid ports">
    @Test
    public void constructor_portAboveMaximumGiven_throwsException() {
        // act, assert
        assertThrows(IllegalArgumentException.class,
            () -> new CServerSocketConnector(MAX_PORT + 1));
        assertThrows(IllegalArgumentException.class,
            () -> new CClientSocketConnector("localhost", MAX_PORT + 1));
    }

    @Test
    public void constructor_negativePortGiven_throwsException() {
        // act, assert
        assertThrows(IllegalArgumentException.class,
            () -> new CServerSocketConnector(-1));
        assertThrows(IllegalArgumentException.class,
            () -> new CClientSocketConnector("localhost", -1));
    }

    @Test
    public void constructor_soTimeoutOverloadWithInvalidPort_throwsException() {
        // act, assert: the overloads with an explicit soTimeout must validate the port too
        assertThrows(IllegalArgumentException.class,
            () -> new CServerSocketConnector(MAX_PORT + 1, 1000));
        assertThrows(IllegalArgumentException.class,
            () -> new CClientSocketConnector("localhost", MAX_PORT + 1, 1000));
    }
    // </editor-fold>
}
