// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.connector;

import com.sun.jna.Native;
import com.sun.jna.Pointer;
import net.ladenthin.jackpot.configuration.CWindowsNamedPipeServerConnector;
import net.ladenthin.jackpot.connector.jna.Kernel32;
import net.ladenthin.jackpot.wrapper.RandomAccessFileToInputStream;
import net.ladenthin.jackpot.wrapper.RandomAccessFileToOutputStream;

import java.io.*;

/**
 * Created by bernard on 13.05.14.
 */
public class WindowsNamedPipeServerConnector extends WindowsNamedPipeConnector {

    /**
     * Size for the buffer used in defining pipes for Windows in bytes. The buffer is used
     * to copy from memory to an {@link java.io.OutputStream OutputStream} such as
     * {@link net.pms.io.BufferedOutputFile BufferedOutputFile}.
     */
    private static final int BUFSIZE = 500000;

    private Pointer pipeHandle;

    protected String pipeName;
    protected RandomAccessFile pipe;
    protected InputStream is;
    protected OutputStream os;

    public WindowsNamedPipeServerConnector(CWindowsNamedPipeServerConnector cWindowsNamedPipeServerConnector) {
        super(cWindowsNamedPipeServerConnector.pipeName);
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
        if (pipeHandle != null) {
            Kernel32.INSTANCE.CloseHandle(pipeHandle);
            pipeHandle = null;
        }
    }

    @Override
    public void connect() throws IOException {
        close();
        //parameter dwOpenMode: PIPE_ACCESS_DUPLEX (0x00000003)
        //parameter dwPipeMode: PIPE_TYPE_BYTE (0x00000000)
        pipeHandle = Kernel32.INSTANCE.CreateNamedPipeA(pipeName, 3, 0, 255, BUFSIZE, BUFSIZE, 0, null);

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
