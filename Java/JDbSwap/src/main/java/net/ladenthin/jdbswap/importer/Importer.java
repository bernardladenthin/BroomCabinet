// SPDX-FileCopyrightText: 2016 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap.importer;

import java.sql.Connection;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.logging.Logger;

import net.ladenthin.jdbswap.TableFilter;
import net.ladenthin.jdbswap.concurrent.TaskGroup;
import net.ladenthin.jdbswap.dump.DumpDirectory;
import net.ladenthin.jdbswap.dump.Manifest;
import net.ladenthin.jdbswap.jdbc.ConnectionSpec;
import net.ladenthin.jdbswap.jdbc.Dialect;
import net.ladenthin.jdbswap.jdbc.TargetSchema;
import net.ladenthin.jdbswap.progress.Progress;
import net.ladenthin.jdbswap.progress.ProgressReporter;

/**
 * Loads every accepted table of a dump directory into the target.
 *
 * <p>Each table is dropped and created anew; its parts are loaded by up to {@code threads}
 * {@link PartImporter}s at the same time. A part reaches the target table only after its
 * checksum was verified.</p>
 */
public final class Importer {

    private static final Logger LOG = Logger.getLogger(Importer.class.getName());

    private final ConnectionSpec target;
    private final Dialect dialect;
    private final DumpDirectory dump;
    private final TableFilter filter;
    private final String tablePrefix;
    private final int threads;
    private final int batchSize;

    public Importer(ConnectionSpec target, Dialect dialect, DumpDirectory dump, TableFilter filter,
            String tablePrefix, int threads, int batchSize) {
        if (threads < 1 || batchSize < 1) {
            throw new IllegalArgumentException("threads and batchSize must be at least 1");
        }
        this.target = target;
        this.dialect = dialect;
        this.dump = dump;
        this.filter = filter;
        this.tablePrefix = tablePrefix;
        this.threads = threads;
        this.batchSize = batchSize;
    }

    /** @return the tables imported, as the manifest describes them */
    public List<Manifest.Table> run() throws Exception {
        Manifest manifest = dump.readManifest();
        List<Manifest.Table> tables = manifest.tables().stream().filter(table -> filter.accepts(table.name())).toList();
        LOG.info(() -> "Tables to import: " + tables.stream().map(Manifest.Table::name).toList());

        TargetSchema schema;
        try (Connection connection = target.open()) {
            schema = TargetSchema.of(connection, dialect, target.schema(), tablePrefix);
        }
        for (Manifest.Table table : tables) {
            importTable(schema, table);
        }
        return tables;
    }

    private void importTable(TargetSchema schema, Manifest.Table table) throws Exception {
        String targetTable = schema.table(table.name());
        LOG.info(() -> "Import " + table.name() + " into " + targetTable + ": " + table.rows() + " rows in "
                + table.parts().size() + " parts");
        try (Connection connection = target.open()) {
            schema.recreate(connection, targetTable, table.columns());
        }

        Progress progress = new Progress(table.rows());
        ExecutorService pool = Executors.newFixedThreadPool(threads);
        try (ProgressReporter reporter = new ProgressReporter("import " + table.name(), progress)) {
            TaskGroup<Long> group = new TaskGroup<>(pool);
            for (int part = 0; part < table.parts().size(); part++) {
                group.submit(new PartImporter(target, schema, table, part, dump.part(table.parts().get(part)),
                        batchSize, progress));
            }
            group.awaitAll();
        } finally {
            pool.shutdownNow();
        }

        try (Connection connection = target.open()) {
            dialect.afterLoad(connection);
        }
    }
}
