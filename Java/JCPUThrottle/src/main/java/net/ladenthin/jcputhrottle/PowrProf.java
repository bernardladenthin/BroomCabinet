// SPDX-FileCopyrightText: 2016 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jcputhrottle;

import com.sun.jna.Native;
import com.sun.jna.Pointer;
import com.sun.jna.platform.win32.WinDef;
import com.sun.jna.platform.win32.WinReg;
import com.sun.jna.win32.StdCallLibrary;

/**
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
