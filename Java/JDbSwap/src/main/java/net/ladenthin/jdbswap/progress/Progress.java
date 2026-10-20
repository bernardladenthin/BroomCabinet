// SPDX-FileCopyrightText: 2016 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap.progress;

import java.util.Locale;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;
import java.util.function.LongSupplier;

/**
 * Rows and bytes moved so far, safe to update from many threads.
 *
 * <p>It waits for nothing: whoever moves the rows decides when a table is done, not a
 * counter that has to reach the expected value.</p>
 */
public final class Progress {

    private final long expectedRows;
    private final LongSupplier nanoTime;
    private final long start;
    private final AtomicLong rows = new AtomicLong();
    private final AtomicLong bytes = new AtomicLong();

    /** @param expectedRows the rows the table should have; {@code 0} or less when unknown */
    public Progress(long expectedRows) {
        this(expectedRows, System::nanoTime);
    }

    Progress(long expectedRows, LongSupplier nanoTime) {
        this.expectedRows = expectedRows;
        this.nanoTime = nanoTime;
        this.start = nanoTime.getAsLong();
    }

    public void add(long rows, long bytes) {
        this.rows.addAndGet(rows);
        this.bytes.addAndGet(bytes);
    }

    public long rows() {
        return rows.get();
    }

    public long bytes() {
        return bytes.get();
    }

    /** {@code 1,500 / 3,000 rows (50%) | 750 rows/s | 1.2 MB/s | 2s left}, or the elapsed time once done. */
    public String format() {
        long rows = rows();
        long elapsedNanos = Math.max(1, nanoTime.getAsLong() - start);
        double seconds = elapsedNanos / 1e9;
        long rowsPerSecond = (long) (rows / seconds);

        StringBuilder sb = new StringBuilder();
        sb.append(String.format(Locale.ROOT, "%,d", rows));
        if (expectedRows > 0) {
            sb.append(String.format(Locale.ROOT, " / %,d rows (%d%%)", expectedRows, Math.min(100, rows * 100 / expectedRows)));
        } else {
            sb.append(" rows");
        }
        sb.append(String.format(Locale.ROOT, " | %,d rows/s | %.1f MB/s", rowsPerSecond, bytes() / 1e6 / seconds));
        if (expectedRows > rows && rowsPerSecond > 0) {
            sb.append(" | ").append(duration((expectedRows - rows) / rowsPerSecond)).append(" left");
        } else {
            sb.append(" | ").append(duration(TimeUnit.NANOSECONDS.toSeconds(elapsedNanos))).append(" elapsed");
        }
        return sb.toString();
    }

    /** {@code 59s}, {@code 1m 05s}, {@code 2h 03m 04s}. */
    static String duration(long seconds) {
        long hours = seconds / 3600;
        long minutes = seconds % 3600 / 60;
        long secs = seconds % 60;
        if (hours > 0) {
            return String.format(Locale.ROOT, "%dh %02dm %02ds", hours, minutes, secs);
        }
        if (minutes > 0) {
            return String.format(Locale.ROOT, "%dm %02ds", minutes, secs);
        }
        return secs + "s";
    }
}
