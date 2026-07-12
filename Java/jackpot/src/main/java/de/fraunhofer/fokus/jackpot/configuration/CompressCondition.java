package de.fraunhofer.fokus.jackpot.configuration;

import java.io.Serializable;

/**
 * Immutable.
 *
 * @author bernard
 */
public class CompressCondition implements Serializable {

    private static final long serialVersionUID = 4932696799314199666L;

    /*
     * Calculate a minimum length for a fast compression.
     * regular MTU (Maximum Transmission Unit): 1500 byte
     * IP header: 20 byte
     * TCP header: 20 byte
     * Of course a RFC1323 Timestamp is used: 12 byte
     * flags (byte): 1 byte
     * length of byte (integer): 8 byte
     * 1500-20-20-12-1-8=1439
     */
    public final static int minimalLength = 1500 - 20 - 20 - 12 - 1 - 8;

    /**
     * Boolean condition member.
     */
    public final BooleanCondition booleanCondition;

    public final int length;

    /**
     * Only transmit if the compressed size is lower as the original size.
     */
    public final boolean useOnlyIfCompressedLower;

    /**
     * @param length
     * @return true if the condition match. Otherwise false.
     */
    final public boolean conditionMatch(int length) {
        switch (booleanCondition) {
        case equal:
            return length == this.length ? true : false;
        case greater:
            return length > this.length ? true : false;
        case greaterEqual:
            return length >= this.length ? true : false;
        case lower:
            return length < this.length ? true : false;
        case lowerEqual:
            return length <= this.length ? true : false;
        case notEqual:
            return length != this.length ? true : false;
        default:
            return false;
        }
    }

    public CompressCondition(final BooleanCondition booleanCondition, final int length,
        final boolean useOnlyIfCompressedLower) {
        this.booleanCondition = booleanCondition;
        this.length = length;
        this.useOnlyIfCompressedLower = useOnlyIfCompressedLower;
    }

    public CompressCondition(final CompressCondition compressCondition) {
        this.booleanCondition = compressCondition.booleanCondition;
        this.length = compressCondition.length;
        this.useOnlyIfCompressedLower = compressCondition.useOnlyIfCompressedLower;
    }

    public CompressCondition() {
        this(BooleanCondition.greaterEqual, minimalLength, true);
    }
}
