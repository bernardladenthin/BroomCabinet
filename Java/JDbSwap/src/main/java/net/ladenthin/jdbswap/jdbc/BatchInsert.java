// SPDX-FileCopyrightText: 2016 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap.jdbc;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.SQLException;
import java.util.List;

/**
 * Inserts rows through one prepared statement, committing every {@code batchSize} rows.
 * The connection must be in manual commit mode.
 */
public final class BatchInsert implements AutoCloseable {

    private final Connection connection;
    private final PreparedStatement statement;
    private final ValueCodec[] codecs;
    private final int batchSize;
    private int pending;

    public BatchInsert(Connection connection, String insertSql, List<Column> columns, int batchSize)
            throws SQLException {
        if (batchSize < 1) {
            throw new IllegalArgumentException("batchSize < 1: " + batchSize);
        }
        this.connection = connection;
        this.statement = connection.prepareStatement(insertSql);
        this.codecs = columns.stream().map(Column::codec).toArray(ValueCodec[]::new);
        this.batchSize = batchSize;
    }

    /** Adds one row of values as {@link ValueCodec#read} or {@link ValueCodec#decode} returned them. */
    public void add(Object[] row) throws SQLException {
        for (int i = 0; i < codecs.length; i++) {
            codecs[i].bind(statement, i + 1, row[i]);
        }
        statement.addBatch();
        if (++pending == batchSize) {
            flush();
        }
    }

    /** Executes and commits what is pending. */
    public void flush() throws SQLException {
        if (pending > 0) {
            statement.executeBatch();
            TargetSchema.commit(connection);
            pending = 0;
        }
    }

    @Override
    public void close() throws SQLException {
        statement.close();
    }
}
