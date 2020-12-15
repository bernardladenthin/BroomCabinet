package net.ladenthin.btcdetector;

import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

public class ReadStatistic {

    public long successful = 0;
    public long unsupported = 0;
    
    public final List<String> errors = new ArrayList<>();

    // generated
    @Override
    public String toString() {
        return "ReadStatistic{" + "successful=" + successful + ", unsupported=" + unsupported + ", errors=" + errors + '}';
    }

    // generated
    @Override
    public int hashCode() {
        int hash = 5;
        hash = 89 * hash + (int) (this.successful ^ (this.successful >>> 32));
        hash = 89 * hash + (int) (this.unsupported ^ (this.unsupported >>> 32));
        hash = 89 * hash + Objects.hashCode(this.errors);
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
        if (this.unsupported != other.unsupported) {
            return false;
        }
        if (!Objects.equals(this.errors, other.errors)) {
            return false;
        }
        return true;
    }
    

    
    

}
