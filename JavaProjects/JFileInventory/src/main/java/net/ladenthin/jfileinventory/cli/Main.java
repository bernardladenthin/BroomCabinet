package net.ladenthin.jfileinventory.cli;

import net.ladenthin.jfileinventory.Command;
import net.ladenthin.jfileinventory.Inventory;
import org.kohsuke.args4j.CmdLineException;
import org.kohsuke.args4j.CmdLineParser;
import org.kohsuke.args4j.Option;
import org.kohsuke.args4j.ParserProperties;

import java.io.File;
import java.io.IOException;

import static org.kohsuke.args4j.OptionHandlerFilter.ALL;

public class Main {

    @Option(name="-d", aliases = { "--database" }, required = true, usage = "path to the inventory database")
    private File database;

    @Option(name = "-c", aliases = { "--command" }, required = true, usage = "command to execute")
    private String command = Command.AddMissing.toString();

    @Option(name = "-s", aliases = { "--source" }, required = true, usage = "source directory")
    private File source;

    @Option(name = "-p", aliases = { "--pathPrefix" }, required = false, usage = "remove directory prefix from path")
    private File pathPrefix;

    public static void main(String[] args) throws CmdLineException, IOException {
        new Main().doMain(args);
    }

    public void doMain(String[] args) throws CmdLineException, IOException {
        ParserProperties pp = ParserProperties.defaults().withUsageWidth(80);
        CmdLineParser parser = new CmdLineParser(this, pp);

        try {
            // parse the arguments.
            parser.parseArgument(args);

        } catch( CmdLineException e ) {
            // if there's a problem in the command line,
            // you'll get this exception. this will report
            // an error message.
            System.err.println(e.getMessage());
            System.err.println("java Inventory.jar [options...]");
            // print the list of available options
            parser.printUsage(System.err);
            System.err.println();

            // print option sample. This is useful some time
            System.err.println("  Example: java Inventory.jar"+parser.printExample(ALL));
            return;
        }

        Inventory inventory = new Inventory(Command.valueOf(command), database.getCanonicalFile(), source, pathPrefix);
        inventory.run();
    }
}
