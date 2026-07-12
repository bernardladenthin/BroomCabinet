package de.fraunhofer.fokus.jackpot.wrapper;

import java.io.IOException;
import java.io.OutputStream;
import java.io.RandomAccessFile;
import java.util.Objects;

/**
 * Created by bernard on 13.05.14.
 */
public class RandomAccessFileToOutputStream extends OutputStream {

    final RandomAccessFile file;

    public RandomAccessFileToOutputStream(final RandomAccessFile file) {
        Objects.requireNonNull(file);
        this.file = file;
    }

    @Override
    public void close() throws IOException {
        file.close();
    }

    @Override
    public void write(final int b) throws IOException {
        file.write(b);
    }

    @Override
    public void write(final byte[] b) throws IOException {
        file.write(b);
    }

    @Override
    public void write(final byte[] b, final int off, final int len) throws IOException {
        file.write(b, off, len);
    }
}
