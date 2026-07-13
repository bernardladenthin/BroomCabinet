// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.configuration;

/**
 * Shared TCP port validation for the socket connector configurations.
 */
final class PortValidation {

    /**
     * The highest valid TCP port number.
     */
    static final int MAX_PORT = 65535;

    private PortValidation() {
    }

    /**
     * @param port the port to validate
     * @throws IllegalArgumentException if the port is outside {@code [0, 65535]}
     */
    static void validate(final int port) {
        if (port < 0 || port > MAX_PORT) {
            throw new IllegalArgumentException("port out of range [0, " + MAX_PORT + "]: " + port);
        }
    }
}
