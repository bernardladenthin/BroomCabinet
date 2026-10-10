<!--
SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# PyFixity — checksums for a directory tree, made once and checked forever

A disk does not tell anybody when a bit flips. A file keeps its name, its size and its date, and
the only way to know its content is still what it was is to have written that down once and to
read the file again later. Digital preservation calls the first part *fixity information* and the
second a *fixity check*. This project is both, for one directory tree.

| | |
|---|---|
| `fixity.py` | the library: one-read hashing, the tree walk, the index, the manifests, comparison and verification runs. Standard library only |
| `pyfixity.py` | the command line: `index`, `verify`, `manifests` |
| `fixity_test.py` | the library, including independent references for every digest and the S3 multipart ETag, the ETag default and `.s3etag`, the same result at every thread count, damage that keeps its date, an index from PyMirror, and a path longer than 300 characters |
| `pyfixity_test.py` | the command line end to end, including that the manifests check out the way `sha256sum -c` would |
| `privacy_test.py` | refuses drive letters, keys, e-mail addresses and home directories in this project |

Standard library only; no dependencies. Works on Windows and on POSIX.

    python pyfixity.py index  D:\data\photos
    python pyfixity.py verify D:\data\photos --older-than 90

## Every folder carries its own record

Six files at the root of the folder, and nothing about it anywhere else:

| | |
|---|---|
| `.sha256sum` `.sha1sum` `.md5sum` `.sfv` | the digests, in the formats every checking tool reads |
| `.s3etag` | the S3 / B2 ETags of the large files (below) |
| `.fixity-state.csv` | sizes, modification times, the last successful check of each file, and the run state — **no digest the manifests hold** |

So the folder is self-contained. Copied, synced or uploaded, its record goes along, and on
another machine the next run reads only what changed there (a copy that did not keep the
modification times is read once, to be safe). Nothing is recorded twice: a digest stays in the
state file only while an interrupted run has not written the manifests yet, and an ETag only when
it was taken over a layout other than the one `.s3etag` lists. A run that finds nothing new does
not rewrite the state file, so it does not hand a sync tool a new version.

Taking a folder over costs no reading:

- **manifests but no state file** (made before it existed, or copied without it): a file not
  modified since the manifests were written is trusted; a newer one is read;
- **an index of an earlier version inside the tree** (`.fixity-index.csv` and its `.state`) is
  taken over with its last checks, and removed once the state file holds everything;
- **an index kept elsewhere** can seed it the same way (`seed=` in the library; PyB2Verify uses it
  to move off `checksums/local`).

`--index FILE` still keeps the record outside the tree instead, for a tree that must not be
written to apart from its manifests.

## One read, four digests — and the ETag the cloud will report

Every file is read **once**, and that read produces SHA-256, SHA-1, MD5 and CRC32. SHA-256 is the
strong one; the other three are there because somebody else speaks them — Backblaze B2 records a
SHA-1, the Internet Archive publishes MD5, RAR and ZIP keep a CRC32 per member. Reading a file
four times would mean four passes over the disk.

**By default the same read also produces the S3 multipart ETag**, for every file larger than
200 MiB, over parts of 100 000 000 bytes. A large file uploaded to B2 or S3 in parts gets *no*
whole-file checksum there — only that ETag, the MD5 of the part MD5s — and no whole-file digest
can be turned into it afterwards: it depends on where the parts were cut. Finding that out after
2.5 TB had been hashed and uploaded meant reading all of it again; computed along, it costs one
more MD5 over bytes that are being read anyway.

The default is the rule real uploads follow: B2's recommended part size and Cyberduck's fixed
behaviour ("files larger than 200MB are split into 100MB chunks"). Every one of 3 572 multipart
files across fifteen real buckets was cut exactly so, and on the first tree it was tried on, all
22 ETags matched what B2 reports. `--s3-part-size` and `--s3-cutoff` adjust it for another
uploader, `--s3-part-size 0` switches it off, and `--parts FILE` gives the real layouts of an
existing cloud copy, which take precedence.

## Fast because the CPU, not the disk, was the limit

Measured on 16 cores: SHA-256 1482, SHA-1 1584, MD5 630 and CRC32 2106 MB/s each — but all of
them one after the other (MD5 twice, for the file and for the ETag's parts) only 202 MB/s, and a
real index run read 72 GB at 178 MB/s with the disk waiting. So:

| | |
|---|---|
| `--hash-threads N` (default 5) | the digests of each file are spread over N threads; every chunk goes to each of them, so the data is still read once. The two MD5s never share a thread. Files under 8 MiB stay in one |
| `--threads N` (default 1) | N files at once. `index` finishes them **in their order** — a file done early waits for the one before it — so the output and an interrupted index look exactly as with one |

The same 72.3 GB, verified against the index: 416 s in one thread (the old way), **128 s** with
`--hash-threads 5`, **69 s** with `--threads 2 --hash-threads 5` (1.0 GB/s) — every digest
identical. `hashlib` and `zlib` release the GIL on large buffers, which is why threads help here.

## Two records, kept apart on purpose

| | where | what | changes when |
|---|---|---|---|
| **state file** | `.fixity-state.csv` at the root of the tree (the default) | CSV: size, mtime, time of the last successful check; run state in `#` lines at the top | a check that found or confirmed something |
| **index** | `--index FILE`, outside the tree | the same, plus all four digests, ETag and part sizes; run state in a `.state` file beside it | every check |
| **manifests** | `.sha256sum` `.sha1sum` `.md5sum` `.sfv` at the root of the tree | the standard formats of `sha256sum`, `sha1sum`, `md5sum` and RHash / QuickSFV | only when content changes |
| **`.s3etag`** | beside them | the ETags of the files above the cutoff, in `md5sum`'s layout, under a header naming the part size | only when content changes |

`.s3etag` exists because the index usually lives in a work directory and the manifests travel
with the tree: uploaded beside the data, it lets the cloud copy be checked from anywhere, with
nothing but a listing — even when the index is long gone. It is written only when every file
above the cutoff has an ETag over exactly the part size its header names; an ETag over another
layout would read as a mismatch on the far side.

The manifests are what other tools already read: OpenHashTab and TeraCopy check them by
double-click, `sha256sum -c .sha256sum` and `md5sum -c .md5sum` work unchanged, and they outlive
this project. Because they change only with the content, they can be uploaded or synced with the
tree without a new version after every check.

The index carries what the manifests cannot: the date of the last check, the part layout, and the
size and mtime that make the next run fast. Its first columns are `path,size,mtime_ns,sha256`,
named as PyMirror names them, so tools that read PyMirror's index read this one too — and
`read_index` reads a PyMirror index as one whose other digests are not known yet.

**No file describes itself.** The five manifests never list themselves, the state file or an index.
A manifest containing its own checksum could never be right. The index, which lives elsewhere,
does list the manifests — so a copy of them in a backup can be checked like any other file.

## What a run does

`index` re-reads only files whose size or modification time moved, or for which a digest or the
ETag is missing — so the first run with the ETag default reads each file above the cutoff once
more, and never again. With `--force` it reads everything — and a file whose size and time did **not** move but
whose content did is not a new version, it is damage: its saved digests are kept, it is reported,
and the exit status is 1.

`verify` reads the files against the index and reports what is new, gone, resized, re-dated or
damaged. A file that fails loses its *last checked* time, so every later run reads it again until
somebody looks at it. Long runs can be interrupted and resumed (`--resume`), limited to what has
not been checked for a while (`--older-than 90`), spread over threads, and narrowed to part of the
tree (`--include` / `--exclude` as regex on the relative path, `--min-size` inclusive and
`--max-size` exclusive). Progress is saved every 30 seconds.

A manifest is written only when the run is complete and every file has that digest. A manifest
that quietly leaves files out reads as a check that was made; an empty one passes `md5sum -c` on
nothing. Neither is written.

## Things it deals with that are easy to get wrong

| | |
|---|---|
| paths of 260 characters and more | every access goes through the `\\?\` prefix on Windows, independent of the machine's LongPathsEnabled setting |
| one name, two spellings | paths are compared in Unicode NFC |
| spaces and odd characters in names | `sha256sum` lines are split on the first ` *`, `.sfv` lines from the right, as each format requires |
| a backslash or newline in a name | escaped the way GNU coreutils escape it (impossible on Windows, kept correct anyway) |
| Ctrl+C on Windows | waits use a timeout, so an interruption is seen, saved and reported |

## Meant to be the one implementation

Hashing a tree and checking it again is what `PyB2Verify` does for its local side and what
`PyMirror` does for its archives, each with its own code. This project exists so that the logic
lives in one place. `PyB2Verify` builds its local side on this library, adding only the part
layouts B2 reports; `PyMirror`'s packer already calls `pyfixity.py index`, so its archives get
`.s3etag` and the speed without a change of their own; the rest of `PyMirror` can follow — its manifests already have the same names and formats,
and its index the same leading columns.

## Tests

    python fixity_test.py
    python pyfixity_test.py
    python privacy_test.py
