package net.ladenthin.jfileinventory;

import java.sql.*;

public class InventoryPersistenceImplSQLite implements InventoryPersistence {

    Connection c;
    private static final String DB_DRIVER = "org.sqlite.JDBC";
    private final String dbConnection;

    public InventoryPersistenceImplSQLite(String database) {
        dbConnection = "jdbc:sqlite:" + database;
    }

    @Override
    public void initConnection() throws ClassNotFoundException, SQLException {
        Class.forName(DB_DRIVER);
        c = DriverManager.getConnection(dbConnection);
    }

    @Override
    public void initPersistence() throws SQLException {
        createTableIfNotExistsFiles();
    }

    private void createTableIfNotExistsFiles() throws SQLException {
        String sql = "CREATE TABLE if not exists `files` (" +
                "`id` INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE, " +
                "`path` TEXT NOT NULL UNIQUE, " +
                "`lastModified` INTEGER NOT NULL, " +
                "`length` INTEGER NOT NULL, " +
                "`sha256` TEXT NOT NULL, " +
                "`lastSeen` INTEGER NOT NULL " +
                ");";
        Statement statement = c.createStatement();
        statement.executeUpdate(sql);
        statement.close();
    }

    @Override
    public void insertFile(FileDescription fd) throws SQLException {
        String sql = "INSERT INTO 'files'"
                + "('path', 'lastModified', 'length', 'sha256', 'lastSeen') VALUES (?,?,?,?,?)";
        PreparedStatement statement = c.prepareStatement(sql);
        statement.setString(1, fd.path);
        statement.setLong(2, fd.lastModified);
        statement.setLong(3, fd.length);
        statement.setString(4, fd.sha256);
        statement.setLong(5, fd.lastSeen);
        statement.executeUpdate();
        statement.close();
    }

    @Override
    public void updateLastSeenByPath(long timestamp, String path) throws SQLException {
        String sql = "UPDATE 'files' SET lastSeen = ? WHERE path = ?";
        PreparedStatement statement = c.prepareStatement(sql);
        statement.setLong(1, timestamp);
        statement.setString(2, path);
        statement.executeUpdate();
        statement.close();
    }

    @Override
    public FileDescription getFileByPath(String path) throws SQLException {
        String sql = "SELECT id, path, lastModified, length, sha256, lastSeen from files WHERE path = ?";
        PreparedStatement statement = c.prepareStatement(sql);
        statement.setString(1, path);
        ResultSet rs = statement.executeQuery();

        if (!rs.next()) {
            statement.close();
            return null;
        }

        FileDescription fd = new FileDescription();
        fd.id = rs.getLong("id");
        fd.path = rs.getString("path");
        fd.lastModified = rs.getLong("lastModified");
        fd.length = rs.getLong("length");
        fd.sha256 = rs.getString("sha256");
        fd.lastSeen = rs.getLong("lastSeen");

        statement.close();
        return fd;
    }
}
