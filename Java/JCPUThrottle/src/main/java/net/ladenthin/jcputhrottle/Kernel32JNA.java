// SPDX-FileCopyrightText: 2016 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jcputhrottle;

import com.sun.jna.Native;

/**
 * @author Bernard Ladenthin bernard.ladenthin@gmail.com
 */
public class Kernel32JNA {

    private final Kernel32 kernel32;

    public Kernel32JNA(Kernel32 kernel32) {
        this.kernel32 = kernel32;
    }

    public SYSTEM_POWER_STATUS jna_GetSystemPowerStatus() {
        SYSTEM_POWER_STATUS systemPowerStatus = new SYSTEM_POWER_STATUS();
        int retval = Kernel32.INSTANCE.GetSystemPowerStatus(systemPowerStatus);
        if (retval == 0) {
            int lastError = Native.getLastError();
            // https://msdn.microsoft.com/en-us/library/windows/desktop/ms681381.aspx
            throw new RuntimeException("GetSystemPowerStatus returns an error: " + getErrorCodeAsString(lastError));
        }
        return systemPowerStatus;
    }

    public static String getErrorCodeAsString(int lastError) {
        return lastError + " " + getErrorCodeAsHexString(lastError);
    }

    public static String getErrorCodeAsHexString(int lastError) {
        return "(0x" + Integer.toHexString(lastError) + ")";
    }
}
