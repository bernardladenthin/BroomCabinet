package net.ladenthin.screenshot;

import javax.crypto.*;
import javax.crypto.spec.IvParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import java.security.InvalidAlgorithmParameterException;
import java.security.InvalidKeyException;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.util.Arrays;

public class Security {

    public final static int InitializationVectorBytes = 16;

    public Security() {

    }

    public static byte[] encrypt(byte[] input, byte[] keyBytes, byte[] ivBytes, boolean only128BitKey) throws InvalidAlgorithmParameterException, InvalidKeyException, NoSuchPaddingException, NoSuchAlgorithmException, ShortBufferException, BadPaddingException, IllegalBlockSizeException {
        if (only128BitKey) {
            keyBytes = Arrays.copyOf(keyBytes, 16);
        }
        SecretKeySpec key = new SecretKeySpec(keyBytes, "AES");
        IvParameterSpec iv = new IvParameterSpec(ivBytes);
        Cipher cipher = Cipher.getInstance("AES/CBC/PKCS5Padding");
        cipher.init(Cipher.ENCRYPT_MODE, key, iv);
        byte[] encrypted = cipher.doFinal(input);
        return encrypted;
    }

    public static byte[] decrypt(byte[] input, byte[] keyBytes, byte[] ivBytes, boolean only128BitKey) throws InvalidAlgorithmParameterException, InvalidKeyException, NoSuchPaddingException, NoSuchAlgorithmException, ShortBufferException, BadPaddingException, IllegalBlockSizeException {
        if (only128BitKey) {
            keyBytes = Arrays.copyOf(keyBytes, 16);
        }
        SecretKeySpec key = new SecretKeySpec(keyBytes, "AES");
        IvParameterSpec iv = new IvParameterSpec(ivBytes);
        Cipher cipher = Cipher.getInstance("AES/CBC/PKCS5Padding");
        cipher.init(Cipher.DECRYPT_MODE, key, iv);
        byte[] decrypted = cipher.doFinal(input);
        return decrypted;
    }

    public static byte[] generate16RandomBytes() {
        // build the initialization vector (randomly).
        SecureRandom random = new SecureRandom();
        //generate random 16 byte IV AES is always 16bytes
        byte iv[] = new byte[InitializationVectorBytes];
        random.nextBytes(iv);
        return iv;
    }

    //http://stackoverflow.com/questions/11707976/cryptography-in-java
}