// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/**
 * The command line as a whole: exit codes, and export plus import configured the way a
 * script would, through the environment.
 */
public class MainTest {

    private final ByteArrayOutputStream err = new ByteArrayOutputStream();

    @TempDir
    Path temp;

    @Test
    public void help() {
        assertEquals(Main.EXIT_OK, run(Map.of(), "--help"));
        assertTrue(err().contains("--source-url"), err());
    }

    @Test
    public void missingOptionsAreAUsageError() {
        assertEquals(Main.EXIT_USAGE, run(Map.of(), "--task", "export"));
        assertTrue(err().contains("--source-url is missing"), err());
        assertTrue(err().contains("--data-path is missing"), err());
    }

    @Test
    public void unknownOptionIsAUsageError() {
        assertEquals(Main.EXIT_USAGE, run(Map.of(), "--frobnicate"));
    }

    @Test
    public void failingJobExitsWithFailure() {
        // an empty directory has no manifest
        assertEquals(Main.EXIT_FAILED,
                run(Map.of(), "--task", "import", "--target-url", "jdbc:h2:mem:unused", "--data-path", temp.toString()));
    }

    @Test
    public void exportThenImportThroughTheEnvironment() throws Exception {
        try (H2Database source = new H2Database(); H2Database target = new H2Database()) {
            SourceFixture.create(source);
            String dataPath = temp.resolve("dump").toString();

            int exported = run(Map.of(
                    "DBSWAP_TASK", "export",
                    "DBSWAP_SOURCE_URL", source.url(),
                    "DBSWAP_DATA_PATH", dataPath,
                    "DBSWAP_EXCLUDE", "IMPORTED_.*",
                    "DBSWAP_PARTS", "4"));
            assertEquals(Main.EXIT_OK, exported, err());

            int imported = run(Map.of(
                    "DBSWAP_TASK", "import",
                    "DBSWAP_TARGET_URL", target.url(),
                    "DBSWAP_DATA_PATH", dataPath,
                    "DBSWAP_IMPORT_THREADS", "3",
                    "DBSWAP_BATCH_SIZE", "5"));
            assertEquals(Main.EXIT_OK, imported, err());

            String orders = String.format(SourceFixture.ORDERS_QUERY, "ORDERS");
            assertEquals(source.rows(orders), target.rows(orders));
            assertEquals(List.of("ORDERS", "ORDERXITEMS", "ORDER_ITEMS"), target.tables());
        }
    }

    @Test
    public void copyThroughTheCommandLine() throws Exception {
        try (H2Database source = new H2Database(); H2Database target = new H2Database()) {
            SourceFixture.create(source);

            int copied = run(Map.of(), "--task", "copy", "--source-url", source.url(), "--target-url", target.url(),
                    "--include", "ORDER_ITEMS");

            assertEquals(Main.EXIT_OK, copied, err());
            assertEquals(3, target.rows("SELECT * FROM ORDER_ITEMS").size());
        }
    }

    private int run(Map<String, String> environment, String... args) {
        return Main.run(args, environment, new PrintStream(err, true, StandardCharsets.UTF_8));
    }

    private String err() {
        return err.toString(StandardCharsets.UTF_8);
    }
}
