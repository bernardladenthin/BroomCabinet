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
package net.ladenthin.jcputhrottle;

import com.sun.jna.Native;
import com.sun.jna.Pointer;
import com.sun.jna.platform.win32.WinDef;
import com.sun.jna.platform.win32.WinReg;
import com.sun.jna.win32.StdCallLibrary;

/**
 *
 * @author Bernard Ladenthin bernard.ladenthin@gmail.com
 */
public interface PowrProf extends StdCallLibrary {
    PowrProf INSTANCE = (PowrProf) Native.loadLibrary("PowrProf.dll", PowrProf.class);

    WinDef.DWORD PowerGetActiveScheme(
            WinReg.HKEY UserRootPowerKey,
            Pointer ActivePolicyGuid
    );

    WinDef.DWORD PowerReadACValueIndex(
            WinReg.HKEY RootPowerKey,
            Pointer SchemeGuid,
            Pointer SubGroupOfPowerSettingsGuid,
            Pointer PowerSettingGuid,
            WinDef.DWORDByReference AcValueIndex
    );

    WinDef.DWORD PowerReadDCValueIndex(
            WinReg.HKEY RootPowerKey,
            Pointer SchemeGuid,
            Pointer SubGroupOfPowerSettingsGuid,
            Pointer PowerSettingGuid,
            WinDef.DWORDByReference AcValueIndex
    );

    WinDef.DWORD PowerWriteACValueIndex(
            WinReg.HKEY RootPowerKey,
            Pointer SchemeGuid,
            Pointer SubGroupOfPowerSettingsGuid,
            Pointer PowerSettingGuid,
            WinDef.DWORD AcValueIndex
    );

    WinDef.DWORD PowerWriteDCValueIndex(
            WinReg.HKEY RootPowerKey,
            Pointer SchemeGuid,
            Pointer SubGroupOfPowerSettingsGuid,
            Pointer PowerSettingGuid,
            WinDef.DWORD AcValueIndex
    );
}
