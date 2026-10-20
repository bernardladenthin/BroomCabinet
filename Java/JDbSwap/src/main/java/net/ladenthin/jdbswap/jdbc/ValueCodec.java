// SPDX-FileCopyrightText: 2016 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap.jdbc;

import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.sql.Date;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Time;
import java.sql.Timestamp;
import java.sql.Types;

/**
 * How a value of one column family is read from the source, carried and bound in the target.
 *
 * <p>Every value travels in a canonical, driver-independent form: binary columns as their
 * bytes, everything else as a string that the matching {@code valueOf}/{@code parse}
 * method reads back exactly ({@link BigDecimal#toPlainString()}, {@link Double#toString(double)},
 * {@link Timestamp#toString()}, ...). The target therefore gets typed parameters instead of
 * strings it has to interpret.</p>
 *
 * <p>Date and time values pass through {@link Date}, {@link Time} and {@link Timestamp} and so
 * through the JVM's default time zone: export and import must run in the same one.</p>
 */
public enum ValueCodec {

    TEXT(Types.VARCHAR) {
        @Override
        public Object read(ResultSet rs, int index) throws SQLException {
            return rs.getString(index);
        }

        @Override
        void bindValue(PreparedStatement ps, int index, Object value) throws SQLException {
            ps.setString(index, (String) value);
        }
    },

    INTEGER(Types.BIGINT) {
        @Override
        public Object read(ResultSet rs, int index) throws SQLException {
            long value = rs.getLong(index);
            return rs.wasNull() ? null : Long.toString(value);
        }

        @Override
        void bindValue(PreparedStatement ps, int index, Object value) throws SQLException {
            ps.setLong(index, Long.parseLong((String) value));
        }
    },

    DECIMAL(Types.DECIMAL) {
        @Override
        public Object read(ResultSet rs, int index) throws SQLException {
            BigDecimal value = rs.getBigDecimal(index);
            return value == null ? null : value.toPlainString();
        }

        @Override
        void bindValue(PreparedStatement ps, int index, Object value) throws SQLException {
            ps.setBigDecimal(index, new BigDecimal((String) value));
        }
    },

    FLOATING(Types.DOUBLE) {
        @Override
        public Object read(ResultSet rs, int index) throws SQLException {
            double value = rs.getDouble(index);
            return rs.wasNull() ? null : Double.toString(value);
        }

        @Override
        void bindValue(PreparedStatement ps, int index, Object value) throws SQLException {
            ps.setDouble(index, Double.parseDouble((String) value));
        }
    },

    BOOLEAN(Types.BOOLEAN) {
        @Override
        public Object read(ResultSet rs, int index) throws SQLException {
            boolean value = rs.getBoolean(index);
            return rs.wasNull() ? null : Boolean.toString(value);
        }

        @Override
        void bindValue(PreparedStatement ps, int index, Object value) throws SQLException {
            ps.setBoolean(index, Boolean.parseBoolean((String) value));
        }
    },

    DATE(Types.DATE) {
        @Override
        public Object read(ResultSet rs, int index) throws SQLException {
            Date value = rs.getDate(index);
            return value == null ? null : value.toString();
        }

        @Override
        void bindValue(PreparedStatement ps, int index, Object value) throws SQLException {
            ps.setDate(index, Date.valueOf((String) value));
        }
    },

    TIME(Types.TIME) {
        @Override
        public Object read(ResultSet rs, int index) throws SQLException {
            Time value = rs.getTime(index);
            return value == null ? null : value.toString();
        }

        @Override
        void bindValue(PreparedStatement ps, int index, Object value) throws SQLException {
            ps.setTime(index, Time.valueOf((String) value));
        }
    },

    TIMESTAMP(Types.TIMESTAMP) {
        @Override
        public Object read(ResultSet rs, int index) throws SQLException {
            Timestamp value = rs.getTimestamp(index);
            return value == null ? null : value.toString();
        }

        @Override
        void bindValue(PreparedStatement ps, int index, Object value) throws SQLException {
            ps.setTimestamp(index, Timestamp.valueOf((String) value));
        }
    },

    BINARY(Types.VARBINARY) {
        @Override
        public Object read(ResultSet rs, int index) throws SQLException {
            return rs.getBytes(index);
        }

        @Override
        void bindValue(PreparedStatement ps, int index, Object value) throws SQLException {
            ps.setBytes(index, (byte[]) value);
        }

        @Override
        public byte[] encode(Object value) {
            return (byte[]) value;
        }

        @Override
        public Object decode(byte[] bytes) {
            return bytes;
        }

        @Override
        public long length(Object value) {
            return ((byte[]) value).length;
        }
    };

    /** The type given to {@link PreparedStatement#setNull(int, int)}. */
    private final int nullType;

    ValueCodec(int nullType) {
        this.nullType = nullType;
    }

    /** The codec for a {@link Types} constant; types it does not know travel as text. */
    public static ValueCodec of(int jdbcType) {
        return switch (jdbcType) {
            case Types.TINYINT, Types.SMALLINT, Types.INTEGER, Types.BIGINT -> INTEGER;
            case Types.DECIMAL, Types.NUMERIC -> DECIMAL;
            case Types.FLOAT, Types.REAL, Types.DOUBLE -> FLOATING;
            case Types.BOOLEAN, Types.BIT -> BOOLEAN;
            case Types.DATE -> DATE;
            case Types.TIME -> TIME;
            case Types.TIMESTAMP -> TIMESTAMP;
            case Types.BINARY, Types.VARBINARY, Types.LONGVARBINARY, Types.BLOB -> BINARY;
            default -> TEXT;
        };
    }

    /**
     * Reads column {@code index} (1-based) of the current row.
     *
     * @return {@code null}, a {@link String}, or a {@code byte[]} for {@link #BINARY}
     */
    public abstract Object read(ResultSet rs, int index) throws SQLException;

    abstract void bindValue(PreparedStatement ps, int index, Object value) throws SQLException;

    /** Binds a value {@link #read} returned, {@code null} included, to parameter {@code index}. */
    public void bind(PreparedStatement ps, int index, Object value) throws SQLException {
        if (value == null) {
            ps.setNull(index, nullType);
        } else {
            bindValue(ps, index, value);
        }
    }

    /** The bytes a non-null value is stored as in a dump. */
    public byte[] encode(Object value) {
        return ((String) value).getBytes(StandardCharsets.UTF_8);
    }

    /** The inverse of {@link #encode(Object)}. */
    public Object decode(byte[] bytes) {
        return new String(bytes, StandardCharsets.UTF_8);
    }

    /** Characters of a text value, bytes of a binary one: what a column has to hold. */
    public long length(Object value) {
        return ((String) value).length();
    }
}
