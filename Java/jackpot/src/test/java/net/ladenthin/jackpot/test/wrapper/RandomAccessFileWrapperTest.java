// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.wrapper;

import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.is;
import static org.junit.jupiter.api.Assertions.assertArrayEquals;

import java.io.File;
import java.io.IOException;
import java.io.RandomAccessFile;
import java.nio.file.Path;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import net.ladenthin.jackpot.wrapper.RandomAccessFileToInputStream;
import net.ladenthin.jackpot.wrapper.RandomAccessFileToOutputStream;

/**
 * The {@link RandomAccessFileToInputStream}/{@link RandomAccessFileToOutputStream} wrappers
 * adapt a {@link RandomAccessFile} (the Windows named pipe handle) to the stream interfaces
 * the {@link net.ladenthin.jackpot.ConnectionLayer} consumes. Verified against a regular
 * file, which shares the RandomAccessFile read/write semantics.
 */
public class RandomAccessFileWrapperTest {

    @TempDir
    Path tempDir;

    // <editor-fold defaultstate="collapsed" desc="write and read round trip">
    @Test
    public void read_bytesWrittenThroughOutputStreamWrapper_sameBytesReadThroughInputStreamWrapper() throws IOException {
        // arrange
        final File file = tempDir.resolve("wrapper-round-trip").toFile();
        final byte[] payload = RandomAccessFileWrapperTest.class.getCanonicalName().getBytes();

        // act: write through the OutputStream wrapper
        try (RandomAccessFile writeFile = new RandomAccessFile(file, "rw");
             RandomAccessFileToOutputStream out = new RandomAccessFileToOutputStream(writeFile)) {
            out.write(payload);
            out.write('!');
            out.flush();
        }

        // act: read back through the InputStream wrapper
        final byte[] readBack = new byte[payload.length];
        final int single;
        try (RandomAccessFile readFile = new RandomAccessFile(file, "r");
             RandomAccessFileToInputStream in = new RandomAccessFileToInputStream(readFile)) {
            int offset = 0;
            while (offset < readBack.length) {
                final int read = in.read(readBack, offset, readBack.length - offset);
                if (read < 0) {
                    break;
                }
                offset += read;
            }
            single = in.read();

            // assert
            assertArrayEquals(payload, readBack);
            assertThat(single, is(equalTo((int) '!')));
            assertThat("End of file must be signalled with -1", in.read(), is(equalTo(-1)));
        }
    }
    // </editor-fold>
}
