// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap.jdbc;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.sql.SQLException;
import java.sql.Types;
import java.util.List;

import org.junit.jupiter.api.Test;

import net.ladenthin.jdbswap.H2Database;

public class CatalogTest {

    @Test
    public void tables_sortedAndOnlyOfTheSchema() throws Exception {
        try (H2Database db = new H2Database()) {
            db.execute("CREATE TABLE ZEBRA (A INT)", "CREATE TABLE APPLE (A INT)", "CREATE SCHEMA OTHER",
                    "CREATE TABLE OTHER.MANGO (A INT)");

            assertEquals(List.of("APPLE", "ZEBRA"), Catalog.tables(db.connection(), "PUBLIC"));
        }
    }

    @Test
    public void tables_underscoreIsNoWildcardForTheSchema() throws Exception {
        try (H2Database db = new H2Database()) {
            db.execute("CREATE SCHEMA MY_DB", "CREATE SCHEMA MYXDB", "CREATE TABLE MY_DB.A (A INT)",
                    "CREATE TABLE MYXDB.B (A INT)");

            assertEquals(List.of("A"), Catalog.tables(db.connection(), "MY_DB"));
        }
    }

    @Test
    public void columns_inOrdinalOrderWithTypeAndSize() throws Exception {
        try (H2Database db = new H2Database()) {
            db.execute("CREATE TABLE T (Z VARCHAR(20), A DECIMAL(10, 2), M INT)");

            List<Column> columns = Catalog.columns(db.connection(), "PUBLIC", "T");

            assertEquals(List.of("Z", "A", "M"), columns.stream().map(Column::name).toList());
            assertEquals(Types.VARCHAR, columns.get(0).jdbcType());
            assertEquals(20, columns.get(0).size());
            assertEquals(10, columns.get(1).size());
            assertEquals(2, columns.get(1).decimalDigits());
            assertEquals(Column.UNKNOWN, columns.get(2).longest());
        }
    }

    @Test
    public void columns_underscoreInTheTableNameMatchesOnlyThatTable() throws Exception {
        try (H2Database db = new H2Database()) {
            // as a LIKE pattern, ORDER_ITEMS also matches ORDERXITEMS
            db.execute("CREATE TABLE ORDER_ITEMS (A INT)", "CREATE TABLE ORDERXITEMS (B INT, C INT)");

            List<Column> columns = Catalog.columns(db.connection(), "PUBLIC", "ORDER_ITEMS");

            assertEquals(List.of("A"), columns.stream().map(Column::name).toList());
        }
    }

    @Test
    public void columns_unknownTableFails() throws Exception {
        try (H2Database db = new H2Database()) {
            assertThrows(SQLException.class, () -> Catalog.columns(db.connection(), "PUBLIC", "MISSING"));
        }
    }

    @Test
    public void schemaOrCurrent() throws Exception {
        try (H2Database db = new H2Database()) {
            assertEquals("SHOP", Catalog.schemaOrCurrent(db.connection(), "SHOP"));
            assertEquals("PUBLIC", Catalog.schemaOrCurrent(db.connection(), null));
            assertEquals("PUBLIC", Catalog.schemaOrCurrent(db.connection(), ""));
        }
    }

    @Test
    public void count_isALong() throws Exception {
        try (H2Database db = new H2Database()) {
            db.execute("CREATE TABLE T (A INT)", "INSERT INTO T VALUES (1), (2), (3)");

            assertEquals(3L, Catalog.count(db.connection(), "\"PUBLIC\".\"T\""));
        }
    }
}
