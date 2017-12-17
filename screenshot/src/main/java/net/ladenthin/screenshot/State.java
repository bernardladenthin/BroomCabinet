package net.ladenthin.screenshot;

import java.util.Arrays;

public class State implements Comparable<State> {
    private long timestamp;
    private Chunk[][] chunks;

    public long getTimestamp() {
        return timestamp;
    }

    public void setTimestamp(long timestamp) {
        this.timestamp = timestamp;
    }

    public Chunk[][] getChunks() {
        return chunks;
    }

    public void setChunks(Chunk[][] chunks) {
        this.chunks = chunks;
    }

    @Override
    public String toString() {
        return "State{" +
                "timestamp=" + timestamp +
                ", chunks=" + Arrays.deepToString(chunks) +
                '}';
    }

    @Override
    public int compareTo(State o) {
        if (o == null) {
            return 0;
        }
        return Long.compare(this.getTimestamp(), o.getTimestamp());
    }
}