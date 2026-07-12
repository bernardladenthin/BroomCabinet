package de.fraunhofer.fokus.jackpot.connector;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;

public interface Connector {

    public OutputStream getOutputStream() throws IOException;

    public InputStream getInputStream() throws IOException;

    public void close() throws IOException;

    public void connect() throws IOException;
}
