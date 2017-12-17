package net.ladenthin.hddfiller;

import java.io.*;
import java.util.Arrays;

public class Main {

    public static void main(String[] argv) {
        if (argv.length != 2) {
            System.err.println("First parameter: size of each file. Add optional Unit: [KB, MB, GB]. E.g. 128KB. Default unit: KB");
            System.err.println("Second parameter: number of files. Unitless");
            return;
        }

        long sizeOfFile = getSizeInKbOfString(argv[0]);
        int numberOfFile = Integer.parseInt(argv[1]);

        File parent = new File("hddFiller");
        parent.mkdirs();

        for (int i = 0; i < numberOfFile; i++) {
            System.out.printf("Start to write content to file %7d.", i);
            try {
                File file = new File(parent, i+".txt");
                createFile(file, sizeOfFile);
            } catch (IOException e) {
                throw new RuntimeException(e);
            }
        }
    }
    private static void createFile(File file, final long kb) throws IOException {
        // create a new string to fill the file
        char[] chars = new char[1024];
        Arrays.fill(chars, 'A');
        // a kilobyte of data
        String longLine = new String(chars);

        long start = System.nanoTime();
        PrintWriter pw = new PrintWriter(new FileWriter(file));
        int lastPercent = -1;
        // create a new line for the progress log
        System.out.println();
        for (long i = 0; i < kb; i++) {
            lastPercent = logProgress(i, kb, lastPercent);
            pw.print(longLine);
        }
        pw.close();

        long end = System.nanoTime();
        long duration = end - start;
        System.out.printf("Took %.3f seconds to write to a %d MB, file rate: %.1f MB/s%n", duration / 1e9, file.length() >> 20, file.length() * 1000.0 / duration);
    }

    private static int logProgress(long current, long max, int lastPercent) {
        int percent = (int) ((current / (float)max) * 100);
        if (lastPercent != percent) {
            System.out.print("\r" + percent + " %\r");
        }
        return percent;
    }

    private static long getSizeInKbOfString(String s) {
        s = s.toLowerCase();
        long l;
        if (s.contains("kb")) {
            l = Long.parseLong(s.substring(0, s.indexOf("kb")));
        } else if (s.contains("mb")) {
            l = Long.parseLong(s.substring(0, s.indexOf("mb")));
            l *= 1024;
        } else if (s.contains("gb")) {
            l = Long.parseLong(s.substring(0, s.indexOf("gb")));
            l *= 1024 * 1024;
        } else {
            l = Long.parseLong(s);
        }
        return l;
    }
}
