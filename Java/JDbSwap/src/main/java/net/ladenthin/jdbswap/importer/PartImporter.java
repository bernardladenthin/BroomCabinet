// SPDX-FileCopyrightText: 2016 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap.importer;

import java.nio.file.Path;
import java.sql.Connection;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.List;
import java.util.concurrent.Callable;

import net.ladenthin.jdbswap.dump.Manifest;
import net.ladenthin.jdbswap.dump.PartReader;
import net.ladenthin.jdbswap.jdbc.BatchInsert;
import net.ladenthin.jdbswap.jdbc.Column;
import net.ladenthin.jdbswap.jdbc.ConnectionSpec;
import net.ladenthin.jdbswap.jdbc.TargetSchema;
import net.ladenthin.jdbswap.jdbc.ValueCodec;
import net.ladenthin.jdbswap.progress.Progress;

/**
 * Loads one part on its own connection: into a staging table first, verified, then with one
 * {@code INSERT ... SELECT} into the target table.
 *
 * <p>The staging table exists because the Exasol driver locks prepared inserts into the same
 * table across connections; with one staging table per part the parts load in parallel and
 * the database moves them over itself.</p>
 */
final class PartImporter implements Callable<Long> {

    private final ConnectionSpec target;
    private final TargetSchema schema;
    private final Manifest.Table table;
    private final int part;
    private final Path file;
    private final int batchSize;
    private final Progress progress;

    PartImporter(ConnectionSpec target, TargetSchema schema, Manifest.Table table, int part, Path file,
            int batchSize, Progress progress) {
        this.target = target;
        this.schema = schema;
        this.table = table;
        this.part = part;
        this.file = file;
        this.batchSize = batchSize;
        this.progress = progress;
    }

    /** @return the rows loaded */
    @Override
    public Long call() throws Exception {
        List<Column> columns = table.columns();
        Manifest.Part manifestPart = table.parts().get(part);
        String staging = schema.temporaryTable(table.name(), part);

        try (Connection connection = target.open()) {
            connection.setAutoCommit(false);
            schema.recreate(connection, staging, columns);
            try {
                load(connection, staging, columns, manifestPart);
                try (Statement statement = connection.createStatement()) {
                    statement.executeUpdate(schema.copySql(staging, schema.table(table.name()), columns));
                }
                TargetSchema.commit(connection);
            } finally {
                dropQuietly(connection, staging);
            }
        }
        return manifestPart.rows();
    }

    private void load(Connection connection, String staging, List<Column> columns, Manifest.Part manifestPart)
            throws Exception {
        ValueCodec[] codecs = columns.stream().map(Column::codec).toArray(ValueCodec[]::new);
        try (PartReader reader = new PartReader(file);
             BatchInsert insert = new BatchInsert(connection, schema.insertSql(staging, columns), columns, batchSize)) {
            for (long row = 0; row < manifestPart.rows(); row++) {
                byte[][] encoded = reader.readRow(codecs.length);
                Object[] values = new Object[codecs.length];
                long bytes = 0;
                for (int i = 0; i < codecs.length; i++) {
                    if (encoded[i] != null) {
                        values[i] = codecs[i].decode(encoded[i]);
                        bytes += encoded[i].length;
                    }
                }
                insert.add(values);
                progress.add(1, bytes);
            }
            insert.flush();
            // before anything of this part reaches the target table
            reader.verify(manifestPart.sha256());
        }
    }

    private void dropQuietly(Connection connection, String staging) {
        try {
            connection.rollback();
            schema.drop(connection, staging);
            TargetSchema.commit(connection);
        } catch (SQLException e) {
            // the connection may be the reason we got here; the next import drops it anyway
        }
    }
}
