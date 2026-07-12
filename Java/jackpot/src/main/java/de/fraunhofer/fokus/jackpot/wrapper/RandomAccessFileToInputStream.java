package de.fraunhofer.fokus.jackpot.wrapper;

import java.io.IOException;
import java.io.InputStream;
import java.io.RandomAccessFile;
import java.util.Objects;

/**
 * Created by bernard on 13.05.14.
 */
public class RandomAccessFileToInputStream extends InputStream {

    final RandomAccessFile file;

    public RandomAccessFileToInputStream(final RandomAccessFile file) {
        Objects.requireNonNull(file);
        this.file = file;
    }

    @Override
    public int available() throws IOException {
        return -1;
    }

    @Override
    public void close() throws IOException {
        file.close();
    }

    @Override
    public int read() throws IOException {
        return file.read();
    }

    @Override
    public int read(final byte[] b) throws IOException {
        return file.read(b);
    }

    @Override
    public int read(final byte[] b, final int off, final int len) throws IOException {
        return file.read(b, off, len);
    }
}
