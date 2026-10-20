// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap.dump;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.EOFException;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;

import org.junit.jupiter.api.Test;

/**
 * The value framing of format version 2. Format 1 stored values with {@code writeUTF}, which
 * cannot hold more than 65535 bytes, and {@code NULL} as a magic string a real value could
 * collide with.
 */
public class DumpFormatTest {

    @Test
    public void roundTrip_nullEmptyAndValues() throws IOException {
        byte[][] values = {null, new byte[0], {1, 2, 3}, null, "äöü".getBytes(StandardCharsets.UTF_8)};

        DataInputStream in = new DataInputStream(new ByteArrayInputStream(write(values)));

        for (byte[] value : values) {
            byte[] read = DumpFormat.readValue(in);
            if (value == null) {
                assertNull(read);
            } else {
                assertArrayEquals(value, read);
            }
        }
        assertThrows(EOFException.class, () -> DumpFormat.readValue(in));
    }

    @Test
    public void roundTrip_valueLongerThan64KiB() throws IOException {
        byte[] large = new byte[200_000];
        Arrays.fill(large, (byte) 'x');

        DataInputStream in = new DataInputStream(new ByteArrayInputStream(write(new byte[][] {large})));

        assertArrayEquals(large, DumpFormat.readValue(in));
    }

    @Test
    public void theFormerNullPlaceholderIsAnOrdinaryValue() throws IOException {
        byte[] placeholder = "{!%N".getBytes(StandardCharsets.UTF_8);

        DataInputStream in = new DataInputStream(new ByteArrayInputStream(write(new byte[][] {placeholder, null})));

        assertArrayEquals(placeholder, DumpFormat.readValue(in));
        assertNull(DumpFormat.readValue(in));
    }

    @Test
    public void unknownTagIsCorrupt() {
        DataInputStream in = new DataInputStream(new ByteArrayInputStream(new byte[] {7}));

        IOException e = assertThrows(IOException.class, () -> DumpFormat.readValue(in));
        assertTrue(e.getMessage().contains("tag 7"), e.getMessage());
    }

    @Test
    public void negativeLengthIsCorrupt() {
        DataInputStream in = new DataInputStream(new ByteArrayInputStream(new byte[] {1, (byte) 0xFF, 0, 0, 0}));

        assertThrows(IOException.class, () -> DumpFormat.readValue(in));
    }

    @Test
    public void truncatedValueFails() {
        DataInputStream in = new DataInputStream(new ByteArrayInputStream(new byte[] {1, 0, 0, 0, 5, 'a', 'b'}));

        assertThrows(EOFException.class, () -> DumpFormat.readValue(in));
    }

    @Test
    public void partFileName() {
        assertEquals("0003-order_items.part0011.gz", DumpFormat.partFileName(3, "order_items", 11));
        assertEquals("0000-a_b_c_.part0000.gz", DumpFormat.partFileName(0, "a/b\\c.", 0));
        assertEquals("0001-___.part0002.gz", DumpFormat.partFileName(1, "..\u00e4", 2));
    }

    @Test
    public void partFileName_alwaysMatchesWhatTheManifestAccepts() {
        for (String table : new String[] {"orders", "../../etc/passwd", "C:\\x", "with space", "Ünïcode", ""}) {
            String name = DumpFormat.partFileName(12, table, 345);
            assertTrue(DumpFormat.PART_FILE_NAME.matcher(name).matches(), name);
        }
    }

    private static byte[] write(byte[][] values) throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (DataOutputStream out = new DataOutputStream(bytes)) {
            for (byte[] value : values) {
                DumpFormat.writeValue(out, value);
            }
        }
        return bytes.toByteArray();
    }
}
