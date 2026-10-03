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
| `fixity_test.py` | the library, including independent references for every digest and the S3 multipart ETag, damage that keeps its date, an index from PyMirror, and a path longer than 300 characters |
| `pyfixity_test.py` | the command line end to end, including that the manifests check out the way `sha256sum -c` would |
| `privacy_test.py` | refuses drive letters, keys, e-mail addresses and home directories in this project |

Standard library only; no dependencies. Works on Windows and on POSIX.

    python pyfixity.py index  D:\data\photos --index D:\data-state\photos.csv
    python pyfixity.py verify D:\data\photos --index D:\data-state\photos.csv --older-than 90

## One read, four digests

Every file is read **once**, and that read produces SHA-256, SHA-1, MD5 and CRC32. SHA-256 is the
strong one; the other three are there because somebody else speaks them — Backblaze B2 records a
SHA-1, the Internet Archive publishes MD5, RAR and ZIP keep a CRC32 per member. Reading a file
four times would mean four passes over the disk, which is the slow part; four digests in one
pass cost CPU that a disk leaves idle anyway.

When the part sizes of an S3 multipart upload are known (`--parts`), the same read also produces
that upload's ETag — the MD5 of the part MD5s — so a cloud copy that has no whole-file checksum
can still be compared without downloading it.

## Two records, kept apart on purpose

| | where | what | changes when |
|---|---|---|---|
| **index** | `--index FILE`, best **outside** the tree | CSV: size, mtime, all four digests, ETag and part sizes, time of the last successful check | every check |
| **manifests** | `.sha256sum` `.sha1sum` `.md5sum` `.sfv` at the root of the tree | the standard formats of `sha256sum`, `sha1sum`, `md5sum` and RHash / QuickSFV | only when content changes |

The manifests are what other tools already read: OpenHashTab and TeraCopy check them by
double-click, `sha256sum -c .sha256sum` and `md5sum -c .md5sum` work unchanged, and they outlive
this project. Because they change only with the content, they can be uploaded or synced with the
tree without a new version after every check.

The index carries what the manifests cannot: the date of the last check, the part layout, and the
size and mtime that make the next run fast. Its first columns are `path,size,mtime_ns,sha256`,
named as PyMirror names them, so tools that read PyMirror's index read this one too — and
`read_index` reads a PyMirror index as one whose other digests are not known yet.

**No file describes itself.** The manifests never list themselves, the index or its state file.
A manifest containing its own checksum could never be right. The index, which lives elsewhere,
does list the manifests — so a copy of them in a backup can be checked like any other file.

## What a run does

`index` re-reads only files whose size or modification time moved, or for which a digest is
missing. With `--force` it reads everything — and a file whose size and time did **not** move but
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
lives in one place: `PyB2Verify` moves its local side onto this library next, adding only the part
layouts B2 reports, and `PyMirror` can follow — its manifests already have the same names and
formats, and its index the same leading columns.

## Tests

    python fixity_test.py
    python pyfixity_test.py
    python privacy_test.py
