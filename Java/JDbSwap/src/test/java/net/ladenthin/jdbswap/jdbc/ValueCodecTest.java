// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap.jdbc;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.Statement;
import java.sql.Types;
import java.util.stream.Stream;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.EnumSource;
import org.junit.jupiter.params.provider.MethodSource;

import net.ladenthin.jdbswap.H2Database;

/**
 * Every codec reads a value into its canonical form and binds that form back so that the
 * database stores the same value again.
 */
public class ValueCodecTest {

    static Stream<Arguments> jdbcTypes() {
        return Stream.of(
                Arguments.of(Types.VARCHAR, ValueCodec.TEXT),
                Arguments.of(Types.CHAR, ValueCodec.TEXT),
                Arguments.of(Types.CLOB, ValueCodec.TEXT),
                Arguments.of(Types.OTHER, ValueCodec.TEXT),
                Arguments.of(Types.TINYINT, ValueCodec.INTEGER),
                Arguments.of(Types.SMALLINT, ValueCodec.INTEGER),
                Arguments.of(Types.INTEGER, ValueCodec.INTEGER),
                Arguments.of(Types.BIGINT, ValueCodec.INTEGER),
                Arguments.of(Types.DECIMAL, ValueCodec.DECIMAL),
                Arguments.of(Types.NUMERIC, ValueCodec.DECIMAL),
                Arguments.of(Types.FLOAT, ValueCodec.FLOATING),
                Arguments.of(Types.REAL, ValueCodec.FLOATING),
                Arguments.of(Types.DOUBLE, ValueCodec.FLOATING),
                Arguments.of(Types.BOOLEAN, ValueCodec.BOOLEAN),
                Arguments.of(Types.BIT, ValueCodec.BOOLEAN),
                Arguments.of(Types.DATE, ValueCodec.DATE),
                Arguments.of(Types.TIME, ValueCodec.TIME),
                Arguments.of(Types.TIMESTAMP, ValueCodec.TIMESTAMP),
                Arguments.of(Types.BINARY, ValueCodec.BINARY),
                Arguments.of(Types.VARBINARY, ValueCodec.BINARY),
                Arguments.of(Types.LONGVARBINARY, ValueCodec.BINARY),
                Arguments.of(Types.BLOB, ValueCodec.BINARY));
    }

    @ParameterizedTest
    @MethodSource("jdbcTypes")
    public void of(int jdbcType, ValueCodec expected) {
        assertEquals(expected, ValueCodec.of(jdbcType));
    }

    @Test
    public void text_encodeDecodeLength() {
        String value = "äöü€😀";
        byte[] encoded = ValueCodec.TEXT.encode(value);

        assertArrayEquals(value.getBytes(StandardCharsets.UTF_8), encoded);
        assertEquals(value, ValueCodec.TEXT.decode(encoded));
        // UTF-16 units: what VARCHAR(n) counts in the databases this tool targets
        assertEquals(6, ValueCodec.TEXT.length(value));
    }

    @Test
    public void binary_encodeDecodeLength() {
        byte[] value = {0, 1, (byte) 0xFF};

        assertArrayEquals(value, ValueCodec.BINARY.encode(value));
        assertArrayEquals(value, (byte[]) ValueCodec.BINARY.decode(value));
        assertEquals(3, ValueCodec.BINARY.length(value));
    }

    static Stream<Arguments> roundTrips() {
        return Stream.of(
                Arguments.of("VARCHAR(100)", "'äöü € text'", ValueCodec.TEXT, "äöü € text"),
                Arguments.of("BIGINT", "-9223372036854775808", ValueCodec.INTEGER, "-9223372036854775808"),
                Arguments.of("TINYINT", "-7", ValueCodec.INTEGER, "-7"),
                Arguments.of("DECIMAL(20, 4)", "12345678901234.5600", ValueCodec.DECIMAL, "12345678901234.5600"),
                Arguments.of("DECIMAL(10, 0)", "1E+3", ValueCodec.DECIMAL, "1000"),
                Arguments.of("DOUBLE PRECISION", "0.1", ValueCodec.FLOATING, "0.1"),
                Arguments.of("DOUBLE PRECISION", "1.0E300", ValueCodec.FLOATING, "1.0E300"),
                Arguments.of("BOOLEAN", "TRUE", ValueCodec.BOOLEAN, "true"),
                Arguments.of("BOOLEAN", "FALSE", ValueCodec.BOOLEAN, "false"),
                Arguments.of("DATE", "DATE '1999-12-31'", ValueCodec.DATE, "1999-12-31"),
                Arguments.of("TIME", "TIME '23:59:58'", ValueCodec.TIME, "23:59:58"),
                Arguments.of("TIMESTAMP(3)", "TIMESTAMP '2016-02-29 12:34:56.789'", ValueCodec.TIMESTAMP,
                        "2016-02-29 12:34:56.789"),
                Arguments.of("VARBINARY(10)", "X'00ff10'", ValueCodec.BINARY, null));
    }

    @ParameterizedTest
    @MethodSource("roundTrips")
    public void readAndBindRoundTrip(String sqlType, String literal, ValueCodec codec, String canonical)
            throws Exception {
        try (H2Database db = new H2Database()) {
            db.execute("CREATE TABLE T (V " + sqlType + ")", "CREATE TABLE U (V " + sqlType + ")",
                    "INSERT INTO T VALUES (" + literal + ")");
            Connection connection = db.connection();

            Object read;
            try (Statement statement = connection.createStatement(); ResultSet rs = statement.executeQuery("SELECT V FROM T")) {
                rs.next();
                read = codec.read(rs, 1);
            }
            if (canonical != null) {
                assertEquals(canonical, read);
            }
            Object decoded = codec.decode(codec.encode(read));

            try (PreparedStatement insert = connection.prepareStatement("INSERT INTO U VALUES (?)")) {
                codec.bind(insert, 1, decoded);
                insert.executeUpdate();
            }
            assertEquals(db.rows("SELECT V FROM T"), db.rows("SELECT V FROM U"));
        }
    }

    @ParameterizedTest
    @EnumSource(ValueCodec.class)
    public void nullReadsAsNullAndBindsAsNull(ValueCodec codec) throws Exception {
        String sqlType = switch (codec) {
            case TEXT -> "VARCHAR(10)";
            case INTEGER -> "BIGINT";
            case DECIMAL -> "DECIMAL(10, 2)";
            case FLOATING -> "DOUBLE PRECISION";
            case BOOLEAN -> "BOOLEAN";
            case DATE -> "DATE";
            case TIME -> "TIME";
            case TIMESTAMP -> "TIMESTAMP";
            case BINARY -> "VARBINARY(10)";
        };
        try (H2Database db = new H2Database()) {
            db.execute("CREATE TABLE T (V " + sqlType + ")", "INSERT INTO T VALUES (NULL)",
                    "CREATE TABLE U (V " + sqlType + ")");
            try (Statement statement = db.connection().createStatement();
                 ResultSet rs = statement.executeQuery("SELECT V FROM T")) {
                rs.next();
                assertNull(codec.read(rs, 1));
            }
            try (PreparedStatement insert = db.connection().prepareStatement("INSERT INTO U VALUES (?)")) {
                codec.bind(insert, 1, null);
                insert.executeUpdate();
            }
            assertNull(db.rows("SELECT V FROM U").get(0).get(0));
        }
    }

    @Test
    public void decimalKeepsScaleAndNoExponent() throws Exception {
        try (H2Database db = new H2Database()) {
            db.execute("CREATE TABLE T (V DECIMAL(30, 10))", "INSERT INTO T VALUES (0.0000000001)");
            try (Statement statement = db.connection().createStatement();
                 ResultSet rs = statement.executeQuery("SELECT V FROM T")) {
                rs.next();
                Object read = ValueCodec.DECIMAL.read(rs, 1);
                assertEquals("0.0000000001", read);
                assertEquals(new BigDecimal("1E-10"), new BigDecimal((String) read));
            }
        }
    }
}
