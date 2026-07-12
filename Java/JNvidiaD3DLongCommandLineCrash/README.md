# JNvidiaD3DLongCommandLineCrash

A minimal Java reproducer and crash analysis for a **hard process termination
inside NVIDIA's Direct3D user-mode driver** (`nvd3dumx.dll`) that fires when a
Java process is launched with a **command line longer than ~260 characters** and
then initializes the Java 2D **Direct3D** pipeline (e.g. by creating a Swing
window).

> Reproduced August 2017, but the analysis is general. The project name may
> change.

## TL;DR — most probable root cause

During Direct3D adapter initialization, the NVIDIA D3D user-mode driver copies a
process-identifying string (the command line and/or a path derived from it) into
a fixed **`MAX_PATH` = 260-byte** buffer using a **bounds-checked "secure" CRT
function** (`*_s`, e.g. `strcpy_s`/`sprintf_s`). Because this Java launch's
command line exceeds 260 characters, the length check **fails and calls the CRT
invalid-parameter handler**, which does `__fastfail(FAST_FAIL_INVALID_ARG)` and
**kills the process**.

It is **not** an exploitable memory-corruption bug — the guard fires *correctly*.
It's a **robustness defect**: the driver assumes every process command line/path
fits in `MAX_PATH`, which Windows does not guarantee (command lines may be up to
32,767 chars). Disabling Java's Direct3D pipeline avoids the driver call entirely.

## Reproduce

- [`src/main/java/Main.java`](src/main/java/Main.java) — waits 15 s, then
  `new JFrame("Test")` forces AWT/Java 2D to initialize the **Direct3D** pipeline,
  then prints `success`.
- [`run.bat`](run.bat) — launches `java.exe` with a classpath whose first entry
  is `.main` followed by ~270 digits — i.e. a **> 260-character** `-cp` argument.
  Without the D3D pipeline the same launch is fine; the commented
  `rem -Dsun.java2d.d3d=false` is the workaround.

To trigger it you need: an NVIDIA GPU + that era's driver, a **> ~260-char
command line**, and code that initializes the D3D pipeline (any AWT/Swing window).
Shortening the classpath, or adding `-Dsun.java2d.d3d=false`, both avoid the crash.

## Environment (from the dumps / DLL)

| | |
|---|---|
| OS | Windows 10 1607, build **14393** (x64) |
| GPU driver | **NVIDIA 385.08** — `nvd3dumx.dll` file version `23.21.13.8508`, "NVIDIA WDDM D3D Driver, Version 385.08" |
| Hardware | hybrid **Intel + NVIDIA** laptop |
| JVM | OpenJDK 8 (`1.8.0.111` fastdebug), also `jdk1.8.0_66` |
| CRT | `msvcr100.dll` (VC++ 2010 runtime) |

### Faulting driver binary — `nvd3dumx.dll`

Version-resource and identity of the exact DLL that fast-fails (from the copy
captured for this project):

| Field | Value |
|---|---|
| File / product version | `23.21.13.8508` |
| Description | NVIDIA WDDM D3D Driver, Version 385.08 |
| Company | NVIDIA Corporation |
| Internal / original name | `NVD3DUM` / `NVD3DUM.DLL` |
| Copyright | © 2017 NVIDIA Corporation |
| Size | 18,275,080 bytes |

Checksums (so the specific binary can be identified without shipping it):

| Algorithm | Digest |
|---|---|
| CRC32 | `1D83CF5C` |
| MD5 | `4D3BF138E297B69C556798D16391CFA1` |
| RIPEMD-160 | `57678A3E3C3A2B4C29483F064BB17158898BAEE8` |
| SHA-1 | `34F10FC435C3236E1187CB6818008D9C61E62FD1` |
| SHA-256 | `255FA7F018DE9E4084475FA4175C641F950A4B47B48934808745458599435D12` |
| SHA-512 | `C850E43086312810DC09AAF4D23C31006414766BE5832AB2913CFF51649C0CD05DB1D1E5730CB5CA5DA602868FF0307805865F711DC8902E9EE65C1C51E35214` |
| SHA3-224 | `1446E99427823A11215853DE31BB3052EE926061749D214A8A2D6616` |
| SHA3-256 | `E898C9DCB1EA1ACB3C550480BE511AEEA4FA3060DA9849052BFBD746FFB0AA04` |
| SHA3-384 | `62F917794590DD27AD009BC4F4B147DCE2369D42B156806356AF4082BD6BAA65A1ADE96759D310F8A6B2196F468B6630` |
| SHA3-512 | `80B01DE72461DB2637004EB08338E6C6706213C8AE08B973199B9CE59CCFFC329A332344DD2001063C1576610FE6A16AB97D4C71146CF67039BE4FC3914907CE` |

## Crash signature

From the WinDbg `.ecxr` (see the raw dump text and screenshots that were captured
for this project):

```
(2dfc.3680): Security check failure or stack buffer overrun - code c0000409
nvd3dumx!QueryOglResource+0x251a93:
00007ffe`ddd3c503 cd29            int     29h            ; __fastfail

rip=00007ffeddd3c503 ... r15=0000000000000104   ; r15 = 0x104 = 260 = MAX_PATH
```

**Call stack** (top of the faulting thread) — AWT initializes D3D, which enters
the NVIDIA driver via `OpenAdapter`, which then fast-fails:

```
awt!D3DPipelineManager::CreateInstance / InitD3D
  d3d9!Direct3DCreate9 → CEnum → InternalDirectDrawCreate → FetchDirectDrawData
    d3d9!CreateDeviceLHDDI
      nvldumdx!OpenAdapter12
        nvd3dumx!OpenAdapter
          … (internal nvd3dumx functions) …
            __fastfail (int 29h)   ← crash
```

## What the disassembly actually shows

The bytes around the faulting `int 29h` are the **MSVC C-runtime fail-fast
sequence**, not a raw /GS stack-cookie failure:

```asm
mov  ecx, 17h          ; 23 = PF_FASTFAIL_AVAILABLE
call ...               ; IsProcessorFeaturePresent(PF_FASTFAIL_AVAILABLE)
test eax, eax
je   fallback
mov  ecx, 5            ; 5 = FAST_FAIL_INVALID_ARG
int  29h               ; __fastfail(FAST_FAIL_INVALID_ARG)   ← crash
fallback:
mov  edx, 0C0000417h   ; STATUS_INVALID_CRUNTIME_PARAMETER
...                    ; raise the exception manually if fastfail unavailable
```

- Subcode **`ecx = 5` = `FAST_FAIL_INVALID_ARG`**, and the fallback loads
  **`0xC0000417` = `STATUS_INVALID_CRUNTIME_PARAMETER`** — the exact signature of
  the CRT's `_invalid_parameter` handler, which the **"secure" `*_s` CRT string
  functions** call when a destination buffer is too small.
- WinDbg reports the generic `c0000409` because *every* `int 29h` fast-fail
  surfaces as `STATUS_STACK_BUFFER_OVERRUN`; that name is
  [misleading](https://devblogs.microsoft.com/oldnewthing/20230731-00/?p=108505) —
  it really means "program self-triggered abnormal termination". The real reason
  is the subcode, here `5` (invalid arg), i.e. a **bounds check that failed**, not
  an unbounded overflow. (Adversarial verification of the "unbounded `strcpy`"
  theory refuted it.)

## Why 260

`r15 = 0x104 = 260 = MAX_PATH`. A local Windows path is
`drive:\…<NUL>`, capped at `MAX_PATH`
([MS Learn](https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation)).
But `CreateProcess` command lines can be up to **32,767** chars
([Old New Thing](https://devblogs.microsoft.com/oldnewthing/20031210-00/?p=41553)),
so a driver sizing a command-line/path buffer at `MAX_PATH` is making an unsafe
assumption — which is exactly what breaks here.

## Mitigations

1. **Keep the command line / classpath under ~260 characters.** (Directly avoids
   the over-length copy.)
2. **`-Dsun.java2d.d3d=false`** — disable Java 2D's Direct3D pipeline so the JVM
   never calls the NVIDIA D3D driver. Oracle documents this as the remedy for
   buggy Direct3D drivers
   ([Java 2D flags](https://docs.oracle.com/javase/8/docs/technotes/guides/2d/flags.html)).
   Must be set **at launch**, before Java 2D initializes
   ([JDK-8111822](https://bugs.openjdk.org/browse/JDK-8111822)).
3. **`-Dsun.java2d.opengl=true`** — use the OpenGL pipeline instead of Direct3D
   (alternative acceleration path).
4. **Update the NVIDIA driver** (385.08 is from Aug 2017).

## Not a security vulnerability

The `/GS`-flavoured code name is misleading; the driver's own bounds check fired
and terminated the process — no attacker-controlled corruption. It is a
reliability bug, distinct from `CVE-2017-0313` (an NVIDIA **kernel-mode**
`DxgkDdiSubmitCommandVirtual` overflow in the 375.70 driver).

## Related public reports (same DLL / crash family)

The `nvd3dumx.dll` Direct3D fast-fail is a well-known crash family — often in the
same `QueryOglResource` function — but a web search (July 2026) found **no public
report that identifies the `>260`-char command line / `MAX_PATH` bounds check as
the trigger**. The closest existing reports describe the same symptom with
different (or unknown) causes; the length-based root cause here appears to be
otherwise undocumented.

- Mozilla — [Bugzilla #1294748](https://bugzilla.mozilla.org/show_bug.cgi?id=1294748) — crashes in `nvd3dumx.dll` with `QueryOglResource` on the stack (Firefox; same fault location, different trigger)
- NVIDIA Developer Forums — [DirectDraw crash in nvd3dumx.dll](https://devtalk.nvidia.com/default/topic/1009227/directx-and-direct-compute/directdraw-crash-in-nvd3dumx-dll/)
- NVIDIA GeForce Forums — [Java app crashes on exit, nvd3dumx.dll, Windows 10](https://www.nvidia.com/en-us/geforce/forums/discover/247774/java-app-crashes-on-exit-nvd3dumx-dll-windows-10/)

## References

- Oracle — [System Properties for Java 2D](https://docs.oracle.com/javase/8/docs/technotes/guides/2d/flags.html) (`sun.java2d.d3d`, `sun.java2d.opengl`)
- OpenJDK — [JDK-8111822](https://bugs.openjdk.org/browse/JDK-8111822) (D3D + AWT instability; set the flag before init)
- Microsoft — [MAX_PATH / path limits](https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation)
- Raymond Chen — [command-line length limit (32,767)](https://devblogs.microsoft.com/oldnewthing/20031210-00/?p=41553), [misleading `STATUS_STACK_BUFFER_OVERRUN`](https://devblogs.microsoft.com/oldnewthing/20230731-00/?p=108505)
- Software Verify — [fast-fail codes](https://www.softwareverify.com/blog/fail-fast-codes/) (`int 29h`, subcodes, `0xC0000409`)

## Appendix — raw WinDbg output

The full debugger output captured for this crash (dump metadata and the `.ecxr`
register state that the analysis above is derived from):

<details>
<summary>WinDbg dump analysis (<code>.ecxr</code>)</summary>

```
Microsoft (R) Windows Debugger Version 10.0.15063.468 AMD64
Copyright (c) Microsoft Corporation. All rights reserved.

Loading Dump File [helper\javaw.dmp]
User Mini Dump File with Full Memory: Only application data is available

Symbol search path is: srv*
Executable search path is:
Windows 10 Version 14393 MP (8 procs) Free x64
Product: WinNt, suite: SingleUserTS
10.0.14393.206 (rs1_release.160915-0644)
Machine Name:
Debug session time: Fri Aug  4 14:04:48.000 2017 (UTC + 2:00)
System Uptime: 0 days 3:18:12.657
Process Uptime: 0 days 0:00:45.000
.......................................................
This dump file has an exception of interest stored in it.
The stored exception information can be accessed via .ecxr.
(2dfc.3680): Security check failure or stack buffer overrun - code c0000409 (first/second chance not available)
*** ERROR: Symbol file could not be found.  Defaulted to export symbols for nvd3dumx.dll -
nvd3dumx!QueryOglResource+0x251a93:
00007ffe`ddd3c503 cd29            int     29h

0:026> .ecxr
rax=0000000000000001 rbx=0000000000000000 rcx=0000000000000005
rdx=0000000000000000 rsi=0000000000000000 rdi=0000000000000000
rip=00007ffeddd3c503 rsp=0000000016fac060 rbp=0000000000000000
 r8=0000000000000000  r9=0000000000000000 r10=00003e700557b103
r11=00000000176b32f8 r12=00007ffede290920 r13=0000000000000000
r14=0000000000000000 r15=0000000000000104
iopl=0         nv up ei pl nz na pe nc
cs=0033  ss=002b  ds=0000  es=0000  fs=0000  gs=0000             efl=00000202
nvd3dumx!QueryOglResource+0x251a93:
00007ffe`ddd3c503 cd29            int     29h
```

</details>
