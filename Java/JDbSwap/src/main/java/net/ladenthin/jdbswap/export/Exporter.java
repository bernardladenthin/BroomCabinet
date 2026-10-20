// SPDX-FileCopyrightText: 2016 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap.export;

import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.logging.Logger;

import net.ladenthin.jdbswap.TableFilter;
import net.ladenthin.jdbswap.concurrent.TaskGroup;
import net.ladenthin.jdbswap.dump.DumpDirectory;
import net.ladenthin.jdbswap.dump.DumpFormat;
import net.ladenthin.jdbswap.dump.Manifest;
import net.ladenthin.jdbswap.dump.PartWriter;
import net.ladenthin.jdbswap.jdbc.Catalog;
import net.ladenthin.jdbswap.jdbc.Column;
import net.ladenthin.jdbswap.jdbc.ConnectionSpec;
import net.ladenthin.jdbswap.jdbc.SqlNames;
import net.ladenthin.jdbswap.jdbc.ValueCodec;
import net.ladenthin.jdbswap.progress.Progress;
import net.ladenthin.jdbswap.progress.ProgressReporter;

/**
 * Writes every accepted table of the source schema into a dump directory.
 *
 * <p>One thread reads the table and deals its rows round-robin to {@code parts} writer threads,
 * each of which compresses and hashes its own part file.</p>
 */
public final class Exporter {

    private static final Logger LOG = Logger.getLogger(Exporter.class.getName());

    private final ConnectionSpec source;
    private final DumpDirectory dump;
    private final TableFilter filter;
    private final int parts;

    public Exporter(ConnectionSpec source, DumpDirectory dump, TableFilter filter, int parts) {
        if (parts < 1) {
            throw new IllegalArgumentException("parts < 1: " + parts);
        }
        this.source = source;
        this.dump = dump;
        this.filter = filter;
        this.parts = parts;
    }

    public Manifest run() throws Exception {
        dump.prepareForExport();
        List<Manifest.Table> exported = new ArrayList<>();
        Manifest manifest = new Manifest(DumpFormat.VERSION, List.copyOf(exported));
        dump.writeManifest(manifest);

        try (Connection connection = source.open()) {
            SqlNames names = SqlNames.of(connection.getMetaData());
            String schema = Catalog.schemaOrCurrent(connection, source.schema());
            List<String> tables = filter.apply(Catalog.tables(connection, schema));
            LOG.info(() -> "Tables to export from " + schema + ": " + tables);

            for (int i = 0; i < tables.size(); i++) {
                exported.add(exportTable(connection, names, schema, i, tables.get(i)));
                manifest = new Manifest(DumpFormat.VERSION, List.copyOf(exported));
                dump.writeManifest(manifest);
            }
        }
        return manifest;
    }

    private Manifest.Table exportTable(Connection connection, SqlNames names, String schema, int tableIndex,
            String table) throws Exception {
        List<Column> columns = Catalog.columns(connection, schema, table);
        List<ValueCodec> codecs = columns.stream().map(Column::codec).toList();
        String qualified = names.qualified(schema, table);
        long expectedRows = Catalog.count(connection, qualified);
        LOG.info(() -> "Export " + table + ": " + expectedRows + " rows, " + columns.size() + " columns");

        Progress progress = new Progress(expectedRows);
        List<String> files = new ArrayList<>();
        List<PartWriter> writers = new ArrayList<>();
        for (int part = 0; part < parts; part++) {
            String file = DumpFormat.partFileName(tableIndex, table, part);
            files.add(file);
            writers.add(new PartWriter(dump.path().resolve(file), codecs, progress));
        }

        List<PartWriter.Result> results;
        ExecutorService pool = Executors.newFixedThreadPool(parts);
        try (ProgressReporter reporter = new ProgressReporter("export " + table, progress)) {
            TaskGroup<PartWriter.Result> group = new TaskGroup<>(pool);
            writers.forEach(group::submit);

            Exception readFailure = null;
            String select = "SELECT " + names.columnList(columns, false) + " FROM " + qualified;
            try (Statement statement = connection.createStatement();
                 ResultSet rs = statement.executeQuery(select)) {
                int part = 0;
                while (rs.next()) {
                    Object[] row = new Object[codecs.size()];
                    for (int i = 0; i < row.length; i++) {
                        row[i] = codecs.get(i).read(rs, i + 1);
                    }
                    writers.get(part).put(row);
                    part = (part + 1) % parts;
                }
            } catch (Exception e) {
                readFailure = e;
            } finally {
                for (PartWriter writer : writers) {
                    writer.finish();
                }
            }
            // a failed writer is the cause of a failed put, so its exception comes first
            results = group.awaitAll();
            if (readFailure != null) {
                throw readFailure;
            }
        } finally {
            pool.shutdownNow();
        }

        long rows = 0;
        long[] longest = new long[columns.size()];
        List<Manifest.Part> partList = new ArrayList<>();
        for (int part = 0; part < parts; part++) {
            PartWriter.Result result = results.get(part);
            rows += result.rows();
            for (int i = 0; i < longest.length; i++) {
                longest[i] = Math.max(longest[i], result.longest()[i]);
            }
            partList.add(new Manifest.Part(files.get(part), result.rows(), result.sha256()));
        }
        List<Column> measured = new ArrayList<>();
        for (int i = 0; i < columns.size(); i++) {
            measured.add(columns.get(i).withLongest(longest[i]));
        }
        if (rows != expectedRows) {
            long written = rows;
            LOG.warning(() -> "Export " + table + ": COUNT(*) said " + expectedRows + " rows, " + written
                    + " were read (the table changed during the export?)");
        }
        return new Manifest.Table(table, measured, rows, partList);
    }
}
