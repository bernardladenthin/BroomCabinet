// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap.jdbc;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.sql.Types;

import org.junit.jupiter.api.Test;

/**
 * The column types created in the target, above all how long text columns become.
 */
public class DialectTest {

    /** What Impala's driver reports for a {@code STRING} column. */
    private static final int UNBOUNDED = Integer.MAX_VALUE;

    @Test
    public void forUrl() {
        assertEquals(Dialect.EXASOL, Dialect.forUrl("jdbc:exa:host:8563"));
        assertEquals(Dialect.EXASOL, Dialect.forUrl("JDBC:EXA:host:8563"));
        assertEquals(Dialect.MONETDB, Dialect.forUrl("jdbc:monetdb://host/db"));
        assertEquals(Dialect.GENERIC, Dialect.forUrl("jdbc:h2:mem:x"));
    }

    @Test
    public void parse() {
        assertEquals(Dialect.EXASOL, Dialect.parse(null, "jdbc:exa:host"));
        assertEquals(Dialect.EXASOL, Dialect.parse("auto", "jdbc:exa:host"));
        assertEquals(Dialect.MONETDB, Dialect.parse("MonetDB", "jdbc:exa:host"));
        assertEquals(Dialect.GENERIC, Dialect.parse("generic", "jdbc:exa:host"));
        assertThrows(IllegalArgumentException.class, () -> Dialect.parse("oracle", "jdbc:exa:host"));
    }

    @Test
    public void varchar_keepsTheDeclaredLength() {
        assertEquals("VARCHAR(255)", Dialect.EXASOL.columnType(column(Types.VARCHAR, 255, 0, 17)));
    }

    @Test
    public void varchar_unboundedGetsTheMeasuredLength() {
        // instead of the fixed VARCHAR(8192) that once broke at a 4594 character value of a 4096 column
        assertEquals("VARCHAR(4594)", Dialect.EXASOL.columnType(column(Types.VARCHAR, UNBOUNDED, 0, 4594)));
    }

    @Test
    public void varchar_unboundedAndOnlyNullsGetsLengthOne() {
        assertEquals("VARCHAR(1)", Dialect.GENERIC.columnType(column(Types.VARCHAR, UNBOUNDED, 0, 0)));
    }

    @Test
    public void varchar_unboundedAndUnmeasuredGetsTheMaximum() {
        assertEquals("VARCHAR(2000000)", Dialect.EXASOL.columnType(column(Types.VARCHAR, UNBOUNDED, 0, Column.UNKNOWN)));
        assertEquals("VARCHAR(1000000)", Dialect.GENERIC.columnType(column(Types.VARCHAR, 0, 0, Column.UNKNOWN)));
    }

    @Test
    public void varchar_longerThanTheTargetCanHoldFails() {
        Column column = column(Types.VARCHAR, UNBOUNDED, 0, 2_000_001);

        assertThrows(UnsupportedOperationException.class, () -> Dialect.EXASOL.columnType(column));
    }

    @Test
    public void char_keepsItsLengthUpTo2000() {
        assertEquals("CHAR(5)", Dialect.GENERIC.columnType(column(Types.CHAR, 5, 0, 5)));
        assertEquals("VARCHAR(2001)", Dialect.GENERIC.columnType(column(Types.CHAR, 2001, 0, 2001)));
    }

    @Test
    public void integers() {
        assertEquals("TINYINT", Dialect.GENERIC.columnType(column(Types.TINYINT, 3, 0, 1)));
        assertEquals("SMALLINT", Dialect.GENERIC.columnType(column(Types.SMALLINT, 5, 0, 1)));
        assertEquals("INTEGER", Dialect.GENERIC.columnType(column(Types.INTEGER, 10, 0, 1)));
        assertEquals("BIGINT", Dialect.GENERIC.columnType(column(Types.BIGINT, 19, 0, 1)));
    }

    @Test
    public void decimal_keepsPrecisionAndScale() {
        assertEquals("DECIMAL(10, 2)", Dialect.GENERIC.columnType(column(Types.DECIMAL, 10, 2, 5)));
    }

    @Test
    public void decimal_precisionIsCappedForExasol() {
        assertEquals("DECIMAL(36, 4)", Dialect.EXASOL.columnType(column(Types.DECIMAL, 38, 4, 5)));
        assertEquals("DECIMAL(38, 4)", Dialect.GENERIC.columnType(column(Types.DECIMAL, 38, 4, 5)));
    }

    @Test
    public void decimal_withoutPrecisionGetsTheMaximum() {
        assertEquals("DECIMAL(36, 0)", Dialect.EXASOL.columnType(column(Types.NUMERIC, 0, 0, 5)));
    }

    @Test
    public void otherTypes() {
        assertEquals("DOUBLE PRECISION", Dialect.EXASOL.columnType(column(Types.FLOAT, 0, 0, 1)));
        assertEquals("BOOLEAN", Dialect.EXASOL.columnType(column(Types.BOOLEAN, 0, 0, 1)));
        assertEquals("DATE", Dialect.EXASOL.columnType(column(Types.DATE, 0, 0, 1)));
        assertEquals("TIMESTAMP", Dialect.EXASOL.columnType(column(Types.TIMESTAMP, 0, 0, 1)));
        assertEquals("TIME", Dialect.GENERIC.columnType(column(Types.TIME, 0, 0, 1)));
    }

    @Test
    public void binary() {
        assertEquals("VARBINARY(16)", Dialect.GENERIC.columnType(column(Types.BINARY, 16, 0, 16)));
        assertEquals("VARBINARY(3)", Dialect.GENERIC.columnType(column(Types.BLOB, UNBOUNDED, 0, 3)));
        assertEquals("BLOB", Dialect.MONETDB.columnType(column(Types.VARBINARY, 16, 0, 16)));
    }

    @Test
    public void exasol_hasNoBinaryAndNoTime() {
        assertThrows(UnsupportedOperationException.class, () -> Dialect.EXASOL.columnType(column(Types.VARBINARY, 16, 0, 1)));
        assertThrows(UnsupportedOperationException.class, () -> Dialect.EXASOL.columnType(column(Types.TIME, 0, 0, 1)));
    }

    private static Column column(int jdbcType, int size, int decimalDigits, long longest) {
        return new Column("c", jdbcType, "T", size, decimalDigits, longest);
    }
}
