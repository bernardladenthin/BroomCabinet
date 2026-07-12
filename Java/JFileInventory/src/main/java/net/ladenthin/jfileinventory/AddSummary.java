// SPDX-FileCopyrightText: 2018 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jfileinventory;

import java.io.PrintStream;

public class AddSummary {
    public long couldNotAccess;
    public long add;
    public long updateLastSeen;

    public void printSummary(PrintStream out) {
        out.println();
        out.println("===== SUMMARY ===== ");
        out.println("??:  Could not access: " + couldNotAccess);
        out.println("OK: Add: " + add);
        out.println("OK: Update lastSeen: Already exists: " + updateLastSeen);
        out.println();
        out.println();
    }
}
