# ECC memory — checking and detecting errors

## Is ECC error-correction active?

```bat
wmic memphysical get memoryerrorcorrection
```

| Value | Meaning |
|-------|---------|
| 0 | Reserved |
| 1 | Other |
| 2 | Unknown |
| 3 | None |
| 4 | Parity |
| 5 | Single-bit ECC |
| 6 | Multi-bit ECC |
| 7 | CRC |

## Where ECC errors show up (Windows)

Windows logs memory/hardware errors through **WHEA** (Windows Hardware Error
Architecture).

* **Event Viewer** → *Windows Logs → System*
* **Source:** `WHEA-Logger`

| Event ID | Meaning | Typical detail fields |
|----------|---------|-----------------------|
| **19** | *"A corrected hardware error has occurred."* — a **corrected** error (CE / single-bit "soft" error). Logged as **Warning**. | Reported by component: `Processor Core` · Error Source: `Corrected Machine Check` · Error Type: `Cache Hierarchy Error` |
| **18** | *"A fatal hardware error has occurred."* — an **uncorrected** error (UE / multi-bit "hard" error). | Reported by component: `Processor Core` · Error Source: `Machine Check Exception` · Error Type: `Bus/Interconnect Error` · `Processor APIC ID` |

Filter the System log by source `WHEA-Logger` to count them. Opening an event's
**Details** tab shows more; `ErrorType 9` there means a *memory hierarchy error*.

## Interpretation notes

* ECC **corrects** single-bit errors (CE) and only **detects** two-bit errors
  (UE) — two-bit errors cannot be corrected. A UE should ideally halt the system
  with a `WHEA_UNCORRECTABLE_ERROR` bugcheck (BSOD).
* An MCE (Machine Check Exception) means the CPU detected a hardware problem, but
  it can be triggered by ECC-protected CPU caches (L1/L2/L3) too — not
  necessarily the DIMMs — so a "Corrected Machine Check" alone does not prove the
  RAM is the source.
* On some consumer platforms (e.g. early AMD AM4/Ryzen) Windows does not report
  ECC as *enabled*, so it logs generic MCE/WHEA warnings instead of proper ECC
  memory-error events — ECC can still be working at the hardware level.

## Detecting errors on Linux

The kernel EDAC subsystem logs corrected (CE) and uncorrected (UE) counts. You
can deliberately provoke errors to confirm ECC is live, e.g. tighten memory
timings and stress RAM:

```bash
sudo apt-get install stress
stress --vm 50 --vm-bytes 256M   # ~12.8 GB of heavy RAM usage
```

Corrected errors appear as `CE`, uncorrected as `UE` in the logs.

---

*Background distilled from a 2017 "ECC Memory & AMD's Ryzen" deep-dive article;
technical facts only.*
