// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.connector;

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

    /**
     * Creates the FIFO special file if it does not exist yet, WAITING for mkfifo to finish:
     * without the wait, the subsequent stream open races the mkfifo process and
     * {@link FileOutputStream} silently creates a REGULAR file instead — the transport then
     * never behaves like a pipe. Tolerant when the file already exists (the other side may
     * have created it first).
     *
     * @param pipe the FIFO path
     */
    private void createFifo(final String pipe) throws IOException {
        final File pipeFile = new File(pipe);
        if (!pipeFile.exists()) {
            try {
                Runtime.getRuntime().exec(new String[] {"mkfifo", pipe}).waitFor();
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new IOException("interrupted while creating fifo " + pipe, e);
            }
        }
        if (!pipeFile.exists()) {
            throw new IOException("could not create fifo " + pipe);
        }
    }

    /**
     * Opens both FIFO ends. Opening a FIFO blocks until the OTHER end is opened by the peer,
     * so the two sides must open in complementary order: the server opens its input first and
     * the client its output first — with both sides opening the output first (the historical
     * behaviour) each waited forever for a reader that could never come (mutual open
     * deadlock; this transport never managed to connect at all).
     *
     * @param requestPipe the pipe this side writes to
     * @param responsePipe the pipe this side reads from
     * @param openInputFirst true for the server side, false for the client side
     */
    protected void connect(final String requestPipe, final String responsePipe,
        final boolean openInputFirst) throws IOException {
        close();
        this.requestPipe = requestPipe;
        this.responsePipe = responsePipe;
        createFifo(requestPipe);
        createFifo(responsePipe);
        if (openInputFirst) {
            responseStream = new FileInputStream(responsePipe);
            requestStream = new FileOutputStream(requestPipe);
        } else {
            requestStream = new FileOutputStream(requestPipe);
            responseStream = new FileInputStream(responsePipe);
        }
    }

}
