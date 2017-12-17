package net.ladenthin.screenshot;

import java.awt.image.BufferedImage;
import java.awt.image.DataBufferByte;
import java.io.IOException;
import java.util.Arrays;
import java.util.zip.DataFormatException;

public class Chunk {

    private long id;
    private String digest;

    private BufferedImage image;
    private byte[] threeByteBGR;
    private byte[] compressedThreeByteBGR;

    private int width;
    private int height;

    public int getWidth() {
        return width;
    }

    public void setWidth(int width) {
        this.width = width;
    }

    public int getHeight() {
        return height;
    }

    public void setHeight(int height) {
        this.height = height;
    }

    public long getId() {
        return id;
    }

    public void setId(long id) {
        this.id = id;
    }

    public BufferedImage getImage() {
        return image;
    }

    @Deprecated
    public void setImage(BufferedImage image) {
        this.image = image;
    }

    @Deprecated
    public void setPNGDataFromBufferedImage() throws IOException {
        //setPngData(ImageHelper.convertBufferedImageToPNGByteArray(image));
    }

    @Deprecated
    public void setImageFromPNGData() throws IOException {
        //image = ImageHelper.convertByteArrayToBufferedImage(pngData);
    }

    /*
    public void setPixelFromImage() {
        pixel = new int[image.getWidth() * image.getHeight()];
        image.getRGB(0, 0, image.getWidth(), image.getHeight(), pixel, 0, 1);
    }
    */

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;

        Chunk chunk = (Chunk) o;

        return Arrays.equals(threeByteBGR, chunk.threeByteBGR);
    }

    @Override
    public int hashCode() {
        return digest.hashCode();
    }

    @Override
    public String toString() {
        return "Chunk{" +
                "id=" + id +
                '}';
    }

    public String getMetrics() throws IOException {
        String string = "id: " + id;
        string += "; ";
        string += "getThreeByteBGR().length: " + getThreeByteBGR().length;
        string += "; ";
        string += "compressedThreeByteBGR.length: " + compressedThreeByteBGR.length;
        return string;
    }

    public void setThreeByteBGR(byte[] threeByteBGR) {
        this.threeByteBGR = threeByteBGR;
    }

    public byte[] getThreeByteBGR() {
        return threeByteBGR;
    }

    public void setDigest(String digest) {
        this.digest = digest;
    }

    public String getDigest() {
        return digest;
    }

    public void setCompressedThreeByteBGR(byte[] compressedThreeByteBGR) {
        this.compressedThreeByteBGR = compressedThreeByteBGR;
    }

    public byte[] getCompressedThreeByteBGR() {
        return compressedThreeByteBGR;
    }

    public void createBufferedImage() throws IOException, DataFormatException {
        if (getCompressedThreeByteBGR()!= null && image == null) {
            image = new BufferedImage(getWidth(), getHeight(), BufferedImage.TYPE_3BYTE_BGR);
            DataBufferByte dataBuffer = (DataBufferByte) image.getRaster().getDataBuffer();
            byte[] data = dataBuffer.getData();
            byte[] newData = ByteUtils.decompressDeflate(getCompressedThreeByteBGR());
            System.arraycopy(newData, 0, data, 0, data.length);
        }
    }

}
