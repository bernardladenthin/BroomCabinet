package de.fraunhofer.fokus.jackpot.connector;

import java.io.*;

/**
 * Created by bernard on 13.05.14.
 */
public abstract class UnixNamedPipeConnector implements Connector {

    protected FileOutputStream requestStream;
    protected FileInputStream responseStream;
    protected String requestPipe;
    protected String responsePipe;

    protected void checkOperatingSystem() {
        if (System.getProperty("os.name").toLowerCase().contains("windows")) {
            throw new UnsupportedOperationException("This method is not supported on this operating system.");
        }
    }

    @Override
    public OutputStream getOutputStream() throws IOException {
        return requestStream;
    }

    @Override
    public InputStream getInputStream() throws IOException {
        return responseStream;
    }

    @Override
    public void close() throws IOException {
        if (requestStream != null) {
            requestStream.close();
        }
        requestStream = null;

        if (responseStream != null) {
            responseStream.close();
        }
        responseStream = null;
        if (requestPipe != null) {
            final File requestPipeFile = new File(requestPipe);
            if (requestPipeFile.exists()) {
                requestPipeFile.delete();
            }
        }

        if (responsePipe != null) {
            final File responsePipeFile = new File(responsePipe);
            if (responsePipeFile.exists()) {
                responsePipeFile.delete();
            }
        }
    }

    protected void connect(final String requestPipe, final String responsePipe) throws IOException {
        close();
        this.requestPipe = requestPipe;
        this.responsePipe = responsePipe;
        Runtime.getRuntime().exec("mkfifo " + requestPipe);
        Runtime.getRuntime().exec("mkfifo " + responsePipe);
        requestStream = new FileOutputStream(requestPipe);
        responseStream = new FileInputStream(responsePipe);
    }

}
