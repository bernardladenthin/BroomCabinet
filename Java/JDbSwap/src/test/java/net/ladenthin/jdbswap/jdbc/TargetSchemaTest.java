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
import java.sql.Types;
import java.util.List;

import org.junit.jupiter.api.Test;

import net.ladenthin.jdbswap.H2Database;

public class TargetSchemaTest {

    private static final SqlNames NAMES = new SqlNames("\"", SqlNames.Case.UPPER);
    private static final List<Column> COLUMNS = List.of(
            new Column("id", Types.INTEGER, "INT", 10, 0, 3),
            new Column("name", Types.VARCHAR, "STRING", Integer.MAX_VALUE, 0, 42));

    @Test
    public void names_withSchemaAndPrefix() {
        TargetSchema schema = new TargetSchema(Dialect.EXASOL, NAMES, "dbswap", "x_");

        assertEquals("\"DBSWAP\".\"X_ORDERS\"", schema.table("orders"));
        assertEquals("\"DBSWAP\".\"DBSWAP_TMP_X_ORDERS_3\"", schema.temporaryTable("orders", 3));
    }

    @Test
    public void names_withoutSchemaAreUnqualified() {
        TargetSchema schema = new TargetSchema(Dialect.GENERIC, NAMES, null, null);

        assertEquals("\"ORDERS\"", schema.table("orders"));
    }

    @Test
    public void sql() {
        TargetSchema schema = new TargetSchema(Dialect.EXASOL, NAMES, null, "");

        assertEquals("CREATE TABLE \"T\" (\"ID\" INTEGER, \"NAME\" VARCHAR(42))", schema.createTableSql("\"T\"", COLUMNS));
        assertEquals("INSERT INTO \"T\" (\"ID\", \"NAME\") VALUES (?, ?)", schema.insertSql("\"T\"", COLUMNS));
        assertEquals("INSERT INTO \"T\" (\"ID\", \"NAME\") SELECT \"ID\", \"NAME\" FROM \"S\"",
                schema.copySql("\"S\"", "\"T\"", COLUMNS));
    }

    @Test
    public void recreate_replacesAnExistingTable() throws Exception {
        try (H2Database db = new H2Database()) {
            db.execute("CREATE TABLE ORDERS (OLD INT)", "INSERT INTO ORDERS VALUES (1)");
            Connection connection = db.connection();
            TargetSchema schema = TargetSchema.of(connection, Dialect.GENERIC, "PUBLIC", "");

            schema.recreate(connection, schema.table("orders"), COLUMNS);

            assertEquals(List.of(), db.rows("SELECT ID, NAME FROM ORDERS"));
            assertThrows(SQLException.class, () -> db.rows("SELECT OLD FROM ORDERS"));
        }
    }

    @Test
    public void drop_ofAMissingTableIsFine() throws Exception {
        try (H2Database db = new H2Database()) {
            TargetSchema schema = TargetSchema.of(db.connection(), Dialect.GENERIC, null, "");

            schema.drop(db.connection(), schema.table("missing"));

            assertTrue(db.tables().isEmpty());
        }
    }

    @Test
    public void commit_staysInManualMode() throws Exception {
        try (H2Database db = new H2Database()) {
            db.connection().setAutoCommit(false);

            TargetSchema.commit(db.connection());

            assertFalse(db.connection().getAutoCommit());
        }
    }
}
