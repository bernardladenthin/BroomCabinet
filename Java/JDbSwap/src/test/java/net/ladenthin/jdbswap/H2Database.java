// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;
import java.util.UUID;

import net.ladenthin.jdbswap.jdbc.ConnectionSpec;

/**
 * A private in-memory H2 database for one test. It lives as long as this object holds its
 * keeper connection; every other connection the code under test opens and closes sees it.
 */
public final class H2Database implements AutoCloseable {

    private final String url = "jdbc:h2:mem:" + UUID.randomUUID();
    private final Connection keeper;

    public H2Database() throws SQLException {
        keeper = DriverManager.getConnection(url);
    }

    public String url() {
        return url;
    }

    public Connection connection() {
        return keeper;
    }

    /** Source or target spec of the {@code PUBLIC} schema, or unqualified with {@code schema == null}. */
    public ConnectionSpec spec(String schema) {
        return new ConnectionSpec(url, null, null, schema);
    }

    public void execute(String... statements) throws SQLException {
        try (Statement statement = keeper.createStatement()) {
            for (String sql : statements) {
                statement.execute(sql);
            }
        }
    }

    /** Every row of {@code query}, each value as {@link ResultSet#getObject(int)} returned it. */
    public List<List<Object>> rows(String query) throws SQLException {
        List<List<Object>> rows = new ArrayList<>();
        try (Statement statement = keeper.createStatement(); ResultSet rs = statement.executeQuery(query)) {
            int columns = rs.getMetaData().getColumnCount();
            while (rs.next()) {
                List<Object> row = new ArrayList<>();
                for (int i = 1; i <= columns; i++) {
                    Object value = rs.getObject(i);
                    row.add(value instanceof byte[] bytes ? HexFormat.of().formatHex(bytes) : value);
                }
                rows.add(row);
            }
        }
        return rows;
    }

    public List<String> tables() throws SQLException {
        List<String> tables = new ArrayList<>();
        for (List<Object> row : rows("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'PUBLIC' ORDER BY TABLE_NAME")) {
            tables.add((String) row.get(0));
        }
        return tables;
    }

    @Override
    public void close() throws SQLException {
        keeper.close();
    }
}
