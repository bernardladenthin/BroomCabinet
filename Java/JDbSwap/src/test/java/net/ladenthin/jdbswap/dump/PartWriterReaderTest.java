// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap.dump;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTimeoutPreemptively;

import java.io.DataOutputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.zip.GZIPOutputStream;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import net.ladenthin.jdbswap.jdbc.ValueCodec;
import net.ladenthin.jdbswap.progress.Progress;

/**
 * A part as {@link PartWriter} writes it and {@link PartReader} reads and verifies it.
 */
public class PartWriterReaderTest {

    private static final List<ValueCodec> CODECS = List.of(ValueCodec.INTEGER, ValueCodec.TEXT, ValueCodec.BINARY);

    @TempDir
    Path temp;

    @Test
    public void roundTripWithChecksum() throws Exception {
        Path file = temp.resolve("part.gz");
        Progress progress = new Progress(2);
        PartWriter writer = new PartWriter(file, CODECS, progress);
        writer.put(new Object[] {"1", "first", new byte[] {1, 2}});
        writer.put(new Object[] {"2", null, null});
        writer.finish();

        PartWriter.Result result = writer.call();

        assertEquals(2, result.rows());
        assertArrayEquals(new long[] {1, 5, 2}, result.longest());
        assertEquals(2, progress.rows());
        assertEquals(1 + 5 + 2 + 1, progress.bytes());

        try (PartReader reader = new PartReader(file)) {
            byte[][] first = reader.readRow(3);
            assertEquals("1", new String(first[0], StandardCharsets.UTF_8));
            assertEquals("first", new String(first[1], StandardCharsets.UTF_8));
            assertArrayEquals(new byte[] {1, 2}, first[2]);
            byte[][] second = reader.readRow(3);
            assertEquals("2", new String(second[0], StandardCharsets.UTF_8));
            assertNull(second[1]);
            assertNull(second[2]);
            reader.verify(result.sha256());
        }
    }

    @Test
    public void emptyPart() throws Exception {
        Path file = temp.resolve("part.gz");
        PartWriter writer = new PartWriter(file, CODECS, new Progress(0));
        writer.finish();

        PartWriter.Result result = writer.call();

        assertEquals(0, result.rows());
        // SHA-256 of nothing
        assertEquals("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", result.sha256());
        try (PartReader reader = new PartReader(file)) {
            reader.verify(result.sha256());
        }
    }

    @Test
    public void verify_detectsChangedContent() throws Exception {
        Path file = temp.resolve("part.gz");
        PartWriter.Result result = writeOneRow(file, "original");
        // same framing and length, different bytes: only the checksum can tell
        rewrite(file, "0", "forgery!");

        try (PartReader reader = new PartReader(file)) {
            reader.readRow(2);
            assertThrows(PartReader.ChecksumException.class, () -> reader.verify(result.sha256()));
        }
    }

    @Test
    public void verify_detectsTrailingData() throws Exception {
        Path file = temp.resolve("part.gz");
        PartWriter.Result result = writeOneRow(file, "original");
        try (PartReader reader = new PartReader(file)) {
            // the manifest claims fewer columns than the file holds
            reader.readRow(1);
            IOException e = assertThrows(IOException.class, () -> reader.verify(result.sha256()));
            assertEquals(IOException.class, e.getClass());
        }
    }

    @Test
    public void reader_ofANonGzipFileFailsAndReleasesTheFile() throws IOException {
        Path file = Files.writeString(temp.resolve("part.gz"), "not gzip");

        assertThrows(IOException.class, () -> new PartReader(file));
        // on Windows a leaked stream would keep the file locked
        Files.delete(file);
    }

    @Test
    public void writerThatCannotOpenItsFileStopsTheProducerInsteadOfBlockingIt() throws Exception {
        Path file = Files.writeString(temp.resolve("part.gz"), "exists already");
        PartWriter writer = new PartWriter(file, CODECS, new Progress(0));
        ExecutorService pool = Executors.newSingleThreadExecutor();
        try {
            Future<PartWriter.Result> future = pool.submit(writer);
            assertThrows(Exception.class, future::get);

            assertTimeoutPreemptively(Duration.ofSeconds(10), () -> {
                assertThrows(IllegalStateException.class, () -> writer.put(new Object[] {"1", "a", null}));
                writer.finish();
            });
        } finally {
            pool.shutdownNow();
        }
    }

    private static PartWriter.Result writeOneRow(Path file, String text) throws Exception {
        PartWriter writer = new PartWriter(file, List.of(ValueCodec.INTEGER, ValueCodec.TEXT), new Progress(1));
        writer.put(new Object[] {"0", text});
        writer.finish();
        return writer.call();
    }

    private static void rewrite(Path file, String number, String text) throws IOException {
        try (OutputStream raw = Files.newOutputStream(file);
             DataOutputStream out = new DataOutputStream(new GZIPOutputStream(raw))) {
            DumpFormat.writeValue(out, number.getBytes(StandardCharsets.UTF_8));
            DumpFormat.writeValue(out, text.getBytes(StandardCharsets.UTF_8));
        }
    }
}
