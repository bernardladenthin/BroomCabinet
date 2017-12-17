package net.ladenthin.screenshot.socket;

import java.io.*;
import java.net.Socket;
import java.net.SocketException;
import java.net.SocketTimeoutException;
import java.util.logging.Level;
import java.util.logging.Logger;

public class SecureServerRequestCycleSocket implements Runnable {

    private static final Logger logger = Logger.getLogger(SecureServerRequestCycleSocket.class.getName());

    private final Socket clientSocket;
    private InputStream inputStream;
    private DataInputStream dis;
    private OutputStream outputStream;
    private DataOutputStream dos;

    private final byte[] key;
    private final ClientRequest clientRequest;

    public SecureServerRequestCycleSocket(Socket clientSocket, byte[] key, ClientRequest clientRequest) {
        this.clientSocket = clientSocket;
        this.key = key;
        this.clientRequest = clientRequest;
    }

    @Override
    public void run() {
        try {
            init();
            for (; ; ) {
                // input
                EncryptedBlock requestBlock = new EncryptedBlock();
                requestBlock.read(dis);
                byte[] decrypted = requestBlock.decrypt(key);

                // process
                byte[] response = clientRequest.call(decrypted);

                // output
                EncryptedBlock responseBlock = new EncryptedBlock();
                responseBlock.encrypt(response, key);
                responseBlock.write(dos);
                dos.flush();
            }

        } catch (SocketTimeoutException e) {
            // do nothing
        } catch (SocketException e) {
            // do nothing
        } catch (IOException e) {
            logger.log(Level.INFO, e.getMessage(), e);
            e.printStackTrace();
        } catch (Exception e) {
            logger.log(Level.INFO, e.getMessage(), e);
            e.printStackTrace();
        }

        // try to close in any case
        try {
            clientSocket.close();
        } catch (IOException e) {
        }
    }

    private void init() throws IOException {
        inputStream = clientSocket.getInputStream();
        outputStream = clientSocket.getOutputStream();
        clientSocket.setSoTimeout(30000);
        dis = new DataInputStream(inputStream);
        dos = new DataOutputStream(outputStream);
    }
}
