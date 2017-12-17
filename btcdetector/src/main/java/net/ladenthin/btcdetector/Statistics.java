package net.ladenthin.btcdetector;

import org.bitcoinj.core.Sha256Hash;

import java.util.Date;
import java.util.Objects;

public class Statistics {
    private final Sha256Hash currentTransactionHash;
    private final Date currentBlockTime;

    public Statistics(Sha256Hash currentTransactionHash, Date currentBlockTime) {
        this.currentTransactionHash = currentTransactionHash;
        this.currentBlockTime = currentBlockTime;
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        Statistics that = (Statistics) o;
        return Objects.equals(currentTransactionHash, that.currentTransactionHash) &&
                Objects.equals(currentBlockTime, that.currentBlockTime);
    }

    @Override
    public int hashCode() {
        return Objects.hash(currentTransactionHash, currentBlockTime);
    }

    @Override
    public String toString() {
        return "Statistics{" +
                "currentTransactionHash='" + currentTransactionHash + '\'' +
                ", currentBlockTime=" + currentBlockTime +
                '}';
    }
}
