// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.util;

import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.is;
import static org.hamcrest.Matchers.empty;

import java.util.ArrayList;
import java.util.List;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import net.ladenthin.jackpot.message.TError;
import net.ladenthin.jackpot.test.sendAndReceive.SimpleMessage;
import net.ladenthin.jackpot.util.NanoHandler;
import net.ladenthin.jackpot.util.NanoObserver;

/**
 * {@link NanoObserver} is the typed convenience {@link java.util.Observer} for API consumers:
 * it dispatches transceiver notifications either to
 * {@link NanoHandler#handleTransmission(Object)} (message of the expected type) or to
 * {@link NanoHandler#handleError(TError)} and swallows everything else.
 */
public class NanoObserverTest {

    private final List<SimpleMessage> transmissions = new ArrayList<>();
    private final List<TError> errors = new ArrayList<>();

    private NanoObserver<SimpleMessage> observer;

    @BeforeEach
    public void setUp() {
        observer = new NanoObserver<>(SimpleMessage.class, new NanoHandler<SimpleMessage>() {
            @Override
            public void handleTransmission(SimpleMessage transmission) {
                transmissions.add(transmission);
            }

            @Override
            public void handleError(TError t) {
                errors.add(t);
            }
        });
    }

    // <editor-fold defaultstate="collapsed" desc="update dispatch">
    @Test
    public void update_messageOfExpectedType_dispatchedToHandleTransmission() {
        // arrange
        final SimpleMessage message = new SimpleMessage("payload".getBytes());

        // act
        observer.update(null, message);

        // assert
        assertThat(transmissions, hasSize(1));
        assertThat(transmissions.get(0), is(equalTo(message)));
        assertThat(errors, is(empty()));
    }

    @Test
    public void update_errorGiven_dispatchedToHandleError() {
        // arrange
        final TError error = new TError();
        error.expired = true;

        // act
        observer.update(null, error);

        // assert
        assertThat(errors, hasSize(1));
        assertThat(errors.get(0), is(equalTo(error)));
        assertThat(transmissions, is(empty()));
    }

    @Test
    public void update_nullArgument_silentlyIgnored() {
        // act
        observer.update(null, null);

        // assert
        assertThat(transmissions, is(empty()));
        assertThat(errors, is(empty()));
    }

    @Test
    public void update_unrelatedType_silentlyIgnored() {
        // act
        observer.update(null, "neither a SimpleMessage nor a TError");

        // assert
        assertThat(transmissions, is(empty()));
        assertThat(errors, is(empty()));
    }
    // </editor-fold>
}
