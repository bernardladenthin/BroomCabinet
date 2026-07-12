# Scheduled tasks

## Flush the disk write cache every 15 minutes

Runs the Sysinternals [`sync.exe`](https://learn.microsoft.com/sysinternals/downloads/sync)
utility (flushes cached file data to disk) on a fixed interval — useful on
machines that are hard-powered-off or that you want to keep flushed regularly.

`sync.exe` must be present on the machine; the example uses
`C:\Windows\System32\sync.exe` — adjust the path if you keep it elsewhere.

### Command line (recommended)

Create the task from an elevated prompt. Running as `SYSTEM` means no password
is stored, it runs whether or not a user is logged on, and there is no console
window:

```bat
schtasks /Create /TN "Sync" /TR "C:\Windows\System32\sync.exe" /SC MINUTE /MO 15 /RU SYSTEM /RL HIGHEST
```

* `/SC MINUTE /MO 15` — trigger every 15 minutes
* `/RU SYSTEM` — run under the SYSTEM account (no stored password, runs headless)
* `/RL HIGHEST` — run with highest privileges

Manage it afterwards:

```bat
schtasks /Run    /TN "Sync"    :: run once now
schtasks /Query  /TN "Sync" /V :: show details
schtasks /Delete /TN "Sync" /F :: remove
```

### GUI equivalent (Task Scheduler)

1. `taskschd.msc` → **Create Task…** (not the basic wizard).
2. **General:** name `Sync`; select *Run whether user is logged on or not* and
   *Run with highest privileges*. (Using the SYSTEM account avoids storing a
   password.)
3. **Triggers → New:** *At startup*, tick *Repeat task every* **15 minutes** for
   *Indefinitely*.
4. **Actions → New:** *Start a program* → `C:\Windows\System32\sync.exe`.
5. **Conditions:** untick *Start the task only if the computer is on AC power* if
   it should also run on battery.

> Tip: to run a **batch file** on a schedule without a flashing console window,
> run it under the SYSTEM account (as above), or launch it via
> `cmd /c start "" /min "C:\path\to\file.bat"`.
