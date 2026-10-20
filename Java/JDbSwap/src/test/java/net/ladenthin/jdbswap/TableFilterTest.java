// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;

import org.junit.jupiter.api.Test;

public class TableFilterTest {

    @Test
    public void all() {
        assertTrue(TableFilter.ALL.accepts("orders"));
        assertTrue(TableFilter.of(null, null).accepts("orders"));
        assertTrue(TableFilter.of(null, "").accepts("orders"));
    }

    @Test
    public void excludeWinsOverInclude() {
        TableFilter filter = TableFilter.of(".*(orders).*", ".*(imported_orders).*");

        assertTrue(filter.accepts("orders"));
        assertTrue(filter.accepts("all_orders"));
        assertFalse(filter.accepts("imported_orders"));
        assertFalse(filter.accepts("customers"));
    }

    @Test
    public void theWholeNameMustMatch() {
        assertFalse(TableFilter.of("orders", null).accepts("all_orders"));
        assertTrue(TableFilter.of("orders", null).accepts("orders"));
    }

    @Test
    public void apply_keepsTheOrder() {
        assertEquals(List.of("order_items", "orders"),
                TableFilter.of("order.*", null).apply(List.of("order_items", "customers", "orders")));
    }
}
