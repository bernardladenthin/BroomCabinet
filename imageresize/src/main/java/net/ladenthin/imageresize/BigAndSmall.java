package net.ladenthin.imageresize;

import java.awt.*;
import java.io.File;
import java.io.IOException;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;

public class BigAndSmall implements Runnable {

    private final Common common = new Common();

    String url = "https://ladenthin.net/ebay/";

    File workingDirectory = new File(".");

    public static void main(String[] argv) {
        BigAndSmall bigAndSmall = new BigAndSmall();
        bigAndSmall.run();
    }

    @Override
    public void run() {
        common.forEachJpegFile(workingDirectory.toPath(), this::resizeFile);
    }

    public void resizeFile(Path path) {
        try {
            ResizeToDirectory small = new ResizeToDirectory(path, new Dimension(280, 280), 0.90f, "small", "", "_s");
            ResizeToDirectory big = new ResizeToDirectory(path, new Dimension(1600, 1600), 0.95f, "big", "", "");
            Set<String> directoriesToIgnore = new HashSet<>(Arrays.asList(small.directoryName, big.directoryName));

            String parentDirectory = path.getParent().getFileName().toString();
            if (directoriesToIgnore.contains(parentDirectory)) {
                return;
            }

            small.resize();
            big.resize();

            System.out.println("<a href=\""+url+big.getNewFileName()+"\" target=\"_blank\" ><img alt=\"\" src=\""+url+small.getNewFileName()+"\" /></a>");
        } catch (IOException e) {
            throw new RuntimeException(e);
        }
    }
}
