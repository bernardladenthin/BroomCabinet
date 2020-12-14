package net.ladenthin.btcdetector;

public class ReadStatistic {

    public long successful = 0;
    public long error = 0;

    // generated
    @Override
    public String toString() {
        return "ReadStatistic{" + "successful=" + successful + ", error=" + error + '}';
    }

    // generated
    @Override
    public int hashCode() {
        int hash = 5;
        hash = 17 * hash + (int) (this.successful ^ (this.successful >>> 32));
        hash = 17 * hash + (int) (this.error ^ (this.error >>> 32));
        return hash;
    }

    // generated
    @Override
    public boolean equals(Object obj) {
        if (this == obj) {
            return true;
        }
        if (obj == null) {
            return false;
        }
        if (getClass() != obj.getClass()) {
            return false;
        }
        final ReadStatistic other = (ReadStatistic) obj;
        if (this.successful != other.successful) {
            return false;
        }
        if (this.error != other.error) {
            return false;
        }
        return true;
    }

}
