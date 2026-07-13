// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.util;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInput;
import java.io.DataOutput;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.EnumSet;
import java.util.List;
import java.util.Set;
import java.util.zip.GZIPInputStream;
import java.util.zip.GZIPOutputStream;

import net.jpountz.lz4.LZ4FastDecompressor;
import net.jpountz.lz4.LZ4SafeDecompressor;
import net.ladenthin.jackpot.Transceiver;
import net.ladenthin.jackpot.configuration.CLZ4Decompressor;
import net.ladenthin.jackpot.configuration.ConditionGZIP;
import net.ladenthin.jackpot.configuration.ConditionLZ4;
import net.ladenthin.jackpot.configuration.SettingsCompression;

/**
 * Box and unbox a ByteMessage. Immutable.
 *
 * @author bernard
 */
public final class BinaryMessage implements Comparable<BinaryMessage>,
    FromDataInput<BinaryMessage>, ToDataOutput {

    private enum State {

        MESSAGE, HEARTBEAT, ACKNOWLEDGED;
        @SuppressWarnings("unused")
        public Set<State> possibleNext() {
            return EnumSet.noneOf(State.class);
        }

    }

    private final State state;

    public final long id;
    private final byte[] msg;
    private final int uncompressedSize;

    private final BinaryMessageFlags flags;

    private final List<Long> acknowledged;

    /**
     * In Any case one Integer and one Long. Unit: [bytes].
     */
    @SuppressWarnings("unused")
    private final static int headerSize = (Integer.SIZE / Byte.SIZE) + (Long.SIZE / Byte.SIZE);

    private BinaryMessage(final long id, final byte[] msg, final int uncompressedSize,
        final boolean lz4Used, final boolean gzipUsed, final List<Long> acknowledged,
        final State state) {
        this.id = id;
        this.msg = msg;
        this.uncompressedSize = uncompressedSize;
        this.acknowledged = acknowledged;
        this.state = state;

        this.flags =
            new BinaryMessageFlags(lz4Used, gzipUsed, isStateHeartbeat(),
                isStateAcknowledged());
    }

    public boolean isStateHeartbeat() {
        return EnumSet.of(state).contains(State.HEARTBEAT);
    }

    public boolean isStateMessage() {
        return EnumSet.of(state).contains(State.MESSAGE);
    }

    public boolean isStateAcknowledged() {
        return EnumSet.of(state).contains(State.ACKNOWLEDGED);
    }

    public long getId() {
        return id;
    }

    /**
     * The length of the (possibly compressed) payload as it goes on the wire.
     *
     * @return the payload length in bytes
     * @throws IllegalStateException when this is not a message-state frame
     */
    public int getPayloadLength() {
        if (!isStateMessage()) {
            throw new IllegalStateException();
        }
        return msg.length;
    }

    public boolean isLz4Used() {
        if (EnumSet.of(State.MESSAGE).contains(state)) {
            return flags.isLz4Used();
        } else {
            throw new IllegalStateException();
        }
    }

    public boolean isGzipUsed() {
        if (EnumSet.of(State.MESSAGE).contains(state)) {
            return flags.isGzipUsed();
        } else {
            throw new IllegalStateException();
        }
    }

    public List<Long> getAcknowledged() {
        if (EnumSet.of(State.ACKNOWLEDGED).contains(state)) {
            return Collections.unmodifiableList(acknowledged);
        } else {
            throw new IllegalStateException();
        }
    }

    public final static BinaryMessage createHeartbeat(long id) {
        return new BinaryMessage(id, null, 0, false, false, null, State.HEARTBEAT);
    }

    public final static BinaryMessage createAcknowledged(long id,
        List<Long> acknowledged) {
        return new BinaryMessage(id, null, 0, false, false, acknowledged,
            State.ACKNOWLEDGED);
    }

    public final static BinaryMessage box(final long id, final byte[] msg,
        final SettingsCompression settingsCompression) throws IOException {

        boolean lz4Used = false;
        boolean gzipUsed = false;

        final byte[] finalBytes;
        byte[] compressedBytes = null;

        // 1.: Check to compress the byte array
        if (settingsCompression.enableLZ4) {
            for (final ConditionLZ4 condition : settingsCompression.lz4Conditions) {
                if (condition.conditionMatch(msg.length)) {
                    compressedBytes = condition.compressor.compress(msg);

                    if (condition.useOnlyIfCompressedLower) {
                        if (compressedBytes.length < msg.length) {
                            lz4Used = true;
                            break;
                        }
                    } else {
                        lz4Used = true;
                        break;
                    }
                }
            }
        } else if (settingsCompression.enableGZIP) {
            for (final ConditionGZIP condition : settingsCompression.gzipConditions) {
                if (condition.conditionMatch(msg.length)) {
                    final ByteArrayOutputStream out = new ByteArrayOutputStream();

                    final GZIPOutputStream outGZIP = new GZIPOutputStream(out) {
                        {
                            def.setLevel(condition.deflaterLevel);
                        }
                    };

                    outGZIP.write(msg);
                    outGZIP.close();
                    compressedBytes = out.toByteArray();

                    if (condition.useOnlyIfCompressedLower) {
                        if (compressedBytes.length < msg.length) {
                            gzipUsed = true;
                            break;
                        }
                    } else {
                        gzipUsed = true;
                        break;
                    }
                }
            }
        }

        // 2.: Assign the compressed byte array
        if (lz4Used || gzipUsed) {
            finalBytes = compressedBytes;
        } else {
            finalBytes = msg;
        }

        return new BinaryMessage(id, finalBytes, msg.length, lz4Used, gzipUsed, null, State.MESSAGE);
    }

    public final byte[] unbox(final SettingsCompression settingsCompression) throws IOException {
        return unbox(settingsCompression, Integer.MAX_VALUE);
    }

    /**
     * Unbox with an upper bound for the decompressed size.
     *
     * @param maxUncompressedLength decompressing beyond this many bytes aborts with an
     * {@link IOException} (defense against decompression bombs). Unit: [bytes].
     */
    public final byte[] unbox(final SettingsCompression settingsCompression,
        final int maxUncompressedLength) throws IOException {
        if (!isStateMessage()) {
            throw new IllegalStateException();
        }

        final byte[] finalBytes;

        // if compression used, uncompress
        if (flags.isLz4Used()) {
            if (CLZ4Decompressor.isFastDecompressor(settingsCompression.decompressor)) {
                final LZ4FastDecompressor decompressor =
                    CLZ4Decompressor.getFastDecompressor(settingsCompression.decompressor);

                finalBytes = decompressor.decompress(msg, uncompressedSize);
            } else if (CLZ4Decompressor.isSafeDecompressor(settingsCompression.decompressor)) {
                final LZ4SafeDecompressor decompressor =
                    CLZ4Decompressor.getSafeDecompressor(settingsCompression.decompressor);

                finalBytes = decompressor.decompress(msg, uncompressedSize);
            } else {
                throw new IllegalArgumentException("unknown CLZ4Decompressor.");
            }
        } else if (flags.isGzipUsed()) {
            final byte[] gzipBuffer = new byte[settingsCompression.gzipBufferSize];

            try (GZIPInputStream inGZIP = new GZIPInputStream(new ByteArrayInputStream(msg))) {
                ByteArrayOutputStream baos = new ByteArrayOutputStream(uncompressedSize);
                int n;
                while ((n = inGZIP.read(gzipBuffer)) >= 0) {
                    baos.write(gzipBuffer, 0, n);
                    /**
                     * The frame header's uncompressed size is only a claim — the ACTUAL
                     * inflated byte count is what grows without bound in a decompression
                     * bomb, so the loop itself must enforce the limit.
                     */
                    if (baos.size() > maxUncompressedLength) {
                        throw new IOException("decompressed payload exceeds maxUncompressedLength "
                            + maxUncompressedLength);
                    }
                }
                finalBytes = baos.toByteArray();

            }
        } else {
            finalBytes = msg;
        }

        return finalBytes;
    }

    @Override
    public void toDataOutput(DataOutput dOut) throws IOException {
        // write the flags
        flags.toDataOutput(dOut);
        dOut.writeLong(id);
        if (Transceiver.enableDebug) {
            Transceiver.debugLog("writeToDataOutput: headerFlags: " + flags);
            Transceiver.debugLog("writeToDataOutput: id: " + id);
        }

        if (isStateHeartbeat()) {
            // nothing to do
        } else if (isStateMessage()) {
            if (Transceiver.enableDebug) {
                Transceiver.debugLog("writeToDataOutput: msg.length: " + msg.length);
                Transceiver.debugLog("writeToDataOutput: msg: " + Arrays.hashCode(msg));
            }
            // write the msg
            dOut.writeInt(uncompressedSize);
            dOut.writeInt(msg.length);
            dOut.write(msg);
        } else if (isStateAcknowledged()) {
            dOut.writeInt(acknowledged.size());
            for (long l : acknowledged) {
                dOut.writeLong(l);
            }
        } else {
            throw new IllegalStateException();
        }
    }

    @Override
    public BinaryMessage fromDataInput(DataInput dIn) throws IOException {
        throw new RuntimeException("Use the Java8 method");
    }

    public static BinaryMessage fromDataInputJava8(DataInput dIn) throws IOException {
        return fromDataInputJava8(dIn, Integer.MAX_VALUE);
    }

    /**
     * Read a frame with an upper bound for wire-provided lengths.
     *
     * @param maxPayloadLength frames claiming a payload, an uncompressed size or an
     * acknowledgement batch beyond this bound are rejected with an {@link IOException}
     * BEFORE anything is allocated (defense against corrupt frames and allocation attacks).
     * Unit: [bytes].
     */
    public static BinaryMessage fromDataInputJava8(DataInput dIn, final int maxPayloadLength)
        throws IOException {
        // read the flags
        final BinaryMessageFlags bmf = BinaryMessageFlags.fromDataInputReplaceJava8(dIn);
        final long id = dIn.readLong();
        Transceiver.debugLog("readFromDataInput: bmf: " + bmf);
        Transceiver.debugLog("readFromDataInput: id: " + id);

        if (bmf.isHeartbeat()) {
            return createHeartbeat(id);
        } else if (bmf.isAcknowledged()) {
            final int size = dIn.readInt();
            /**
             * A corrupt frame must fail with an IOException so the reader takes its
             * reconnect path — a RuntimeException (here: IllegalArgumentException from a
             * negative ArrayList capacity) would kill the reader thread instead.
             */
            if (size < 0) {
                throw new IOException("corrupt frame: negative acknowledged count " + size);
            }
            /**
             * Reject BEFORE allocating: a huge wire-provided count would allocate gigabytes
             * and kill the reader (or the whole JVM) with an OutOfMemoryError. Each
             * acknowledged id occupies eight bytes on the wire, so the payload bound implies
             * a count bound.
             */
            if (size > maxPayloadLength / Long.BYTES) {
                throw new IOException("frame exceeds maxPayloadLength: acknowledged count "
                    + size + " > " + (maxPayloadLength / Long.BYTES));
            }
            List<Long> acknowledged = new ArrayList<>(size);
            for (int i = 0; i < size; ++i) {
                acknowledged.add(dIn.readLong());
            }
            return createAcknowledged(id, acknowledged);
        } else {
            Transceiver.debugLog("readFromDataInput");
            // read the msg
            Transceiver.debugLog("uncompressedSize : ");
            final int uncompressedSize = dIn.readInt();
            Transceiver.debugLog("uncompressedSize : " + uncompressedSize);
            final int msgLength = dIn.readInt();
            Transceiver.debugLog("msgLength : " + msgLength);
            /**
             * See above: corrupt sizes must surface as IOException (a negative array size
             * would otherwise raise a NegativeArraySizeException and kill the reader).
             */
            if (uncompressedSize < 0 || msgLength < 0) {
                throw new IOException("corrupt frame: negative size (uncompressedSize="
                    + uncompressedSize + ", msgLength=" + msgLength + ")");
            }
            /**
             * Reject BEFORE allocating: a huge wire-provided length would allocate gigabytes
             * and kill the reader (or the whole JVM) with an OutOfMemoryError. The
             * uncompressed size is bounded too — it is the allocation target of the LZ4
             * decompression and the claimed inflation of a GZIP payload.
             */
            if (msgLength > maxPayloadLength || uncompressedSize > maxPayloadLength) {
                throw new IOException("frame exceeds maxPayloadLength " + maxPayloadLength
                    + " (uncompressedSize=" + uncompressedSize + ", msgLength=" + msgLength + ")");
            }
            final byte[] msg = new byte[msgLength];
            dIn.readFully(msg);
            Transceiver.debugLog("din.readFully(msg); finished");

            // construct a new BoxedByteMessage
            return new BinaryMessage(id, msg, uncompressedSize, bmf.isLz4Used(), bmf.isGzipUsed(),
                null, State.MESSAGE);
        }
    }

    @Override
    public int compareTo(BinaryMessage o) {
        return Long.compare(id, o.id);
    }

    @Override
    public int hashCode() {
        final int prime = 31;
        int result = 1;
        result = prime * result + ((flags == null) ? 0 : flags.hashCode());
        result = prime * result + (int) (id ^ (id >>> 32));
        result = prime * result + Arrays.hashCode(msg);
        result = prime * result + ((acknowledged == null) ? 0 : acknowledged.hashCode());
        result = prime * result + ((state == null) ? 0 : state.hashCode());
        result = prime * result + uncompressedSize;
        return result;
    }

    @Override
    public boolean equals(Object obj) {
        if (this == obj)
            return true;
        if (obj == null)
            return false;
        if (getClass() != obj.getClass())
            return false;
        BinaryMessage other = (BinaryMessage) obj;
        if (flags == null) {
            if (other.flags != null)
                return false;
        } else if (!flags.equals(other.flags))
            return false;
        if (id != other.id)
            return false;
        if (!Arrays.equals(msg, other.msg))
            return false;
        if (acknowledged == null) {
            if (other.acknowledged != null)
                return false;
        } else if (!acknowledged.equals(other.acknowledged))
            return false;
        if (state != other.state)
            return false;
        if (uncompressedSize != other.uncompressedSize)
            return false;
        return true;
    }

    /**
     * {@inheritDoc}
     * Warning, this is a modified generated toString method. Use the hashCode for a msg instead the array.
     */
    @Override
    public String toString() {
        return "BinaryMessage [state=" + state + ", id=" + id + ", msg=" + Arrays.hashCode(msg)
            + ", uncompressedSize=" + uncompressedSize + ", flags=" + flags + ", acknowledged="
            + acknowledged + "]";
    }

}
