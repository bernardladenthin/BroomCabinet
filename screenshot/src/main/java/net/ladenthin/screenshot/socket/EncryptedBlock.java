package net.ladenthin.screenshot.socket;

import net.ladenthin.screenshot.Security;

import javax.crypto.BadPaddingException;
import javax.crypto.IllegalBlockSizeException;
import javax.crypto.NoSuchPaddingException;
import javax.crypto.ShortBufferException;
import java.io.DataInput;
import java.io.DataOutput;
import java.io.IOException;
import java.security.InvalidAlgorithmParameterException;
import java.security.InvalidKeyException;
import java.security.NoSuchAlgorithmException;

public class EncryptedBlock {

    private byte[] iv;
    private byte[] ciphertext;

    public void read(DataInput dataInput) throws IOException {
        readInitializationVector(dataInput);
        readCiphertext(dataInput);
    }

    public void write(DataOutput dataOutput) throws IOException {
        dataOutput.write(iv);
        dataOutput.writeInt(ciphertext.length);
        dataOutput.write(ciphertext);
    }

    private byte[] readByteArrayComplete(DataInput dataInput, int length) throws IOException {
        byte[] array = new byte[length];
        dataInput.readFully(array);
        return array;
    }

    private void readCiphertext(DataInput dataInput) throws IOException {
        int ciphertextLength = readArrayLength(dataInput);
        ciphertext = readByteArrayComplete(dataInput, ciphertextLength);
    }

    private int readArrayLength(DataInput dataInput) throws IOException {
        int arrayLength = dataInput.readInt();
        if (arrayLength > Common.MAXIMUM_ARRAY_LENGTH) {
            throw new IOException("The payloadLength exceeds the limit.");
        }
        return arrayLength;
    }

    private void readInitializationVector(DataInput dataInput) throws IOException {
        iv = readByteArrayComplete(dataInput, Security.InitializationVectorBytes);
    }

    public byte[] decrypt(byte[] key) throws NoSuchPaddingException, BadPaddingException, InvalidKeyException, NoSuchAlgorithmException, IllegalBlockSizeException, ShortBufferException, InvalidAlgorithmParameterException {
        return Security.decrypt(ciphertext, key, iv, Common.use128BitKey);
    }

    public void encrypt(byte[] plaintext, byte[] hashedKey) throws NoSuchPaddingException, BadPaddingException, InvalidKeyException, NoSuchAlgorithmException, IllegalBlockSizeException, ShortBufferException, InvalidAlgorithmParameterException {
        iv = Security.generate16RandomBytes();
        ciphertext = Security.encrypt(plaintext, hashedKey, iv, Common.use128BitKey);
    }
}