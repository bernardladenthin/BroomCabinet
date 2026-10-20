// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.kohsuke.args4j.CmdLineException;

public class OptionsTest {

    @Test
    public void environmentName() {
        assertEquals("DBSWAP_SOURCE_URL", Options.environmentName("--source-url"));
        assertEquals("DBSWAP_TASK", Options.environmentName("--task"));
        assertEquals("DBSWAP_IMPORT_THREADS", Options.environmentName("--import-threads"));
    }

    @Test
    public void commandLine() throws CmdLineException {
        Options options = Options.parse(new String[] {"--task", "export", "--parts", "4", "--source-url", "jdbc:x"},
                Map.of());

        assertEquals("export", options.task);
        assertEquals(4, options.parts);
        assertEquals("jdbc:x", options.sourceUrl);
        assertNull(options.targetUrl);
    }

    @Test
    public void environmentFillsWhatTheCommandLineLeftOpen() throws CmdLineException {
        Options options = Options.parse(new String[] {"--task", "import"}, Map.of(
                "DBSWAP_TASK", "export",
                "DBSWAP_TARGET_PASSWORD", "s3cret",
                "DBSWAP_BATCH_SIZE", " 500 ",
                "DBSWAP_TARGET_SCHEMA", ""));

        assertEquals("import", options.task, "the command line wins");
        assertEquals("s3cret", options.targetPassword);
        assertEquals(500, options.batchSize);
        assertNull(options.targetSchema, "an empty variable counts as unset");
    }

    @Test
    public void environmentNumberThatIsNoNumber() {
        CmdLineException e = assertThrows(CmdLineException.class,
                () -> Options.parse(new String[0], Map.of("DBSWAP_PARTS", "many")));

        assertTrue(e.getMessage().contains("DBSWAP_PARTS"), e.getMessage());
    }

    @Test
    public void unknownOption() {
        assertThrows(CmdLineException.class, () -> Options.parse(new String[] {"--nope"}, Map.of()));
    }

    @Test
    public void help() throws CmdLineException {
        assertTrue(Options.parse(new String[] {"--help"}, Map.of()).help);
    }

    @Test
    public void printUsage_listsEveryOption() {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();

        Options.printUsage(new PrintStream(bytes, true, StandardCharsets.UTF_8));

        String usage = bytes.toString(StandardCharsets.UTF_8);
        for (String option : new String[] {"--task", "--data-path", "--source-url", "--target-url", "--target-dialect",
                "--include", "--exclude", "--parts", "--import-threads", "--batch-size", "DBSWAP_SOURCE_URL"}) {
            assertTrue(usage.contains(option), option + " missing in\n" + usage);
        }
    }
}
