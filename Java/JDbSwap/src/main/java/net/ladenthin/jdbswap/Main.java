// SPDX-FileCopyrightText: 2016 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap;

import java.io.PrintStream;
import java.util.Map;
import java.util.logging.Level;
import java.util.logging.Logger;

import org.kohsuke.args4j.CmdLineException;

/**
 * Command line entry point: {@code java -jar jdbswap-...-all.jar --task export ...}.
 */
public final class Main {

    public static final int EXIT_OK = 0;
    public static final int EXIT_FAILED = 1;
    public static final int EXIT_USAGE = 2;

    private static final Logger LOG = Logger.getLogger(Main.class.getName());

    private Main() {
    }

    public static void main(String[] args) {
        // one line per record, unless a format is configured already
        if (System.getProperty("java.util.logging.SimpleFormatter.format") == null) {
            System.setProperty("java.util.logging.SimpleFormatter.format", "%1$tF %1$tT %4$-7s %5$s%6$s%n");
        }
        System.exit(run(args, System.getenv(), System.err));
    }

    /** Everything {@link #main} does except leaving the JVM; returns the exit code. */
    public static int run(String[] args, Map<String, String> environment, PrintStream err) {
        Job job;
        try {
            Options options = Options.parse(args, environment);
            if (options.help) {
                Options.printUsage(err);
                return EXIT_OK;
            }
            job = Job.from(options);
        } catch (CmdLineException | IllegalArgumentException e) {
            err.println(e.getMessage());
            err.println();
            Options.printUsage(err);
            return EXIT_USAGE;
        }

        LOG.info(() -> "Start " + job);
        try {
            job.run();
            LOG.info(() -> job.task() + " done");
            return EXIT_OK;
        } catch (Exception e) {
            LOG.log(Level.SEVERE, job.task() + " failed", e);
            return EXIT_FAILED;
        }
    }
}
