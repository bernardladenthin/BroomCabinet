// SPDX-FileCopyrightText: 2016 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap.jdbc;

import java.sql.Connection;
import java.sql.DatabaseMetaData;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/**
 * Tables and columns of a schema, read from {@link DatabaseMetaData}.
 *
 * <p>The metadata calls take LIKE patterns, in which {@code _} matches any character:
 * {@code order_items} would also find {@code orderXitems}. Instead of escaping (which not every
 * driver honours), every result is compared with the exact name.</p>
 */
public final class Catalog {

    private Catalog() {
    }

    /** {@code schema}, or the connection's current schema when {@code schema} is empty. */
    public static String schemaOrCurrent(Connection connection, String schema) throws SQLException {
        if (schema != null && !schema.isEmpty()) {
            return schema;
        }
        String current = connection.getSchema();
        if (current == null || current.isEmpty()) {
            throw new SQLException("The source connection has no current schema; set the source schema.");
        }
        return current;
    }

    /** The table and view names of {@code schema}, sorted. */
    public static List<String> tables(Connection connection, String schema) throws SQLException {
        List<String> tables = new ArrayList<>();
        try (ResultSet rs = connection.getMetaData().getTables(null, schema, "%", null)) {
            while (rs.next()) {
                if (sameOrUnknown(schema, rs.getString("TABLE_SCHEM"))) {
                    tables.add(rs.getString("TABLE_NAME"));
                }
            }
        }
        tables.sort(Comparator.naturalOrder());
        return tables;
    }

    /** The columns of {@code table} in their ordinal order. */
    public static List<Column> columns(Connection connection, String schema, String table) throws SQLException {
        Map<Integer, Column> byPosition = new TreeMap<>();
        try (ResultSet rs = connection.getMetaData().getColumns(null, schema, table, "%")) {
            while (rs.next()) {
                if (!table.equals(rs.getString("TABLE_NAME")) || !sameOrUnknown(schema, rs.getString("TABLE_SCHEM"))) {
                    continue;
                }
                Column column = new Column(
                        rs.getString("COLUMN_NAME"),
                        rs.getInt("DATA_TYPE"),
                        rs.getString("TYPE_NAME"),
                        rs.getInt("COLUMN_SIZE"),
                        rs.getInt("DECIMAL_DIGITS"),
                        Column.UNKNOWN);
                byPosition.put(rs.getInt("ORDINAL_POSITION"), column);
            }
        }
        if (byPosition.isEmpty()) {
            throw new SQLException("No columns found for table " + table + " in schema " + schema);
        }
        return new ArrayList<>(byPosition.values());
    }

    /** {@code SELECT COUNT(*)} of a table; {@code qualifiedTable} must already be quoted. */
    public static long count(Connection connection, String qualifiedTable) throws SQLException {
        try (Statement statement = connection.createStatement();
             ResultSet rs = statement.executeQuery("SELECT COUNT(*) FROM " + qualifiedTable)) {
            rs.next();
            return rs.getLong(1);
        }
    }

    private static boolean sameOrUnknown(String expected, String actual) {
        return expected == null || actual == null || expected.equals(actual);
    }
}
