// SPDX-FileCopyrightText: 2017 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

import javax.swing.JFrame;

public class Main {

    public static void main(String[] args) throws Exception {
        block(15);
        new JFrame("Test");
        System.out.println("success, exit");
    }

    private static void block(int timeoutinSeconds) throws InterruptedException {
        for (int i = timeoutinSeconds; i >= 0; i--) {
            System.out.println(i + " seconds remaining");
            Thread.sleep(1000);
        }
    }
}
