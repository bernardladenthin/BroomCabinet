package net.ladenthin.screenshot;

public class KeyProvider {

    private static byte[] hashedKey;

    public static void setHashedKey(byte[] hashedKey) {
        KeyProvider.hashedKey = hashedKey;
    }

    public static byte[] getHashedKey() {
        return hashedKey;
    }
}