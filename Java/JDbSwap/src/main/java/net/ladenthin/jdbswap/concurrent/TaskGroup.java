// SPDX-FileCopyrightText: 2016 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap.concurrent;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.Callable;
import java.util.concurrent.CompletionService;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.Executor;
import java.util.concurrent.ExecutorCompletionService;
import java.util.concurrent.Future;

/**
 * Tasks that succeed together or fail together.
 *
 * <p>{@link #awaitAll()} takes the tasks in the order they finish: the first failure cancels
 * every other task and is thrown at once, even while an earlier task still runs for hours.
 * ({@code ExecutorService.execute} would only print such a failure on the dying thread.)</p>
 */
public final class TaskGroup<T> {

    private final CompletionService<T> completion;
    private final List<Future<T>> futures = new ArrayList<>();

    public TaskGroup(Executor executor) {
        this.completion = new ExecutorCompletionService<>(executor);
    }

    public Future<T> submit(Callable<T> task) {
        Future<T> future = completion.submit(task);
        futures.add(future);
        return future;
    }

    /**
     * Waits for every task.
     *
     * @return the results in the order the tasks were submitted
     * @throws Exception the first failure, unwrapped
     */
    public List<T> awaitAll() throws Exception {
        try {
            for (int i = 0; i < futures.size(); i++) {
                Future<T> done = completion.take();
                try {
                    done.get();
                } catch (ExecutionException e) {
                    throw unwrap(e);
                }
            }
        } catch (Exception | Error e) {
            cancelAll();
            throw e;
        }
        List<T> results = new ArrayList<>(futures.size());
        for (Future<T> future : futures) {
            results.add(future.get());
        }
        return results;
    }

    /** Interrupts every task that still runs. */
    public void cancelAll() {
        futures.forEach(future -> future.cancel(true));
    }

    private static Exception unwrap(ExecutionException e) {
        Throwable cause = e.getCause();
        if (cause instanceof Error error) {
            throw error;
        }
        return cause instanceof Exception exception ? exception : e;
    }
}
