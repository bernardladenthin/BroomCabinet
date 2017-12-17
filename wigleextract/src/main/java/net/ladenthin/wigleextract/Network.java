package net.ladenthin.wigleextract;

public class Network {

    private double latitude;
    private double longitude;
    private String bssid;

    public Network() {
    }

    public void setLatitude(double latitude) {
        this.latitude = latitude;
    }

    public double getLatitude() {
        return latitude;
    }

    public void setLongitude(double longitude) {
        this.longitude = longitude;
    }

    public double getLongitude() {
        return longitude;
    }

    public void setBssid(String bssid) {
        this.bssid = bssid;
    }

    public String getBssid() {
        return bssid;
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;

        Network network = (Network) o;

        if (Double.compare(network.latitude, latitude) != 0) return false;
        if (Double.compare(network.longitude, longitude) != 0) return false;
        return !(bssid != null ? !bssid.equals(network.bssid) : network.bssid != null);

    }

    @Override
    public int hashCode() {
        int result;
        long temp;
        temp = Double.doubleToLongBits(latitude);
        result = (int) (temp ^ (temp >>> 32));
        temp = Double.doubleToLongBits(longitude);
        result = 31 * result + (int) (temp ^ (temp >>> 32));
        result = 31 * result + (bssid != null ? bssid.hashCode() : 0);
        return result;
    }

    @Override
    public String toString() {
        return "Network{" +
                "latitude=" + latitude +
                ", longitude=" + longitude +
                ", bssid='" + bssid + '\'' +
                '}';
    }
}