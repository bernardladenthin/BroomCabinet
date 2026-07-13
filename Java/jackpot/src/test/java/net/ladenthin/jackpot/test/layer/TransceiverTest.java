// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.layer;

import static org.junit.jupiter.api.Assertions.assertThrows;

import com.google.gson.reflect.TypeToken;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;

import net.ladenthin.jackpot.Transceiver;
import net.ladenthin.jackpot.configuration.CClientSocketConnector;
import net.ladenthin.jackpot.configuration.CConnector;
import net.ladenthin.jackpot.configuration.CTransceiver;
import net.ladenthin.jackpot.configuration.CTransceiverSession;
import net.ladenthin.jackpot.configuration.ConnectionType;
import net.ladenthin.jackpot.message.TCommand;
import net.ladenthin.jackpot.test.sendAndReceive.SimpleMessage;

/**
 * Input validation of the {@link Transceiver#update} entry point — the single door every
 * outbound message passes through. Nothing is connected in these tests (the client connector
 * points at an unreachable port; the background reconnect is stopped by the shutdown in
 * teardown).
 */
public class TransceiverTest {

    private Transceiver<SimpleMessage> transceiver;

    @BeforeEach
    public void setUp() {
        transceiver = new Transceiver<>(new CTransceiverSession(
            "transceiverUpdateTest",
            new TypeToken<SimpleMessage>() {}.getType(),
            SimpleMessage.class,
            new CTransceiver(
                ConnectionType.ClientSocketConnection,
                // unreachable on purpose: these tests never need a connection
                new CConnector(new CClientSocketConnector("localhost", 1))
            )
        ));
    }

    @AfterEach
    public void tearDown() {
        final TCommand command = new TCommand();
        command.shutdown = true;
        transceiver.update(null, command);
    }

    // <editor-fold defaultstate="collapsed" desc="update input validation">
    @Test
    @Timeout(30)
    public void update_nullMessageGiven_throwsException() {
        // act, assert: must fail fast with a clear message instead of an accidental
        // NullPointerException from arg.getClass()
        assertThrows(IllegalArgumentException.class, () -> transceiver.update(null, null));
    }

    @Test
    @Timeout(30)
    public void update_unrelatedTypeGiven_throwsException() {
        // act, assert
        assertThrows(IllegalArgumentException.class,
            () -> transceiver.update(null, Integer.valueOf(42)));
    }
    // </editor-fold>
}
