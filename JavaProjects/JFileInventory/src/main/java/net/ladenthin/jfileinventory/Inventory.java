package net.ladenthin.jfileinventory;

import java.io.*;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.sql.SQLException;

public class Inventory {

    private final File database;
    private final File source;
    private final Command command;
    private File pathPrefix = null;
    private String pathPrefixAsStringWithSeparator = null;

    private PrintStream out = System.out;
    private PrintStream err = System.err;

    private InventoryPersistence inventoryPersistence;

    public Inventory(Command command, File database, File source, File pathPrefix) {
        this.command = command;
        this.database = database;
        this.source = source;
        this.pathPrefix = pathPrefix;
    }

    public PrintStream getOut() {
        return out;
    }

    public void setOut(PrintStream out) {
        this.out = out;
    }

    public PrintStream getErr() {
        return err;
    }

    public void setErr(PrintStream err) {
        this.err = err;
    }

    public void run() {
        try {
            sanitisePathPrefix();
            inventoryPersistence = new InventoryPersistenceImplSQLite(database.getAbsolutePath());
            inventoryPersistence.initConnection();
            inventoryPersistence.initPersistence();
            switch (command) {
                case AddMissing:
                    addMissing();
                    break;
                case TestExisting:
                    testExisting();
                    break;
            }
        } catch (IOException | ClassNotFoundException | SQLException e) {
            throw new RuntimeException(e);
        }
    }

    private FileDescription getFileDescription(File file) {
        FileDescription fd = new FileDescription();
        fd.lastModified = file.lastModified();
        fd.length = file.length();
        try {
            fd.path = removePathPrefix(file.getCanonicalPath());
            fd.sha256 = fileToChecksum(file);
        } catch (IOException | NoSuchAlgorithmException e) {
            return null;
        }
        fd.lastSeen = System.currentTimeMillis();
        return fd;
    }

    // http://stackoverflow.com/questions/32032851/how-to-calculate-hash-value-of-a-file-in-java
    private String fileToChecksum(File file) throws IOException, NoSuchAlgorithmException {
        byte[] buffer = new byte[1024 * 1024];//1MB
        int count;
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        try (BufferedInputStream bis = new BufferedInputStream(new FileInputStream(file))) {
            while ((count = bis.read(buffer)) > 0) {
                digest.update(buffer, 0, count);
            }
        }
        byte[] hash = digest.digest();
        return hashToString(hash);
    }

    private String hashToString(byte[] hash) {
        StringBuffer hexString = new StringBuffer();

        for (int i = 0; i < hash.length; i++) {
            String hex = Integer.toHexString(0xff & hash[i]);
            if (hex.length() == 1) hexString.append('0');
            hexString.append(hex);
        }

        return hexString.toString();
    }

    private void testExisting() throws IOException {
        TestSummary ts = new TestSummary();
        String path = source.getAbsolutePath();
        Files.find(Paths.get(path),
                Integer.MAX_VALUE,
                (filePath, fileAttr) -> fileAttr.isRegularFile())
                .map(Path::toFile)
                .forEach(element -> testExisting(element, ts));
        ts.printSummary(getOut());
    }

    private void addMissing() throws IOException {
        // https://github.com/brettryan/io-recurse-tests
        AddSummary addSummary = new AddSummary();
        String path = source.getAbsolutePath();
        Files.find(Paths.get(path),
                Integer.MAX_VALUE,
                (filePath, fileAttr) -> fileAttr.isRegularFile())
                .map(Path::toFile)
                .forEach(element -> insertFileIfNotExists(element, addSummary));
        addSummary.printSummary(getOut());
    }

    private void insertFileIfNotExists(File element, AddSummary addsummary) {
        try {
            String path = removePathPrefix(element.getCanonicalPath());
            FileDescription fileByPath = inventoryPersistence.getFileByPath(path);
            if (fileByPath == null) {
                FileDescription fd = getFileDescription(element);
                if (fd == null) {
                    addsummary.couldNotAccess++;
                    getErr().println("??:  Could not access: " + path);
                    return;
                }
                inventoryPersistence.insertFile(fd);
                addsummary.add++;
                getOut().println("OK: Add: " + fd);
            } else {
                // file already exists in database
                inventoryPersistence.updateLastSeenByPath(System.currentTimeMillis(), fileByPath.path);
                addsummary.updateLastSeen++;
                getOut().println("OK: Update lastSeen: Already exists: " + fileByPath.path);
            }
        } catch (IOException | SQLException e) {
            throw new RuntimeException(e);
        }
    }

    private void testExisting(File element, TestSummary testSummary) {
        try {
            String path = removePathPrefix(element.getCanonicalPath());
            FileDescription fileByPath = inventoryPersistence.getFileByPath(path);
            if (fileByPath != null) {
                FileDescription fd = getFileDescription(element);
                boolean sameChecksum = fileByPath.sha256.equals(fd.sha256);
                if (fileByPath.lastModified == fd.lastModified) {
                    // same modification date
                    if (!sameChecksum) {
                        // not same checksum
                        testSummary.notModifiedAndDifferentChecksum++;
                        getErr().println("NOK: Not modified and different checksum: " + fd.path + " inventory:SHA256: " + fileByPath.sha256 + " filesystem:SHA256: " + fd.sha256);
                    } else {
                        testSummary.notModifiedAndSameChecksum++;
                        getOut().println("OK:  Not modified and same checksum: " + fd.path);
                    }
                } else {
                    if (sameChecksum) {
                        testSummary.modifiedAndSameChecksum++;
                        getOut().println("OK:  Modified and same checksum: " + fd.path);
                    } else {
                        if (fileByPath.length == fd.length) {
                            testSummary.modifiedSameLengthAndDifferenChecksum++;
                            getOut().println("??:  Modified, same length and different checksum: " + fd.path);
                        } else {
                            testSummary.modifiedDifferentLengthAndDifferenChecksum++;
                            getOut().println("??:  Modified, different length and different checksum: " + fd.path);
                        }
                    }
                }
            } else {
                testSummary.notExistsInInventory++;
                getOut().println("??:  Not exists in inventory: " + path);
            }
        } catch (IOException | SQLException e) {
            throw new RuntimeException(e);
        }
    }

    private void sanitisePathPrefix() throws IOException {
        if (pathPrefix != null) {
            pathPrefix = pathPrefix.getCanonicalFile();
            if (!pathPrefix.isDirectory()) {
                throw new RuntimeException("PathPrefix is not a directory: " + pathPrefix);
            }
            pathPrefixAsStringWithSeparator = pathPrefix.getCanonicalPath();
            if (!pathPrefixAsStringWithSeparator.endsWith(File.separator)) {
                pathPrefixAsStringWithSeparator += File.separator;
            }
        }
    }

    private String removePathPrefix(String path) {
        if (path == null) {
            return null;
        }
        if (pathPrefixAsStringWithSeparator != null) {
            return path.startsWith(pathPrefixAsStringWithSeparator) ? path.substring(pathPrefixAsStringWithSeparator.length()) : path;
        }
        return path;
    }
}
