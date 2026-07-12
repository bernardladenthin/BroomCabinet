package de.fraunhofer.fokus.jackpot.connector;

import de.fraunhofer.fokus.jackpot.configuration.CWindowsNamedPipeClientConnector;
import de.fraunhofer.fokus.jackpot.wrapper.RandomAccessFileToInputStream;
import de.fraunhofer.fokus.jackpot.wrapper.RandomAccessFileToOutputStream;

import java.io.*;

/**
 * Created by bernard on 13.05.14.
 */
public class WindowsNamedPipeClientConnector extends WindowsNamedPipeConnector {

    protected RandomAccessFile pipe;
    protected InputStream is;
    protected OutputStream os;

    public WindowsNamedPipeClientConnector(final CWindowsNamedPipeClientConnector cWindowsNamedPipeClientConnector) {
        super(cWindowsNamedPipeClientConnector.pipeName);
        checkOperatingSystem();
    }

    @Override
    public OutputStream getOutputStream() throws IOException {
        return os;
    }

    @Override
    public InputStream getInputStream() throws IOException {
        return is;
    }

    @Override
    public void close() throws IOException {
        if (is != null) {
            is.close();
        }
        is = null;

        if (os != null) {
            os.close();
        }
        os = null;

        if (pipe != null) {
            pipe.close();
        }
        pipe = null;
    }

    @Override
    public void connect() throws IOException {
        close();
        pipe = new RandomAccessFile("\\\\.\\pipe\\" + pipeName, "rw");
        is = new RandomAccessFileToInputStream(pipe);
        os = new RandomAccessFileToOutputStream(pipe);
    }

    @Override
    protected void finalize() throws Throwable {
        super.finalize();
        close();
    }
}
