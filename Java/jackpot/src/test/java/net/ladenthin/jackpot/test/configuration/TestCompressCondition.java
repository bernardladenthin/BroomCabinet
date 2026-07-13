// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.configuration;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

import net.ladenthin.jackpot.configuration.BooleanCondition;
import net.ladenthin.jackpot.configuration.CompressCondition;

/**
 * {@link CompressCondition#conditionMatch(int)} is the switch that decides whether a message
 * gets compressed at all ({@link net.ladenthin.jackpot.util.BinaryMessage#box}). Before this
 * test it had no direct coverage: every existing fixture only ever exercises the
 * {@code greaterEqual} branch (see {@code Common.alwaysTrueCompressCondition}). Each branch of
 * the enum switch is pinned individually here, including its boundary.
 */
public class TestCompressCondition {

    private static final int THRESHOLD = 100;

    @Test
    public void equalMatchesOnlyExactLength() {
        final CompressCondition condition = new CompressCondition(BooleanCondition.equal, THRESHOLD, false);

        assertTrue(condition.conditionMatch(THRESHOLD));
        assertFalse(condition.conditionMatch(THRESHOLD - 1));
        assertFalse(condition.conditionMatch(THRESHOLD + 1));
    }

    @Test
    public void greaterMatchesStrictlyAboveThreshold() {
        final CompressCondition condition = new CompressCondition(BooleanCondition.greater, THRESHOLD, false);

        assertFalse(condition.conditionMatch(THRESHOLD));
        assertTrue(condition.conditionMatch(THRESHOLD + 1));
        assertFalse(condition.conditionMatch(THRESHOLD - 1));
    }

    @Test
    public void greaterEqualMatchesThresholdAndAbove() {
        final CompressCondition condition = new CompressCondition(BooleanCondition.greaterEqual, THRESHOLD, false);

        assertTrue(condition.conditionMatch(THRESHOLD));
        assertTrue(condition.conditionMatch(THRESHOLD + 1));
        assertFalse(condition.conditionMatch(THRESHOLD - 1));
    }

    @Test
    public void lowerMatchesStrictlyBelowThreshold() {
        final CompressCondition condition = new CompressCondition(BooleanCondition.lower, THRESHOLD, false);

        assertFalse(condition.conditionMatch(THRESHOLD));
        assertTrue(condition.conditionMatch(THRESHOLD - 1));
        assertFalse(condition.conditionMatch(THRESHOLD + 1));
    }

    @Test
    public void lowerEqualMatchesThresholdAndBelow() {
        final CompressCondition condition = new CompressCondition(BooleanCondition.lowerEqual, THRESHOLD, false);

        assertTrue(condition.conditionMatch(THRESHOLD));
        assertTrue(condition.conditionMatch(THRESHOLD - 1));
        assertFalse(condition.conditionMatch(THRESHOLD + 1));
    }

    @Test
    public void notEqualMatchesEverythingButThreshold() {
        final CompressCondition condition = new CompressCondition(BooleanCondition.notEqual, THRESHOLD, false);

        assertFalse(condition.conditionMatch(THRESHOLD));
        assertTrue(condition.conditionMatch(THRESHOLD - 1));
        assertTrue(condition.conditionMatch(THRESHOLD + 1));
    }

    @Test
    public void copyConstructorPreservesAllFields() {
        final CompressCondition original = new CompressCondition(BooleanCondition.lower, THRESHOLD, true);
        final CompressCondition copy = new CompressCondition(original);

        assertTrue(copy.booleanCondition == original.booleanCondition);
        assertTrue(copy.length == original.length);
        assertTrue(copy.useOnlyIfCompressedLower == original.useOnlyIfCompressedLower);
    }

    @Test
    public void defaultConstructorUsesDocumentedMtuDerivedDefaults() {
        final CompressCondition defaultCondition = new CompressCondition();

        assertTrue(defaultCondition.booleanCondition == BooleanCondition.greaterEqual);
        assertTrue(defaultCondition.length == CompressCondition.minimalLength);
        assertTrue(defaultCondition.useOnlyIfCompressedLower);
        // pin the documented MTU-derived arithmetic (1500 - 20 - 20 - 12 - 1 - 8) so a future
        // edit to the formula is a deliberate, visible change rather than an accidental drift.
        assertTrue(CompressCondition.minimalLength == 1439);
    }
}
