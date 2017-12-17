package net.ladenthin.screenshot;

import net.ladenthin.screenshot.client.View;
import net.ladenthin.screenshot.server.Server;

public class Main {

    public static void printUsage() {
        System.out.println("Please give the option --client or --server.");
    }

    public static void main(String argv[]) {
        if (argv.length < 1) {
            printUsage();
            return;
        }

        switch (argv[0]) {
            case "--client" :
                View.main(argv);
                break;
            case "--server":
                Server.main(argv);
                break;
            default:
                printUsage();
                break;
        }
    }
}