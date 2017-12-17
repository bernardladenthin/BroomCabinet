import java.awt.image.BufferedImage;
import java.awt.Image;
import java.awt.Dimension;
import java.awt.Graphics;
import java.io.File;
import javax.imageio.ImageIO;
import javax.swing.ImageIcon;

def maxWidth = 360;
def maxHeight = 360;

// https://stackoverflow.com/questions/10245220/java-image-resize-maintain-aspect-ratio
// SNIP
def Dimension getScaledDimension(Dimension imgSize, Dimension boundary) {

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
// SNAP

def resize(file, maxDimension) {
    Image img = new ImageIcon(ImageIO.read(file)).getImage();
    Dimension imgDimension = new Dimension(img.getWidth(null), img.getHeight(null));
    
    Dimension newDimension = getScaledDimension(imgDimension, maxDimension);
    
    Image scaledImage = img.getScaledInstance(newDimension.@width, newDimension.@height, Image.SCALE_SMOOTH);
    BufferedImage outImg = new BufferedImage(newDimension.@width, newDimension.@height, BufferedImage.TYPE_INT_RGB);
    Graphics g = outImg.getGraphics();
    g.drawImage(scaledImage, 0, 0, null);
    g.dispose();
    ImageIO.write(outImg, "jpeg", file);
}

// main loop
new File('.').eachFileRecurse {
    def isJpeg = it.name.toLowerCase().endsWith(".jpg")
    if (isJpeg) {
        println "ok, resize: " + it.name;
        resize(it, new Dimension(maxWidth, maxHeight));
    }
}
