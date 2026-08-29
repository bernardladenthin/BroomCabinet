<!--
SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# mirror — tools for archives that may not survive their maintainer

A threaded mirror for whole HTTP archives and rsync modules, a checksum index that stays current
as a side effect of mirroring, and three tools that use those checksums to answer questions about
what you have. Standard library only; no dependencies.

They exist because the archives below are mostly one person's server, and because the ways a
crawler quietly *fails to copy something* turn out to be far more numerous, and far harder to
notice, than the ways it fails loudly. Most of this file is about the second thing.

| | |
|---|---|
| `mirror.py` | mirrors the archives; writes each one's marker and checksum index |
| `checksums.py` | the same manifest format for a tree that is *not* a mirror |
| `audit.py` | reads any number of manifests; finds duplicates across trees, and files that lie about what they are. **Deletes nothing** |
| `dedupe-docs.py` | deletes an outer copy, but only after re-reading both sides in full |
| `wayback-salvage.py` | recovers a host that is already gone, from the Internet Archive |
| `wedge_test.py` | the termination tests for `mirror.py` |

```
python mirror.py --root /srv/mirror                    all archives, resuming
python mirror.py --root /srv/mirror --archive tuhs     one of them
python mirror.py --root /srv/mirror --verify           check each tree against its marker
python mirror.py --root /srv/mirror --index            refresh the checksum index (no network)
python mirror.py --root /srv/mirror --fix-times        stamp files with their published dates

python checksums.py --root /srv/collection             manifest for a non-mirror tree
python audit.py --index /srv/mirror --index /srv/collection/collection-index.csv
python dedupe-docs.py --root /srv/collection --mirror /srv/mirror
python wedge_test.py
```

Every path is a parameter. None of these tools has a default location for anything, which is the
subject of the next section.

## Where the mirror goes

`--root` names the directory that holds one subdirectory per archive. There is **no default**:
`$MIRROR_ROOT` is consulted next, and after that the working directory — but only if it already
holds mirrors, proved by a completion marker or checksum index in one of its subdirectories.

The tool used to assume its own directory, which was correct only while script and archives sat
in the same place. They no longer do, and inheriting that default would have been wrong in the
one direction that costs something: silently filling whatever directory the script happens to
live in. It also refuses to write into a git working copy unless an empty `.mirror-root` file
there says you mean it.

## What it mirrors

| | Files | Size | Source |
|---|---:|---:|---|
| `bitsavers` | 176 012 | 1 241.5 GB | the computing documentation archive, via `rsync.mirrorservice.org` |
| `ibm-aix` | 190 976 | 702.4 GB | IBM's own AIX distribution tree, including the Toolbox |
| `ps-2.kev009.com` | 94 899 | 332.0 GB | RS/6000, AS/400, S/390 and PS/2 documentation and firmware |
| `vtda` | 29 759 | 234.7 GB | the Vintage Technology Digital Archive, five rsync modules |
| `oss4aix.org` | 184 465 | 208.0 GB | Michael Perzl's AIX open-source builds — RPMs, SRPMs, specs, patches |
| `bull-rpms` | 7 117 | 45.8 GB | Bull Freeware binaries, via the power-devops rescue |
| `ardent-tool` | 23 185 | 23.6 GB | The Ardent Tool of Capitalism — board-level RS/6000 detail |
| `bull-srpms` | 1 873 | 19.2 GB | the sources those binaries were built from |
| `rwth-aachen-ftp` | 10 561 | 10.3 GB | an open directory at RWTH Aachen, including a copy of IBM's PC BBS |
| `tuhs` | 12 139 | 9.3 GB | The Unix Heritage Society — the original UNIX distribution tapes |
| `gsi-collection` | 4 688 | 0.9 GB | GSI Darmstadt's vintage collection |
| `filibeto-aix-lib` | 174 | 0.8 GB | the AIX manual sets IBM no longer serves |
| `aixtools` | 99 | 0.26 GB | AIX software as installp/BFF filesets — **salvaged; the site is gone** |
| **13 archives** | **735 947** | **2 828.8 GB** | |

One deliberate omission: `bits/NetBSD/` inside bitsavers, 606.8 GB of an operating system that is
in no danger whatsoever. It is named in `RSYNC["bitsavers"]["filter"]` rather than left to memory.

### One of them is not a mirror

`aixtools` is listed in `FROZEN`, not in `RSYNC` or the crawler's set, because **its source no
longer exists**. Michael Felt's site published open-source software for AIX as installp/BFF
filesets rather than as RPM — installable without `rpm.rte`, which is what an old AIX needs and
what nothing else here carries. It died between its last capture on 2025-01-14 and 2026-08-29,
when this was checked: `/tools/` answers 404 rather than 403, both vhosts serve Apache's stock
placeholder under one shared ETag, ports 443, 873 and 21 all refuse, and the domain is parked.

What is here came from the Internet Archive via `wayback-salvage.py`: 75 of the 87 filesets that
were ever captured, plus the 19 directory index pages that are now the only record of what each
directory held. 62 of the 85 entries in the operator's own `MD5.checksums` verify bit-identical.

`FROZEN` earns its place as a concept rather than a special case. A completion marker says a run
had nothing outstanding, and the cure for anything missing is another run; here another run cannot
help, and pointing the crawler at the dead host would fetch a tree of 404s and end INCOMPLETE — a
verdict that reads as *we failed* when it means *there is nothing there any more*. So the transfer
is refused with its reason, while `--index` and `--verify` keep working on what was recovered.

This is also the argument of this whole directory arriving once: an archive served by one person,
with no successor, that went away before it was copied.

### The selection rule

Not "everything useful" — *everything that might not be there in ten years*. An archive with a
funded host, a foundation, or a hundred mirrors is not a candidate however useful it is; one
person serving twenty years of scans from a machine under a desk is. Several of these have
already lost a maintainer once:

**Bull** was the rescue that proves the rule. Atos closed `www.bullfreeware.com` on **1 March
2022**; `dl.power-devops.com` is one volunteer's copy made shortly before, and there was no
second. Every file in it carries February 2022 as its date, because that is when the rescue
happened, not when the package was published.

**oss4aix** is effectively *the* package source for AIX 5.3 — nothing else still serves binaries
for that release. Of three advertised download methods only HTTP answers: `ftp://` is silent and
`rsync://public@www.oss4aix.org/public` refuses the connection.

**ibm-aix** is mirrored from `aix.software.ibm.com`, **not** `public.dhe.ibm.com`. Same tree, same
bytes; `index.txt` is 2 911 bytes on both. But `public.dhe.ibm.com` *omits README files from its
directory listings while still serving them* — `aix/README_AIX` answers 200 with 4 012 bytes on
both hosts and appears in the listing on only one. A crawler follows links, so mirroring from the
better-known hostname would have silently dropped every README in the tree: six of them in a
twenty-directory sample, including the 1996 FixDist text that explains what that server was.

**The hardware archives** — bitsavers, vtda, ardent-tool, gsi-collection — are not AIX archives at
all. They are here because an emulator is written against *chips*: the National PC87312 super I/O,
the Intel 82378 PCI-ISA bridge, the AMD PCnet and 53C974, the Cirrus CL-GD5446. Those manuals live
here and in very few other places. `test_equipment/ancot/DSC-202/` is a SCSI bus analyser manual —
the instrument that decodes the wire protocol, and the sort of document that exists nowhere else.

Taken whole, on purpose. A vendor tree cut down to what looks relevant today is not a mirror, and
"that branch is just operational amplifiers" is exactly the judgement that turns out wrong later.

## Ask the operator, not just `robots.txt`

**bitsavers has not permitted bulk HTTP downloading since April 2026.** Its front page says so in
plain words, asking for anonymous rsync instead and explaining why: people were pulling the entire
site through the web interface, and it got worse when LLM scrapers appeared.

`robots.txt` on that host is **empty**, which reads as "no restriction". The restriction is on the
front page, written by a human. This tool crawled the archive over HTTP twice before anyone read
it. **Checking the machine-readable signal is not the same as asking the operator** — for a
one-person archive, the page *is* the policy, and where a site publishes wishes a machine cannot
parse, they belong in `RSYNC[]` or `EXCLUDE[]` by hand.

`WORKERS_BY_ARCHIVE` sets politeness per host and per shape: eight connections for a package
archive, four for a volunteer documentation server, three for a hand-written site — where an HTML
crawl already asks for every page twice, once as a file and once as a listing.

### rsync, and one decision that looks like a mistake

`--delete` is **off**, deliberately. bitsavers warns that names, dates and locations change and
that these are not permalinks, so staying in sync means deleting what was renamed. That is what
keeps a *current* copy. This is a *historical* one, and the two are different objects. The cost is
real — after an upstream rename a file exists here twice and the marker's counts grow — and it is
a decision, not a command line copied off a web page.

`--dry-run` before every filter change. It costs a file list and answers the only question that
matters, how many files and how many bytes, before the change costs hundreds of gigabytes.

## A mirror stays complete

**Nothing inside a mirror is ever deleted as a duplicate** — not against another mirror, and not
against itself. No sorting, no renaming, no normalising of extensions.

The temptation is concrete: of oss4aix's 208 GB only about 85 GB is distinct, because `everything/`
repeats 97 % of `RPMS/`, 93 % of `SRPMS/` and 99 % of both `latest/` and `compatible/`.
Deduplicating would reclaim over 100 GB in an afternoon.

It would also destroy the only question a mirror exists to answer: *what did this archive serve,
and under which path*. `RPMS/gcc/foo.rpm` and `everything/foo.rpm` are two different answers even
when the bytes are identical. That layout belongs to the source, not to us. The same holds between
archives — if two of them carry a file, each is entitled to its own copy.

Files this tool writes into a mirror (marker, index, sums, provenance notes) are not content, and
must be listed in `OWN_FILES` — otherwise every marker becomes wrong the moment the first one is
written, and `--verify` reports a discrepancy on every archive at once.

### Which is why finding duplicates is a reporting job, not a cleanup job

`audit.py` takes any number of manifests — `--index` accepts a file, or a directory it searches
one level deep, so a mirror root loads every archive in it at once — and classifies every group
of identical files by *where the copies sit*:

| | |
|---|---|
| **PROTECTED** | every copy is in a mirror. Never a candidate, not even across two mirrors |
| **CANDIDATE** | at least one copy in a mirror, at least one outside. The outside one is redundant |
| **LOOSE** | no copy in any mirror. A judgement call, not a rule |

A tree counts as protected when its manifest is a mirror's `.mirror-index.csv`. That takes no
configuration and cannot be forgotten on the day it matters.

Doing this from the manifests instead of from the disk changed the answer, not just the runtime.
The previous version walked the trees and matched on **name and size**, because hashing hundreds
of gigabytes to find a handful of matches was not worth the disk pass. It found **5** duplicates
where the manifests find **163** — everything renamed on its way in was invisible to it, and
renaming is precisely what happens to a document that gets filed by hand. One measured example: a
book sitting in a curated `docs/books/` under a long descriptive filename, and the same bytes in a
mirror under the publisher's short one. Name matching cannot see that pair; a hash cannot miss it.

`dedupe-docs.py` is the other half and is deliberately narrow. It proposes from the manifests but
**re-reads both sides in full** before unlinking anything, because a manifest is a cache keyed on
size and mtime — it was right when it was written — and a deletion is not reversible. A file is
removed only when the mirror copy exists and is readable, both sides are the same size, both hash
identically *now*, and that hash still equals what the manifest recorded. Any mismatch, any
unreadable file, any exception: skipped and reported. There is no "close enough" branch.

## Verdicts

A finished mirror carries **`.mirror-complete`** with its source, date, file count and byte count.
While it exists `--fresh` refuses to run, because one absent-minded invocation would delete
hundreds of gigabytes that took days and may not be re-fetchable.

The marker is a **claim, not a receipt**: it is written only when the run had zero unreadable
listings and zero failures, and for an rsync archive the verdict is rsync's own exit code. Two
corollaries that were learned rather than designed:

- **A verdict must not survive its own error log.** One archive ended COMPLETE with 260 files
  missing and every one of them logged, because a branch returned `"skip"` where it meant `"fail"`.
- **Check all, then judge.** `all(verify(n) for n in ...)` short-circuits: one unverifiable archive
  ended the pass and left four mirrors unchecked. A verification that stops at the first problem
  does not verify.

## Checksums

Each mirror carries two more files next to the marker:

| | |
|---|---|
| `.mirror-index.csv` | the master — `path,size,mtime_ns,sha256`, one row per file |
| `.sha256sum` | derived from it, in the format GNU `sha256sum -c` reads |

The `.sha256sum` is the portable artefact and holds nothing extra. The CSV exists for its two
other columns: **size and mtime are what let a re-run skip a file it has already hashed.** Without
them the only way to refresh a manifest is to read everything again; with them an unchanged 702 GB
archive re-indexes in the time it takes to `stat` 190 000 files.

The mtime is compared in **nanoseconds**. Seconds would let a file rewritten inside the same
second keep its old hash.

A mirroring run refreshes the index when it finishes, so re-mirroring keeps the checksums current
as a side effect — whatever the run changed is exactly what gets re-hashed. `--no-index`
suppresses that, and `--index` does it alone, without touching the network.

**This catches what `--verify` cannot.** `--verify` compares file and byte counts, which finds what
went missing or arrived. It cannot see a file whose content changed while its size stayed the same
— and over years and terabytes that is the realistic failure, on archives that are in several
cases the last copy in existence.

## What the tool learned the hard way

Ten defects, each found by measurement rather than reasoning, and every one of them invisible in a
progress bar. They are listed because the next archive will break the tool in some new way, and the
pattern is more useful than the individual fixes.

**A listing matcher counted the wrong row.** A pattern that matched nothing but lighttpd's "Parent
Directory" row counted as a successful parse, suppressed the fallback, and hid **97 % of an
archive — 5.3 GB where 332 GB stood** — without a single error message. A directory that parses to
nothing is indistinguishable from an empty one.

**A crawler mirrors what is linked, not what exists.** The same archive was mirrored from its root,
finished with no unreadable listings, and was marked COMPLETE at 7 826 files. Its front page does
not link `basil.holloway/`, which holds 1 955 PDFs on its own, nor seven subtrees under `rs6000/`
including all 99 machine service guides. Nothing malfunctioned — a directory the crawler never
learns about produces no failure of any kind. **The completeness a mirror can prove is completeness
with respect to its seed.** Only listing the live server and diffing it against the mirror finds
this; `--seed` and the `SEEDS` table exist so that what was found does not live in a shell history.

**A path can be a file and a directory at once on a server, and cannot be both on disk.** A
hand-written page linked a subdirectory *without* a trailing slash — the only signal a crawler has
— so the directory's own index page was fetched and written to disk as a file. **49 files and
7.6 GB hung behind it.** The failures said `FileExistsError` and `FileNotFoundError`, which reads
like a disk problem and is not one. Detected at the cause now: a 301 onto the same path plus a
slash means "that is a directory", so the page it returns is not saved. A scan of all twelve
archives for the same shape checked 76 000 candidates and found no others — which fits, because
generated autoindexes always emit the slash.

Those three defects all struck **the same archive**, and that is not a coincidence: it is the only
one whose front page is maintained by a person rather than by a directory generator. An archive
that grew by hand for twenty years is where a crawler's assumptions break.

**A fix cannot undo what the broken version already wrote.** Seven index pages, saved under
directory names by a buggy run, blocked 260 downloads in the *fixed* run. When a rule changes, ask
what the old rule left on disk.

**Directory listings had no retry.** One transient timeout — and the first run over one archive hit
35 — silently amputates a whole subtree while the run still reports success.

**Raw spaces in URLs.** Generated indexes escape them; hand-made pages do not. One page links
`AS400 Processor Summary.html` unescaped and urllib refuses it outright: **188 failures in the
first 221 files**, better than one in four, silently lost. Only the request is quoted now; the
unencoded URL stays canonical for the local name and the collision key.

**A short measurement described the wrong timescale.** A few seconds per step showed throughput
scaling linearly with connections, so 8 were raised to 16. Over hours: 2.78 MB/s at 8 against
2.88 MB/s at 16, while connection timeouts went from 1 to 23. The cap was on the client, not the
connection. Put back to 8.

**Extrapolated sizes are not measurements.** A 22-vendor sample put one subtree at 44 GB; rsync
said 127.9 GB. The *counts* from a published index were right to two files; the average was wrong
by a factor of three. Ask the archive for its own index before walking it — several publish
`IndexByDate.txt` per category, and sizing two trees took two requests instead of several hundred
directory fetches.

**A filter must name what comes in, not only what stays out.** Naming exclusions on a 1.86 TB
module pulled in 74 GB nobody asked for, because that root has 28 directories and not the six its
front page names.

**Reachability and usefulness are two different tests.** A mirror was chosen because it answered
first: 1.11 MB/s, against 9.29 from the one that answered second.

## Case collisions

NTFS folds case; HTTP paths do not. Two remote files differing only in case land on one local file,
the second overwriting the first, with no error anywhere.

Measured rather than assumed — 0 collisions across 195 067 files in the first two archives, 0 in
the next three, and **4 019 in IBM's tree**, where they are not incidental: `libc_advisory.asc` and
`libC_advisory.asc` are advisories for two *different* libraries, C and C++, and `dce.msg.ES_ES`,
`dce.msg.Es_ES` and `dce.msg.es_ES` are three AIX locales with different codesets.

`NEEDS_CASE_SENSITIVE` names the archives created with the NTFS per-directory case-sensitive flag.
It needs no elevation and is inherited only by directories made **afterwards**, never
retroactively — so it is only ever effective on a fresh root. Proven end-to-end before the real
run: the same subtree produced **1 041 files without the flag and 1 043 with it**.

## Logs and file dates

One log per archive under `<root>/logs/`, named after it, append-only. Three kinds of entry meaning
three different things: `RETRY` is noise, four attempts with a growing wait, almost all recover;
`PERMFAIL` is a 403 or 404, the server's settled answer; **`LISTFAIL` is the one that matters**,
because a listing that could not be read takes its whole subtree with it. Any `LISTFAIL` or `FAIL`
makes the process exit non-zero.

The rsync progress meter is only attached when stdout is a terminal. Redirected to a file it was
36 MB of a line redrawing itself — 494 010 of 494 247 captured lines — so a redirected run gets
`--stats` instead: what was transferred, once, at the end.

Every mirrored file carries the date the **source** publishes, not the date it was copied. New
downloads take it from `Last-Modified`, which is exact to the second and free, since the header
arrives with the response anyway. Mirrors made before that existed were stamped afterwards from the
listings — **2 519 requests instead of 195 000**, because one listing carries the date for all its
files. The price is precision, minutes instead of seconds, which for a twenty-year-old package is
not worth 190 000 requests. The result is a real archive's date profile rather than "everything
made today": the oldest file in the oss4aix mirror is a patch from **30 August 2000**.

## Tests

`wedge_test.py` drives the abnormal producer-exit paths in separate processes under a wall-clock
limit, because the failure it guards against is a **hang**, and a hang is not an exception that can
be caught and asserted on.

It is built defensively, because a test that reports success by *not* doing something is the
easiest kind of green to fake — and this one was silently blind for a week in three ways at once:
its stub producer did not accept keywords the caller had grown, its fake `args` was missing
attributes the code had started reading, and it pushed a two-field queue item after the item had
grown a third field. All three made the producer die *before doing anything*, and a producer that
dies instantly does terminate. Every scenario passed; none of them tested.

So there are three guards, each aimed at one way of lying: a **contract check** of the signatures
the stubs replace, a **STUB-RAN** marker so that "it terminated" cannot mean "it never began", and
a **positive control** that must hang — a termination test that has never seen a hang proves
nothing about its own ability to detect one.

Repairing it turned up a real defect: the worker's queue-item unpack sat one line *outside* its own
"a worker must never die" guard, so a single malformed item killed the thread that pulled it, and
enough of them killed every thread — after which the producer blocked forever on a queue nobody
would ever drain again. That case is now a scenario of its own.

> **Before changing `mirror.py`, read the `REQUIREMENTS` block at the top of it.** Thirty-five
> numbered rules, each written after something broke, each dated so it can be traced back. Most of
> those breakages were **silent**: the run ended, printed DONE, wrote a completion marker, and was
> wrong.
>
> This README describes what the tool does. That block describes what it must never do again.

## Licence

`mirror.py` and `wedge_test.py` are Apache-2.0, like the rest of this repository. What they
produce is not: a mirror is third-party material copied verbatim, and each archive carries
whatever terms its source carries. Nothing in a mirror is extracted, disassembled or derived —
it is a byte copy of what a public server serves.
