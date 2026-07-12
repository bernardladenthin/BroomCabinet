// SPDX-FileCopyrightText: 2017 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jscreenstreamer;

public class KeyProvider {

    private static byte[] hashedKey;

    public static void setHashedKey(byte[] hashedKey) {
        KeyProvider.hashedKey = hashedKey;
    }

    public static byte[] getHashedKey() {
        return hashedKey;
    }
}