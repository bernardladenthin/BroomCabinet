// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.Map;

import org.junit.jupiter.api.Test;
import org.kohsuke.args4j.CmdLineException;

import net.ladenthin.jdbswap.jdbc.Dialect;

public class JobTest {

    @Test
    public void export_withDefaults() throws CmdLineException {
        Job job = job("--task", "export", "--source-url", "jdbc:hive2://h:21050/;auth=noSasl", "--data-path", "dump");

        assertEquals(Job.Task.EXPORT, job.task());
        assertEquals(Job.DEFAULT_PARTS, job.parts());
        assertEquals(Job.DEFAULT_IMPORT_THREADS, job.importThreads());
        assertEquals(Job.DEFAULT_BATCH_SIZE, job.batchSize());
        assertEquals("", job.tablePrefix());
        assertTrue(job.filter().accepts("anything"));
        assertNull(job.target());
        assertNull(job.dialect());
    }

    @Test
    public void import_dialectFromTheUrl() throws CmdLineException {
        Job job = job("--task", "IMPORT", "--target-url", "jdbc:exa:h:8563", "--data-path", "dump");

        assertEquals(Job.Task.IMPORT, job.task());
        assertEquals(Dialect.EXASOL, job.dialect());
        assertNull(job.source());
    }

    @Test
    public void import_dialectOverridden() throws CmdLineException {
        Job job = job("--task", "import", "--target-url", "jdbc:h2:mem:x", "--data-path", "d", "--target-dialect", "monetdb");

        assertEquals(Dialect.MONETDB, job.dialect());
    }

    @Test
    public void copy_needsNoDataPath() throws CmdLineException {
        Job job = job("--task", "copy", "--source-url", "jdbc:a", "--target-url", "jdbc:b");

        assertNull(job.dump());
        assertEquals(Dialect.GENERIC, job.dialect());
    }

    @Test
    public void everyProblemIsNamedAtOnce() {
        IllegalArgumentException e = assertThrows(IllegalArgumentException.class,
                () -> job("--task", "copy", "--parts", "0", "--include", "(", "--target-dialect", "oracle",
                        "--target-url", "jdbc:x"));

        String message = e.getMessage();
        assertTrue(message.contains("--source-url is missing (or DBSWAP_SOURCE_URL)"), message);
        assertTrue(message.contains("--parts must be at least 1"), message);
        assertTrue(message.contains("regular expression"), message);
        assertTrue(message.contains("--target-dialect"), message);
        assertFalse(message.contains("--data-path"), message);
    }

    @Test
    public void missingTask() {
        IllegalArgumentException e = assertThrows(IllegalArgumentException.class, () -> job());

        assertTrue(e.getMessage().contains("--task is missing"), e.getMessage());
    }

    @Test
    public void unknownTask() {
        IllegalArgumentException e = assertThrows(IllegalArgumentException.class, () -> job("--task", "swap"));

        assertTrue(e.getMessage().contains("not swap"), e.getMessage());
    }

    @Test
    public void toString_hidesPasswords() throws CmdLineException {
        Job job = Job.from(Options.parse(new String[] {"--task", "copy", "--source-url", "jdbc:a", "--target-url", "jdbc:b"},
                Map.of("DBSWAP_SOURCE_PASSWORD", "s3cret", "DBSWAP_TARGET_PASSWORD", "t0psecret")));

        assertFalse(job.toString().contains("s3cret"), job.toString());
        assertFalse(job.toString().contains("t0psecret"), job.toString());
        assertEquals("s3cret", job.source().password());
    }

    private static Job job(String... args) throws CmdLineException {
        return Job.from(Options.parse(args, Map.of()));
    }
}
