// SPDX-FileCopyrightText: 2016 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap.copy;

import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.List;
import java.util.logging.Logger;

import net.ladenthin.jdbswap.TableFilter;
import net.ladenthin.jdbswap.jdbc.BatchInsert;
import net.ladenthin.jdbswap.jdbc.Catalog;
import net.ladenthin.jdbswap.jdbc.Column;
import net.ladenthin.jdbswap.jdbc.ConnectionSpec;
import net.ladenthin.jdbswap.jdbc.Dialect;
import net.ladenthin.jdbswap.jdbc.SqlNames;
import net.ladenthin.jdbswap.jdbc.TargetSchema;
import net.ladenthin.jdbswap.jdbc.ValueCodec;
import net.ladenthin.jdbswap.progress.Progress;
import net.ladenthin.jdbswap.progress.ProgressReporter;

/**
 * Copies every accepted table straight from source to target, without a dump directory.
 *
 * <p>Simpler, but single-threaded, without a checksum, and unbounded text columns are created
 * with the dialect's maximum length because nothing measured them beforehand.</p>
 */
public final class Copier {

    private static final Logger LOG = Logger.getLogger(Copier.class.getName());

    private final ConnectionSpec source;
    private final ConnectionSpec target;
    private final Dialect dialect;
    private final TableFilter filter;
    private final String tablePrefix;
    private final int batchSize;

    public Copier(ConnectionSpec source, ConnectionSpec target, Dialect dialect, TableFilter filter,
            String tablePrefix, int batchSize) {
        this.source = source;
        this.target = target;
        this.dialect = dialect;
        this.filter = filter;
        this.tablePrefix = tablePrefix;
        this.batchSize = batchSize;
    }

    /** @return the source tables copied */
    public List<String> run() throws Exception {
        try (Connection from = source.open(); Connection to = target.open()) {
            to.setAutoCommit(false);
            SqlNames names = SqlNames.of(from.getMetaData());
            TargetSchema schema = TargetSchema.of(to, dialect, target.schema(), tablePrefix);
            String sourceSchema = Catalog.schemaOrCurrent(from, source.schema());
            List<String> tables = filter.apply(Catalog.tables(from, sourceSchema));
            LOG.info(() -> "Tables to copy from " + sourceSchema + ": " + tables);
            for (String table : tables) {
                copyTable(from, to, names, sourceSchema, schema, table);
            }
            return tables;
        }
    }

    private void copyTable(Connection from, Connection to, SqlNames names, String sourceSchema, TargetSchema schema,
            String table) throws Exception {
        List<Column> columns = Catalog.columns(from, sourceSchema, table);
        ValueCodec[] codecs = columns.stream().map(Column::codec).toArray(ValueCodec[]::new);
        String qualified = names.qualified(sourceSchema, table);
        String targetTable = schema.table(table);
        Progress progress = new Progress(Catalog.count(from, qualified));
        LOG.info(() -> "Copy " + table + " into " + targetTable);

        schema.recreate(to, targetTable, columns);
        try (ProgressReporter reporter = new ProgressReporter("copy " + table, progress);
             Statement statement = from.createStatement();
             ResultSet rs = statement.executeQuery("SELECT " + names.columnList(columns, false) + " FROM " + qualified);
             BatchInsert insert = new BatchInsert(to, schema.insertSql(targetTable, columns), columns, batchSize)) {
            while (rs.next()) {
                Object[] row = new Object[codecs.length];
                long bytes = 0;
                for (int i = 0; i < codecs.length; i++) {
                    row[i] = codecs[i].read(rs, i + 1);
                    if (row[i] != null) {
                        bytes += codecs[i].length(row[i]);
                    }
                }
                insert.add(row);
                progress.add(1, bytes);
            }
            insert.flush();
        }
        dialect.afterLoad(to);
        TargetSchema.commit(to);
    }
}
