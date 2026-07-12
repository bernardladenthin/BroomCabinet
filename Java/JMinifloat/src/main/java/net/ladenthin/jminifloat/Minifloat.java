/**
 * Copyright 2026 Bernard Ladenthin bernard.ladenthin@gmail.com
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *    http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package net.ladenthin.jminifloat;

/**
 * An educational 8-bit floating-point value ("minifloat") that models IEEE-754
 * mechanics in a form small enough to reason about by hand.
 *
 * <p>Bit layout, most-significant bit first:</p>
 * <pre>
 *   [ S | E E E | M M M M ]
 *     0   1 2 3   4 5 6 7
 * </pre>
 * <ul>
 *   <li><b>sign</b> S at index {@value #SIGN_INDEX}</li>
 *   <li><b>exponent</b> E, 3 bits, stored in excess-3 (bias 3): stored
 *       {@code 000..111} means actual {@code -3..+4}</li>
 *   <li><b>mantissa</b> M, 4 bits, with an implicit hidden leading 1 for
 *       normalized numbers</li>
 * </ul>
 *
 * <p>Special cases follow IEEE-754: a zero exponent field encodes zero and
 * subnormals; an all-ones exponent field encodes infinity (mantissa 0) or NaN
 * (mantissa non-zero).</p>
 *
 * <p>Internally the eight bits are packed into the low byte of an {@code int}.</p>
 */
public final class Minifloat {

    // --- bit layout: [ S | E E E | M M M M ] ---------------------------------
    // Package-visible so tests can describe patterns via the layout rather than
    // hard-coding indices.
    static final int TOTAL_BITS = 8;
    static final int SIGN_INDEX = 0;
    static final int EXPONENT_FIRST_INDEX = 1;
    static final int EXPONENT_LAST_INDEX = 3;
    static final int MANTISSA_FIRST_INDEX = 4;
    static final int MANTISSA_LAST_INDEX = 7;

    private static final int EXPONENT_WIDTH = EXPONENT_LAST_INDEX - EXPONENT_FIRST_INDEX + 1; // 3
    private static final int MANTISSA_WIDTH = MANTISSA_LAST_INDEX - MANTISSA_FIRST_INDEX + 1; // 4
    private static final int EXPONENT_BIAS = 3;                       // excess-3
    private static final int EXPONENT_MASK = (1 << EXPONENT_WIDTH) - 1;   // 0b111
    private static final int MANTISSA_MASK = (1 << MANTISSA_WIDTH) - 1;   // 0b1111
    private static final int MANTISSA_STEP = 1 << MANTISSA_WIDTH;         // 16
    private static final int EXPONENT_ALL_ONES = EXPONENT_MASK;          // 7 -> inf / NaN
    private static final int MAX_STORED_EXPONENT = EXPONENT_ALL_ONES - 1; // 6 -> largest finite
    private static final double MAX_FINITE = 15.5;                       // largest representable magnitude
    private static final double SUBNORMAL_UNIT =
            Math.pow(2, 1 - EXPONENT_BIAS) / MANTISSA_STEP;             // smallest positive step, 1/64

    /** The eight bits packed into the low byte: {@code sign<<7 | exponent<<4 | mantissa}. */
    private int bits;

    /** Creates a minifloat equal to {@code +0.0}. */
    public Minifloat() {
        this.bits = 0;
    }

    /** Creates a minifloat holding the closest representable value to {@code value}. */
    public Minifloat(double value) {
        setValue(value);
    }

    private int signBit() {
        return (bits >> (TOTAL_BITS - 1)) & 1;
    }

    private int exponentField() {
        return (bits >> MANTISSA_WIDTH) & EXPONENT_MASK;
    }

    private int mantissaField() {
        return bits & MANTISSA_MASK;
    }

    private static int pack(int sign, int exponent, int mantissa) {
        return (sign << (TOTAL_BITS - 1))
                | ((exponent & EXPONENT_MASK) << MANTISSA_WIDTH)
                | (mantissa & MANTISSA_MASK);
    }

    /** Decodes the stored bits to a {@code double}. */
    public double getValue() {
        int exponent = exponentField();
        int mantissa = mantissaField();
        double magnitude;
        if (exponent == 0) {
            // zero and subnormals: 0.mantissa x 2^(1 - bias)
            magnitude = mantissa * SUBNORMAL_UNIT;
        } else if (exponent == EXPONENT_ALL_ONES) {
            if (mantissa != 0) {
                return Double.NaN;
            }
            magnitude = Double.POSITIVE_INFINITY;
        } else {
            // normalized: 1.mantissa x 2^(exponent - bias)
            double significand = 1.0 + mantissa / (double) MANTISSA_STEP;
            magnitude = significand * Math.pow(2, exponent - EXPONENT_BIAS);
        }
        return signBit() == 1 ? -magnitude : magnitude;
    }

    /** Encodes {@code value} into the closest representable minifloat (truncating the mantissa). */
    public void setValue(double value) {
        if (Double.isNaN(value)) {
            bits = pack(0, EXPONENT_ALL_ONES, MANTISSA_MASK);
            return;
        }
        int sign = 0;
        if (value < 0.0) {
            sign = 1;
            value = -value;
        }
        int exponent;
        int mantissa;
        if (value > MAX_FINITE) {                 // includes +infinity -> overflow
            exponent = EXPONENT_ALL_ONES;
            mantissa = 0;
        } else if (value < SUBNORMAL_UNIT) {      // includes 0.0 -> underflow to zero
            exponent = 0;
            mantissa = 0;
        } else if (value < 1.0 * Math.pow(2, 1 - EXPONENT_BIAS)) {
            // subnormal range [SUBNORMAL_UNIT, 2^(1-bias))
            exponent = 0;
            mantissa = (int) Math.floor(value / SUBNORMAL_UNIT);
        } else {
            // normalized
            int unbiased = Math.getExponent(value);                 // floor(log2(value))
            exponent = unbiased + EXPONENT_BIAS;
            double fraction = value / Math.pow(2, unbiased) - 1.0;   // [0, 1)
            mantissa = (int) Math.floor(fraction * MANTISSA_STEP);
            if (mantissa > MANTISSA_MASK) {
                mantissa = MANTISSA_MASK;
            }
            if (exponent > MAX_STORED_EXPONENT) {                   // rounded up into inf
                exponent = EXPONENT_ALL_ONES;
                mantissa = 0;
            }
        }
        bits = pack(sign, exponent, mantissa);
    }

    /** Adds {@code other} to this value (decode, add, re-encode). */
    public void add(Minifloat other) {
        setValue(getValue() + other.getValue());
    }

    /** Returns the 8-character bit string, most-significant bit first. */
    public String getBitString() {
        StringBuilder sb = new StringBuilder(TOTAL_BITS);
        for (int i = TOTAL_BITS - 1; i >= 0; i--) {
            sb.append((bits >> i) & 1);
        }
        return sb.toString();
    }

    /**
     * Builds a minifloat from a most-significant-bit-first {@code '0'}/{@code '1'}
     * pattern. Inputs shorter than {@link #TOTAL_BITS} are zero-padded on the
     * right; longer inputs are truncated.
     */
    public static Minifloat bitsToMinifloat(char[] newBits) {
        int packed = 0;
        int count = Math.min(newBits.length, TOTAL_BITS);
        for (int i = 0; i < count; i++) {
            if (newBits[i] == '1') {
                packed |= 1 << (TOTAL_BITS - 1 - i);
            }
        }
        Minifloat result = new Minifloat();
        result.bits = packed;
        return result;
    }

    @Override
    public String toString() {
        return Double.toString(getValue());
    }
}
