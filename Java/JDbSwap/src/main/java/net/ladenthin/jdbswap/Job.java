// SPDX-FileCopyrightText: 2016 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.regex.PatternSyntaxException;

import net.ladenthin.jdbswap.copy.Copier;
import net.ladenthin.jdbswap.dump.DumpDirectory;
import net.ladenthin.jdbswap.export.Exporter;
import net.ladenthin.jdbswap.importer.Importer;
import net.ladenthin.jdbswap.jdbc.ConnectionSpec;
import net.ladenthin.jdbswap.jdbc.Dialect;

/**
 * Validated {@link Options}: what to run and with which settings.
 *
 * @param source  {@code null} for an import
 * @param target  {@code null} for an export
 * @param dialect {@code null} for an export
 * @param dump    {@code null} for a copy
 */
public record Job(Task task, ConnectionSpec source, ConnectionSpec target, Dialect dialect, DumpDirectory dump,
        TableFilter filter, String tablePrefix, int parts, int importThreads, int batchSize) {

    public enum Task {
        EXPORT, IMPORT, COPY
    }

    public static final int DEFAULT_PARTS = 16;
    public static final int DEFAULT_IMPORT_THREADS = 1;
    public static final int DEFAULT_BATCH_SIZE = 200_000;

    /** @throws IllegalArgumentException naming everything that is missing or wrong */
    public static Job from(Options options) {
        List<String> problems = new ArrayList<>();

        Task task = null;
        if (options.task == null) {
            problems.add("--task is missing (export, import or copy)");
        } else {
            try {
                task = Task.valueOf(options.task.trim().toUpperCase(Locale.ROOT));
            } catch (IllegalArgumentException e) {
                problems.add("--task must be export, import or copy, not " + options.task);
            }
        }

        boolean needsSource = task == Task.EXPORT || task == Task.COPY;
        boolean needsTarget = task == Task.IMPORT || task == Task.COPY;
        boolean needsDump = task == Task.EXPORT || task == Task.IMPORT;

        require(needsSource, options.sourceUrl, "--source-url", problems);
        require(needsTarget, options.targetUrl, "--target-url", problems);
        require(needsDump, options.dataPath, "--data-path", problems);

        int parts = positive(options.parts, DEFAULT_PARTS, "--parts", problems);
        int importThreads = positive(options.importThreads, DEFAULT_IMPORT_THREADS, "--import-threads", problems);
        int batchSize = positive(options.batchSize, DEFAULT_BATCH_SIZE, "--batch-size", problems);

        TableFilter filter = null;
        try {
            filter = TableFilter.of(options.include, options.exclude);
        } catch (PatternSyntaxException e) {
            problems.add("--include/--exclude is not a valid regular expression: " + e.getMessage());
        }

        Dialect dialect = null;
        if (needsTarget && options.targetUrl != null) {
            try {
                dialect = Dialect.parse(options.targetDialect, options.targetUrl);
            } catch (IllegalArgumentException e) {
                problems.add("--target-dialect must be auto, generic, exasol or monetdb, not " + options.targetDialect);
            }
        }

        if (!problems.isEmpty()) {
            throw new IllegalArgumentException(String.join("\n", problems));
        }

        ConnectionSpec source = needsSource
                ? new ConnectionSpec(options.sourceUrl, options.sourceUser, options.sourcePassword, options.sourceSchema)
                : null;
        ConnectionSpec target = needsTarget
                ? new ConnectionSpec(options.targetUrl, options.targetUser, options.targetPassword, options.targetSchema)
                : null;
        DumpDirectory dump = needsDump ? new DumpDirectory(Path.of(options.dataPath)) : null;
        return new Job(task, source, target, dialect, dump, filter, options.tablePrefix == null ? "" : options.tablePrefix,
                parts, importThreads, batchSize);
    }

    public void run() throws Exception {
        switch (task) {
            case EXPORT -> new Exporter(source, dump, filter, parts).run();
            case IMPORT -> new Importer(target, dialect, dump, filter, tablePrefix, importThreads, batchSize).run();
            case COPY -> new Copier(source, target, dialect, filter, tablePrefix, batchSize).run();
        }
    }

    private static void require(boolean needed, String value, String option, List<String> problems) {
        if (needed && (value == null || value.isBlank())) {
            problems.add(option + " is missing (or " + Options.environmentName(option) + ")");
        }
    }

    private static int positive(Integer value, int defaultValue, String option, List<String> problems) {
        if (value == null) {
            return defaultValue;
        }
        if (value < 1) {
            problems.add(option + " must be at least 1, not " + value);
        }
        return value;
    }

    @Override
    public String toString() {
        return "Job{task=" + task + ", source=" + source + ", target=" + target + ", dialect=" + dialect
                + ", dump=" + (dump == null ? null : dump.path()) + ", filter=" + filter + ", tablePrefix='"
                + tablePrefix + "', parts=" + parts + ", importThreads=" + importThreads + ", batchSize=" + batchSize
                + "}";
    }
}
