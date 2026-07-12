// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.joraclerowsetgetrowbug;

import java.sql.SQLException;

import javax.sql.rowset.CachedRowSet;

/**
 * Prints a side-by-side trace of {@link CachedRowSet#getRow()} for the JDK reference
 * implementation and Oracle's {@code OracleCachedRowSet}, walking the cursor from before the
 * first row, through every row, to after the last row.
 *
 * <p>Both implementations agree while the cursor is on a valid row ({@code getRow()} returns
 * the 1-based row number). They diverge once the cursor is {@code afterLast()}: the JDBC spec
 * (see {@link java.sql.ResultSet#getRow()}) requires {@code 0} when there is no current row,
 * which the reference implementation honours, while {@code OracleCachedRowSet} returns the
 * total row count instead.</p>
 *
 * <p>See {@code BUG.md} for the decompiled root cause and a copy-paste-ready bug report.</p>
 */
public final class Main {

    /** Value {@link CachedRowSet#getRow()} must return at {@code afterLast()} per the JDBC spec. */
    private static final int EXPECTED_AFTER_LAST_GET_ROW = 0;

    private Main() {
        // entry point only
    }

    /**
     * Runs the comparison and prints the verdict to standard out.
     *
     * @param args ignored
     * @throws SQLException if a rowset cannot be created or populated
     */
    public static void main(String[] args) throws SQLException {
        System.out.println("Oracle JDBC driver under test : ojdbc8 " + DemoRowSets.configuredOjdbcVersion()
                + " (build property)");
        System.out.println("Driver self-reported version  : " + DemoRowSets.oracleDriverVersion());
        System.out.println("Source query: " + DemoRowSets.SQL);
        System.out.println();

        final int referenceAfterLast;
        try (CachedRowSet reference = DemoRowSets.referenceCachedRowSet()) {
            referenceAfterLast = traverse(reference);
        }
        System.out.println();

        final int oracleAfterLast;
        try (CachedRowSet oracle = DemoRowSets.oracleCachedRowSet()) {
            oracleAfterLast = traverse(oracle);
        }
        System.out.println();

        printVerdict(referenceAfterLast, oracleAfterLast);
    }

    /**
     * Walks the rowset to {@code afterLast()}, printing {@link CachedRowSet#getRow()} at each
     * cursor position.
     *
     * @param crs a freshly populated rowset (cursor before the first row)
     * @return the value of {@code getRow()} once the cursor is {@code afterLast()}
     * @throws SQLException if cursor movement fails
     */
    private static int traverse(CachedRowSet crs) throws SQLException {
        System.out.println("== " + crs.getClass().getName() + " ==");
        System.out.printf("  beforeFirst : getRow()=%d (isBeforeFirst=%b)%n",
                crs.getRow(), crs.isBeforeFirst());

        int rowNumber = 0;
        while (crs.next()) {
            rowNumber++;
            System.out.printf("  row %-7d : getRow()=%d%n", rowNumber, crs.getRow());
        }

        final int afterLast = crs.getRow();
        final String verdict = afterLast == EXPECTED_AFTER_LAST_GET_ROW ? "OK" : "<-- DIVERGENCE";
        System.out.printf("  afterLast   : getRow()=%d (isAfterLast=%b)  expected %d per java.sql.ResultSet#getRow  %s%n",
                afterLast, crs.isAfterLast(), EXPECTED_AFTER_LAST_GET_ROW, verdict);
        return afterLast;
    }

    /**
     * Prints the overall conclusion comparing the two {@code afterLast()} values.
     *
     * @param referenceAfterLast {@code getRow()} from the reference implementation at {@code afterLast()}
     * @param oracleAfterLast    {@code getRow()} from {@code OracleCachedRowSet} at {@code afterLast()}
     */
    private static void printVerdict(int referenceAfterLast, int oracleAfterLast) {
        System.out.println("Summary - getRow() while afterLast():");
        System.out.printf("  reference implementation : %d%n", referenceAfterLast);
        System.out.printf("  OracleCachedRowSet       : %d%n", oracleAfterLast);
        if (oracleAfterLast != EXPECTED_AFTER_LAST_GET_ROW) {
            System.out.println("DIVERGENCE CONFIRMED: OracleCachedRowSet.getRow() returned " + oracleAfterLast
                    + " after afterLast(); the JDBC spec (java.sql.ResultSet#getRow) requires "
                    + EXPECTED_AFTER_LAST_GET_ROW + ".");
            System.out.println("Mechanism: OracleCachedRowSet.getRow() returns rowCount when presentRow > rowCount "
                    + "(the afterLast position) instead of 0. See BUG.md for the decompiled analysis.");
        } else {
            System.out.println("No divergence on this driver version: OracleCachedRowSet.getRow() returned "
                    + EXPECTED_AFTER_LAST_GET_ROW + " as required.");
        }
    }
}
