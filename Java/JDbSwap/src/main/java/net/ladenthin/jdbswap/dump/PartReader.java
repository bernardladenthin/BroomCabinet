// SPDX-FileCopyrightText: 2016 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap.dump;

import java.io.BufferedInputStream;
import java.io.Closeable;
import java.io.DataInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.DigestInputStream;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.zip.GZIPInputStream;

/**
 * Reads one part file row by row. {@link #verify(String)} afterwards proves that the file
 * ended exactly there and that its SHA-256 is the one the export recorded.
 */
public final class PartReader implements Closeable {

    private static final int BUFFER_SIZE = 64 * 1024;

    private final Path file;
    private final MessageDigest digest = DumpFormat.newDigest();
    private final DataInputStream in;

    public PartReader(Path file) throws IOException {
        this.file = file;
        InputStream raw = Files.newInputStream(file);
        try {
            this.in = new DataInputStream(new BufferedInputStream(
                    new DigestInputStream(new GZIPInputStream(raw, BUFFER_SIZE), digest), BUFFER_SIZE));
        } catch (IOException | RuntimeException e) {
            // e.g. no GZIP header: do not leave the file open (and locked on Windows)
            raw.close();
            throw e;
        }
    }

    /** The encoded values of the next row; an element is {@code null} for SQL {@code NULL}. */
    public byte[][] readRow(int columns) throws IOException {
        byte[][] row = new byte[columns][];
        for (int i = 0; i < columns; i++) {
            row[i] = DumpFormat.readValue(in);
        }
        return row;
    }

    /** Fails unless the whole file was read and hashes to {@code expectedSha256}. */
    public void verify(String expectedSha256) throws IOException {
        if (in.read() != -1) {
            throw new IOException("Part file has more data than its rows: " + file);
        }
        String actual = HexFormat.of().formatHex(digest.digest());
        if (!actual.equalsIgnoreCase(expectedSha256)) {
            throw new ChecksumException(file, expectedSha256, actual);
        }
    }

    @Override
    public void close() throws IOException {
        in.close();
    }

    /** A part file whose content is not what the export wrote. */
    public static final class ChecksumException extends IOException {

        private static final long serialVersionUID = 1L;

        public ChecksumException(Path file, String expected, String actual) {
            super("Checksum error in " + file + ": expected SHA-256 " + expected + ", read " + actual);
        }
    }
}
