package net.ladenthin.imageresize;

import javax.imageio.IIOImage;
import javax.imageio.ImageIO;
import javax.imageio.ImageWriteParam;
import javax.imageio.ImageWriter;
import javax.imageio.stream.FileImageOutputStream;
import javax.imageio.stream.ImageOutputStream;
import javax.swing.*;
import java.awt.*;
import java.awt.image.BufferedImage;
import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.function.Consumer;

public class Common {
    /**
     * https://stackoverflow.com/questions/10245220/java-image-resize-maintain-aspect-ratio
     */
    public Dimension getScaledDimension(Dimension imgSize, Dimension boundary) {
        int original_width = imgSize.width;
        int original_height = imgSize.height;
        int bound_width = boundary.width;
        int bound_height = boundary.height;
        int new_width = original_width;
        int new_height = original_height;

        // first check if we need to scale width
        if (original_width > bound_width) {
            //scale width to fit
            new_width = bound_width;
            //scale height to maintain aspect ratio
            new_height = (new_width * original_height) / original_width;
        }

        // then check if we need to scale even with the new height
        if (new_height > bound_height) {
            //scale height to fit instead
            new_height = bound_height;
            //scale width to maintain aspect ratio
            new_width = (new_height * original_width) / original_height;
        }

        return new Dimension(new_width, new_height);
    }
    
    public boolean isFileJpeg(Path filePath) {
        String name = filePath.getFileName().toString().toLowerCase();
        return name.endsWith(".jpg") || name.endsWith(".jpeg");
    }

    public void resize(File file, Dimension maxDimension, float quality) throws IOException {
        Image img = new ImageIcon(ImageIO.read(file)).getImage();
        Dimension imgDimension = new Dimension(img.getWidth(null), img.getHeight(null));

        Dimension newDimension = getScaledDimension(imgDimension, maxDimension);

        Image scaledImage = img.getScaledInstance(newDimension.width,newDimension.height,Image.SCALE_SMOOTH);
        BufferedImage outImg = new BufferedImage(newDimension.width,newDimension.height,BufferedImage.TYPE_INT_RGB);
        Graphics g = outImg.getGraphics();
        g.drawImage(scaledImage, 0, 0, null);
        g.dispose();

        // https://stackoverflow.com/questions/17108234/setting-jpg-compression-level-with-imageio-in-java
        ImageWriter jpgWriter = ImageIO.getImageWritersByFormatName("jpg").next();
        ImageWriteParam jpgWriteParam = jpgWriter.getDefaultWriteParam();
        jpgWriteParam.setCompressionMode(ImageWriteParam.MODE_EXPLICIT);
        jpgWriteParam.setCompressionQuality(quality);

        if(!file.delete()) {
            throw new RuntimeException();
        }
        ImageOutputStream outputStream = new FileImageOutputStream(file);
        jpgWriter.setOutput(outputStream);

        jpgWriter.write(null, new IIOImage(outImg, null, null), jpgWriteParam);
        jpgWriter.dispose();
    }

    public void forEachJpegFile(Path path, Consumer<? super Path> consumer) {
        try {
            Files.find(path,
                    Integer.MAX_VALUE,
                    (filePath, fileAttr) -> fileAttr.isRegularFile() &&  isFileJpeg(filePath))
                    .forEach(consumer);
        } catch (IOException e) {
            throw new RuntimeException(e);
        }
    }

    public String getNameWithoutExtension(String s) {
        return s.substring(0, s.lastIndexOf("."));
    }
}