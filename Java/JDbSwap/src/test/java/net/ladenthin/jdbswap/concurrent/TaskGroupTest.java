// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap.concurrent;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTimeoutPreemptively;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.time.Duration;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

public class TaskGroupTest {

    private final ExecutorService pool = Executors.newFixedThreadPool(4);

    @AfterEach
    public void shutdown() {
        pool.shutdownNow();
    }

    @Test
    public void resultsInSubmissionOrder() throws Exception {
        TaskGroup<Integer> group = new TaskGroup<>(pool);
        group.submit(() -> {
            Thread.sleep(200);
            return 1;
        });
        group.submit(() -> 2);
        group.submit(() -> 3);

        assertEquals(List.of(1, 2, 3), group.awaitAll());
    }

    @Test
    public void empty() throws Exception {
        assertEquals(List.of(), new TaskGroup<Integer>(pool).awaitAll());
    }

    @Test
    public void laterFailureIsThrownAtOnceAndCancelsTheBlockedTask() throws Exception {
        CountDownLatch interrupted = new CountDownLatch(1);
        IOException failure = new IOException("checksum error");
        TaskGroup<Integer> group = new TaskGroup<>(pool);
        group.submit(() -> {
            try {
                // stands for a part that would take hours
                Thread.sleep(TimeUnit.HOURS.toMillis(1));
            } catch (InterruptedException e) {
                interrupted.countDown();
            }
            return 1;
        });
        group.submit(() -> {
            throw failure;
        });

        assertTimeoutPreemptively(Duration.ofSeconds(10), () -> {
            IOException thrown = assertThrows(IOException.class, group::awaitAll);
            assertSame(failure, thrown);
            assertTrue(interrupted.await(5, TimeUnit.SECONDS), "the blocked task was not interrupted");
        });
    }

    @Test
    public void runtimeExceptionIsUnwrapped() {
        TaskGroup<Integer> group = new TaskGroup<>(pool);
        group.submit(() -> {
            throw new IllegalStateException("boom");
        });

        IllegalStateException e = assertThrows(IllegalStateException.class, group::awaitAll);
        assertEquals("boom", e.getMessage());
    }

    @Test
    public void errorIsRethrown() {
        TaskGroup<Integer> group = new TaskGroup<>(pool);
        group.submit(() -> {
            throw new AssertionError("broken");
        });

        assertThrows(AssertionError.class, group::awaitAll);
    }
}
