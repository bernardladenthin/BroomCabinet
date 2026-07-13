<!--
SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# GPS logging endpoint

A small server-side **PHP + MySQL** receiver for the Android
[**GPSLogger**](https://gpslogger.app/) app. The phone posts each location to a
URL; the endpoint stores it and can hand the track back as **JSON**, **CSV** or
**GPX**.

```
GPSLogger (Android)  --GET/POST lat,lon,...-->  gps-endpoint.php  -->  MySQL (gpstracker)
map / tool           <--CSV / GPX / JSON-------  gps-endpoint.php  <--  MySQL
```

## Client setup (GPSLogger app)

In GPSLogger → *Custom URL*, set the URL (the app substitutes the `%…` tokens):

```
http://example.com/gps-endpoint.php?p&usertoken=YOURTOKEN&lat=%LAT&lon=%LON&desc=%DESC&sat=%SAT&alt=%ALT&spd=%SPD&acc=%ACC&dir=%DIR&prov=%PROV&time=%TIME&batt=%BATT&aid=%AID&ser=%SER
```

`p` marks it as a point to store; `usertoken` groups points into one track.

| Param | Meaning | Param | Meaning |
|-------|---------|-------|---------|
| `lat` / `lon` | latitude / longitude | `dir` | direction |
| `alt` | altitude | `prov` | provider (gps/network) |
| `spd` | speed | `time` | timestamp |
| `acc` | accuracy | `batt` | battery |
| `sat` | satellites | `aid` / `ser` | Android id / serial |

## Read the track back

| Request | Returns |
|---------|---------|
| `gps-endpoint.php?usertoken=YOURTOKEN` | latest point as JSON |
| `gps-endpoint.php?usertoken=YOURTOKEN&getAsCsv=1` | full track as CSV |
| `gps-endpoint.php?usertoken=YOURTOKEN&getAsGpx=1` | full track as GPX (import into maps) |

## Table

Create it once (only while `$enableCreateAndDrop` is `true`):

```
gps-endpoint.php?createTable=1
```

`gpstracker` columns: `id, usertoken, lat, lon, desc, sat, alt, spd, acc, dir,
prov, time, stime (server time), batt, aid, ser`.

## ⚠️ Security — read before deploying

This is illustrative, **not production-ready**:

* **Credentials** are placeholders (`localhost` / `mydb` / `dbuser` /
  `CHANGE_ME`). Use your own and keep real secrets out of version control
  (env vars / a git-ignored config).
* **`$enableCreateAndDrop` defaults to `false`** here on purpose. If you enable
  it, remember that `?dropTable=1` / `?createTable=1` come straight from the
  request — with it on, anyone can **drop your table**. Enable it only to
  bootstrap, then turn it back off (or protect it).
* **No authentication.** `usertoken` is the only key — anyone who knows a token
  can read or append to that track. Put it behind auth/HTTPS for anything real.
* **Output escaping.** SQL uses prepared statements (values are safe), but the
  GPX/JSON output echoes stored values without escaping — run
  `htmlspecialchars()` on fields like `desc`/`prov` before emitting XML to avoid
  injection.
