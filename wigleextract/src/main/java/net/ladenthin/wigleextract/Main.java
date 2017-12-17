package net.ladenthin.wigleextract;

import com.google.gson.Gson;

import java.io.File;
import java.sql.*;
import java.util.ArrayList;

public class Main implements Runnable {

    private File databaseFile;

    private double minLatitude;
    private double maxLatitude;
    private double minLongitude;
    private double maxLongitude;

    public static void main(String[] argv) throws Exception {
        if (argv.length != 5) {
            System.err.println("error: invalid arguments");
            System.err.println("usage: database.db minLatitude maxLatitude minLongitude maxLongitude");
            return;
        }

        Main main = new Main();
        main.setDatabaseFile(new File(argv[0]).getCanonicalFile());

        double lat1 = Double.valueOf(argv[1]);
        double lat2 = Double.valueOf(argv[2]);
        main.setMaxLatitude(Math.max(lat1, lat2));
        main.setMinLatitude(Math.min(lat1, lat2));

        double lon1 = Double.valueOf(argv[3]);
        double lon2 = Double.valueOf(argv[4]);
        main.setMaxLongitude(Math.max(lon1, lon2));
        main.setMinLongitude(Math.min(lon1, lon2));

        main.run();
    }

    private boolean isInBound(double latitude, double longitude) {
        return latitude >= minLatitude && latitude <= maxLatitude &&
        longitude >= minLongitude && longitude <= maxLongitude;
    }

    @Override
    public void run() {
        try {
            final String DB_DRIVER = "org.sqlite.JDBC";
            Class.forName(DB_DRIVER);
            final String dbConnection = "jdbc:sqlite:" + getDatabaseFile().getCanonicalPath();
            final Connection c = DriverManager.getConnection(dbConnection);


            String sql = "SELECT * from network";
            Statement statement = c.createStatement();
            ResultSet rs = statement.executeQuery(sql);

            ArrayList<Network> networks = new ArrayList<>();
            int i = 0;

            if (!rs.next() ) {
                throw new RuntimeException("no data");
            } else {
                do {
                    i++;
                    double bestlat = rs.getDouble("bestlat");
                    double bestlon = rs.getDouble("bestlon");
                    Network network = new Network();
                    if (Double.isInfinite(bestlat) || Double.isInfinite(bestlon)) {
                        double lastlat = rs.getDouble("lastlat");
                        double lastlon = rs.getDouble("lastlon");

                        if (Double.isInfinite(lastlat) || Double.isInfinite(lastlon)) {
                            continue;
                        } else {
                            network.setLatitude(lastlat);
                            network.setLongitude(lastlon);
                        }

                    } else {
                        network.setLatitude(bestlat);
                        network.setLongitude(bestlon);
                    }

                    network.setBssid(rs.getString("bssid"));

                    // filter
                    if (isInBound(network.getLatitude(), network.getLongitude())) {
                        networks.add(network);
                    }

                } while (rs.next());
            }
            statement.close();

            System.out.println("i: " + i);
            System.out.println("size: " + networks.size());
            System.out.println();
            System.out.println();

            Gson gson = new Gson();
            String json = gson.toJson(networks);
            System.out.println(json);
            /*
            for (Network network : networks) {
                System.out.println("networks.Add(new Vector2("+network.getLatitude()+"f, "+network.getLongitude()+"f));");
            }
            */

        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }

    public void setMinLatitude(double minLatitude) {
        this.minLatitude = minLatitude;
    }

    public double getMinLatitude() {
        return minLatitude;
    }

    public void setMaxLatitude(double maxLatitude) {
        this.maxLatitude = maxLatitude;
    }

    public double getMaxLatitude() {
        return maxLatitude;
    }

    public void setMinLongitude(double minLongitude) {
        this.minLongitude = minLongitude;
    }

    public double getMinLongitude() {
        return minLongitude;
    }

    public void setMaxLongitude(double maxLongitude) {
        this.maxLongitude = maxLongitude;
    }

    public double getMaxLongitude() {
        return maxLongitude;
    }

    public void setDatabaseFile(File databaseFile) {
        this.databaseFile = databaseFile;
    }

    public File getDatabaseFile() {
        return databaseFile;
    }

    public void sisi() {
    }
}
