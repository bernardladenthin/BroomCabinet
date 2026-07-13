// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.binaryMessage;

import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.is;
import static org.hamcrest.Matchers.not;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.util.stream.Stream;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;

import net.ladenthin.jackpot.util.BinaryMessageFlags;

/**
 * {@link BinaryMessageFlags} hand-packs four booleans into a single {@code int} on the wire
 * (see {@code toInt()}/{@code fromInt(int)}). These tests pin every individual bit plus every
 * legal combination round trip, so no two flags may silently alias onto the same bit.
 */
public class BinaryMessageFlagsTest {

    /**
     * Symbolic name for the local {@code @MethodSource} providing every legal flag combination.
     */
    private static final String DATA_PROVIDER_LEGAL_COMBINATIONS = "legalCombinations";

    /**
     * Every legal (non-exclusive) flag combination: at most one of lz4Used/gzipUsed/heartbeat/
     * acknowledged may be set (see the constructor's truth tables).
     */
    static Stream<Arguments> legalCombinations() {
        return Stream.of(
            Arguments.of(false, false, false, false),
            Arguments.of(true, false, false, false),
            Arguments.of(false, true, false, false),
            Arguments.of(false, false, true, false),
            Arguments.of(false, false, false, true)
        );
    }

    /**
     * Serializes the given flags through {@link BinaryMessageFlags#toDataOutput} and reads them
     * back through {@link BinaryMessageFlags#fromDataInputReplaceJava8}, mimicking the wire
     * round trip.
     */
    private BinaryMessageFlags recreate(BinaryMessageFlags flags) throws IOException {
        final ByteArrayOutputStream baos = new ByteArrayOutputStream();
        final DataOutputStream dOut = new DataOutputStream(baos);
        flags.toDataOutput(dOut);

        final ByteArrayInputStream bais = new ByteArrayInputStream(baos.toByteArray());
        final DataInputStream dIn = new DataInputStream(bais);
        return BinaryMessageFlags.fromDataInputReplaceJava8(dIn);
    }

    // <editor-fold defaultstate="collapsed" desc="wire round trip">
    @ParameterizedTest
    @MethodSource(DATA_PROVIDER_LEGAL_COMBINATIONS)
    public void fromDataInputReplaceJava8_legalCombinationWritten_recreatedPreservesEveryFlag(
        boolean lz4Used, boolean gzipUsed, boolean heartbeat, boolean acknowledged) throws IOException {
        // arrange
        final BinaryMessageFlags flags = new BinaryMessageFlags(lz4Used, gzipUsed, heartbeat, acknowledged);

        // act
        final BinaryMessageFlags recreated = recreate(flags);

        // assert
        assertThat(recreated.isLz4Used(), is(lz4Used));
        assertThat(recreated.isGzipUsed(), is(gzipUsed));
        assertThat(recreated.isHeartbeat(), is(heartbeat));
        assertThat(recreated.isAcknowledged(), is(acknowledged));
        assertThat(recreated, is(equalTo(flags)));
    }
    // </editor-fold>

    // <editor-fold defaultstate="collapsed" desc="equals and hashCode">
    @Test
    public void equals_sameFlagCombination_flagsAreEqualWithSameHashCode() {
        // arrange
        final BinaryMessageFlags a = new BinaryMessageFlags(true, false, false, false);
        final BinaryMessageFlags sameContent = new BinaryMessageFlags(true, false, false, false);

        // act, assert
        assertThat(a, is(equalTo(sameContent)));
        assertThat(a.hashCode(), is(equalTo(sameContent.hashCode())));
    }

    @Test
    public void equals_differentFlagCombination_flagsAreNotEqual() {
        // arrange
        final BinaryMessageFlags a = new BinaryMessageFlags(true, false, false, false);
        final BinaryMessageFlags different = new BinaryMessageFlags(false, true, false, false);

        // act, assert
        assertThat(a, is(not(equalTo(different))));
        assertThat(a.equals(null), is(false));
        assertThat(a.equals("not a BinaryMessageFlags"), is(false));
    }
    // </editor-fold>

    // <editor-fold defaultstate="collapsed" desc="fromDataInput">
    @Test
    public void fromDataInput_instanceMethodCalled_throwsException() {
        // arrange
        final BinaryMessageFlags flags = new BinaryMessageFlags(false, false, false, false);

        // act, assert: the instance method is intentionally unimplemented, callers must use
        // the static fromDataInputReplaceJava8 replacement
        assertThrows(RuntimeException.class, () -> flags.fromDataInput(null));
    }
    // </editor-fold>

    // <editor-fold defaultstate="collapsed" desc="illegal flag combinations">
    /**
     * lz4Used, gzipUsed, heartbeat and acknowledged are mutually exclusive by contract (see the
     * constructor Javadoc's truth tables). Assertions are enabled by Surefire's default
     * {@code enableAssertions=true}, so an illegal combination fails fast in the test JVM.
     */
    @Test
    public void constructor_lz4AndGzipBothTrue_assertionErrorThrown() {
        // act, assert
        assertThrows(AssertionError.class, () -> new BinaryMessageFlags(true, true, false, false));
    }

    @Test
    public void constructor_heartbeatWithCompression_assertionErrorThrown() {
        // act, assert
        assertThrows(AssertionError.class, () -> new BinaryMessageFlags(true, false, true, false));
    }

    @Test
    public void constructor_acknowledgedWithCompression_assertionErrorThrown() {
        // act, assert
        assertThrows(AssertionError.class, () -> new BinaryMessageFlags(true, false, false, true));
    }

    @Test
    public void constructor_acknowledgedWithHeartbeat_assertionErrorThrown() {
        // act, assert
        assertThrows(AssertionError.class, () -> new BinaryMessageFlags(false, false, true, true));
    }
    // </editor-fold>
}
