package net.ladenthin.screenshot;

import java.awt.*;
import java.awt.geom.Rectangle2D;
import java.awt.image.BufferedImage;

public class ImageCapture {

    public BufferedImage getImageFromScreen() throws AWTException {
        Rectangle2D result = new Rectangle2D.Double();
        GraphicsEnvironment localGE = GraphicsEnvironment.getLocalGraphicsEnvironment();
        for (GraphicsDevice gd : localGE.getScreenDevices()) {
            for (GraphicsConfiguration graphicsConfiguration : gd.getConfigurations()) {
                Rectangle bounds = graphicsConfiguration.getBounds();
                //System.out.println("bounds: " + bounds);
                result.union(result, bounds, result);
            }
        }
        //System.out.println("result.getWidth(): " + result.getWidth());
        //System.out.println("result.getHeight(): " + result.getHeight());
        Robot robot = new Robot();
        return robot.createScreenCapture(result.getBounds());
    }

}
