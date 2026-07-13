// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.message;

import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.is;
import static org.hamcrest.Matchers.not;
import static org.hamcrest.Matchers.notNullValue;

import org.junit.jupiter.api.Test;

import net.ladenthin.jackpot.message.TError;

/**
 * {@link TError} is the error envelope every failure reaches the application in — its
 * {@link TError#fromThrowable(Throwable)} factory must carry the full stack trace.
 */
public class TErrorTest {

    // <editor-fold defaultstate="collapsed" desc="fromThrowable">
    @Test
    public void fromThrowable_exceptionGiven_stackTraceCaptured() {
        // arrange
        final IllegalStateException exception = new IllegalStateException("the reason");

        // act
        final TError error = TError.fromThrowable(exception);

        // pre-assert
        assertThat(error.throwableError, is(notNullValue()));

        // assert
        assertThat(error.throwableError, containsString("IllegalStateException"));
        assertThat(error.throwableError, containsString("the reason"));
        assertThat(error.throwableError, containsString(TErrorTest.class.getSimpleName()));
        assertThat(error.expired, is(false));
        assertThat(error.noConnectionPossible, is(false));
        assertThat(error.noInAvailable, is(false));
    }
    // </editor-fold>

    // <editor-fold defaultstate="collapsed" desc="equals and hashCode">
    @Test
    public void equals_sameFlags_errorsAreEqualWithSameHashCode() {
        // arrange
        final TError a = new TError();
        a.expired = true;
        final TError sameContent = new TError();
        sameContent.expired = true;

        // act, assert
        assertThat(a, is(equalTo(sameContent)));
        assertThat(a.hashCode(), is(equalTo(sameContent.hashCode())));
    }

    @Test
    public void equals_differentFlags_errorsAreNotEqual() {
        // arrange
        final TError expired = new TError();
        expired.expired = true;
        final TError noConnection = new TError();
        noConnection.noConnectionPossible = true;

        // act, assert
        assertThat(expired, is(not(equalTo(noConnection))));
        assertThat(expired.equals(null), is(false));
    }

    @Test
    public void toString_flagsSet_containsFlagStates() {
        // arrange
        final TError error = new TError();
        error.expired = true;

        // act, assert
        assertThat(error.toString(), containsString("expired=true"));
    }
    // </editor-fold>
}
