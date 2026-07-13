// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.binaryMessage;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotEquals;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.util.Arrays;

import org.junit.Test;

import net.ladenthin.jackpot.util.BinaryMessageFlags;

/**
 * {@link BinaryMessageFlags} hand-packs four booleans into a single {@code int} on the wire
 * (see {@code toInt()}/{@code fromInt(int)}). That bit-packing has no test coverage anywhere
 * else in the project, so these tests pin every individual bit plus every combination round trip.
 */
public class TestBinaryMessageFlags {

    private BinaryMessageFlags recreate(BinaryMessageFlags flags) throws IOException {
        final ByteArrayOutputStream baos = new ByteArrayOutputStream();
        final DataOutputStream dOut = new DataOutputStream(baos);
        flags.toDataOutput(dOut);

        final ByteArrayInputStream bais = new ByteArrayInputStream(baos.toByteArray());
        final DataInputStream dIn = new DataInputStream(bais);
        return BinaryMessageFlags.fromDataInputReplaceJava8(dIn);
    }

    @Test
    public void allFlagsFalseRoundTrips() throws IOException {
        final BinaryMessageFlags flags = new BinaryMessageFlags(false, false, false, false);
        final BinaryMessageFlags recreated = recreate(flags);

        assertFalse(recreated.isLz4Used());
        assertFalse(recreated.isGzipUsed());
        assertFalse(recreated.isHeartbeat());
        assertFalse(recreated.isAcknowledged());
        assertEquals(flags, recreated);
    }

    @Test
    public void lz4UsedFlagRoundTripsAlone() throws IOException {
        final BinaryMessageFlags flags = new BinaryMessageFlags(true, false, false, false);
        final BinaryMessageFlags recreated = recreate(flags);

        assertTrue(recreated.isLz4Used());
        assertFalse(recreated.isGzipUsed());
        assertFalse(recreated.isHeartbeat());
        assertFalse(recreated.isAcknowledged());
    }

    @Test
    public void gzipUsedFlagRoundTripsAlone() throws IOException {
        final BinaryMessageFlags flags = new BinaryMessageFlags(false, true, false, false);
        final BinaryMessageFlags recreated = recreate(flags);

        assertFalse(recreated.isLz4Used());
        assertTrue(recreated.isGzipUsed());
        assertFalse(recreated.isHeartbeat());
        assertFalse(recreated.isAcknowledged());
    }

    @Test
    public void heartbeatFlagRoundTripsAlone() throws IOException {
        final BinaryMessageFlags flags = new BinaryMessageFlags(false, false, true, false);
        final BinaryMessageFlags recreated = recreate(flags);

        assertFalse(recreated.isLz4Used());
        assertFalse(recreated.isGzipUsed());
        assertTrue(recreated.isHeartbeat());
        assertFalse(recreated.isAcknowledged());
    }

    @Test
    public void acknowledgedFlagRoundTripsAlone() throws IOException {
        final BinaryMessageFlags flags = new BinaryMessageFlags(false, false, false, true);
        final BinaryMessageFlags recreated = recreate(flags);

        assertFalse(recreated.isLz4Used());
        assertFalse(recreated.isGzipUsed());
        assertFalse(recreated.isHeartbeat());
        assertTrue(recreated.isAcknowledged());
    }

    /**
     * Every legal (non-exclusive) combination must survive the toInt()/fromInt() bit packing,
     * i.e. no two flags may alias onto the same bit.
     */
    @Test
    public void everyLegalCombinationRoundTrips() throws IOException {
        final boolean[][] legalCombinations = {
            {false, false, false, false},
            {true, false, false, false},
            {false, true, false, false},
            {false, false, true, false},
            {false, false, false, true},
        };

        for (final boolean[] combination : legalCombinations) {
            final BinaryMessageFlags flags =
                new BinaryMessageFlags(combination[0], combination[1], combination[2], combination[3]);
            final BinaryMessageFlags recreated = recreate(flags);
            assertEquals(Arrays.toString(combination), flags, recreated);
        }
    }

    @Test
    public void equalsAndHashCodeContract() {
        final BinaryMessageFlags a = new BinaryMessageFlags(true, false, false, false);
        final BinaryMessageFlags sameContent = new BinaryMessageFlags(true, false, false, false);
        final BinaryMessageFlags different = new BinaryMessageFlags(false, true, false, false);

        assertEquals(a, sameContent);
        assertEquals(a.hashCode(), sameContent.hashCode());
        assertNotEquals(a, different);
        assertNotEquals(a, null);
        assertNotEquals(a, "not a BinaryMessageFlags");
    }

    @Test
    public void fromDataInputThrowsInsteadOfSilentlyMisreading() {
        try {
            new BinaryMessageFlags(false, false, false, false).fromDataInput(null);
            fail("expected RuntimeException directing callers to the Java 8 replacement method");
        } catch (RuntimeException expected) {
            // expected: the instance method is intentionally unimplemented, see class Javadoc
        } catch (IOException e) {
            fail("unexpected IOException: " + e);
        }
    }

    /**
     * lz4Used and gzipUsed are mutually exclusive by contract (see the constructor Javadoc's
     * truth table). Assertions are enabled by Surefire's default {@code enableAssertions=true},
     * so an illegal combination is expected to fail fast here.
     */
    @Test(expected = AssertionError.class)
    public void constructorRejectsLz4AndGzipBothTrue() {
        new BinaryMessageFlags(true, true, false, false);
    }

    @Test(expected = AssertionError.class)
    public void constructorRejectsHeartbeatWithCompression() {
        new BinaryMessageFlags(true, false, true, false);
    }

    @Test(expected = AssertionError.class)
    public void constructorRejectsAcknowledgedWithCompression() {
        new BinaryMessageFlags(true, false, false, true);
    }

    @Test(expected = AssertionError.class)
    public void constructorRejectsAcknowledgedWithHeartbeat() {
        new BinaryMessageFlags(false, false, true, true);
    }
}
