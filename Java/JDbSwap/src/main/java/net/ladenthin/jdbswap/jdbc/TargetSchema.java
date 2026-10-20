// SPDX-FileCopyrightText: 2016 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap.jdbc;

import java.sql.Connection;
import java.sql.SQLException;
import java.util.List;
import java.util.stream.Collectors;

/**
 * The tables of the target: their names and the SQL that creates, fills and drops them.
 */
public final class TargetSchema {

    /** Prefix of the per-part staging tables of an import. */
    public static final String TEMPORARY_PREFIX = "dbswap_tmp_";

    private final Dialect dialect;
    private final SqlNames names;
    private final String schema;
    private final String tablePrefix;

    /**
     * @param schema      may be {@code null}: tables are then created unqualified
     * @param tablePrefix put in front of every table name; may be empty
     */
    public TargetSchema(Dialect dialect, SqlNames names, String schema, String tablePrefix) {
        this.dialect = dialect;
        this.names = names;
        this.schema = schema;
        this.tablePrefix = tablePrefix == null ? "" : tablePrefix;
    }

    /** Reads quoting and identifier case from the target connection. */
    public static TargetSchema of(Connection connection, Dialect dialect, String schema, String tablePrefix)
            throws SQLException {
        return new TargetSchema(dialect, SqlNames.of(connection.getMetaData()), schema, tablePrefix);
    }

    public Dialect dialect() {
        return dialect;
    }

    /** The quoted, qualified target name of a source table. */
    public String table(String sourceTable) {
        return names.qualifiedTarget(schema, tablePrefix + sourceTable);
    }

    /** The staging table one part of {@code sourceTable} is loaded into first. */
    public String temporaryTable(String sourceTable, int part) {
        return names.qualifiedTarget(schema, TEMPORARY_PREFIX + tablePrefix + sourceTable + "_" + part);
    }

    /** {@code CREATE TABLE} with one column per {@link Column}, typed by the dialect. */
    public String createTableSql(String qualifiedTable, List<Column> columns) {
        String definitions = columns.stream()
                .map(column -> names.target(column.name()) + " " + dialect.columnType(column))
                .collect(Collectors.joining(", "));
        return "CREATE TABLE " + qualifiedTable + " (" + definitions + ")";
    }

    public String insertSql(String qualifiedTable, List<Column> columns) {
        return "INSERT INTO " + qualifiedTable + " (" + names.columnList(columns, true) + ") VALUES ("
                + SqlNames.placeholders(columns.size()) + ")";
    }

    public String copySql(String fromTable, String toTable, List<Column> columns) {
        String columnList = names.columnList(columns, true);
        return "INSERT INTO " + toTable + " (" + columnList + ") SELECT " + columnList + " FROM " + fromTable;
    }

    /** Drops {@code qualifiedTable} if it exists and creates it anew. */
    public void recreate(Connection connection, String qualifiedTable, List<Column> columns) throws SQLException {
        drop(connection, qualifiedTable);
        Dialect.execute(connection, createTableSql(qualifiedTable, columns));
        commitIfManual(connection);
        dialect.afterCreateTable(connection, qualifiedTable);
        commitIfManual(connection);
    }

    public void drop(Connection connection, String qualifiedTable) throws SQLException {
        Dialect.execute(connection, "DROP TABLE IF EXISTS " + qualifiedTable);
    }

    /**
     * Commits and stays in manual commit mode; older Exasol drivers fell back to auto-commit
     * after a commit, and setting the mode again is a no-op everywhere else.
     */
    public static void commit(Connection connection) throws SQLException {
        connection.commit();
        connection.setAutoCommit(false);
    }

    private static void commitIfManual(Connection connection) throws SQLException {
        if (!connection.getAutoCommit()) {
            commit(connection);
        }
    }
}
