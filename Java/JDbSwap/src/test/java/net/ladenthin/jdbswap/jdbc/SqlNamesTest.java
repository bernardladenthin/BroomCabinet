// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap.jdbc;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.sql.Types;
import java.util.List;

import org.junit.jupiter.api.Test;

import net.ladenthin.jdbswap.H2Database;

public class SqlNamesTest {

    private static final SqlNames ANSI_UPPER = new SqlNames("\"", SqlNames.Case.UPPER);
    private static final SqlNames BACKTICK_LOWER = new SqlNames("`", SqlNames.Case.LOWER);
    private static final SqlNames NO_QUOTING = new SqlNames("", SqlNames.Case.AS_IS);

    @Test
    public void quote() {
        assertEquals("\"order\"", ANSI_UPPER.quote("order"));
        assertEquals("`order`", BACKTICK_LOWER.quote("order"));
        assertEquals("order", NO_QUOTING.quote("order"));
    }

    @Test
    public void quote_doublesEmbeddedQuotes() {
        assertEquals("\"a\"\"b\"", ANSI_UPPER.quote("a\"b"));
        assertEquals("`a``b`", BACKTICK_LOWER.quote("a`b"));
    }

    @Test
    public void normalize_foldsLikeAnUnquotedIdentifier() {
        assertEquals("ORDER_ITEMS", ANSI_UPPER.normalize("order_Items"));
        assertEquals("order_items", BACKTICK_LOWER.normalize("ORDER_Items"));
        assertEquals("order_Items", NO_QUOTING.normalize("order_Items"));
    }

    @Test
    public void target_foldsThenQuotes() {
        assertEquals("\"ORDERS\"", ANSI_UPPER.target("orders"));
    }

    @Test
    public void qualified_keepsTheStoredNames() {
        assertEquals("`shop`.`orders`", BACKTICK_LOWER.qualified("shop", "orders"));
        assertEquals("`orders`", BACKTICK_LOWER.qualified(null, "orders"));
        assertEquals("`orders`", BACKTICK_LOWER.qualified("", "orders"));
    }

    @Test
    public void qualifiedTarget_foldsSchemaAndTable() {
        assertEquals("\"DBSWAP\".\"ORDERS\"", ANSI_UPPER.qualifiedTarget("dbswap", "orders"));
        assertEquals("\"ORDERS\"", ANSI_UPPER.qualifiedTarget(null, "orders"));
    }

    @Test
    public void columnList() {
        List<Column> columns = List.of(
                new Column("id", Types.INTEGER, "INT", 10, 0, Column.UNKNOWN),
                new Column("select", Types.VARCHAR, "STRING", 0, 0, Column.UNKNOWN));

        assertEquals("`id`, `select`", BACKTICK_LOWER.columnList(columns, false));
        assertEquals("\"ID\", \"SELECT\"", ANSI_UPPER.columnList(columns, true));
    }

    @Test
    public void placeholders() {
        assertEquals("?, ?, ?", SqlNames.placeholders(3));
        assertEquals("?", SqlNames.placeholders(1));
    }

    @Test
    public void of_readsQuoteAndCaseFromTheDriver() throws Exception {
        try (H2Database db = new H2Database()) {
            SqlNames names = SqlNames.of(db.connection().getMetaData());

            assertEquals("\"ORDERS\"", names.target("orders"));
        }
    }
}
