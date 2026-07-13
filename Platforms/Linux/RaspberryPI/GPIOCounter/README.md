<!--
SPDX-FileCopyrightText: 2016 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# GPIO counter

Counts falling edges on a GPIO pin (e.g. the impulse output of an energy meter,
10000 impulses/kWh), stores the per-minute count in an RRD database and can graph
it. `gpiocounter.py` uses GPIO4 as input and blinks an LED on GPIO17 per pulse.

## requirements

Raspberry Pi OS with:

* **`RPi.GPIO`** — usually preinstalled; otherwise
  `sudo apt-get install python-rpi.gpio`.
* **`rrdtool`** — required; the script calls `/usr/bin/rrdtool` to create/update
  and graph the database:

  ```bash
  sudo apt-get install rrdtool
  ```

On a fresh install it also helps to run `sudo raspi-config` (expand the
filesystem, then reboot) and update the system with
`sudo apt-get update && sudo apt-get full-upgrade`.

## add to cron
start the gpiocounter script on start
```bash
crontab -l | { cat; echo "@reboot python /home/pi/gpiocounter.py &"; } | crontab -
```

create a graph every day
```bash
crontab -l | { cat; echo "@daily bash /home/pi/gpiocountergraphdaily.sh &"; } | crontab -
```

## optional: server-side upload & web chart
Instead of (or in addition to) the local RRD graph, `gpiocounter.py` can POST each
value to a web endpoint. See [`server-example/`](server-example/) for a sanitized
example receiver (PHP + MySQL) and a browser chart.

## data storage (RRD)
`gpiocounter.py` stores the per-minute count in a round-robin database
(`gpiocounter.rrd`, `--step 60`) with three retention tiers, so old data is kept
at coarser resolution:

| Resolution | Kept for |
|------------|----------|
| 1 minute | 1 hour |
| 5 minutes | 6 months |
| 1 hour | 5 years |

## wiring

A phototransistor (e.g. Osram LPT 80A) on **GPIO4** watches the pulse LED of the
energy meter; an indicator LED on **GPIO17** blinks on each pulse.

```text
+------------------------------+
|        Raspberry Pi          |
|                              |
|  3V3                 pin 1 o-+----[ 1 MΩ ]----+
|                              |                |
|  GPIO4 / BCM4        pin 7 o-+----------------+---- C
|                              |                     |\
|                              |       light  ---->  | >  P1
|                              |                     |/   phototransistor
|                              |                      E
|                              |                      |
|  GND                 pin 6 o-+----------------------+-------------------+
|                              |                                          |
|  GPIO17 / BCM17     pin 11 o-+----[ 500 Ω ]---- A|>|K ---- LED --------+
|                              |
+------------------------------+

A = anode, K = cathode
```

Or the two branches on their own:

```text
Phototransistor input
=====================

3.3 V ----[ 1 MΩ ]----+---- GPIO4
                       |
                       C
                     |/
          light ---> |    P1
                     |\
                       E
                       |
                      GND


Indicator LED
=============

GPIO17 ----[ 500 Ω ]---- A|>|K ---- GND
                             LED
```

| Raspberry Pi connection | Connects to |
|-------------------------|-------------|
| 3.3 V, physical pin 1 | one side of the 1 MΩ resistor |
| GPIO4, physical pin 7 | other side of the 1 MΩ resistor and the phototransistor collector |
| GND, physical pin 6 | phototransistor emitter and LED cathode |
| GPIO17, physical pin 11 | 500 Ω resistor, then the LED anode |

The program uses **BCM numbering** — GPIO4 is the falling-edge input, GPIO17 the
LED output. The input is **active-low**: light pulls GPIO4 toward ground (each
falling edge = one pulse); the 1 MΩ resistor otherwise pulls GPIO4 up to 3.3 V.

## circuit notes

From a review of this wiring (values assume a 3.3 V Pi):

* **LED branch (GPIO17, 500 Ω) — fine.** Depending on the LED's forward voltage
  it draws ≈1–3 mA (≈2.6 mA red, ≈1 mA blue), well within the Pi's GPIO output
  spec, and it only lights ~0.5 ms per pulse (tiny duty cycle). Use
  **680 Ω–1 kΩ** for a dimmer indicator / more margin.
* **Input pull-up (GPIO4, 1 MΩ) — safe but not robust.** It only sources ~3.3 µA,
  so it can't overload anything, but it is too high-impedance for a reliable
  digital input: the Pi's input leakage is up to 5 µA (older SoCs) / 10 µA
  (Pi 4), so 1 MΩ can't guarantee a solid HIGH. Rule of thumb
  `R_pull ≤ (Vcc − V_IH) / I_leak` caps it around **340 kΩ (older Pi) / 130 kΩ
  (Pi 4)**. **Prefer a 47 kΩ–100 kΩ pull-up** (100 kΩ a good default, 68 kΩ more
  robust). This isn't a speed problem — at ~44 pulses/s the RC time constant is
  only tens of µs even at 1 MΩ — it's about **noise immunity**: a high-impedance
  node false-triggers on stray light, leakage and long-wire pickup. An optional
  **100 pF–1 nF** cap from GPIO4 to GND helps.
* **Sensor type matters.** `BPW34` / `BPW46` are **PIN photodiodes, not
  phototransistors** — don't treat them as a drop-in for an LPT80A/SFH309-class
  phototransistor. A photodiode is better fed through a transimpedance amp or a
  comparator / Schmitt-trigger (e.g. 74LVC1G14) than straight into GPIO.
* **Debounce.** The code's 1 ms `bouncetime` is fine for a clean optical signal;
  **2–5 ms** is more robust when it's noisy — a second line of defence, not a
  substitute for a sane input stage.

## example
* Output graph: [`example/graph.png`](example/graph.png) (linear) and
  [`example/graph-logarithmic.png`](example/graph-logarithmic.png) (log scale).
  The horizontal rules mark power thresholds (50 W/h … 10 kW/h).

