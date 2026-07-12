# 🖥️ Windows CPU Power Optimization Guide
A quick reference to restore and optimize your Windows power settings for better CPU performance.
## ⚡ 1. Restore the Default Power Plan
**Step 1: Run CMD as Administrator**  
Run: `cmd`  
Then enter: `powercfg -restoredefaultschemes`  
**Step 2: Re-select the 'High Performance' Plan**  
Press `Win + R`, type `powercfg.cpl`, then select **High Performance**
## 🚀 2. Force CPU Speedup (Disable Connected Standby)
**Registry Modification:**  
Open `regedit`  
Navigate to: `HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\Power`  
Create a new **DWORD (32-bit) Value**  
Name: `CsEnabled`  
Value: `0`  
Restart your computer
## ⚙️ 3. Adjust Processor Power Management Settings
Go to: `Control Panel → Power Options → Change plan settings → Change advanced power settings`  
Expand: `Processor power management`  
Set:  
- `Minimum processor state`: `5–20%`  
- `Maximum processor state`: `80–100%`
## 🧩 4. Update Drivers and Firmware
- Update `chipset drivers` from your motherboard manufacturer’s site  
- Update `BIOS/UEFI firmware`  
- Uninstall third-party power managers (e.g. `Dell Power Manager`, `Lenovo Vantage`)
## 🧪 5. Use Built-in Power Troubleshooting Tools
**Generate a power report:**  
Run: `powercfg -energy`  
**List all power plans:**  
Run: `powercfg -list`
## 🧠 6. Unlock Hidden Boost Modes via Registry
**Step 1:** Open `regedit`  
Press `Win + R`, type `regedit`, and press Enter
**Step 2:** Navigate to: 
```
HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\Power\PowerSettings\54533251-82be-4824-96c1-47b60b740d00\be337238-0d82-4146-a960-4f3749d470c7
```
**Step 3:** Modify `Attributes`  
Double-click `Attributes` and change the value from `1` to `2`
**Step 4:** Enable Boost Mode Control  
- Search for **Edit Power Plan** and open it  
- Click **Change advanced power settings**  
- Expand **Processor power management** → **Processor performance boost mode**  
- You can now configure boost mode for **On Battery** and **Plugged in**
## 🛠️ 7. Change Power Mode via Windows 11 Settings
**Step 1:** Open **Settings** (`Win + I`)  
**Step 2:** Click on **System**  
**Step 3:** Click on **Power** (or **Power & battery**) on the right  
**Step 4:** Under **Power mode**, choose one of the following:
- **Best Power Efficiency** – Saves energy by reducing device performance when possible  
- **Balanced** – ⚠️ **Recommended for advanced tweaks to work properly** (unlocks full power settings menu)  
- **Best Performance** – Maximizes performance but may hide certain power options
Windows will now manage power consumption based on your selected mode.  
> 💡 For full access to processor controls (like boost mode or min/max states), **Balanced** or **High Performance** must be selected.
> 💡 This guide is intended for advanced users who want full control over CPU performance and power behavior.
