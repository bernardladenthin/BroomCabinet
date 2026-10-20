// SPDX-FileCopyrightText: 2016 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap.dump;

import java.io.BufferedOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.security.DigestOutputStream;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.List;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.Callable;
import java.util.concurrent.TimeUnit;
import java.util.zip.GZIPOutputStream;

import net.ladenthin.jdbswap.jdbc.ValueCodec;
import net.ladenthin.jdbswap.progress.Progress;

/**
 * Writes the rows one producer hands over into one part file, on its own thread.
 *
 * <p>The producer calls {@link #put(Object[])} for every row and {@link #finish()} at the end.
 * Should the writer fail, {@link #put} stops blocking and throws instead, so the producer can
 * never wait forever on a queue nobody empties any more; the cause comes out of the writer's
 * {@code Future}.</p>
 */
public final class PartWriter implements Callable<PartWriter.Result> {

    /** What one part holds once it is written. */
    public record Result(long rows, String sha256, long[] longest) {
    }

    private static final int CAPACITY = 1024 * 16;
    private static final Object[] END = new Object[0];
    private static final int BUFFER_SIZE = 64 * 1024;

    private final Path file;
    private final List<ValueCodec> codecs;
    private final Progress progress;
    private final BlockingQueue<Object[]> queue = new ArrayBlockingQueue<>(CAPACITY);
    private volatile boolean stopped;

    public PartWriter(Path file, List<ValueCodec> codecs, Progress progress) {
        this.file = file;
        this.codecs = List.copyOf(codecs);
        this.progress = progress;
    }

    /** Hands over one row of values as {@link ValueCodec#read} returned them. */
    public void put(Object[] row) throws InterruptedException {
        offer(row);
    }

    /** No more rows; the writer closes its file once the queue is empty. */
    public void finish() throws InterruptedException {
        offer(END);
    }

    private void offer(Object[] row) throws InterruptedException {
        while (true) {
            if (stopped) {
                if (row == END) {
                    return;
                }
                throw new IllegalStateException("Part writer stopped: " + file);
            }
            if (queue.offer(row, 100, TimeUnit.MILLISECONDS)) {
                return;
            }
        }
    }

    @Override
    public Result call() throws IOException, InterruptedException {
        try {
            MessageDigest digest = DumpFormat.newDigest();
            long[] longest = new long[codecs.size()];
            long rows = 0;
            // the raw stream gets its own resource: it must close even if the GZIP header fails
            try (OutputStream raw = Files.newOutputStream(file, StandardOpenOption.CREATE_NEW);
                 DataOutputStream out = new DataOutputStream(new BufferedOutputStream(
                         new DigestOutputStream(new GZIPOutputStream(raw, BUFFER_SIZE), digest), BUFFER_SIZE))) {
                while (true) {
                    Object[] row = queue.take();
                    if (row == END) {
                        break;
                    }
                    long bytes = 0;
                    for (int i = 0; i < row.length; i++) {
                        Object value = row[i];
                        if (value == null) {
                            DumpFormat.writeValue(out, null);
                        } else {
                            ValueCodec codec = codecs.get(i);
                            longest[i] = Math.max(longest[i], codec.length(value));
                            byte[] encoded = codec.encode(value);
                            DumpFormat.writeValue(out, encoded);
                            bytes += encoded.length;
                        }
                    }
                    rows++;
                    progress.add(1, bytes);
                }
            }
            return new Result(rows, HexFormat.of().formatHex(digest.digest()), longest);
        } finally {
            stopped = true;
        }
    }
}
