// SPDX-FileCopyrightText: 2016 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap.jdbc;

/**
 * One column as the source's {@link java.sql.DatabaseMetaData#getColumns} describes it, plus
 * what the export measured.
 *
 * @param name          as stored in the source
 * @param jdbcType      a {@link java.sql.Types} constant
 * @param typeName      the source's own name of the type, for humans
 * @param size          {@code COLUMN_SIZE}: length of character and binary types, precision of
 *                      numeric types; {@code 0} or huge when unbounded
 * @param decimalDigits {@code DECIMAL_DIGITS}: the scale of numeric types
 * @param longest       the longest value written, in characters (or bytes for binary
 *                      columns); {@link #UNKNOWN} before an export measured it
 */
public record Column(String name, int jdbcType, String typeName, int size, int decimalDigits, long longest) {

    public static final long UNKNOWN = -1;

    public Column withLongest(long longest) {
        return new Column(name, jdbcType, typeName, size, decimalDigits, longest);
    }

    public ValueCodec codec() {
        return ValueCodec.of(jdbcType);
    }
}
