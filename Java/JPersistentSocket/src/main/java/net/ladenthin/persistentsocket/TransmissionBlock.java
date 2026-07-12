// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.persistentsocket;

import java.io.DataInput;
import java.io.DataOutput;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.Objects;

/**
 *
 * @author bernard
 */
public final class TransmissionBlock implements Comparable<TransmissionBlock> {

    public final long id;
    private final byte[] data;
    private final List<Long> acknowledged;

    public TransmissionBlock(final long id, final byte[] data, final List<Long> acknowledged) {
        this.id = id;
        this.data = data;
        this.acknowledged = acknowledged;
    }

    public long getId() {
        return id;
    }

    public boolean hasData() {
        return data != null;
    }

    public boolean hasAcknowledged() {
        return acknowledged != null;
    }

    public List<Long> getAcknowledged() {
        return acknowledged;
    }

    public void writeBlock(DataOutput dOut) throws IOException {
        // write the id
        dOut.writeLong(id);

        // write data
        if (hasData()) {
            // write the data length
            dOut.writeInt(data.length);
            // write the data
            dOut.write(data);
        } else {
            // no data available
            dOut.writeInt(0);
        }

        if (hasAcknowledged()) {
            // write the list size
            dOut.writeInt(acknowledged.size());
            // write each element
            for (long ack : acknowledged) {
                dOut.writeLong(ack);
            }
        } else {
            // no acknowledged available
            dOut.writeInt(0);
        }
    }

    public static TransmissionBlock readBlock(DataInput dIn) throws IOException {
        // read the id
        final long id = dIn.readLong();

        // read the data length
        final int dataLength = dIn.readInt();
        final byte[] data;

        if (dataLength != 0) {
            // read the data
            data = new byte[dataLength];
            dIn.readFully(data);
        } else {
            data = null;
        }

        // read the acknowledged size
        final int acknowledgedSize = dIn.readInt();
        final List<Long> acknowledged;

        if (acknowledgedSize != 0) {
            final ArrayList<Long> acknowledgedModifiable = new ArrayList<>(acknowledgedSize);
            // read each element
            for (int i = 0; i < acknowledgedSize; ++i) {
                acknowledgedModifiable.add(dIn.readLong());
            }
            acknowledged = Collections.unmodifiableList(acknowledgedModifiable);
        } else {
            acknowledged = null;
        }

        return new TransmissionBlock(id, data, acknowledged);
    }

    @Override
    public int compareTo(TransmissionBlock o) {
        return Long.compare(id, o.id);
    }

    @Override
    public int hashCode() {
        int hash = 3;
        hash = 47 * hash + (int) (this.id ^ (this.id >>> 32));
        return hash;
    }

    @Override
    public boolean equals(Object obj) {
        if (obj == null) {
            return false;
        }
        if (getClass() != obj.getClass()) {
            return false;
        }
        final TransmissionBlock other = (TransmissionBlock) obj;
        if (this.id != other.id) {
            return false;
        }
        if (!Arrays.equals(this.data, other.data)) {
            return false;
        }
        if (!Objects.equals(this.acknowledged, other.acknowledged)) {
            return false;
        }
        return true;
    }
    
}
