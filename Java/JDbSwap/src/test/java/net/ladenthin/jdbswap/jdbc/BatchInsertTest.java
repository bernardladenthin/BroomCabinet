// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap.jdbc;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.Types;
import java.util.Arrays;
import java.util.List;

import org.junit.jupiter.api.Test;

import net.ladenthin.jdbswap.H2Database;

public class BatchInsertTest {

    private static final List<Column> COLUMNS = List.of(
            new Column("ID", Types.INTEGER, "INT", 10, 0, Column.UNKNOWN),
            new Column("NAME", Types.VARCHAR, "VARCHAR", 10, 0, Column.UNKNOWN));

    @Test
    public void commitsEveryBatchSizeRows() throws Exception {
        try (H2Database db = new H2Database()) {
            db.execute("CREATE TABLE T (ID INT, NAME VARCHAR(10))");
            try (Connection connection = DriverManager.getConnection(db.url())) {
                connection.setAutoCommit(false);
                try (BatchInsert insert = new BatchInsert(connection, "INSERT INTO T VALUES (?, ?)", COLUMNS, 2)) {
                    insert.add(new Object[] {"1", "a"});
                    // nothing committed yet: another connection sees no row
                    assertEquals(0, db.rows("SELECT * FROM T").size());
                    insert.add(new Object[] {"2", null});
                    assertEquals(2, db.rows("SELECT * FROM T").size());
                    insert.add(new Object[] {"3", "c"});
                    insert.flush();
                }
            }
            assertEquals(List.of(List.of(1, "a"), Arrays.asList(2, null), List.of(3, "c")),
                    db.rows("SELECT ID, NAME FROM T ORDER BY ID"));
        }
    }

    @Test
    public void batchSizeMustBePositive() throws Exception {
        try (H2Database db = new H2Database()) {
            db.execute("CREATE TABLE T (ID INT, NAME VARCHAR(10))");
            assertThrows(IllegalArgumentException.class,
                    () -> new BatchInsert(db.connection(), "INSERT INTO T VALUES (?, ?)", COLUMNS, 0));
        }
    }
}
