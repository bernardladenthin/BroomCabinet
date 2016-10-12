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

import com.sun.jna.platform.win32.Guid;
import com.sun.jna.platform.win32.WinDef;

/**
 *
 * @author Bernard Ladenthin bernard.ladenthin@gmail.com
 */
public class JCPUThrottle implements Runnable {

    private final PowrProfJNA profJNA = new PowrProfJNA(PowrProf.INSTANCE);
    private final Kernel32JNA kernel32JNA = new Kernel32JNA(Kernel32.INSTANCE);

    @Override
    public void run() {
        Guid.GUID activeScheme = profJNA.jna_PowerGetActiveScheme();
        System.out.println(activeScheme.toGuidString());

        profJNA.jna_PowerWriteACValueIndex(activeScheme, PowrProfJNA.SUB_PROCESSOR, PowrProfJNA.PROCTHROTTLEMIN, new WinDef.DWORD(1));
        profJNA.jna_PowerWriteACValueIndex(activeScheme, PowrProfJNA.SUB_PROCESSOR, PowrProfJNA.PROCTHROTTLEMAX, new WinDef.DWORD(60));
        profJNA.jna_PowerWriteDCValueIndex(activeScheme, PowrProfJNA.SUB_PROCESSOR, PowrProfJNA.PROCTHROTTLEMIN, new WinDef.DWORD(1));
        profJNA.jna_PowerWriteDCValueIndex(activeScheme, PowrProfJNA.SUB_PROCESSOR, PowrProfJNA.PROCTHROTTLEMAX, new WinDef.DWORD(60));

        int acProcThrottleMin = profJNA.jna_PowerReadACValueIndex(activeScheme, PowrProfJNA.SUB_PROCESSOR, PowrProfJNA.PROCTHROTTLEMIN);
        int acProcThrottleMax = profJNA.jna_PowerReadACValueIndex(activeScheme, PowrProfJNA.SUB_PROCESSOR, PowrProfJNA.PROCTHROTTLEMAX);
        int dcProcThrottleMin = profJNA.jna_PowerReadDCValueIndex(activeScheme, PowrProfJNA.SUB_PROCESSOR, PowrProfJNA.PROCTHROTTLEMIN);
        int dcProcThrottleMax = profJNA.jna_PowerReadDCValueIndex(activeScheme, PowrProfJNA.SUB_PROCESSOR, PowrProfJNA.PROCTHROTTLEMAX);

        SYSTEM_POWER_STATUS systemPowerStatus = kernel32JNA.jna_GetSystemPowerStatus();
        System.out.println("acProcThrottleMin: " + acProcThrottleMin);
        System.out.println("acProcThrottleMax: " + acProcThrottleMax);
        System.out.println("dcProcThrottleMin: " + dcProcThrottleMin);
        System.out.println("dcProcThrottleMax: " + dcProcThrottleMax);

        System.out.println("systemPowerStatus: " + systemPowerStatus);

        if (systemPowerStatus.isAcConnected()) {
            System.out.println("AC is connected.");
        }
    }

    public static void main(String[] args) {
        JCPUThrottle jcpuThrottle = new JCPUThrottle();
        jcpuThrottle.run();
    }
}
