// SPDX-FileCopyrightText: 2016 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap.dump;

import java.io.IOException;
import java.io.Reader;
import java.io.Writer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.HexFormat;
import java.util.stream.Stream;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonParseException;

/**
 * A dump directory: preparing it, writing and validating its manifest, finding its parts.
 *
 * <p>The manifest is plain JSON read into records, so a dump from an untrusted place can not
 * make the import instantiate anything else. Its part file names are checked before use and
 * can not point outside the directory.</p>
 */
public final class DumpDirectory {

    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().disableHtmlEscaping().create();

    private final Path path;

    public DumpDirectory(Path path) {
        this.path = path.toAbsolutePath().normalize();
    }

    public Path path() {
        return path;
    }

    /**
     * Makes sure an export can write here: creates the directory, or accepts an existing
     * empty one. Nothing is ever deleted.
     */
    public void prepareForExport() throws IOException {
        if (Files.exists(path)) {
            if (!Files.isDirectory(path)) {
                throw new IOException("Data path is not a directory: " + path);
            }
            try (Stream<Path> entries = Files.list(path)) {
                if (entries.findAny().isPresent()) {
                    throw new IOException("Data path is not empty: " + path
                            + " (an export writes only into a new or empty directory; remove the old dump yourself)");
                }
            }
        } else {
            Files.createDirectories(path);
        }
    }

    /** Writes the manifest through a temporary file, so a reader never sees half of it. */
    public void writeManifest(Manifest manifest) throws IOException {
        Path temporary = path.resolve(DumpFormat.MANIFEST + ".tmp");
        try (Writer writer = Files.newBufferedWriter(temporary, StandardCharsets.UTF_8)) {
            GSON.toJson(manifest, writer);
        }
        Files.move(temporary, path.resolve(DumpFormat.MANIFEST), StandardCopyOption.REPLACE_EXISTING,
                StandardCopyOption.ATOMIC_MOVE);
    }

    /** Reads and validates the manifest. */
    public Manifest readManifest() throws IOException {
        Path file = path.resolve(DumpFormat.MANIFEST);
        if (!Files.isRegularFile(file)) {
            throw new IOException("No " + DumpFormat.MANIFEST + " in " + path + " - not a dump directory?");
        }
        Manifest manifest;
        try (Reader reader = Files.newBufferedReader(file, StandardCharsets.UTF_8)) {
            manifest = GSON.fromJson(reader, Manifest.class);
        } catch (JsonParseException e) {
            throw new IOException("Unreadable " + file + ": " + e.getMessage(), e);
        }
        validate(manifest);
        return manifest;
    }

    /** The file of a part, checked to be a part file name inside this directory. */
    public Path part(Manifest.Part part) throws IOException {
        if (part.file() == null || !DumpFormat.PART_FILE_NAME.matcher(part.file()).matches()) {
            throw new IOException("Invalid part file name in manifest: " + part.file());
        }
        Path file = path.resolve(part.file()).normalize();
        if (!path.equals(file.getParent())) {
            throw new IOException("Part file outside the dump directory: " + part.file());
        }
        return file;
    }

    private void validate(Manifest manifest) throws IOException {
        if (manifest == null) {
            throw new IOException("Empty " + DumpFormat.MANIFEST);
        }
        if (manifest.formatVersion() != DumpFormat.VERSION) {
            throw new IOException("Dump format " + manifest.formatVersion() + ", this build reads format "
                    + DumpFormat.VERSION);
        }
        if (manifest.tables() == null) {
            throw new IOException("Manifest without tables");
        }
        for (Manifest.Table table : manifest.tables()) {
            if (table == null || table.name() == null || table.columns() == null || table.columns().isEmpty()
                    || table.parts() == null) {
                throw new IOException("Incomplete table in manifest: " + table);
            }
            if (table.columns().stream().anyMatch(column -> column == null || column.name() == null)) {
                throw new IOException("Incomplete column in manifest of table " + table.name());
            }
            long rows = 0;
            for (Manifest.Part part : table.parts()) {
                if (part == null) {
                    throw new IOException("Incomplete part in manifest of table " + table.name());
                }
                part(part);
                if (part.rows() < 0 || part.sha256() == null || part.sha256().length() != 64
                        || !isHex(part.sha256())) {
                    throw new IOException("Invalid part in manifest of table " + table.name() + ": " + part);
                }
                rows += part.rows();
            }
            if (rows != table.rows()) {
                throw new IOException("Table " + table.name() + " has " + table.rows() + " rows but its parts "
                        + rows);
            }
        }
    }

    private static boolean isHex(String s) {
        try {
            HexFormat.of().parseHex(s);
            return true;
        } catch (IllegalArgumentException e) {
            return false;
        }
    }
}
