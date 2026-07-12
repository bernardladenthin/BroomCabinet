// SPDX-FileCopyrightText: 2014 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.persistentsocket;

import static org.junit.Assert.assertEquals;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.util.Arrays;
import org.junit.Test;

public class TransmissionBlockTest {

    /**
     * Serialises a block with {@link TransmissionBlock#writeBlock} and reads it
     * back with {@link TransmissionBlock#readBlock}, returning the reconstructed
     * block.
     */
    private static TransmissionBlock roundTrip(final TransmissionBlock block) throws IOException {
        final ByteArrayOutputStream baos = new ByteArrayOutputStream();
        try (DataOutputStream out = new DataOutputStream(baos)) {
            block.writeBlock(out);
        }

        try (DataInputStream in = new DataInputStream(new ByteArrayInputStream(baos.toByteArray()))) {
            return TransmissionBlock.readBlock(in);
        }
    }

    @Test
    public void writeBlock_thenReadBlock_reconstructsAnEqualBlockWithDataAndAcknowledgements()
            throws IOException {
        final TransmissionBlock original =
                new TransmissionBlock(42L, new byte[] {1, 2, 3, 4}, Arrays.asList(7L, 8L, 9L));

        final TransmissionBlock restored = roundTrip(original);

        assertEquals(original, restored);
        assertEquals(42L, restored.getId());
        assertEquals(Arrays.asList(7L, 8L, 9L), restored.getAcknowledged());
    }

    @Test
    public void writeBlock_thenReadBlock_reconstructsAnEqualBlockWithDataOnly() throws IOException {
        final TransmissionBlock original =
                new TransmissionBlock(1L, new byte[] {10, 20, 30}, null);

        final TransmissionBlock restored = roundTrip(original);

        assertEquals(original, restored);
        assertEquals(true, restored.hasData());
        assertEquals(false, restored.hasAcknowledged());
    }

    @Test
    public void writeBlock_thenReadBlock_reconstructsAnEqualBlockWithAcknowledgementsOnly()
            throws IOException {
        final TransmissionBlock original =
                new TransmissionBlock(99L, null, Arrays.asList(1L, 2L));

        final TransmissionBlock restored = roundTrip(original);

        assertEquals(original, restored);
        assertEquals(false, restored.hasData());
        assertEquals(true, restored.hasAcknowledged());
    }

    @Test
    public void writeBlock_thenReadBlock_reconstructsAnEqualEmptyBlock() throws IOException {
        final TransmissionBlock original = new TransmissionBlock(0L, null, null);

        final TransmissionBlock restored = roundTrip(original);

        assertEquals(original, restored);
        assertEquals(0L, restored.getId());
        assertEquals(false, restored.hasData());
        assertEquals(false, restored.hasAcknowledged());
    }
}
