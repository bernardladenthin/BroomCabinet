// SPDX-FileCopyrightText: 2016 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap.progress;

import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.logging.Logger;

/**
 * Logs a {@link Progress} at a fixed interval until it is closed, then once more.
 */
public final class ProgressReporter implements AutoCloseable {

    private static final Logger LOG = Logger.getLogger(ProgressReporter.class.getName());
    private static final long INTERVAL_SECONDS = 10;

    private final String label;
    private final Progress progress;
    private final ScheduledExecutorService scheduler;

    public ProgressReporter(String label, Progress progress) {
        this.label = label;
        this.progress = progress;
        this.scheduler = Executors.newSingleThreadScheduledExecutor(runnable -> {
            Thread thread = new Thread(runnable, "progress-" + label);
            thread.setDaemon(true);
            return thread;
        });
        scheduler.scheduleAtFixedRate(this::report, INTERVAL_SECONDS, INTERVAL_SECONDS, TimeUnit.SECONDS);
    }

    private void report() {
        LOG.info(() -> label + ": " + progress.format());
    }

    @Override
    public void close() {
        scheduler.shutdownNow();
        report();
    }
}
