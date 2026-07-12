// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jminifloat;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

/**
 * Tests for {@link Minifloat}.
 *
 * <p>The {@code decode*} / {@code encode*} / {@code add*} tests describe the
 * expected behaviour. The {@code bitsToMinifloat_*} tests pin the intended
 * behaviour of {@link Minifloat#bitsToMinifloat(char[])} for inputs whose length
 * differs from 8; they fail against the original {@code Math.max(...)} loop bound
 * (which throws {@link ArrayIndexOutOfBoundsException}) and pass once it is fixed
 * to {@code Math.min(...)}.</p>
 */
public class MinifloatTest {

    private static final double DELTA = 0.0;

    private static final int EXPONENT_WIDTH =
            Minifloat.EXPONENT_LAST_INDEX - Minifloat.EXPONENT_FIRST_INDEX + 1;
    private static final int MANTISSA_WIDTH =
            Minifloat.MANTISSA_LAST_INDEX - Minifloat.MANTISSA_FIRST_INDEX + 1;

    /**
     * Builds a Minifloat from a {@code sign} / {@code exponent} / {@code mantissa}
     * bit pattern, validating each field width against the layout constants so the
     * tests never hard-code the field positions.
     */
    private static Minifloat of(String sign, String exponent, String mantissa) {
        assertEquals("sign width", 1, sign.length());
        assertEquals("exponent width", EXPONENT_WIDTH, exponent.length());
        assertEquals("mantissa width", MANTISSA_WIDTH, mantissa.length());
        return Minifloat.bitsToMinifloat((sign + exponent + mantissa).toCharArray());
    }

    // --- layout constants -----------------------------------------------------

    @Test
    public void layoutConstantsAreConsistent() {
        assertEquals(0, Minifloat.SIGN_INDEX);
        assertEquals(Minifloat.EXPONENT_LAST_INDEX + 1, Minifloat.MANTISSA_FIRST_INDEX);
        assertEquals(Minifloat.TOTAL_BITS - 1, Minifloat.MANTISSA_LAST_INDEX);
        // sign(1) + exponent + mantissa == total
        assertEquals(Minifloat.TOTAL_BITS, 1 + EXPONENT_WIDTH + MANTISSA_WIDTH);
    }

    // --- decoding: explicit bit patterns -> value -----------------------------

    @Test
    public void decodeZero() {
        assertEquals(0.0, of("0", "000", "0000").getValue(), DELTA);
    }

    @Test
    public void decodeOne() {
        // exp 011 (=0), mantissa 0000, hidden bit -> 1.0
        assertEquals(1.0, of("0", "011", "0000").getValue(), DELTA);
    }

    @Test
    public void decodeOnePointFive() {
        // exp 011 (=0), mantissa 1000 -> 1.5
        assertEquals(1.5, of("0", "011", "1000").getValue(), DELTA);
    }

    @Test
    public void decodeTwo() {
        // exp 100 (=1), mantissa 0000 -> 2.0
        assertEquals(2.0, of("0", "100", "0000").getValue(), DELTA);
    }

    @Test
    public void decodeMaxNormal() {
        // exp 110 (=3), mantissa 1111 -> 1.9375 * 8 = 15.5
        assertEquals(15.5, of("0", "110", "1111").getValue(), DELTA);
    }

    @Test
    public void decodePositiveInfinity() {
        assertEquals(Double.POSITIVE_INFINITY, of("0", "111", "0000").getValue(), DELTA);
    }

    @Test
    public void decodeNegativeInfinity() {
        assertEquals(Double.NEGATIVE_INFINITY, of("1", "111", "0000").getValue(), DELTA);
    }

    @Test
    public void decodeNaN() {
        // exponent all ones + non-zero mantissa -> NaN
        assertTrue(Double.isNaN(of("0", "111", "1000").getValue()));
    }

    // --- encoding: double -> value round-trips --------------------------------

    @Test
    public void encodeRoundTrips() {
        double[] values = {0.0, 1.0, 1.5, 2.0, -1.0, -2.0, 0.25, 0.125, 15.5};
        for (double v : values) {
            assertEquals("round-trip of " + v, v, new Minifloat(v).getValue(), DELTA);
        }
    }

    @Test
    public void encodeOverflowBecomesInfinity() {
        assertEquals(Double.POSITIVE_INFINITY, new Minifloat(100.0).getValue(), DELTA);
    }

    @Test
    public void encodeUnderflowBecomesZero() {
        // below the smallest denormal (1/64) rounds to 0
        assertEquals(0.0, new Minifloat(0.001).getValue(), DELTA);
    }

    @Test
    public void bitStringHasLayoutLength() {
        assertEquals(Minifloat.TOTAL_BITS, new Minifloat(1.0).getBitString().length());
        assertEquals("00110000", new Minifloat(1.0).getBitString());
    }

    // --- addition -------------------------------------------------------------

    @Test
    public void addOnePlusOne() {
        Minifloat a = new Minifloat(1.0);
        a.add(new Minifloat(1.0));
        assertEquals(2.0, a.getValue(), DELTA);
    }

    @Test
    public void addTwoPlusTwo() {
        Minifloat a = new Minifloat(2.0);
        a.add(new Minifloat(2.0));
        assertEquals(4.0, a.getValue(), DELTA);
    }

    @Test
    public void addOnePlusTwo() {
        Minifloat a = new Minifloat(1.0);
        a.add(new Minifloat(2.0));
        assertEquals(3.0, a.getValue(), DELTA);
    }

    // --- bitsToMinifloat length handling (the bug) ----------------------------

    @Test
    public void bitsToMinifloat_shorterInput_isZeroPadded() {
        // fewer than TOTAL_BITS given -> remaining bits default to '0', no exception.
        Minifloat m = Minifloat.bitsToMinifloat("0100".toCharArray());
        assertEquals("01000000", m.getBitString());
        assertEquals(2.0, m.getValue(), DELTA);
    }

    @Test
    public void bitsToMinifloat_longerInput_isTruncated() {
        // more than TOTAL_BITS given -> only the first 8 are used, no exception.
        Minifloat m = Minifloat.bitsToMinifloat("0100000011".toCharArray());
        assertEquals("01000000", m.getBitString());
        assertEquals(2.0, m.getValue(), DELTA);
    }
}
