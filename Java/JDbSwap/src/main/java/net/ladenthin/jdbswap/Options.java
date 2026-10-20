// SPDX-FileCopyrightText: 2016 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap;

import java.io.PrintStream;
import java.lang.reflect.Field;
import java.util.Locale;
import java.util.Map;

import org.kohsuke.args4j.CmdLineException;
import org.kohsuke.args4j.CmdLineParser;
import org.kohsuke.args4j.Option;

/**
 * The command line. Every option can also come from an environment variable: {@code --source-url}
 * from {@code DBSWAP_SOURCE_URL} and so on (see {@link #environmentName(String)}). The command
 * line wins. Passwords belong in the environment - a command line is visible to every user of
 * the machine.
 */
public final class Options {

    public static final String ENVIRONMENT_PREFIX = "DBSWAP_";

    @Option(name = "--task", metaVar = "TASK", usage = "export, import or copy")
    String task;

    @Option(name = "--data-path", metaVar = "DIR", usage = "the dump directory (export: new or empty)")
    String dataPath;

    @Option(name = "--source-url", metaVar = "URL", usage = "JDBC URL of the source, e.g. jdbc:hive2://host:21050/;auth=noSasl")
    String sourceUrl;

    @Option(name = "--source-user", metaVar = "USER")
    String sourceUser;

    @Option(name = "--source-password", metaVar = "PASSWORD", usage = "prefer DBSWAP_SOURCE_PASSWORD")
    String sourcePassword;

    @Option(name = "--source-schema", metaVar = "SCHEMA", usage = "default: the connection's current schema")
    String sourceSchema;

    @Option(name = "--target-url", metaVar = "URL", usage = "JDBC URL of the target, e.g. jdbc:exa:host:8563")
    String targetUrl;

    @Option(name = "--target-user", metaVar = "USER")
    String targetUser;

    @Option(name = "--target-password", metaVar = "PASSWORD", usage = "prefer DBSWAP_TARGET_PASSWORD")
    String targetPassword;

    @Option(name = "--target-schema", metaVar = "SCHEMA", usage = "default: unqualified table names")
    String targetSchema;

    @Option(name = "--target-dialect", metaVar = "DIALECT", usage = "auto (from the URL), generic, exasol or monetdb")
    String targetDialect;

    @Option(name = "--table-prefix", metaVar = "PREFIX", usage = "put in front of every target table name")
    String tablePrefix;

    @Option(name = "--include", metaVar = "REGEX", usage = "tables whose whole name matches (default .*)")
    String include;

    @Option(name = "--exclude", metaVar = "REGEX", usage = "tables whose whole name matches are left out")
    String exclude;

    @Option(name = "--parts", metaVar = "N", usage = "export: part files and writer threads per table (default 16)")
    Integer parts;

    @Option(name = "--import-threads", metaVar = "N", usage = "import: parts loaded at the same time (default 1)")
    Integer importThreads;

    @Option(name = "--batch-size", metaVar = "N", usage = "import, copy: rows per JDBC batch and commit (default 200000)")
    Integer batchSize;

    @Option(name = "--help", help = true, usage = "show this help")
    boolean help;

    /** Parses {@code args}, then fills every option still unset from {@code environment}. */
    public static Options parse(String[] args, Map<String, String> environment) throws CmdLineException {
        Options options = new Options();
        CmdLineParser parser = new CmdLineParser(options);
        parser.parseArgument(args);
        options.applyEnvironment(environment, parser);
        return options;
    }

    /** {@code --source-url} becomes {@code DBSWAP_SOURCE_URL}. */
    public static String environmentName(String optionName) {
        return ENVIRONMENT_PREFIX + optionName.replaceFirst("^--", "").replace('-', '_').toUpperCase(Locale.ROOT);
    }

    private void applyEnvironment(Map<String, String> environment, CmdLineParser parser) throws CmdLineException {
        for (Field field : Options.class.getDeclaredFields()) {
            Option option = field.getAnnotation(Option.class);
            if (option == null || option.help()) {
                continue;
            }
            String value = environment.get(environmentName(option.name()));
            if (value == null || value.isEmpty()) {
                continue;
            }
            try {
                if (field.get(this) != null) {
                    continue;
                }
                if (field.getType() == Integer.class) {
                    field.set(this, Integer.valueOf(value.trim()));
                } else {
                    field.set(this, value);
                }
            } catch (NumberFormatException e) {
                throw new CmdLineException(parser, environmentName(option.name()) + " is not a number: " + value, e);
            } catch (IllegalAccessException e) {
                throw new IllegalStateException(e);
            }
        }
    }

    public static void printUsage(PrintStream out) {
        out.println("java -jar jdbswap-1.0.0-SNAPSHOT-all.jar --task export|import|copy [options]");
        out.println("Every option can be set as environment variable instead, e.g. --source-url as "
                + environmentName("--source-url") + ".");
        out.println();
        new CmdLineParser(new Options()).printUsage(out);
    }
}
