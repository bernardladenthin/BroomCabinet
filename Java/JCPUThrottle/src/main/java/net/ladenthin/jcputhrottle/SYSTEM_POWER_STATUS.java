// SPDX-FileCopyrightText: 2016 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jcputhrottle;

import com.sun.jna.Structure;

import java.util.ArrayList;
import java.util.List;

/**
 * @author Bernard Ladenthin bernard.ladenthin@gmail.com
 * @see <a href="http://msdn2.microsoft.com/en-us/library/aa373232.aspx">MSDN</a>
 */
public class SYSTEM_POWER_STATUS extends Structure {

    public byte ACLineStatus;
    public byte BatteryFlag;
    public byte BatteryLifePercent;
    public byte SystemStatusFlag;
    public int BatteryLifeTime;
    public int BatteryFullLifeTime;

    @Override
    protected List<String> getFieldOrder() {
        ArrayList<String> fields = new ArrayList<String>();
        fields.add("ACLineStatus");
        fields.add("BatteryFlag");
        fields.add("BatteryFullLifeTime");
        fields.add("SystemStatusFlag");
        fields.add("BatteryLifePercent");
        fields.add("BatteryLifeTime");
        return fields;
    }

    /**
     * The AC power status.
     */
    public String getACLineStatusAsString() {
        switch (ACLineStatus) {
            case (0):
                return "Offline";
            case (1):
                return "Online";
            default:
                return "Unknown status";
        }
    }

    /**
     * The system status.
     */
    public String getSystemStatusFlagAsString() {
        switch (SystemStatusFlag) {
            case (0):
                return "Battery saver is off.";
            case (1):
                return "Battery saver on. Save energy where possible.";
            default:
                return "Unknown status";
        }
    }

    /**
     * The battery charge status.
     */
    public String getBatteryFlagAsString() {
        switch (BatteryFlag) {
            case (0):
                return "The battery is not being charged and the battery capacity is between 66 and 33 percent";
            case (1):
                return "High - the battery capacity is at more than 66 percent";
            case (2):
                return "Low - the battery capacity is at less than 33 percent";
            case (4):
                return "Critical - the battery capacity is at less than five percent";
            case (8):
                return "Charging";
            case ((byte) 128):
                return "No system battery";
            default:
                return "Unknown status - unable to read the battery flag information";
        }
    }

    /**
     * The percentage of full battery charge remaining.
     */
    public String getBatteryLifePercentAsString() {
        return isBatteryPercentValid() ? String.valueOf(BatteryLifePercent) : "Unknown";
    }

    /**
     * The number of seconds of battery life remaining.
     */
    public String getBatteryLifeTimeAsString() {
        return (BatteryLifeTime == -1) ? "Unknown or connected to AC power" : String.valueOf(BatteryLifeTime);
    }

    /**
     * The number of seconds of battery life when at full charge.
     */
    public String getBatteryFullLifeTimeAsString() {
        return (BatteryFullLifeTime == -1) ? "Unknown or connected to AC power" : String.valueOf(BatteryFullLifeTime);
    }

    /**
     * Returns true if AC power is connected, false otherwise.
     *
     * @return boolean
     */
    public boolean isAcConnected() {
        return ACLineStatus == 1;
    }

    /**
     * Returns true if battery saver is on, false otherwise.
     *
     * @return boolean
     */
    public boolean isBatterySaverOn() {
        return SystemStatusFlag == 1;
    }

    /**
     * Returns true if battery is present, false otherwise.
     *
     * @return boolean
     */
    public boolean isBatteryPresent() {
        switch (BatteryFlag) {
            case (0):
                return true;
            case (1):
                return true;
            case (2):
                return true;
            case (4):
                return true;
            case (8):
                return true;
            case ((byte) 128):
                return false;
            default:
                return false;
        }
    }

    /**
     * Returns true if battery percent is valid, false otherwise.
     *
     * @return boolean
     */
    public boolean isBatteryPercentValid() {
        return BatteryLifePercent != (byte) 255;
    }

    /**
     * Returns the battery life percent.
     *
     * @return integer
     */
    public int getBatteryLifePercent() {
        return BatteryLifePercent;
    }

    public int getBatteryLifePercentAndNegativeForInvalidValue() {
        if (isBatteryPercentValid()) {
            return getBatteryLifePercent();
        } else {
            return -1;
        }
    }

    @Override
    public String toString() {
        return "SYSTEM_POWER_STATUS{" +
                "ACLineStatus=" + getACLineStatusAsString() +
                ", BatteryFlag=" + getBatteryFlagAsString() +
                ", BatteryLifePercent=" + getBatteryLifePercentAsString() +
                ", SystemStatusFlag=" + getSystemStatusFlagAsString() +
                ", BatteryLifeTime=" + getBatteryLifeTimeAsString() +
                ", BatteryFullLifeTime=" + getBatteryFullLifeTimeAsString() +
                '}';
    }
}
