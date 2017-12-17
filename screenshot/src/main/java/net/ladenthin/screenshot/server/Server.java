package net.ladenthin.screenshot.server;

import net.ladenthin.screenshot.*;
import net.ladenthin.screenshot.byteprotocol.Message;
import net.ladenthin.screenshot.socket.ClientRequest;
import net.ladenthin.screenshot.socket.Common;
import net.ladenthin.screenshot.socket.SecureServerRequestCycleSocketAcceptor;

import java.awt.*;
import java.awt.image.BufferedImage;
import java.io.IOException;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.logging.Level;
import java.util.logging.Logger;

public class Server {

    private static final Logger logger = Logger.getLogger(Server.class.getName());

    private final ImageCapture ic = new ImageCapture();
    private final static ImagePersistence imagePersistence = new ImagePersistenceImplSQLite("server.db");
    private volatile long nextUpdate = -1;

    private static volatile State STATIC_STATE;

    public static void main(String[] argv) {
        Server server = new Server();
        server.run();
    }

    public class ServiceTask implements Runnable {
        public void run() {
            if (nextUpdate > System.currentTimeMillis()) {
                // skip this wakeup
                return;
            }

            try {
                shot();
            } catch (Exception e) {
                e.printStackTrace();
                logger.warning("Error during shot, try again in a few moments. " + e.getMessage());
                // try again in one minute
                nextUpdate = System.currentTimeMillis() + TimeUnit.MINUTES.toMillis(1);
                return;
            }
            // send an update every 300 milli seconds
            nextUpdate = System.currentTimeMillis() + TimeUnit.MILLISECONDS.toMillis(300);
            logger.info("Successful shot.");
        }
    }

    private void encryptRoundTrip() {
        try {
            byte[] key = ByteUtils.getSha256("Geheim".getBytes(), "Salz".getBytes());
            byte[] iv = Security.generate16RandomBytes();
            byte[] raw = "Hallo World".getBytes();
            logger.finest("key.length: " + key.length);
            byte[] encrypted = Security.encrypt(raw, key, iv, false);

            byte[] decrypted = Security.decrypt(encrypted, key, iv, false);
            if (logger.isLoggable(Level.FINEST)) {
                logger.finest("raw: " + Arrays.toString(raw));
                logger.finest("encrypted: " + Arrays.toString(encrypted));
                logger.finest("decrypted: " + Arrays.toString(decrypted));
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    private void run() {
        byte[] key = ByteUtils.getSha256("Socket Password".getBytes(), "My Socket Salt".getBytes());
        KeyProvider.setHashedKey(key);
        KeyProvider.getHashedKey();

        Thread serverSocket = new Thread(new SecureServerRequestCycleSocketAcceptor(Common.SERVER_PORT, key, new ClientRequest() {
            @Override
            public byte[] call(byte[] request) {
                try {
                    Message requestMessage = new Message();
                    requestMessage.deserialize(request);

                    if (logger.isLoggable(Level.FINEST)) {
                        logger.finest("");
                        logger.finest("");
                        logger.finest("===== SERVER BEGIN =====");
                        logger.finest("requestMessage: " + requestMessage);
                        logger.finest("===== SERVER END =====");
                        logger.finest("");
                        logger.finest("");
                    }

                    Message responseMessage = new Message();
                    if (requestMessage.isRequestState() && STATIC_STATE != null) {
                        shot();
                        responseMessage.setResponseState(true);
                        responseMessage.setResponseStateContainer(STATIC_STATE);
                    }

                    if (requestMessage.isRequestChunks()) {
                        ArrayList<Chunk> chunks = new ArrayList<>();
                        for (Long requestChunkId : requestMessage.getRequestChunkIds()) {
                            try {
                                chunks.add(imagePersistence.getChunkById(requestChunkId));
                            } catch (SQLException e) {
                                throw new RuntimeException(e);
                            }
                        }
                        responseMessage.setResponseChunks(true);
                        responseMessage.setResponseChunks(chunks);
                    }

                    byte[] serialize = responseMessage.serialize();

                    return serialize;

                } catch (IOException e) {
                    Message responseMessage = new Message();
                    responseMessage.setInvalidRequest(true);
                    try {
                        return responseMessage.serialize();
                    } catch (IOException e1) {
                        throw new RuntimeException(e1);
                    }
                } catch (Exception e) {
                    throw new RuntimeException(e);
                }
            }
        }));
        serverSocket.start();

        try {
            imagePersistence.initConnection();
            imagePersistence.initPersistence();
        } catch (ClassNotFoundException | SQLException e) {
            throw new RuntimeException(e);
        }

        ServiceTask st = new ServiceTask();
        ScheduledExecutorService executor = Executors.newScheduledThreadPool(1);
        executor.scheduleAtFixedRate(st, 0, 1, TimeUnit.SECONDS);
    }

    private synchronized void shot() throws Exception {
        BufferedImage screen = ic.getImageFromScreen();
        Chunk[][] chunks = ImageHelper.splitBufferedImageToChunks(screen, 256, 256);

        State state = imagePersistence.persistChunks(chunks);
        STATIC_STATE = state;
        if (logger.isLoggable(Level.FINEST)) {
            logger.finest(state.toString());
        }
        /*
        for (int row = 0; row < chunks.length; row++) {
            for (int col = 0; col < chunks[row].length; col++) {
                BufferedImage chunk = chunks[row][col];
                chunskBin[row][col] = ic.convertBufferedImageToPNGByteArray(chunk);

                long xId = id +col+row*chunks[row].length;
                System.out.println(xId);
                insertImage(xId, chunskBin[row][col]);
            }
        }
        */


        //screenShot = getScaledImage(screenShot, screenShot.getWidth() / 2, screenShot.getHeight() / 2);
        //screenShot = getGrayScale(screenShot);

        //File outputfile = new File(id + ".png");
        //ImageIO.write(screenShot, "png", outputfile);




        /*
        PNGImageWriteParam
        JPEGImageWriteParam jpegParams = new JPEGImageWriteParam(null);
        jpegParams.setCompressionMode(ImageWriteParam.MODE_EXPLICIT);
        jpegParams.
        jpegParams.setCompressionQuality(0.0f);
        File outputfile = new File(System.currentTimeMillis() + ".jpg");
        ImageIO.write(screenShot, "jpg", outputfile);
        */
        /*
        cached output stream
        ByteArrayOutputStream baos = new ByteArrayOutputStream(); writer.setOutput(new MemoryCacheImageOutputStream(baos)); ... baos.flush(); byte[] returnImage = baos.toByteArray(); baos.close();

        OutputStream outputStream = createOutputStream(); //For example, FileImageOutputStream
        jpgWriter.setOutput(outputStream);
        IIOImage outputImage = new IIOImage(image, null, null);
        jpgWriter.write(null, outputImage, jpgWriteParam);
        jpgWriter.dispose();
         */
    }



    //http://codehustler.org/blog/java-to-create-grayscale-images-icons/

    // https://github.com/depsypher/pngtastic

    // http://objectplanet.com/pngencoder/images/alltests.gif

    public static BufferedImage getGrayScale(BufferedImage inputImage){
        BufferedImage img = new BufferedImage(inputImage.getWidth(), inputImage.getHeight(), BufferedImage.TYPE_BYTE_GRAY);
        Graphics g = img.getGraphics();
        g.drawImage(inputImage, 0, 0, null);
        g.dispose();
        return img;
    }

    /**
     * Resizes an image using a Graphics2D object backed by a BufferedImage.
     * @param src - source image to scale
     * @param w - desired width
     * @param h - desired height
     * @return - the new resized image
     */
    private static BufferedImage getScaledImage(BufferedImage src, int w, int h){
        int finalw = w;
        int finalh = h;
        double factor = 1.0d;
        if (src.getWidth() > src.getHeight()) {
            factor = ((double)src.getHeight()/(double)src.getWidth());
            finalh = (int)(finalw * factor);
        } else {
            factor = ((double)src.getWidth()/(double)src.getHeight());
            finalw = (int)(finalh * factor);
        }

        BufferedImage resizedImg = new BufferedImage(finalw, finalh, BufferedImage.TYPE_INT_RGB);
        Graphics2D g2 = resizedImg.createGraphics();
        g2.setRenderingHint(RenderingHints.KEY_INTERPOLATION, RenderingHints.VALUE_INTERPOLATION_BILINEAR);
        g2.drawImage(src, 0, 0, finalw, finalh, null);
        g2.dispose();
        return resizedImg;
    }

}