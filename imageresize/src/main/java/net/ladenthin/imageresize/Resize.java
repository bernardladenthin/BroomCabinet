package net.ladenthin.imageresize;

import java.awt.*;
import java.io.File;
import java.io.IOException;
import java.nio.file.Path;

public class Resize implements Runnable {

    private Common common = new Common();
    float compressionQuality = 0.80f;
    Dimension dimension = new Dimension(600, 600);
    File workingDirectory = new File(".");

    public static void main(String[] argv) {
        Resize resize = new Resize();
        resize.run();
    }

    @Override
    public void run() {
        common.forEachJpegFile(workingDirectory.toPath(), this::resizeFile);
    }

    public void resizeFile(Path p) {
        System.out.println(p);
        try {
            common.resize(p.toFile(), dimension, compressionQuality);
        } catch (IOException e) {
            throw new RuntimeException(e);
        }
    }
}
