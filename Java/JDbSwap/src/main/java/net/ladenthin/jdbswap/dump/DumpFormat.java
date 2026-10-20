// SPDX-FileCopyrightText: 2016 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap.dump;

import java.io.DataInput;
import java.io.DataOutput;
import java.io.IOException;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.regex.Pattern;

/**
 * The layout of a dump directory, format version {@value #VERSION}.
 *
 * <ul>
 *   <li>{@value #MANIFEST}: tables, columns, parts, row counts and SHA-256 per part, as JSON
 *       ({@link Manifest}).</li>
 *   <li>one gzip file per part, named by {@link #partFileName(int, String, int)}. Uncompressed
 *       it is every value of every row in column order, each as a tag byte ({@code 0} =
 *       {@code NULL}, {@code 1} = value) followed for a value by its length as {@code int} and
 *       its bytes. The SHA-256 covers exactly these uncompressed bytes.</li>
 * </ul>
 */
public final class DumpFormat {

    public static final int VERSION = 2;
    public static final String MANIFEST = "dbswap.json";
    public static final String DIGEST = "SHA-256";

    /** What {@link #partFileName} produces; anything else in a manifest is rejected. */
    static final Pattern PART_FILE_NAME = Pattern.compile("[0-9]{4}-[A-Za-z0-9_-]*\\.part[0-9]{4}\\.gz");

    private static final int TAG_NULL = 0;
    private static final int TAG_VALUE = 1;
    private static final Pattern UNSAFE = Pattern.compile("[^A-Za-z0-9_-]");

    private DumpFormat() {
    }

    /** {@code 0003-order_items.part0011.gz}: unique by index, readable by name. */
    public static String partFileName(int tableIndex, String table, int part) {
        return String.format("%04d-%s.part%04d.gz", tableIndex, UNSAFE.matcher(table).replaceAll("_"), part);
    }

    /** Writes one value; {@code null} stands for SQL {@code NULL}. */
    public static void writeValue(DataOutput out, byte[] value) throws IOException {
        if (value == null) {
            out.writeByte(TAG_NULL);
        } else {
            out.writeByte(TAG_VALUE);
            out.writeInt(value.length);
            out.write(value);
        }
    }

    /** Reads one value written by {@link #writeValue}. */
    public static byte[] readValue(DataInput in) throws IOException {
        int tag = in.readUnsignedByte();
        if (tag == TAG_NULL) {
            return null;
        }
        if (tag != TAG_VALUE) {
            throw new IOException("Corrupt part file: unknown value tag " + tag);
        }
        int length = in.readInt();
        if (length < 0) {
            throw new IOException("Corrupt part file: negative value length " + length);
        }
        byte[] value = new byte[length];
        in.readFully(value);
        return value;
    }

    static MessageDigest newDigest() {
        try {
            return MessageDigest.getInstance(DIGEST);
        } catch (NoSuchAlgorithmException e) {
            // every Java platform has to provide SHA-256
            throw new IllegalStateException(e);
        }
    }
}
