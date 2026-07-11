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

import com.sun.jna.platform.win32.Guid;
import com.sun.jna.platform.win32.Kernel32;
import com.sun.jna.platform.win32.WinDef;
import com.sun.jna.ptr.PointerByReference;

import static com.sun.jna.platform.win32.WinError.ERROR_SUCCESS;

/**
 * @author Bernard Ladenthin bernard.ladenthin@gmail.com
 */
public class PowrProfJNA {

    private final PowrProf powrProf;

    // ################################################################################
    // Settings belonging to no subgroup
    public final static Guid.GUID SUB_NONE = new Guid.GUID("fea3413e-7e05-4911-9a71-700331f1c294"); // is alias
    // Require a password on wakeup
    public final static Guid.GUID CONSOLELOCK = new Guid.GUID("0e796bdb-100d-47d6-a2d5-f7d2daa51f51"); // is alias

    // ################################################################################
    // Hard disk
    public final static Guid.GUID SUB_DISK = new Guid.GUID("0012ee47-9041-4b5d-9b77-535fba8b1442"); // is alias
    // Turn off hard disk after
    public final static Guid.GUID DISKIDLE = new Guid.GUID("6738e2c4-e8a5-4a42-b16a-e040e769756e"); // is alias

    // ################################################################################
    // Internet Explorer
    public final static Guid.GUID SUB_INTERNETEXPLORER = new Guid.GUID("02f815b5-a5cf-4c84-bf20-649d1f75d3d8"); // no alias
    // JavaScript Timer Frequency
    public final static Guid.GUID IEJavaScriptTimerFrequency = new Guid.GUID("4c793e7d-a264-42e1-87d3-7a0d2f523ccd"); // no alias

    // ################################################################################
    // Desktop background settings
    public final static Guid.GUID SUB_DESKTOPBACKGROUNDSETTINGS = new Guid.GUID("0d7dbae2-4294-402a-ba8e-26777e8488cd"); // no alias
    // Slide show
    public final static Guid.GUID SLIDESHOW = new Guid.GUID("309dce9b-bef4-4119-9921-a851fb12f0f4"); // no alias

    // ################################################################################
    // Wireless Adapter Settings
    public final static Guid.GUID SUB_WIRELESSADAPTERSETTINGS = new Guid.GUID("19cbb8fa-5279-450e-9fac-8a3d5fedd0c1"); // no alias
    // Power Saving Mode
    public final static Guid.GUID WIRELESSADAPTERPOWERSAVINGMODE = new Guid.GUID("12bbebe6-58d6-4636-95bb-3217ef867c1a"); // no alias

    // ################################################################################
    // Sleep
    public final static Guid.GUID SUB_SLEEP = new Guid.GUID("238C9FA8-0AAD-41ED-83F4-97BE242C8F20"); // is alias
    // Sleep after
    public final static Guid.GUID STANDBYIDLE = new Guid.GUID("29f6c1db-86da-48c5-9fdb-f2b67b1f44da"); // is alias
    // Allow hybrid sleep
    public final static Guid.GUID HYBRIDSLEEP = new Guid.GUID("94ac6d29-73ce-41a6-809f-6363ba21b47e"); // is alias
    // Hibernate after
    public final static Guid.GUID HIBERNATEIDLE = new Guid.GUID("9d7815a6-7ee4-497e-8888-515a05f02364"); // is alias
    // Allow wake timers
    public final static Guid.GUID RTCWAKE = new Guid.GUID("bd3b718a-0680-4d9d-8ab2-e1d2b4ac806d"); // is alias

    // ################################################################################
    // USB settings
    public final static Guid.GUID SUB_USBSETTINGS = new Guid.GUID("2a737441-1930-4402-8d77-b2bebba308a3"); // no alias
    // USB selective suspend setting
    public final static Guid.GUID USB_Selective_Suspend = new Guid.GUID("48e6b7a6-50f5-4782-a5d4-53bb8f07e226"); // no alias

    // ################################################################################
    // Idle Resiliency
    public final static Guid.GUID SUB_IR = new Guid.GUID("2e601130-5351-4d9d-8e04-252966bad054"); // is alias

    // ################################################################################
    // Interrupt Steering Settings
    public final static Guid.GUID SUB_INTSTEER = new Guid.GUID("48672f38-7a9a-4bb2-8bf8-3d85be19de4e"); // is alias

    // ################################################################################
    // Power buttons and lid
    public final static Guid.GUID SUB_BUTTONS = new Guid.GUID("4f971e89-eebd-4455-a8de-9e59040e7347"); // is alias
    // Lid close action
    public final static Guid.GUID LIDACTION = new Guid.GUID("5ca83367-6e45-459f-a27b-476b1d01c936"); // is alias
    // Power button action
    public final static Guid.GUID PBUTTONACTION = new Guid.GUID("7648efa3-dd9c-4e3e-b566-50f929386280"); // is alias
    // Sleep button action
    public final static Guid.GUID SBUTTONACTION = new Guid.GUID("96996bc0-ad50-47ec-923b-6f41874dd9eb"); // is alias
    // Start menu power button
    public final static Guid.GUID UIBUTTON_ACTION = new Guid.GUID("a7066653-8d6c-40a8-910e-a1f54b84c7e5"); // is alias

    // ################################################################################
    // PCI Express
    public final static Guid.GUID SUB_PCIEXPRESS = new Guid.GUID("501a4d13-42af-4429-9fd1-a8218c268e20"); // is alias
    // Link State Power Management
    public final static Guid.GUID ASPM = new Guid.GUID("ee12f906-d277-404b-b6da-e5fa1a576df5"); // is alias

    // ################################################################################
    // Processor power management
    public final static Guid.GUID SUB_PROCESSOR = new Guid.GUID("54533251-82be-4824-96c1-47b60b740d00"); // is alias
    // Minimum processor state
    public final static Guid.GUID PROCTHROTTLEMIN = new Guid.GUID("893dee8e-2bef-41e0-89c6-b55d0929964c"); // is alias
    // System cooling policy
    public final static Guid.GUID SYSCOOLPOL = new Guid.GUID("94d3a615-a899-4ac5-ae2b-e4d8f634367f"); // is alias
    // Maximum processor state
    public final static Guid.GUID PROCTHROTTLEMAX = new Guid.GUID("bc5038f7-23e0-4960-96da-33abaf5935ec"); // is alias

    // ################################################################################
    // Display
    public final static Guid.GUID SUB_VIDEO = new Guid.GUID("7516b95f-f776-4464-8c53-06167f40cc99"); // is alias
    // Dim display after
    public final static Guid.GUID VIDEODIM = new Guid.GUID("17aaa29b-8b43-4b94-aafe-35f64daaf1ee"); // is alias
    // Turn off display after
    public final static Guid.GUID VIDEOIDLE = new Guid.GUID("3c0bc021-c8a8-4e07-a973-6b14cbcb2b7e"); // is alias
    // User annoyance timeout
    public final static Guid.GUID VIDEOANNOY = new Guid.GUID("82dbcf2d-cd67-40c5-bfdc-9f1a5ccd4663"); // is alias
    // Console lock display off timeout
    public final static Guid.GUID VIDEOCONLOCK = new Guid.GUID("8ec4b3a5-6868-48c2-be75-4f3044be88a7"); // is alias
    // Adaptive display
    public final static Guid.GUID VIDEOADAPT = new Guid.GUID("90959d22-d6a1-49b9-af93-bce885ad335b"); // is alias
    // Allow display required policy
    public final static Guid.GUID ALLOWDISPLAY = new Guid.GUID("a9ceb8da-cd46-44fb-a98b-02af69de4623"); // is alias
    // Display brightness
    public final static Guid.GUID VIDEOBRIGHTNESS = new Guid.GUID("aded5e82-b909-4619-9949-f5d71dac0bcb"); // no alias
    // Increase adaptive timeout by
    public final static Guid.GUID VIDEOADAPTINC = new Guid.GUID("eed904df-b142-4183-b10b-5a1197a37864"); // is alias
    // Dimmed display brightness
    public final static Guid.GUID VIDEOBRIGHTNESS_DIM = new Guid.GUID("f1fbfde2-a960-4165-9f88-50667911ce96"); // no alias
    // Enable adaptive brightness
    public final static Guid.GUID ADAPTBRIGHT = new Guid.GUID("fbd9aa66-9553-4097-ba44-ed6e9d65eab8"); // is alias

    // ################################################################################
    // Presence Aware Power Behavior
    public final static Guid.GUID SUB_PRESENCE = new Guid.GUID("8619b916-e004-4dd8-9b66-dae86f806698"); // is alias

    // ################################################################################
    // Multimedia settings
    public final static Guid.GUID SUB_MULTIMEDIASETTINGS = new Guid.GUID("9596fb26-9850-41fd-ac3e-f7c3c00afd4b"); // no alias
    // When sharing media
    public final static Guid.GUID WHENSHARINGMEDIA = new Guid.GUID("03680956-93bc-4294-bba6-4e0f09bb717f"); // no alias
    // When playing video
    public final static Guid.GUID WHENPLAYINGVIDEO = new Guid.GUID("34c7b99f-9a6d-4b3c-8dc7-b6693b78cef4"); // no alias

    // ################################################################################
    // Battery
    public final static Guid.GUID SUB_BATTERY = new Guid.GUID("e73a048d-bf27-4f12-9731-8b2076e8891f"); // is alias
    // Critical battery action
    public final static Guid.GUID BATACTIONCRIT = new Guid.GUID("637ea02f-bbcb-4015-8e2c-a1c7b9c0b546"); // is alias
    // Low battery level
    public final static Guid.GUID BATLEVELLOW = new Guid.GUID("8183ba9a-e910-48da-8769-14ae6dc1170a"); // is alias
    // Critical battery level
    public final static Guid.GUID BATLEVELCRIT = new Guid.GUID("9a66d8d7-4ff7-4ef9-b5a2-5a326ca2a469"); // is alias
    // Low battery notification
    public final static Guid.GUID BATFLAGSLOW = new Guid.GUID("bcded951-187b-4d05-bccc-f7e51960c258"); // is alias
    // Low battery action
    public final static Guid.GUID BATACTIONLOW = new Guid.GUID("d8742dcb-3e6a-4b3c-b3fe-374623cdcf06"); // is alias
    // Reserve battery level
    public final static Guid.GUID BATRESERVELEVEL = new Guid.GUID("f3c5027d-cd16-4930-aa6b-90db844a8f00"); // no alias

    // ################################################################################
    // unknown subgroup
    public final static Guid.GUID UNKNOWN_0000 = new Guid.GUID("29e6fab8-ce22-4a98-9d8b-75fe10526ac7"); // no alias
    // unknown subgroup
    public final static Guid.GUID UNKNOWN_0001 = new Guid.GUID("e276e160-7cb0-43c6-b20b-73f5dce39954"); // no alias
    // unknown subgroup
    public final static Guid.GUID UNKNOWN_0002 = new Guid.GUID("2adaa5b8-1289-467b-a809-b95c40d27b4c"); // no alias

    PowrProfJNA(PowrProf powrProf) {
        this.powrProf = powrProf;
    }

    public Guid.GUID jna_PowerGetActiveScheme() {
        PointerByReference pPowerScheme = new PointerByReference();
        powrProf.PowerGetActiveScheme(null, pPowerScheme.getPointer());
        Guid.GUID guid = new Guid.GUID(pPowerScheme.getValue());
        if (pPowerScheme.getPointer() != null) {
            Kernel32.INSTANCE.LocalFree(pPowerScheme.getPointer());
        }
        return guid;
    }

    public int jna_PowerReadACValueIndex(Guid.GUID schemeGuid, Guid.GUID subGroupOfPowerSettingsGuid, Guid.GUID powerSettingGuid) {
        WinDef.DWORDByReference acValueIndex = new WinDef.DWORDByReference();
        WinDef.DWORD retval = powrProf.PowerReadACValueIndex(null, schemeGuid.getPointer(), subGroupOfPowerSettingsGuid.getPointer(), powerSettingGuid.getPointer(), acValueIndex);
        if (retval.intValue() != ERROR_SUCCESS) {
            throw new RuntimeException("retval.intValue() != ERROR_SUCCESS: " + retval.intValue());
        }
        return acValueIndex.getValue().intValue();
    }

    /**
     * same as {@link #jna_PowerReadACValueIndex(Guid.GUID, Guid.GUID, Guid.GUID)}  but call PowerReadDCValueIndex
     */
    public int jna_PowerReadDCValueIndex(Guid.GUID schemeGuid, Guid.GUID subGroupOfPowerSettingsGuid, Guid.GUID powerSettingGuid) {
        WinDef.DWORDByReference acValueIndex = new WinDef.DWORDByReference();
        WinDef.DWORD retval = powrProf.PowerReadDCValueIndex(null, schemeGuid.getPointer(), subGroupOfPowerSettingsGuid.getPointer(), powerSettingGuid.getPointer(), acValueIndex);
        if (retval.intValue() != ERROR_SUCCESS) {
            throw new RuntimeException("retval.intValue() != ERROR_SUCCESS: " + retval.intValue());
        }
        return acValueIndex.getValue().intValue();
    }

    public void jna_PowerWriteACValueIndex(Guid.GUID schemeGuid, Guid.GUID subGroupOfPowerSettingsGuid, Guid.GUID powerSettingGuid, WinDef.DWORD acValueIndex) {
        WinDef.DWORD retval = powrProf.PowerWriteACValueIndex(null, schemeGuid.getPointer(), subGroupOfPowerSettingsGuid.getPointer(), powerSettingGuid.getPointer(), acValueIndex);
        if (retval.intValue() != ERROR_SUCCESS) {
            throw new RuntimeException("retval.intValue() != ERROR_SUCCESS: " + retval.intValue());
        }
    }

    /**
     * same as {@link #jna_PowerWriteACValueIndex(Guid.GUID, Guid.GUID, Guid.GUID, WinDef.DWORD)} but call PowerWriteDCValueIndex
     */
    public void jna_PowerWriteDCValueIndex(Guid.GUID schemeGuid, Guid.GUID subGroupOfPowerSettingsGuid, Guid.GUID powerSettingGuid, WinDef.DWORD acValueIndex) {
        WinDef.DWORD retval = powrProf.PowerWriteDCValueIndex(null, schemeGuid.getPointer(), subGroupOfPowerSettingsGuid.getPointer(), powerSettingGuid.getPointer(), acValueIndex);
        if (retval.intValue() != ERROR_SUCCESS) {
            throw new RuntimeException("retval.intValue() != ERROR_SUCCESS: " + retval.intValue());
        }
    }
}
