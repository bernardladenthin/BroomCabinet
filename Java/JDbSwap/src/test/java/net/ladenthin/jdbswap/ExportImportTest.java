// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.DataOutputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.stream.Stream;
import java.util.zip.GZIPOutputStream;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import net.ladenthin.jdbswap.dump.DumpDirectory;
import net.ladenthin.jdbswap.dump.DumpFormat;
import net.ladenthin.jdbswap.dump.Manifest;
import net.ladenthin.jdbswap.dump.PartReader;
import net.ladenthin.jdbswap.export.Exporter;
import net.ladenthin.jdbswap.importer.Importer;
import net.ladenthin.jdbswap.jdbc.Column;
import net.ladenthin.jdbswap.jdbc.Dialect;

/**
 * Export from one H2 database, import into another, compare. H2 stands in for Impala and
 * Exasol; what is Exasol-specific lives in {@link Dialect} and is tested there.
 */
public class ExportImportTest {

    private static final TableFilter WITHOUT_IMPORTED = TableFilter.of(null, "IMPORTED_.*");

    @TempDir
    Path temp;

    private H2Database source;
    private H2Database target;
    private DumpDirectory dump;

    @BeforeEach
    public void setUp() throws Exception {
        source = new H2Database();
        target = new H2Database();
        SourceFixture.create(source);
        dump = new DumpDirectory(temp.resolve("dump"));
    }

    @AfterEach
    public void tearDown() throws Exception {
        source.close();
        target.close();
    }

    @Test
    public void roundTrip() throws Exception {
        Manifest manifest = new Exporter(source.spec("PUBLIC"), dump, WITHOUT_IMPORTED, 3).run();

        assertEquals(List.of("ORDERS", "ORDERXITEMS", "ORDER_ITEMS"), manifest.tables().stream().map(Manifest.Table::name).toList());
        Manifest.Table orders = manifest.tables().get(0);
        assertEquals(25, orders.rows());
        assertEquals(3, orders.parts().size());
        assertEquals(List.of(9L, 8L, 8L), orders.parts().stream().map(Manifest.Part::rows).toList());
        assertEquals(SourceFixture.LONG_TEXT.length(), column(orders, "NAME").longest());
        assertEquals(List.of("ORDER_ID", "ITEM"), manifest.tables().get(2).columns().stream().map(Column::name).toList(),
                "ORDER_ITEMS must not pick up the columns of ORDERXITEMS");
        assertEquals(manifest, dump.readManifest());

        List<Manifest.Table> imported = new Importer(target.spec("PUBLIC"), Dialect.GENERIC, dump, TableFilter.ALL, "", 2, 2).run();

        assertEquals(3, imported.size());
        assertEquals(List.of("ORDERS", "ORDERXITEMS", "ORDER_ITEMS"), target.tables(), "no staging table is left");
        assertSameRows(String.format(SourceFixture.ORDERS_QUERY, "ORDERS"));
        assertSameRows("SELECT ORDER_ID, ITEM FROM ORDER_ITEMS ORDER BY ORDER_ID, ITEM");
        assertSameRows("SELECT OTHER FROM ORDERXITEMS");
        assertEquals(List.of(List.of((long) SourceFixture.LONG_TEXT.length())), target.rows(
                "SELECT CHARACTER_MAXIMUM_LENGTH FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'ORDERS' AND COLUMN_NAME = 'NAME'"),
                "an unbounded column is created as long as its longest value");
    }

    @Test
    public void import_withTablePrefixFilterAndSchema() throws Exception {
        new Exporter(source.spec(null), dump, WITHOUT_IMPORTED, 2).run();

        new Importer(target.spec("PUBLIC"), Dialect.GENERIC, dump, TableFilter.of(".*ITEMS", null), "copy_", 1, 1000).run();

        assertEquals(List.of("COPY_ORDERXITEMS", "COPY_ORDER_ITEMS"), target.tables());
        assertEquals(source.rows("SELECT ORDER_ID, ITEM FROM ORDER_ITEMS ORDER BY ORDER_ID, ITEM"),
                target.rows("SELECT ORDER_ID, ITEM FROM COPY_ORDER_ITEMS ORDER BY ORDER_ID, ITEM"));
    }

    @Test
    public void import_twiceReplacesTheTables() throws Exception {
        new Exporter(source.spec("PUBLIC"), dump, TableFilter.of("ORDER_ITEMS", null), 2).run();
        Importer importer = new Importer(target.spec(null), Dialect.GENERIC, dump, TableFilter.ALL, "", 2, 1);

        importer.run();
        importer.run();

        assertEquals(3, target.rows("SELECT * FROM ORDER_ITEMS").size());
    }

    @Test
    public void import_ofAChangedPartFailsAndLeavesTheTargetTableEmpty() throws Exception {
        new Exporter(source.spec("PUBLIC"), dump, TableFilter.of("ORDER_ITEMS", null), 1).run();
        Manifest.Table table = dump.readManifest().tables().get(0);
        forge(dump.part(table.parts().get(0)), table.columns().size(), "apple", "APPLE");

        Importer importer = new Importer(target.spec("PUBLIC"), Dialect.GENERIC, dump, TableFilter.ALL, "", 1, 1);

        assertThrows(PartReader.ChecksumException.class, importer::run);
        assertEquals(List.of(), target.rows("SELECT * FROM ORDER_ITEMS"), "nothing of a broken part reaches the table");
        assertEquals(List.of("ORDER_ITEMS"), target.tables(), "the staging table is dropped");
    }

    @Test
    public void export_refusesANonEmptyDataPathAndDeletesNothing() throws Exception {
        Files.createDirectories(dump.path());
        Path precious = Files.writeString(dump.path().resolve("precious.txt"), "keep me");

        assertThrows(IOException.class, () -> new Exporter(source.spec("PUBLIC"), dump, TableFilter.ALL, 2).run());

        assertEquals("keep me", Files.readString(precious));
    }

    @Test
    public void export_ofAnUnknownSchemaExportsNothing() throws Exception {
        Manifest manifest = new Exporter(source.spec("NO_SUCH_SCHEMA"), dump, TableFilter.ALL, 2).run();

        assertEquals(List.of(), manifest.tables());
    }

    @Test
    public void exportWritesTheManifestAfterEveryTable() throws Exception {
        new Exporter(source.spec("PUBLIC"), dump, TableFilter.of("ORDER.*", null), 1).run();

        try (Stream<Path> files = Files.list(dump.path())) {
            List<String> names = files.map(path -> path.getFileName().toString()).sorted().toList();
            assertEquals(List.of("0000-ORDERS.part0000.gz", "0001-ORDERXITEMS.part0000.gz", "0002-ORDER_ITEMS.part0000.gz",
                    DumpFormat.MANIFEST), names);
        }
    }

    private void assertSameRows(String query) throws Exception {
        List<List<Object>> expected = source.rows(query);
        assertTrue(expected.size() > 0, query);
        assertEquals(expected, target.rows(query), query);
    }

    private static Column column(Manifest.Table table, String name) {
        return table.columns().stream().filter(column -> column.name().equals(name)).findFirst().orElseThrow();
    }

    /** Rewrites a part with one value replaced: same framing, same row count, other bytes. */
    private static void forge(Path part, int columns, String from, String to) throws IOException {
        List<byte[][]> rows = new ArrayList<>();
        try (PartReader reader = new PartReader(part)) {
            for (int i = 0; i < 3; i++) {
                rows.add(reader.readRow(columns));
            }
        }
        try (OutputStream raw = Files.newOutputStream(part); DataOutputStream out = new DataOutputStream(new GZIPOutputStream(raw))) {
            for (byte[][] row : rows) {
                for (byte[] value : row) {
                    boolean replace = value != null && from.equals(new String(value, StandardCharsets.UTF_8));
                    DumpFormat.writeValue(out, replace ? to.getBytes(StandardCharsets.UTF_8) : value);
                }
            }
        }
    }
}
