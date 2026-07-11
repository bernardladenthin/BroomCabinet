// @formatter:off
/**
 * Copyright 2016 Bernard Ladenthin bernard.ladenthin@gmail.com
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *    http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 */
// @formatter:on
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
