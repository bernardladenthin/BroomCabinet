package de.fraunhofer.fokus.jackpot.util;

import java.io.DataInput;
import java.io.DataOutput;
import java.io.IOException;
import java.io.Serializable;

public class BinaryMessageFlags implements FromDataInput<BinaryMessageFlags>, ToDataOutput,
    Serializable {
    private static final long serialVersionUID = -2578154650878929352L;

    private static final byte BIT_LZ4USED = 1;
    private static final byte BIT_GZIPUSED = 2;
    private static final byte BIT_HEARTBEAT = 4;
    private static final byte BIT_ACKNOWLEDGED = 8;

    private final boolean lz4Used;
    private final boolean gzipUsed;
    private final boolean heartbeat;
    private final boolean acknowledged;

    private final static BinaryMessageFlags fromInt(int flags) {
        return new BinaryMessageFlags((flags & BIT_LZ4USED) == BIT_LZ4USED,
            (flags & BIT_GZIPUSED) == BIT_GZIPUSED, (flags & BIT_HEARTBEAT) == BIT_HEARTBEAT,
            (flags & BIT_ACKNOWLEDGED) == BIT_ACKNOWLEDGED);
    }

    private final int toInt() {
        int flags = 0;

        if (lz4Used) {
            flags = (flags | BIT_LZ4USED);
        }

        if (gzipUsed) {
            flags = (flags | BIT_GZIPUSED);
        }

        if (heartbeat) {
            flags = (flags | BIT_HEARTBEAT);
        }

        if (acknowledged) {
            flags = (flags | BIT_ACKNOWLEDGED);
        }
        return flags;
    }

    /**
     * @param lz4Used
     * @param gzipUsed
     * @param heartbeat
     * @param acknowledged
     */
    public BinaryMessageFlags(final boolean lz4Used, final boolean gzipUsed,
        final boolean heartbeat, final boolean acknowledged) {
        /*
         * allow only one compression
         * logical NAND:
         * p=lz4Used
         * | q=gzipUsed
         * | |   y=result of the combination
         * | |   |
         * p q   y
         * ====|==
         * 0 0 | 1
         * 0 1 | 1
         * 1 0 | 1
         * 1 1 | 0
         */
        assert (!(lz4Used && gzipUsed)) : "illegal flag combination: lz4Used and gzipUsed booth true";

        /*
         * heartbeat is exclusive
         * logical NAND:
         * p=heartbeat
         * | q=compression used (lz4Used || gzipUsed)
         * | |   y=result of the combination
         * | |   |
         * p q   y
         * ====|==
         * 0 0 | 1
         * 0 1 | 1
         * 1 0 | 1
         * 1 1 | 0
         */
        assert (!(heartbeat && (lz4Used || gzipUsed))) : "illegal flag combination: heartbeat used and compression set";

        // signalMessagesReceived is also exclusive
        assert (!(acknowledged && (heartbeat || lz4Used || gzipUsed))) : "illegal flag combination: heartbeat used and compression set";

        this.lz4Used = lz4Used;
        this.gzipUsed = gzipUsed;
        this.heartbeat = heartbeat;
        this.acknowledged = acknowledged;
    }

    public final boolean isLz4Used() {
        return lz4Used;
    }

    public final boolean isGzipUsed() {
        return gzipUsed;
    }

    public final boolean isHeartbeat() {
        return heartbeat;
    }

    public final boolean isAcknowledged() {
        return acknowledged;
    }

    @Override
    public void toDataOutput(DataOutput dOut) throws IOException {
        dOut.writeInt(toInt());
    }

    @Override
    public BinaryMessageFlags fromDataInput(DataInput dIn) throws IOException {
        throw new RuntimeException("Use the java 8 function");
    }

    public static BinaryMessageFlags fromDataInputReplaceJava8(DataInput dIn) throws IOException {
        return BinaryMessageFlags.fromInt(dIn.readInt());
    }

    @Override
    public int hashCode() {
        final int prime = 31;
        int result = 1;
        result = prime * result + (gzipUsed ? 1231 : 1237);
        result = prime * result + (heartbeat ? 1231 : 1237);
        result = prime * result + (lz4Used ? 1231 : 1237);
        result = prime * result + (acknowledged ? 1231 : 1237);
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
        BinaryMessageFlags other = (BinaryMessageFlags) obj;
        if (gzipUsed != other.gzipUsed)
            return false;
        if (heartbeat != other.heartbeat)
            return false;
        if (lz4Used != other.lz4Used)
            return false;
        if (acknowledged != other.acknowledged)
            return false;
        return true;
    }

    @Override
    public String toString() {
        return "BinaryMessageFlags [lz4Used=" + lz4Used + ", gzipUsed=" + gzipUsed + ", heartbeat="
            + heartbeat + ", acknowledged=" + acknowledged + "]";
    }

}
