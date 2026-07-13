// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.configuration;

import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.is;

import java.util.stream.Stream;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;

import net.ladenthin.jackpot.configuration.BooleanCondition;
import net.ladenthin.jackpot.configuration.CompressCondition;

/**
 * {@link CompressCondition#conditionMatch(int)} is the switch that decides whether a message
 * gets compressed at all ({@link net.ladenthin.jackpot.util.BinaryMessage#box}). Each branch
 * of the enum switch is pinned individually here, including its boundary values.
 */
public class CompressConditionTest {

    /**
     * The threshold length every condition in this test is configured with.
     */
    private static final int THRESHOLD = 100;

    /**
     * Symbolic name for the local {@code @MethodSource} providing one row per
     * {@link BooleanCondition} branch and boundary.
     */
    private static final String DATA_PROVIDER_CONDITION_MATCH = "conditionMatchArguments";

    /**
     * One row per (condition, probed length, expected match) covering every enum branch at,
     * below and above the threshold.
     */
    static Stream<Arguments> conditionMatchArguments() {
        return Stream.of(
            Arguments.of(BooleanCondition.equal, THRESHOLD, true),
            Arguments.of(BooleanCondition.equal, THRESHOLD - 1, false),
            Arguments.of(BooleanCondition.equal, THRESHOLD + 1, false),
            Arguments.of(BooleanCondition.greater, THRESHOLD, false),
            Arguments.of(BooleanCondition.greater, THRESHOLD - 1, false),
            Arguments.of(BooleanCondition.greater, THRESHOLD + 1, true),
            Arguments.of(BooleanCondition.greaterEqual, THRESHOLD, true),
            Arguments.of(BooleanCondition.greaterEqual, THRESHOLD - 1, false),
            Arguments.of(BooleanCondition.greaterEqual, THRESHOLD + 1, true),
            Arguments.of(BooleanCondition.lower, THRESHOLD, false),
            Arguments.of(BooleanCondition.lower, THRESHOLD - 1, true),
            Arguments.of(BooleanCondition.lower, THRESHOLD + 1, false),
            Arguments.of(BooleanCondition.lowerEqual, THRESHOLD, true),
            Arguments.of(BooleanCondition.lowerEqual, THRESHOLD - 1, true),
            Arguments.of(BooleanCondition.lowerEqual, THRESHOLD + 1, false),
            Arguments.of(BooleanCondition.notEqual, THRESHOLD, false),
            Arguments.of(BooleanCondition.notEqual, THRESHOLD - 1, true),
            Arguments.of(BooleanCondition.notEqual, THRESHOLD + 1, true)
        );
    }

    // <editor-fold defaultstate="collapsed" desc="conditionMatch">
    @ParameterizedTest
    @MethodSource(DATA_PROVIDER_CONDITION_MATCH)
    public void conditionMatch_lengthGiven_matchEqualsExpectation(
        BooleanCondition booleanCondition, int probedLength, boolean expectedMatch) {
        // arrange
        final CompressCondition condition = new CompressCondition(booleanCondition, THRESHOLD, false);

        // act, assert
        assertThat(condition.conditionMatch(probedLength), is(expectedMatch));
    }
    // </editor-fold>

    // <editor-fold defaultstate="collapsed" desc="constructors">
    @Test
    public void constructor_copyConstructorUsed_allFieldsPreserved() {
        // arrange
        final CompressCondition original = new CompressCondition(BooleanCondition.lower, THRESHOLD, true);

        // act
        final CompressCondition copy = new CompressCondition(original);

        // assert
        assertThat(copy.booleanCondition, is(equalTo(original.booleanCondition)));
        assertThat(copy.length, is(equalTo(original.length)));
        assertThat(copy.useOnlyIfCompressedLower, is(original.useOnlyIfCompressedLower));
    }

    @Test
    public void constructor_noArguments_usesDocumentedMtuDerivedDefaults() {
        // arrange, act
        final CompressCondition defaultCondition = new CompressCondition();

        // assert
        assertThat(defaultCondition.booleanCondition, is(equalTo(BooleanCondition.greaterEqual)));
        assertThat(defaultCondition.length, is(equalTo(CompressCondition.minimalLength)));
        assertThat(defaultCondition.useOnlyIfCompressedLower, is(true));
        // pin the documented MTU-derived arithmetic (1500 - 20 - 20 - 12 - 1 - 8) so a future
        // edit to the formula is a deliberate, visible change rather than an accidental drift.
        assertThat(CompressCondition.minimalLength, is(equalTo(1439)));
    }
    // </editor-fold>
}
