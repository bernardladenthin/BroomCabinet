package net.ladenthin.screenshot;

import javafx.embed.swing.SwingFXUtils;
import javafx.scene.image.ImageView;
import javafx.scene.image.WritableImage;

import javax.imageio.ImageIO;
import java.awt.*;
import java.awt.image.*;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Arrays;
import java.util.logging.Logger;
import java.util.zip.DataFormatException;

public enum ImageHelper {
    ;
    private static final Logger logger = Logger.getLogger(ImageHelper.class.getName());

    public final static int persistenceType = BufferedImage.TYPE_3BYTE_BGR;
    public final static byte[] SHA_Salt = new byte[]{12, 67 , 77, -118, 107};

    /*
    public byte[] getImageFromScreenAsPNGByteArray() throws AWTException, IOException {
        return convertBufferedImageToPNGByteArray(getImageFromScreen());
    }
    */
    public static byte[] convertBufferedImageToPNGByteArray(BufferedImage image) throws IOException {
        ByteArrayOutputStream os = new ByteArrayOutputStream();
        ImageIO.write(image, "png", os);
        return os.toByteArray();
    }

    public static BufferedImage convertByteArrayToBufferedImage(byte[] bytes) throws IOException {
        return ImageIO.read(new ByteArrayInputStream(bytes));
    }

    public static Chunk[][] splitBufferedImageToChunks(BufferedImage image, int maxWidth, int maxHeight) throws IOException {
        // ensure the max values are not greater as the image to split
        if (maxWidth > image.getWidth()) {
            maxWidth = image.getWidth();
        }
        if (maxHeight > image.getHeight()) {
            maxHeight = image.getHeight();
        }

        logger.finest("maxWidth: " + maxWidth);
        logger.finest("maxHeight: " + maxHeight);

        int nCols =  (int)Math.ceil(((double)image.getWidth() / (double)maxWidth));
        int nRows = (int)Math.ceil(((double)image.getHeight() / (double)maxHeight));

        logger.finest("nCols: " + nCols);
        logger.finest("nRows: " + nRows);

        int maxMergedWidth = maxWidth * nCols;
        int maxMergedHeight = maxHeight * nRows;
        logger.finest("maxMergedWidth: " + maxMergedWidth);
        logger.finest("maxMergedHeight: " + maxMergedHeight);

        // subtract the difference to calcualte the size for the last column / row
        int lastColWidth = maxWidth-Math.abs(image.getWidth() - maxMergedWidth);
        int lastRowHeight = maxHeight-Math.abs(image.getHeight() - maxMergedHeight);
        logger.finest("lastColWidth: " + lastColWidth);
        logger.finest("lastRowHeight: " + lastRowHeight);

        //Image array to hold image chunks
        Chunk chunks[][] = new Chunk[nRows][nCols];

        for (int row = 0; row < nRows; row++) {
            for (int col = 0; col < nCols; col++) {
                boolean isLastRow = nRows - 1 == row;
                boolean isLastCol = nCols - 1 == col;

                // is this the last column / row?
                int width = maxWidth;
                int height = maxHeight;
                if (isLastRow) {
                    height = lastRowHeight;
                }
                if (isLastCol) {
                    width = lastColWidth;
                }

                Chunk chunk = new Chunk();
                chunk.setWidth(width);
                chunk.setHeight(height);
                chunks[row][col] = chunk;

                // BufferedImage.TYPE_3BYTE_BGR uses byte[3]
                // BufferedImage.TYPE_INT_RGB uses an int
                BufferedImage chunkImage = new BufferedImage(width, height, persistenceType);

                Graphics2D graphics = chunkImage.createGraphics();
                graphics.drawImage(image, 0, 0, width, height, col * maxWidth, row * maxWidth, col * maxWidth + width, row * maxWidth + height, null);
                graphics.dispose();

                // see above
                DataBufferByte dataBuffer = (DataBufferByte) chunkImage.getRaster().getDataBuffer();
                // this is necessary to store the data in the database
                byte[] raw = dataBuffer.getData();
                // may https://en.wikipedia.org/wiki/PBKDF2 in future?
                String digest = ByteUtils.getSha256String(raw, SHA_Salt);

                chunk.setDigest(digest);
                chunk.setThreeByteBGR(raw);
                byte[] compressed = ByteUtils.compressDeflate(raw);
                chunk.setCompressedThreeByteBGR(compressed);

                BufferedImage rgb565 = downsampleTo_TYPE_USHORT_565_RGB(chunkImage);
                DataBufferUShort dbrgb565 = (DataBufferUShort) rgb565.getRaster().getDataBuffer();
                short[] datadbrgb565 = dbrgb565.getData();
                byte[] datadbrgb565Compressed = ByteUtils.compressDeflate(ByteUtils.shortsToBytes(datadbrgb565));

                logger.finest("compressed.length: " + compressed.length);
                logger.finest("datadbrgb565Compressed.length: " + datadbrgb565Compressed.length);
            }
        }
        return chunks;
    }

    /**
     * Gut, aber wir haben keine direkten bytes (weil png header, etc. fehlt)
     * @param imageData
     * @return
     */
    public static BufferedImage createImageFromBytes(byte[] imageData) {
        ByteArrayInputStream bais = new ByteArrayInputStream(imageData);
        try {
            return ImageIO.read(bais);
        } catch (IOException e) {
            throw new RuntimeException(e);
        }
    }

    /**
     * http://stackoverflow.com/questions/11006394/is-there-a-simple-way-to-compare-bufferedimage-instances
     */
    public static boolean fastCompareBufferedImageWithSameColor(BufferedImage a, BufferedImage b) {
        DataBuffer dbA = a.getRaster().getDataBuffer();
        DataBuffer dbB = b.getRaster().getDataBuffer();
        DataBufferInt dbAInt = (DataBufferInt) dbA;
        DataBufferInt dbBInt = (DataBufferInt) dbB;

        for (int bank = 0; bank < dbAInt.getNumBanks(); bank++) {
            int[] actual = dbAInt.getData(bank);
            int[] expected = dbBInt.getData(bank);

            // this line may vary depending on your test framework
            if(Arrays.equals(actual, expected) == false) {
                return false;
            }
        }
        return true;
    }

    public static BufferedImage createBufferedImageFromRawByteArray_TYPE_3BYTE_BGR(byte[] srcbuf, int width, int height) {
        BufferedImage img;
        img = new BufferedImage(width, height, BufferedImage.TYPE_3BYTE_BGR);
        img.setData(Raster.createRaster(img.getSampleModel(), new DataBufferByte(srcbuf, srcbuf.length), new Point()) );
        return img;
    }

    public static BufferedImage createBufferedImageFromRawByteArray_TYPE_USHORT_565_RGB(byte[] srcbuf, int width, int height) {
        BufferedImage img;
        img=new BufferedImage(width, height, BufferedImage.TYPE_USHORT_565_RGB);
        img.setData(Raster.createRaster(img.getSampleModel(), new DataBufferByte(srcbuf, srcbuf.length), new Point()) );
        return img;
    }

    public static BufferedImage createBufferedImageFromRawByteArray_TYPE_BYTE_INDEXED(byte[] srcbuf, int width, int height) {
        BufferedImage img;
        img=new BufferedImage(width, height, BufferedImage.TYPE_BYTE_INDEXED);
        img.setData(Raster.createRaster(img.getSampleModel(), new DataBufferByte(srcbuf, srcbuf.length), new Point()) );
        return img;
    }

    public static BufferedImage downsampleTo_TYPE_USHORT_565_RGB(BufferedImage bi32) {
        BufferedImage bi = new BufferedImage(bi32.getWidth(), bi32.getHeight(), BufferedImage.TYPE_USHORT_565_RGB);
        Graphics2D g2d = (Graphics2D)bi.getGraphics();
        g2d.setComposite(AlphaComposite.Src);
        g2d.drawImage(bi32, 0, 0, null);
        g2d.dispose();
        return bi;
    }

    public static BufferedImage downsampleTo_TYPE_BYTE_INDEXED(BufferedImage bi32) {
        BufferedImage bi = new BufferedImage(bi32.getWidth(), bi32.getHeight(), BufferedImage.TYPE_BYTE_INDEXED);
        Graphics2D g2d = (Graphics2D)bi.getGraphics();
        g2d.setComposite(AlphaComposite.Src);
        g2d.drawImage(bi32, 0, 0, null);
        g2d.dispose();
        return bi;
    }

    /**
     * http://software-talk.org/blog/2013/12/java-image-manipulation-bufferedimage/#Java%20add%20two%20BufferedImages%20opaque
     * http://codereview.stackexchange.com/questions/58067/more-efficient-way-to-draw-bufferedimage-into-another
     */
    /**
     * prints the contents of buff2 on buff1 with the given opaque value
     * starting at position 0, 0.
     *
     * @param buff1 buffer
     * @param buff2 buffer to add to buff1
     * @param opaque opacity
     */
    public static void addImage(BufferedImage buff1, BufferedImage buff2, float opaque) {
        addImage(buff1, buff2, opaque, 0, 0);
    }

    /**
     * prints the contents of buff2 on buff1 with the given opaque value.
     *
     * @param buff1 buffer
     * @param buff2 buffer
     * @param opaque how opaque the second buffer should be drawn
     * @param x x position where the second buffer should be drawn
     * @param y y position where the second buffer should be drawn
     */
    public static void addImage(BufferedImage buff1, BufferedImage buff2, float opaque, int x, int y) {
        Graphics2D g2d = buff1.createGraphics();
        g2d.setComposite( AlphaComposite.getInstance(AlphaComposite.SRC_OVER, opaque));
        g2d.drawImage(buff2, x, y, null);
        g2d.dispose();
    }

    public static BufferedImage createImageFromChunks(Chunk[][] chunks) throws IOException, DataFormatException {
        // calculate width and height
        int widthExceptLastElement = chunks[0][0].getWidth() * (chunks[0].length-1);
        int heightExceptLastElement = chunks[0][0].getHeight() * (chunks.length-1);

        int widthLastElement = chunks[0][chunks[0].length-1].getWidth();
        int heightLastElement = chunks[chunks.length-1][0].getHeight();

        int width = widthExceptLastElement + widthLastElement;
        int height = heightExceptLastElement + heightLastElement;

        BufferedImage stateImage = new BufferedImage(width, height, BufferedImage.TYPE_3BYTE_BGR);
        Graphics2D graphics = stateImage.createGraphics();
        int heightOffset = 0;
        for (int row = 0; row < chunks.length; row++) {
            int widthOffset = 0;
            for (int col = 0; col < chunks[row].length; col++) {
                Chunk chunk = chunks[row][col];
                chunk.createBufferedImage();
                graphics.drawImage(chunk.getImage(), widthOffset, heightOffset, widthOffset + chunk.getWidth(), heightOffset + chunk.getHeight(), 0, 0, chunk.getWidth(), chunk.getHeight(), null);
                widthOffset += chunk.getWidth();
            }
            heightOffset += chunks[row][0].getHeight();
        }
        graphics.dispose();
        return stateImage;
    }

    public static ImageView createImageViewFromBufferedImage(BufferedImage bufferedImage) {
        // resizes the image to have a fixed width while preserving the ratio and using
        // higher quality filtering method; this ImageView is also cached to improve performance
        ImageView iv = new ImageView();
        WritableImage image = SwingFXUtils.toFXImage(bufferedImage, null);
        iv.setImage(image);
        return iv;
    }
}