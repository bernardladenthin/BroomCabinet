// @formatter:off
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
 *
 */
// @formatter:on
package net.ladenthin.oraclecachedrowset;

import static org.hamcrest.CoreMatchers.is;
import static org.hamcrest.CoreMatchers.not;
import static org.junit.Assert.assertThat;

import javax.sql.rowset.CachedRowSet;

import org.junit.Test;

/**
 * Demonstrates the {@link CachedRowSet#getRow()} divergence between the JDK reference
 * implementation and Oracle's {@code OracleCachedRowSet} once the cursor is {@code afterLast()}.
 *
 * <p>The JDBC specification ({@link java.sql.ResultSet#getRow()}) states that a value of
 * {@code 0} indicates there is no current row, so {@code getRow()} must return {@code 0} both
 * before the first row and after the last row.</p>
 */
public class CachedRowSetGetRowTest {

    /** Value {@code getRow()} must return when the cursor is not on a valid row, per the JDBC spec. */
    private static final int EXPECTED_AFTER_LAST_GET_ROW = 0;

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
                    crs.getRow(), is(EXPECTED_AFTER_LAST_GET_ROW));

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
                    crs.getRow(), is(EXPECTED_AFTER_LAST_GET_ROW));
        }
    }

    /**
     * {@code OracleCachedRowSet} agrees with the reference implementation while the cursor is on a
     * valid row, but diverges at {@code afterLast()} by returning the total row count instead of
     * {@code 0}.
     *
     * <p>This is a deliberate tripwire: it pins the <em>current</em>, non-conforming behavior. If a
     * future ojdbc8 release fixes {@code getRow()} to return {@code 0} at {@code afterLast()} (per
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
                    afterLast, is(not(EXPECTED_AFTER_LAST_GET_ROW)));
            assertThat("OracleCachedRowSet.getRow() at afterLast() currently returns the row count",
                    afterLast, is(ROW_COUNT));
        }
    }
}
