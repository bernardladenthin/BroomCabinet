package net.ladenthin.imageresize;

import java.awt.*;
import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

public class ResizeToDirectory {
    private final static String EXTENSION = ".jpg";

    private final Common common = new Common();

    private final Path path;
    private final Dimension dimension;
    private final float compressionQuality;
    public final String directoryName;
    private final String prefix;
    private final String suffix;

    public ResizeToDirectory(Path path, Dimension dimension, float compressionQuality, String directoryName, String prefix, String suffix) {
        this.path = path;
        this.dimension = dimension;
        this.compressionQuality = compressionQuality;
        this.directoryName = directoryName;
        this.prefix = prefix;
        this.suffix = suffix;
    }

    public void resize() throws IOException {
        File directory = new File(path.getParent().toFile(), directoryName);
        directory.mkdirs();

        Path file = Paths.get(directory.getAbsolutePath(), getNewFileName());
        Files.copy(path, file);

        common.resize(file.toFile(), dimension, compressionQuality);
    }

    public String getNewFileName() {
        String fileName = path.getFileName().toString();
        String newFileName = "";
        if (prefix != null) {
            newFileName += prefix;
        }
        newFileName += common.getNameWithoutExtension(fileName);
        if (suffix != null) {
            newFileName += suffix;
        }
        newFileName += EXTENSION;
        return newFileName;
    }
}
