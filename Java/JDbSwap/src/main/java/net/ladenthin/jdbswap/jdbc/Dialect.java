// SPDX-FileCopyrightText: 2016 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap.jdbc;

import java.sql.Connection;
import java.sql.SQLException;
import java.sql.Statement;
import java.sql.Types;
import java.util.Locale;

/**
 * What differs between target databases: column types and the housekeeping after a load.
 */
public enum Dialect {

    /** Standard SQL types; nothing to do after a load. */
    GENERIC(1_000_000, 38),

    /**
     * Exasol: no binary and no time-of-day type, {@code VARCHAR} up to 2,000,000 characters,
     * {@code DECIMAL} up to precision 36, and {@code REORGANIZE} after creating and loading.
     */
    EXASOL(2_000_000, 36) {
        @Override
        String binaryType(Column column) {
            throw new UnsupportedOperationException("Exasol has no binary column type: " + column);
        }

        @Override
        String timeType(Column column) {
            throw new UnsupportedOperationException("Exasol has no TIME column type: " + column);
        }

        @Override
        public void afterCreateTable(Connection connection, String qualifiedTable) throws SQLException {
            execute(connection, "REORGANIZE TABLE " + qualifiedTable);
        }

        @Override
        public void afterLoad(Connection connection) throws SQLException {
            execute(connection, "REORGANIZE DATABASE");
        }
    },

    /** MonetDB: binary data as {@code BLOB}. */
    MONETDB(1_000_000, 38) {
        @Override
        String binaryType(Column column) {
            return "BLOB";
        }
    };

    /** The longest {@code CHAR} every supported database accepts. */
    static final int MAX_CHAR_LENGTH = 2000;

    private final int maxVarcharLength;
    private final int maxDecimalPrecision;

    Dialect(int maxVarcharLength, int maxDecimalPrecision) {
        this.maxVarcharLength = maxVarcharLength;
        this.maxDecimalPrecision = maxDecimalPrecision;
    }

    /** The dialect a JDBC URL points to; {@link #GENERIC} for every database without one. */
    public static Dialect forUrl(String url) {
        String lower = url.toLowerCase(Locale.ROOT);
        if (lower.startsWith("jdbc:exa:")) {
            return EXASOL;
        }
        if (lower.startsWith("jdbc:monetdb:")) {
            return MONETDB;
        }
        return GENERIC;
    }

    /** {@code generic}, {@code exasol} or {@code monetdb}; {@code auto} or {@code null} asks the URL. */
    public static Dialect parse(String name, String url) {
        if (name == null || name.equalsIgnoreCase("auto")) {
            return forUrl(url);
        }
        return valueOf(name.toUpperCase(Locale.ROOT));
    }

    public int maxVarcharLength() {
        return maxVarcharLength;
    }

    /**
     * The column type to create in the target.
     *
     * <p>Character and binary columns keep their declared length when the target can hold it.
     * An unbounded one (Impala's {@code STRING} reports {@link Integer#MAX_VALUE}) gets the
     * longest value the export measured, or the dialect's maximum when nothing was measured
     * (a direct copy).</p>
     */
    public String columnType(Column column) {
        return switch (column.codec()) {
            case TEXT -> textType(column);
            case INTEGER -> integerType(column);
            case DECIMAL -> decimalType(column);
            case FLOATING -> "DOUBLE PRECISION";
            case BOOLEAN -> "BOOLEAN";
            case DATE -> "DATE";
            case TIME -> timeType(column);
            case TIMESTAMP -> "TIMESTAMP";
            case BINARY -> binaryType(column);
        };
    }

    /** Called once a table exists, before rows go in; {@code qualifiedTable} is quoted. */
    public void afterCreateTable(Connection connection, String qualifiedTable) throws SQLException {
    }

    /** Called after a table is completely loaded. */
    public void afterLoad(Connection connection) throws SQLException {
    }

    String textType(Column column) {
        boolean isChar = column.jdbcType() == Types.CHAR || column.jdbcType() == Types.NCHAR;
        if (isChar && column.size() > 0 && column.size() <= MAX_CHAR_LENGTH) {
            return "CHAR(" + column.size() + ")";
        }
        return "VARCHAR(" + length(column) + ")";
    }

    String binaryType(Column column) {
        return "VARBINARY(" + length(column) + ")";
    }

    String timeType(Column column) {
        return "TIME";
    }

    /** The declared length if it fits, else the measured one, else the maximum. */
    long length(Column column) {
        if (column.size() > 0 && column.size() <= maxVarcharLength) {
            return column.size();
        }
        if (column.longest() == Column.UNKNOWN) {
            return maxVarcharLength;
        }
        if (column.longest() > maxVarcharLength) {
            throw new UnsupportedOperationException("Column " + column.name() + " holds a value of " + column.longest()
                    + " characters, more than the " + maxVarcharLength + " the target accepts");
        }
        return Math.max(1, column.longest());
    }

    String integerType(Column column) {
        return switch (column.jdbcType()) {
            case Types.TINYINT -> "TINYINT";
            case Types.SMALLINT -> "SMALLINT";
            case Types.INTEGER -> "INTEGER";
            default -> "BIGINT";
        };
    }

    String decimalType(Column column) {
        int precision = column.size() > 0 ? Math.min(column.size(), maxDecimalPrecision) : maxDecimalPrecision;
        int scale = Math.max(0, Math.min(column.decimalDigits(), precision));
        return "DECIMAL(" + precision + ", " + scale + ")";
    }

    static void execute(Connection connection, String sql) throws SQLException {
        try (Statement statement = connection.createStatement()) {
            statement.executeUpdate(sql);
        }
    }
}
