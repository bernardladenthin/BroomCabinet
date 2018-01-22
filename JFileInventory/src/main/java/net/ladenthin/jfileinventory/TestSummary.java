package net.ladenthin.jfileinventory;

import java.io.PrintStream;

public class TestSummary {
    public long notModifiedAndDifferentChecksum = 0;
    public long notModifiedAndSameChecksum = 0;
    public long modifiedAndSameChecksum = 0;
    public long modifiedSameLengthAndDifferenChecksum = 0;
    public long modifiedDifferentLengthAndDifferenChecksum = 0;
    public long notExistsInInventory = 0;

    public void printSummary(PrintStream out) {
        out.println();
        out.println("===== SUMMARY ===== ");
        out.println("NOK: notModifiedAndDifferentChecksum: " + notModifiedAndDifferentChecksum);
        out.println("OK:  notModifiedAndSameChecksum: " + notModifiedAndSameChecksum);
        out.println("OK:  modifiedAndSameChecksum: " + modifiedAndSameChecksum);
        out.println("??:  modifiedSameLengthAndDifferenChecksum: " + modifiedSameLengthAndDifferenChecksum);
        out.println("??:  modifiedDifferentLengthAndDifferenChecksum: " + modifiedDifferentLengthAndDifferenChecksum);
        out.println("??:  notExistsInInventory: " + notExistsInInventory);
        out.println();
        out.println();
    }
}
