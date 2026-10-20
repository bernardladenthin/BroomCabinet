// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.List;

import org.junit.jupiter.api.Test;

import net.ladenthin.jdbswap.copy.Copier;
import net.ladenthin.jdbswap.jdbc.Dialect;

public class CopierTest {

    @Test
    public void copiesTablesDirectly() throws Exception {
        try (H2Database source = new H2Database(); H2Database target = new H2Database()) {
            SourceFixture.create(source);

            List<String> copied = new Copier(source.spec("PUBLIC"), target.spec(null), Dialect.GENERIC,
                    TableFilter.of("ORDERS|ORDER_ITEMS", null), "", 4).run();

            assertEquals(List.of("ORDERS", "ORDER_ITEMS"), copied);
            assertEquals(List.of("ORDERS", "ORDER_ITEMS"), target.tables());
            String orders = String.format(SourceFixture.ORDERS_QUERY, "ORDERS");
            assertEquals(source.rows(orders), target.rows(orders));
            assertEquals(List.of(List.of((long) Dialect.GENERIC.maxVarcharLength())), target.rows(
                    "SELECT CHARACTER_MAXIMUM_LENGTH FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'ORDERS' AND COLUMN_NAME = 'NAME'"),
                    "nothing was measured, so an unbounded column gets the maximum");
        }
    }

    @Test
    public void withPrefix() throws Exception {
        try (H2Database source = new H2Database(); H2Database target = new H2Database()) {
            SourceFixture.create(source);

            new Copier(source.spec(null), target.spec("PUBLIC"), Dialect.GENERIC, TableFilter.of("ORDER_ITEMS", null),
                    "old_", 1).run();

            assertEquals(source.rows("SELECT * FROM ORDER_ITEMS ORDER BY ORDER_ID, ITEM"),
                    target.rows("SELECT * FROM OLD_ORDER_ITEMS ORDER BY ORDER_ID, ITEM"));
        }
    }
}
