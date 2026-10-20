// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap.progress;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;

import org.junit.jupiter.api.Test;

public class ProgressTest {

    private final AtomicLong now = new AtomicLong(1_000);

    @Test
    public void format_withExpectedRows() {
        Progress progress = new Progress(3000, now::get);
        progress.add(1500, 2_400_000);
        elapse(2);

        assertEquals("1,500 / 3,000 rows (50%) | 750 rows/s | 1.2 MB/s | 2s left", progress.format());
    }

    @Test
    public void format_done() {
        Progress progress = new Progress(100, now::get);
        progress.add(100, 0);
        elapse(65);

        assertEquals("100 / 100 rows (100%) | 1 rows/s | 0.0 MB/s | 1m 05s elapsed", progress.format());
    }

    @Test
    public void format_moreRowsThanExpectedStaysAt100Percent() {
        Progress progress = new Progress(10, now::get);
        progress.add(12, 0);
        elapse(1);

        assertEquals("12 / 10 rows (100%) | 12 rows/s | 0.0 MB/s | 1s elapsed", progress.format());
    }

    @Test
    public void format_unknownExpectedRows() {
        Progress progress = new Progress(0, now::get);
        progress.add(5, 0);
        elapse(1);

        assertEquals("5 rows | 5 rows/s | 0.0 MB/s | 1s elapsed", progress.format());
    }

    @Test
    public void format_beforeAnyTimePassedDoesNotDivideByZero() {
        Progress progress = new Progress(10, now::get);

        assertEquals("0 / 10 rows (0%) | 0 rows/s | 0.0 MB/s | 0s elapsed", progress.format());
    }

    @Test
    public void addIsSafeFromManyThreads() throws InterruptedException {
        Progress progress = new Progress(0);
        Thread[] threads = new Thread[8];
        for (int i = 0; i < threads.length; i++) {
            threads[i] = new Thread(() -> {
                for (int j = 0; j < 10_000; j++) {
                    progress.add(1, 3);
                }
            });
            threads[i].start();
        }
        for (Thread thread : threads) {
            thread.join();
        }

        assertEquals(80_000, progress.rows());
        assertEquals(240_000, progress.bytes());
    }

    @Test
    public void duration() {
        assertEquals("0s", Progress.duration(0));
        assertEquals("59s", Progress.duration(59));
        assertEquals("1m 00s", Progress.duration(60));
        assertEquals("59m 59s", Progress.duration(3599));
        assertEquals("1h 00m 00s", Progress.duration(3600));
        assertEquals("40h 02m 03s", Progress.duration(40 * 3600 + 123));
    }

    private void elapse(long seconds) {
        now.addAndGet(TimeUnit.SECONDS.toNanos(seconds));
    }
}
