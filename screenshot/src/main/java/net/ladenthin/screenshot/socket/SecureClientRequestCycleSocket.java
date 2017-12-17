package net.ladenthin.screenshot.socket;

import java.io.*;
import java.net.ConnectException;
import java.net.Socket;
import java.net.SocketException;
import java.util.logging.Level;
import java.util.logging.Logger;

public class SecureClientRequestCycleSocket implements Runnable {

    private static final Logger logger = Logger.getLogger(SecureClientRequestCycleSocket.class.getName());

    private final String host;
    private final int port;
    private final ServerRequest serverRequest;
    private final byte[] key;
    private final ServerResponse serverResponse;

    public SecureClientRequestCycleSocket(String host, int port, byte[] key, ServerRequest serverRequest, ServerResponse serverResponse) {
        this.host = host;
        this.port = port;
        this.key = key;
        this.serverRequest = serverRequest;
        this.serverResponse = serverResponse;
    }

    private Socket serverSocket;
    private InputStream inputStream;
    private DataInputStream dis;
    private OutputStream outputStream;
    private DataOutputStream dos;

    @Override
    public void run() {
        outer:
        for (; ; ) {
            try {
                init();

                for (; ; ) {
                    // output
                    byte[] request = serverRequest.call();

                    EncryptedBlock requestBlock = new EncryptedBlock();
                    requestBlock.encrypt(request, key);
                    requestBlock.write(dos);
                    dos.flush();

                    // wait for an input
                    // ....

                    // input
                    EncryptedBlock responseBlock = new EncryptedBlock();
                    responseBlock.read(dis);
                    byte[] decrypted = responseBlock.decrypt(key);

                    // process
                    serverResponse.call(decrypted);
                }
            } catch (ConnectException e) {
                logger.info("Could not connect, wait a little bit.");
                try {
                    Thread.sleep(5000);
                } catch (InterruptedException e1) {
                }
            } catch (SocketException e) {
                logger.log(Level.INFO, e.getMessage(), e);
            } catch (Exception e) {
                e.printStackTrace();
            }
        }
    }

    private void init() throws IOException {
        serverSocket = new Socket(host, port);
        inputStream = serverSocket.getInputStream();
        outputStream = serverSocket.getOutputStream();
        serverSocket.setSoTimeout(30000);
        dis = new DataInputStream(inputStream);
        dos = new DataOutputStream(outputStream);
    }
}