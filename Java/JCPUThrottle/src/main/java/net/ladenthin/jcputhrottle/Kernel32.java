// SPDX-FileCopyrightText: 2016 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jcputhrottle;

import com.sun.jna.Native;
import com.sun.jna.win32.StdCallLibrary;

/**
 * @author Bernard Ladenthin bernard.ladenthin@gmail.com
 */
public interface Kernel32 extends StdCallLibrary {

    Kernel32 INSTANCE = (Kernel32) Native.loadLibrary("Kernel32", Kernel32.class);

    /**
     * Fill the structure.
     */
    int GetSystemPowerStatus(SYSTEM_POWER_STATUS result);
}
