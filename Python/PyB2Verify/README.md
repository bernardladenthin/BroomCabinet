<!--
SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# PyB2Verify — proving that a Backblaze B2 backup still holds the same bytes

A backup is only as good as the last time somebody checked it. B2 stores a checksum next to each
file, but it computed that checksum once, at upload, and nothing re-reads the bytes against it.
A local disk does not check its files either. So two questions stay open for years: *does the
bucket hold what the disk holds?* and *does either of them still hold what it held a year ago?*

These tools answer both, and **never upload, change or delete anything in B2**.

| | |
|---|---|
| `b2verify.py` | the command line: index each side, compare them, re-read either side against its index |
| `b2lib.py` | the B2 side without the network: what B2 states about a file, its checksum file, how a difference is explained, unfinished uploads, and the one-time move of first-version local checksums onto PyFixity |
| `b2lib_test.py` | covers `b2lib.py`, including that move — adopted without reading, and damage since then still reported |
| `b2verify_test.py` | drives `hash-local`, `verify-local` and `compare` end to end through the real command line, on a throwaway tree with a flipped byte |
| `privacy_test.py` | refuses drive letters, keys, e-mail addresses and home directories in this project |

**The local side is [PyFixity](../PyFixity/README.md)**, imported from beside this project: one read
of each file gives SHA-256, SHA-1, MD5, CRC32 and — with the part sizes `hash-b2` recorded — the S3
ETag; the result is PyFixity's index and the manifests `.sha256sum .sha1sum .md5sum .sfv` at the
root of each bucket directory, which OpenHashTab and `sha256sum -c` read. The manifests are
uploaded with the data; both sides of every comparison leave them out, because they describe a
bucket rather than belong to it.

Needs `b2sdk` and `boto3` (`requirements.txt`) for the commands that talk to B2. `--help`, both
libraries and every test run on the standard library alone.

## Setup

    python -m venv .venv
    .venv\Scripts\python -m pip install -r requirements.txt

Create an **application key with read access only** in the B2 console. A master key works for the
B2 API but is refused by B2's S3 endpoint, which this tool needs for large files (below) — and a
key that can delete has no business in a verification tool.

The configuration is a properties file **outside this repository**; it holds the key:

    keyId=<application key id>
    applicationKey=<application key>
    localRoot=D:/backup                     one directory per bucket below it; needed only by
                                            check, hash-local and verify-local
    stateDir=D:/backup-state                optional; default: the directory of this file
    reportDir=D:/backup-state/reports       optional; default: <stateDir>/reports
    exclude=Thumbs.db,desktop.ini,*.lnk     optional; glob patterns that are never compared
    flatBuckets=example-flat-bucket         optional; buckets uploaded without their directories
    ignoreDirs=scratch                      optional; directories below localRoot that are no bucket

The checksum and report directories may live inside `localRoot`; they are recognised by their
configured path and never taken for a bucket. Pass the file with `--config FILE`, or set
`B2VERIFY_CONFIG` once in a small wrapper script.

### Verifying B2 from somewhere else

`hash-b2`, `verify-b2` and `compare` need no local data and no `localRoot` — only the key and the
checksum files. So the download-heavy `verify-b2 --download` can run on a machine close to the
bucket that holds nothing but a copy of `checksums/b2/`:

    python b2verify.py verify-b2 --download --threads 16 --resume --config b2.properties

Copy `checksums/b2/` back afterwards: it now carries the time of each successful check, and a
real SHA-1 for every file that was confirmed through its ETag. Use a key of its own on that
machine, read-only, and revoke it when the run is done.

Before the first B2 request the tool checks, within 15 seconds, that a TLS handshake with the B2
API completes. Without that check b2sdk retries a dead connection for minutes and the run sits
silent — which is exactly what happened the first time this was tried from a data centre.

### TCP connects but TLS to B2 never completes

That machine reached every B2 storage endpoint by TCP, in every region, and no TLS handshake ever
finished — while other HTTPS sites, including Backblaze's own web site, worked. It was not DNS, not
the CA bundle, not the TLS version and not the key: the handshake timed out with certificate
checking switched off, and with any server name.

A packet capture during one attempt shows the cause:

    tcpdump -n -i <interface> host <B2 address>
    openssl s_client -connect <B2 address>:443 -servername <B2 host name>

    > SYN, mss 8960                          the interface had jumbo frames (MTU 9000)
    < SYN-ACK, mss 1460
    > ClientHello, 219 bytes                 acknowledged by B2
    < seq 4345:4955, 610 bytes               only the LAST piece of B2's reply arrives;
                                             bytes 1-4344, three full 1500-byte packets, never do

A **path-MTU black hole**: a hop on the way back carries less than 1500 bytes, and the "fragmentation
needed" message that would make B2 send smaller packets never reaches it. Sites behind large CDNs
work because those send smaller packets anyway; B2's storage servers do not.

The fix is to make the client *announce* a smaller segment size in its SYN, so that B2 sends small
packets from the start. On the system where this was found (AIX 7.3), what did and did not work:

| attempt | result |
|---|---|
| `setsockopt(TCP_MAXSEG)` in the client | ignored for the SYN |
| a route with its own MTU (`route add ... -mtu 1400`) | limits only what is *sent*; the SYN still announces the interface MTU |
| per-interface `ifconfig <if> tcp_mssdflt 1360` alone | ignored while path-MTU discovery is on |
| `ifconfig <if> tcp_mssdflt 1360` **and** `no -o tcp_pmtu_discover=0` | **works**: SYN announces 1360, the handshake completes |

Both settings are runtime-only and are undone with `no -o tcp_pmtu_discover=1` and
`ifconfig <if> tcp_mssdflt 0`. Lowering the interface MTU to 1400 should work as well, but touches
all traffic on that interface. On Linux the equivalent knob is the per-route `advmss`
(`ip route add <B2 network> via <gateway> advmss 1360`), or an MSS clamp in the firewall — not
tested here.

## Two sides, two indexes, one comparison

Each side is indexed on its own, so either can be refreshed or re-read without touching the other:

    python b2verify.py hash-b2                    what B2 states: SHA-1, else S3 ETag and part sizes
    python b2verify.py hash-local                 local checksums, re-reading only what changed
    python b2verify.py compare                    the two indexes against each other, 1:1

    python b2verify.py verify-local               re-read every local file against its index
    python b2verify.py verify-b2                  the bucket listing against its index
    python b2verify.py verify-b2 --download       stream every file from B2 and hash it

    python b2verify.py check                      quick and live: names and sizes only

What B2 states lands in `<stateDir>/checksums/b2/<bucket>.tsv` (size, time, SHA-1, ETag, part
sizes, file id, last check); the local side in PyFixity's index `<stateDir>/checksums/local/<bucket>.csv`
(all four digests, ETag, part sizes, last check) plus the four manifests in the bucket directory;
and every check writes one Markdown report per bucket.

A local `<bucket>.tsv` from the first version of this tool is moved onto the index the first time
it is needed, **without reading any file**: an entry is adopted while the file keeps its recorded
size and time. It has only SHA-1, so the next `hash-local` reads every file once more to add SHA-256,
MD5 and CRC32 — checking the old SHA-1 on the way. The old file stays as `<bucket>.tsv.migrated`.

Run `hash-b2` **before** `hash-local`: the part sizes come from B2, and the local file is cut the
same way while it is read anyway.

`compare` works on what `hash-b2` recorded, not on the live bucket — so after an upload, run
`hash-b2` again first. When a differing local file is newer than the B2 record, `compare` says so:
*the B2 checksums are from …; N differing local file(s) are newer than that — run hash-b2*.

## Large files have no SHA-1 in B2, and still get checked

A file uploaded in parts usually carries no SHA-1 at all. Its S3 ETag is the MD5 of the
concatenated part MD5s, suffixed with the part count. `hash-b2` asks B2's S3 endpoint for that
ETag and for the part sizes; `hash-local` then cuts the local file at the same boundaries. One
read produces both the SHA-1 and the ETag, so an 18 GB archive is verified without downloading it.

`verify-b2 --download` checks the other direction — that B2 still *delivers* what its metadata
claims. The download is streamed straight into the hasher; no temporary file is written. A file
confirmed through its ETag gets its real SHA-1 recorded, so it is comparable by SHA-1 from then on.

## Silent damage is reported, never written over

`hash-local` re-reads only files whose size or modification time moved. With `--force` it reads
everything — and if a file has the same size and the same time but different bytes, that is not
a new version, it is damage: the saved checksum is **kept**, the file is reported, and the exit
status is 1. `verify-local` then says whether the copy in B2 still matches the saved checksum,
i.e. whether the file can be restored from there.

A file that fails a check loses its *last checked* time, so every later run reads it again until
somebody looks at it.

## Long runs: threads, resume, age, selection

    --threads 8                 files in parallel (default: local 1, B2 4); one B2 connection each
    --resume                    continue an interrupted run where it stopped
    --older-than 90             only files not successfully checked for 90 days
    --include '\.mp4$'          relative path, regex, repeatable, case-insensitive
    --exclude '^Recordings/'
    --min-size 1M               inclusive
    --max-size 1M               exclusive: --max-size 1M and --min-size 1M split a bucket exactly

Progress is written every 30 seconds, so an interruption costs at most that much. A single
download stream is often slow (a few MB/s); threads help with many files, not with one large one.
A whole collection is better verified in portions — one bucket per night with `--older-than 90`.

## Things it deals with that are easy to get wrong

| | |
|---|---|
| paths of 260 characters and more | every local access goes through the `\\?\` prefix on Windows, so the result does not depend on the machine's LongPathsEnabled setting |
| one name, two spellings | names are compared in Unicode NFC; B2 and a Windows disk do not always agree |
| buckets uploaded without directories | `flatBuckets` / `--flat` compares file names only and reports a name that occurs twice instead of guessing |
| folders created in the B2 web interface | the `.bzEmpty` placeholder is not a file and is ignored |
| a B2 file replaced by a new upload | B2 files are immutable; a new file id means new content, so nothing is carried over from the old one |
| an upload cut off by a dropped connection | a multi-part upload stays open in B2: its parts are stored and billed, but it appears in no listing. `hash-b2` and `verify-b2` list them, as *leftover* when a finished file of that name exists and *NOT IN B2* when none does. A read-only key cannot cancel them; a lifecycle rule on the bucket ("cancel unfinished large files after N days") can |

## Tests

    python b2lib_test.py
    python b2verify_test.py
    python privacy_test.py

No B2 account is needed. The commands that do need one — `hash-b2`, `verify-b2` and `check` — were
run against real buckets of several terabytes while this was written.
