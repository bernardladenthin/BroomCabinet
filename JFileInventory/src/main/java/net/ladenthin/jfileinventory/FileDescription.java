package net.ladenthin.jfileinventory;

import java.util.Objects;

public class FileDescription  {
    public long id;
    public String path;
    public long lastModified;
    public long length;
    public String sha256;
    public long lastSeen;

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        FileDescription that = (FileDescription) o;
        return id == that.id &&
                lastModified == that.lastModified &&
                length == that.length &&
                lastSeen == that.lastSeen &&
                Objects.equals(path, that.path) &&
                Objects.equals(sha256, that.sha256);
    }

    @Override
    public int hashCode() {
        return Objects.hash(id, path, lastModified, length, sha256, lastSeen);
    }

    @Override
    public String toString() {
        return "FileDescription{" +
                "id=" + id +
                ", path='" + path + '\'' +
                ", lastModified=" + lastModified +
                ", length=" + length +
                ", sha256='" + sha256 + '\'' +
                ", lastSeen=" + lastSeen +
                '}';
    }
}
