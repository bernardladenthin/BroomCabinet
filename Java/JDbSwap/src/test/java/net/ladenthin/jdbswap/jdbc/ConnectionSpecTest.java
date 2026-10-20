// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap.jdbc;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.sql.Connection;
import java.sql.SQLException;

import org.junit.jupiter.api.Test;

import net.ladenthin.jdbswap.H2Database;

public class ConnectionSpecTest {

    @Test
    public void toString_neverShowsThePassword() {
        String shown = new ConnectionSpec("jdbc:exa:host:8563", "sys", "s3cret", "DBSWAP").toString();

        assertFalse(shown.contains("s3cret"), shown);
        assertTrue(shown.contains(ConnectionSpec.MASK), shown);
        assertTrue(shown.contains("sys"), shown);
    }

    @Test
    public void toString_withoutPassword() {
        assertTrue(new ConnectionSpec("jdbc:h2:mem:x", null, null, null).toString().contains("password=null"));
    }

    @Test
    public void urlIsRequired() {
        assertThrows(NullPointerException.class, () -> new ConnectionSpec(null, null, null, null));
    }

    @Test
    public void open_findsTheDriverByUrl() throws Exception {
        try (H2Database db = new H2Database(); Connection connection = db.spec(null).open()) {
            assertEquals("H2", connection.getMetaData().getDatabaseProductName());
        }
    }

    @Test
    public void open_unknownDriverFails() {
        assertThrows(SQLException.class, () -> new ConnectionSpec("jdbc:nosuchdb:x", null, null, null).open());
    }
}
