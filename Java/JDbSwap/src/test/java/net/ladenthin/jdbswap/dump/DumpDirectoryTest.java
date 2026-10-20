// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap.dump;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Types;
import java.util.List;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import net.ladenthin.jdbswap.jdbc.Column;

public class DumpDirectoryTest {

    private static final String SHA = "a".repeat(64);

    @TempDir
    Path temp;

    @Test
    public void prepareForExport_createsAMissingDirectory() throws IOException {
        Path path = temp.resolve("new/dump");

        new DumpDirectory(path).prepareForExport();

        assertTrue(Files.isDirectory(path));
    }

    @Test
    public void prepareForExport_acceptsAnEmptyDirectory() throws IOException {
        new DumpDirectory(temp).prepareForExport();
    }

    @Test
    public void prepareForExport_refusesANonEmptyDirectoryAndDeletesNothing() throws IOException {
        Path precious = Files.writeString(temp.resolve("precious.txt"), "keep me");

        IOException e = assertThrows(IOException.class, () -> new DumpDirectory(temp).prepareForExport());

        assertTrue(e.getMessage().contains("not empty"), e.getMessage());
        assertEquals("keep me", Files.readString(precious));
    }

    @Test
    public void prepareForExport_refusesAFile() throws IOException {
        Path file = Files.writeString(temp.resolve("file"), "x");

        assertThrows(IOException.class, () -> new DumpDirectory(file).prepareForExport());
    }

    @Test
    public void manifest_roundTrip() throws IOException {
        DumpDirectory dump = new DumpDirectory(temp);
        Manifest manifest = manifest(part("0000-orders.part0000.gz", 2), part("0000-orders.part0001.gz", 1));

        dump.writeManifest(manifest);

        assertEquals(manifest, dump.readManifest());
        assertFalse(Files.exists(temp.resolve(DumpFormat.MANIFEST + ".tmp")));
    }

    @Test
    public void manifest_isReadableJson() throws IOException {
        DumpDirectory dump = new DumpDirectory(temp);
        dump.writeManifest(manifest(part("0000-orders.part0000.gz", 3)));

        String json = Files.readString(temp.resolve(DumpFormat.MANIFEST));

        assertTrue(json.contains("\"formatVersion\": 2"), json);
        assertTrue(json.contains("\"name\": \"orders\""), json);
    }

    @Test
    public void readManifest_missing() {
        IOException e = assertThrows(IOException.class, () -> new DumpDirectory(temp).readManifest());

        assertTrue(e.getMessage().contains("not a dump directory"), e.getMessage());
    }

    @Test
    public void readManifest_otherFormatVersion() throws IOException {
        Files.writeString(temp.resolve(DumpFormat.MANIFEST), "{\"formatVersion\": 1, \"tables\": []}");

        IOException e = assertThrows(IOException.class, () -> new DumpDirectory(temp).readManifest());

        assertTrue(e.getMessage().contains("format 1"), e.getMessage());
    }

    @Test
    public void readManifest_brokenJson() throws IOException {
        Files.writeString(temp.resolve(DumpFormat.MANIFEST), "{\"formatVersion\": 2, \"tables\": [", StandardCharsets.UTF_8);

        assertThrows(IOException.class, () -> new DumpDirectory(temp).readManifest());
    }

    @ParameterizedTest
    @ValueSource(strings = {"../0000-orders.part0000.gz", "/etc/passwd", "C:\\Windows\\win.ini", "sub/0000-orders.part0000.gz",
            "0000-orders.part0000.gz/..", "anything.gz", ""})
    public void readManifest_refusesPartFilesOutsideTheDirectory(String file) throws IOException {
        new DumpDirectory(temp).writeManifest(manifest(part(file, 1)));

        assertThrows(IOException.class, () -> new DumpDirectory(temp).readManifest());
    }

    @Test
    public void readManifest_refusesAnInvalidChecksum() throws IOException {
        new DumpDirectory(temp).writeManifest(manifest(new Manifest.Part("0000-orders.part0000.gz", 1, "xyz")));

        assertThrows(IOException.class, () -> new DumpDirectory(temp).readManifest());
    }

    @Test
    public void readManifest_refusesRowsThatDoNotAddUp() throws IOException {
        Manifest.Table table = new Manifest.Table("orders", List.of(column()), 5, List.of(part("0000-orders.part0000.gz", 4)));
        new DumpDirectory(temp).writeManifest(new Manifest(DumpFormat.VERSION, List.of(table)));

        assertThrows(IOException.class, () -> new DumpDirectory(temp).readManifest());
    }

    @Test
    public void readManifest_refusesATableWithoutColumns() throws IOException {
        Manifest.Table table = new Manifest.Table("orders", List.of(), 0, List.of());
        new DumpDirectory(temp).writeManifest(new Manifest(DumpFormat.VERSION, List.of(table)));

        assertThrows(IOException.class, () -> new DumpDirectory(temp).readManifest());
    }

    @Test
    public void part_resolvesInsideTheDirectory() throws IOException {
        DumpDirectory dump = new DumpDirectory(temp);

        assertEquals(temp.toAbsolutePath().normalize().resolve("0000-orders.part0000.gz"),
                dump.part(part("0000-orders.part0000.gz", 1)));
    }

    private static Manifest manifest(Manifest.Part... parts) {
        long rows = 0;
        for (Manifest.Part part : parts) {
            rows += part.rows();
        }
        return new Manifest(DumpFormat.VERSION, List.of(new Manifest.Table("orders", List.of(column()), rows, List.of(parts))));
    }

    private static Manifest.Part part(String file, long rows) {
        return new Manifest.Part(file, rows, SHA);
    }

    private static Column column() {
        return new Column("id", Types.INTEGER, "INT", 10, 0, 3);
    }
}
