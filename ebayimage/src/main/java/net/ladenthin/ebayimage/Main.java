package net.ladenthin.ebayimage;

import javax.imageio.ImageIO;
import javax.swing.*;
import java.awt.*;
import java.awt.image.BufferedImage;
import java.io.File;
import java.io.FilenameFilter;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

public class Main implements Runnable {

    public static void main(String[] argv) {
        Main main = new Main();
        main.run();
    }

    public static class MyImage {
        public String normalName;
        public String smallName;
    }

    @Override
    public void run() {
        final List<MyImage> done = new ArrayList<>();
        try {
            final File currentWorkingDirectory = new File(".").getCanonicalFile();

            // create the small directory
            File smallPath = new File(currentWorkingDirectory.getCanonicalPath() + "/small");
            smallPath.mkdirs();

            // create the big directory
            File bigPath = new File(currentWorkingDirectory.getCanonicalPath() + "/big");
            bigPath.mkdirs();

            // get all jpg files
            File[] jpgFiles = currentWorkingDirectory.listFiles(new FilenameFilter() {
                @Override
                public boolean accept(File dir, String name) {
                    if (name.endsWith(".jpg") || name.endsWith(".JPG") || name.endsWith(".jpeg") || name.endsWith(".JPEG")) {
                        return true;
                    }
                    return false;
                }
            });

            // rename all files to a lowercase jpg extension
            for (File jpgFile : jpgFiles) {
                File newFilename = new File(jpgFile.getParent(), getNameWithoutExtension(jpgFile) + ".jpg");
                jpgFile.renameTo(newFilename);
            }

            // get all jpg files without underscore and s _s
            File[] jpgFilesNormalSize = currentWorkingDirectory.listFiles(new FilenameFilter() {
                @Override
                public boolean accept(File dir, String name) {
                    if (name.endsWith(".jpg") && !name.endsWith("_s.jpg")) {
                        return true;
                    }
                    return false;
                }
            });

            // iterate over all normal images and create small images
            for (File file : jpgFilesNormalSize) {
                System.out.println("process: " + file.getName());
                createMiniImage(file, new File(bigPath.getAbsolutePath() + "/" + file.getName()), 1600);
                final String smallName = getNameWithoutExtension(file) + "_s.jpg";
                File newFilename = new File(smallPath, smallName);
                createMiniImage(file, newFilename, 280);
                MyImage myImage = new MyImage();
                myImage.normalName = file.getName();
                myImage.smallName = smallName;
                done.add(myImage);
            }

            System.out.println();
            for (MyImage myImage : done) {
                System.out.println("<a href=\"http://ladenthin.net/ebay/"+myImage.normalName+"\" target=\"_blank\" ><img alt=\"\" src=\"http://ladenthin.net/ebay/"+myImage.smallName+"\" /></a>");
            }
            System.out.println();

        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }

    private String getNameWithoutExtension(File f) {
        return f.getName().substring(0, f.getName().lastIndexOf("."));
    }

    private void createMiniImage(File file, File newFilename, final int newWidth) throws IOException {
        Image img = new ImageIcon(ImageIO.read(file)).getImage();

        double scale = (double)img.getWidth(null) / (double)newWidth;
        int hNew = (int)((double)img.getHeight(null) / scale);
        Image scaledImage = img.getScaledInstance(newWidth, hNew, Image.SCALE_SMOOTH);
        BufferedImage outImg = new BufferedImage(newWidth, hNew, BufferedImage.TYPE_INT_RGB);

        Graphics g = outImg.getGraphics();
        g.drawImage(scaledImage, 0, 0, null);
        g.dispose();

        ImageIO.write(outImg, "jpeg", newFilename);
    }
}
