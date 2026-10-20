// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap;

import java.math.BigDecimal;
import java.sql.Date;
import java.sql.PreparedStatement;
import java.sql.SQLException;
import java.sql.Timestamp;

/**
 * A source schema with what used to go wrong: every column family, {@code NULL}s, a value
 * longer than 64 KiB, a reserved word as column name, the former null placeholder as a real
 * value, and two tables whose names are equal as LIKE patterns.
 */
public final class SourceFixture {

    /** Longer than the 65535 bytes {@code writeUTF} could store. */
    public static final String LONG_TEXT = "äöü€-".repeat(20_000);

    public static final String ORDERS_QUERY = "SELECT ID, NAME, \"ORDER\", PRICE, RATIO, PAID, ORDERED_ON, CREATED_AT, CODE, NOTE FROM %s ORDER BY ID";

    private SourceFixture() {
    }

    public static void create(H2Database db) throws SQLException {
        db.execute(
                "CREATE TABLE ORDERS (ID BIGINT, NAME VARCHAR, \"ORDER\" INT, PRICE DECIMAL(12, 2), RATIO DOUBLE PRECISION,"
                        + " PAID BOOLEAN, ORDERED_ON DATE, CREATED_AT TIMESTAMP(3), CODE VARBINARY(8), NOTE CHAR(3))",
                "CREATE TABLE ORDER_ITEMS (ORDER_ID BIGINT, ITEM VARCHAR(20))",
                "CREATE TABLE ORDERXITEMS (OTHER INT)",
                "CREATE TABLE IMPORTED_ORDERS (ID INT)",
                "INSERT INTO ORDER_ITEMS VALUES (1, 'apple'), (1, 'pear'), (2, NULL)",
                "INSERT INTO ORDERXITEMS VALUES (42)",
                "INSERT INTO IMPORTED_ORDERS VALUES (1)");
        try (PreparedStatement insert = db.connection().prepareStatement(
                "INSERT INTO ORDERS VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")) {
            for (long id = 1; id <= 25; id++) {
                insert.setLong(1, id);
                insert.setString(2, id == 7 ? LONG_TEXT : id == 8 ? "{!%N" : id == 9 ? null : "name " + id);
                insert.setInt(3, (int) id * 10);
                insert.setBigDecimal(4, new BigDecimal(id + ".05"));
                insert.setDouble(5, 1.0 / id);
                insert.setBoolean(6, id % 2 == 0);
                insert.setDate(7, Date.valueOf("2016-02-" + (10 + id % 18)));
                insert.setTimestamp(8, Timestamp.valueOf("2016-02-29 12:34:56." + (100 + id)));
                insert.setBytes(9, id == 3 ? null : new byte[] {(byte) id, (byte) 0xFF});
                insert.setString(10, id == 4 ? null : "ab");
                insert.addBatch();
            }
            insert.executeBatch();
        }
    }
}
