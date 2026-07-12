// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.connector.jna;

import com.sun.jna.Native;
import com.sun.jna.Pointer;
import com.sun.jna.Structure;
import com.sun.jna.ptr.IntByReference;
import com.sun.jna.win32.StdCallLibrary;

import java.util.Arrays;
import java.util.List;

public interface Kernel32 extends StdCallLibrary {
    Kernel32 INSTANCE = (Kernel32) Native.loadLibrary("kernel32", Kernel32.class);
    Kernel32 SYNC_INSTANCE = (Kernel32) Native.synchronizedLibrary(INSTANCE);

    class SECURITY_ATTRIBUTES extends Structure {
        public int nLength = size();
        public Pointer lpSecurityDescriptor;
        public boolean bInheritHandle;

        @Override
        protected List getFieldOrder() {
            return Arrays.asList(new String[]{"nLength", "lpSecurityDescriptor", "bInheritHandle"});
        }
    }

    public static class LPOVERLAPPED extends Structure {
        @Override
        protected List getFieldOrder() {
            return null;
        }
    }

    /**
     * Creates an instance of a named pipe and returns a handle for subsequent pipe operations.
     * http://msdn.microsoft.com/en-us/library/windows/desktop/aa365150%28v=vs.85%29.aspx
     * <pre>
     * HANDLE WINAPI CreateNamedPipe(
     *   _In_      LPCTSTR lpName,
     *   _In_      DWORD dwOpenMode,
     *   _In_      DWORD dwPipeMode,
     *   _In_      DWORD nMaxInstances,
     *   _In_      DWORD nOutBufferSize,
     *   _In_      DWORD nInBufferSize,
     *   _In_      DWORD nDefaultTimeOut,
     *   _In_opt_  LPSECURITY_ATTRIBUTES lpSecurityAttributes
     * );
     * </pre>
     * @param lpName The unique pipe name.
     * @param dwOpenMode The open mode.
     * @param dwPipeMode The pipe mode. 
     * @param nMaxInstances nMaxInstances
     * @param nOutBufferSize The number of bytes to reserve for the output buffer. 
     * @param nInBufferSize The number of bytes to reserve for the input buffer.
     * @param nDefaultTimeOut The default time-out value, in milliseconds.
     * @param lpSecurityAttributes A pointer to a SECURITY_ATTRIBUTES structure.
     * @return
     */
    Pointer CreateNamedPipeA(String lpName, int dwOpenMode, int dwPipeMode,
                             int nMaxInstances, int nOutBufferSize, int nInBufferSize,
                             int nDefaultTimeOut, SECURITY_ATTRIBUTES lpSecurityAttributes
    );

    boolean ConnectNamedPipe(Pointer handle, LPOVERLAPPED overlapped);

    boolean DisconnectNamedPipe(Pointer handle);

    boolean FlushFileBuffers(Pointer handle);

    /**
     * Closes an open object handle.
     * http://msdn.microsoft.com/en-us/library/windows/desktop/aa365150%28v=vs.85%29.aspx
     * <pre>
     * BOOL WINAPI CloseHandle(
     *   _In_  HANDLE hObject
     * );
     * </pre>
     * @param handle
     * @return If the function succeeds, the return value is nonzero.
     */
    boolean CloseHandle(Pointer handle);

    boolean ReadFile(Pointer hFile, Pointer lpBuffer,
                     int nNumberOfBytesToRead, IntByReference lpNumberOfBytesRead,
                     LPOVERLAPPED lpOverlapped
    );

    boolean WriteFile(Pointer hFile, Pointer lpBuffer,
                      int nNumberOfBytesToRead, IntByReference lpNumberOfBytesRead,
                      LPOVERLAPPED lpOverlapped
    );
}
