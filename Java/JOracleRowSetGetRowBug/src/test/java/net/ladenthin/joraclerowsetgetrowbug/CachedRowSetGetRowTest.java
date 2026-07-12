// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.joraclerowsetgetrowbug;

import static org.hamcrest.CoreMatchers.is;
import static org.hamcrest.CoreMatchers.not;
import static org.hamcrest.MatcherAssert.assertThat;
import static org.junit.Assert.assertThrows;

import java.sql.SQLException;

import javax.sql.rowset.CachedRowSet;
import javax.sql.rowset.RowSetProvider;

import org.junit.Test;

/**
 * Demonstrates the {@link CachedRowSet#getRow()} divergence between the JDK reference
 * implementation and Oracle's {@code OracleCachedRowSet} once the cursor is {@code afterLast()}.
 *
 * <p>The JDBC specification ({@link java.sql.ResultSet#getRow()}) states that a value of
 * {@code 0} indicates there is no current row, so {@code getRow()} must return {@code 0} both
 * before the first row and after the last row.</p>
 *
 * <p>Root cause (decompiled from ojdbc): Oracle's {@code getRow()} is
 * {@code if (presentRow > rowCount) return rowCount; return presentRow;}. At {@code afterLast()}
 * the cursor field {@code presentRow == rowCount + 1}, so the first branch clamps the result to
 * {@code rowCount} instead of returning {@code 0}. The {@code beforeFirst()} case
 * ({@code presentRow == 0}) is correct only incidentally. See {@code BUG.md} for the full analysis.</p>
 */
public class CachedRowSetGetRowTest {

    /** Value {@code getRow()} must return when the cursor is not on a valid row, per the JDBC spec. */
    private static final int EXPECTED_NO_CURRENT_ROW = 0;

    /** Number of rows the shared source query produces. */
    private static final int ROW_COUNT = DemoRowSets.ROW_COUNT;

    /**
     * The JDK reference implementation conforms to the spec: {@code getRow()} is {@code 0} before
     * the first row, equals the 1-based row number while iterating, and returns to {@code 0} once
     * the cursor is {@code afterLast()}.
     *
     * @throws Exception if the rowset cannot be created, populated, or navigated
     */
    @Test
    public void referenceImpl_afterLast_getRowIsZero() throws Exception {
        try (CachedRowSet crs = DemoRowSets.referenceCachedRowSet()) {
            assertThat("populate() leaves the cursor before the first row",
                    crs.getRow(), is(EXPECTED_NO_CURRENT_ROW));

            int rowNumber = 0;
            while (crs.next()) {
                rowNumber++;
                assertThat("getRow() must equal the current 1-based row number while on a valid row",
                        crs.getRow(), is(rowNumber));
            }

            assertThat("sanity: the source produced the expected number of rows",
                    rowNumber, is(ROW_COUNT));
            assertThat("cursor must be after the last row", crs.isAfterLast(), is(true));
            assertThat("JDBC spec: getRow() returns 0 when there is no current row (afterLast)",
                    crs.getRow(), is(EXPECTED_NO_CURRENT_ROW));
        }
    }

    /**
     * {@code OracleCachedRowSet} agrees with the reference implementation while the cursor is on a
     * valid row, but diverges at {@code afterLast()} by returning the total row count instead of
     * {@code 0} (the {@code presentRow > rowCount} clamp in its {@code getRow()}).
     *
     * <p>This is a deliberate tripwire: it pins the <em>current</em>, non-conforming behavior. If a
     * future ojdbc release fixes {@code getRow()} to return {@code 0} at {@code afterLast()} (per
     * {@link java.sql.ResultSet#getRow()}), this test fails &mdash; which is exactly the signal to
     * watch for while walking the {@code ojdbc.version} property.</p>
     *
     * @throws Exception if the rowset cannot be created, populated, or navigated
     */
    @Test
    public void oracleImpl_afterLast_divergesFromSpec() throws Exception {
        try (CachedRowSet crs = DemoRowSets.oracleCachedRowSet()) {
            int rowNumber = 0;
            while (crs.next()) {
                rowNumber++;
                assertThat("while on a valid row both implementations agree: getRow() == row number",
                        crs.getRow(), is(rowNumber));
            }

            assertThat("sanity: the source produced the expected number of rows",
                    rowNumber, is(ROW_COUNT));
            assertThat("cursor must be after the last row", crs.isAfterLast(), is(true));

            final int afterLast = crs.getRow();
            assertThat("OracleCachedRowSet.getRow() at afterLast() must differ from the spec value of 0",
                    afterLast, is(not(EXPECTED_NO_CURRENT_ROW)));
            assertThat("OracleCachedRowSet.getRow() at afterLast() returns the clamped row count",
                    afterLast, is(ROW_COUNT));
        }
    }

    /**
     * {@code OracleCachedRowSet.getRow()} is incidentally correct at {@code beforeFirst()}: the
     * decompiled implementation returns {@code presentRow} directly there (which is {@code 0}),
     * skipping the {@code presentRow > rowCount} clamp that breaks the {@code afterLast()} case.
     * This pins that only the {@code afterLast()} end is non-conforming.
     *
     * @throws Exception if the rowset cannot be created or populated
     */
    @Test
    public void oracleImpl_beforeFirst_getRowIsZero() throws Exception {
        try (CachedRowSet crs = DemoRowSets.oracleCachedRowSet()) {
            assertThat("a freshly populated cursor is positioned before the first row",
                    crs.isBeforeFirst(), is(true));
            assertThat("getRow() is 0 before the first row (presentRow == 0)",
                    crs.getRow(), is(EXPECTED_NO_CURRENT_ROW));
        }
    }

    /**
     * Documents a related gotcha discovered while building this reproducer:
     * {@code OracleCachedRowSet.populate(ResultSet)} requires a source backed by a live
     * {@link java.sql.Statement}. Populating from a disconnected JDK rowset (whose
     * {@code getStatement()} is {@code null}) throws {@link NullPointerException} inside
     * {@code OracleCachedRowSet.populateInit} (it calls {@code getStatement().getMaxFieldSize()}).
     * The JDK reference implementation populates from the very same source without error &mdash;
     * shown here as the contrast and the reason a live H2 {@link java.sql.ResultSet} is used elsewhere.
     *
     * @throws Exception if a rowset cannot be created or the source cannot be built
     */
    @Test
    public void oracleImpl_populateFromDisconnectedSource_throwsNpe() throws Exception {
        // The reference implementation accepts a disconnected source.
        try (CachedRowSet reference = RowSetProvider.newFactory().createCachedRowSet();
                CachedRowSet source = DemoRowSets.disconnectedTwoRowSource()) {
            reference.populate(source);
            assertThat("reference impl populates fine from a disconnected source",
                    countRows(reference), is(ROW_COUNT));
        }

        // OracleCachedRowSet does not: populate() dereferences a null Statement.
        try (CachedRowSet oracle = DemoRowSets.newOracleCachedRowSet();
                CachedRowSet source = DemoRowSets.disconnectedTwoRowSource()) {
            assertThrows(NullPointerException.class, () -> oracle.populate(source));
        }
    }

    /**
     * Counts the rows of a rowset by iterating it to {@code afterLast()}.
     *
     * @param crs the rowset to walk
     * @return the number of rows traversed
     * @throws SQLException if cursor movement fails
     */
    private static int countRows(CachedRowSet crs) throws SQLException {
        int rows = 0;
        while (crs.next()) {
            rows++;
        }
        return rows;
    }
}
