<!--
SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# mirror — tools for archives that may not survive their maintainer

A threaded mirror for whole HTTP archives and rsync modules, a checksum index that stays current
as a side effect of mirroring, tools that use those checksums to answer questions about what you
have, and a handful more for the cases the crawler cannot reach: a host that is already gone, a
wiki that will hand over its own source if asked properly, a site whose TLS chain is broken, and a
blog that only admits to its own contents through a sitemap. Standard library only; no
dependencies.

They exist because the archives below are mostly one person's server, and because the ways a
crawler quietly *fails to copy something* turn out to be far more numerous, and far harder to
notice, than the ways it fails loudly. Most of this file is about the second thing.

| | |
|---|---|
| `common.py` | the library the others are built on — `user_agent()`, `request_headers()`, `long_path`, `exists`, `isfile`, `safe_name`, `relative_to`, `sha256_file`, `sha256_bytes`, `iter_files`, `human`, `parse_size`, `OWN_FILES`. Not a tool: no command line. It exists because the copies had drifted into **eight** different bodies for `long_path`, **nine** for `human`, **three** user agents and **eight** own-files sets of which no two agreed. **27 of the 43 files import from it, `mirror.py` among them** |
| `mirror.py` | mirrors the archives; writes each one's marker and checksum index |
| `checksums.py` | the same manifest format for a tree that is *not* a mirror |
| `audit.py` | reads any number of manifests; finds duplicates across trees, and files that lie about what they are. `--listed` is the one check here that does **not** ask the tree about itself: it compares each file against the size the source's own stored directory index printed for it, which is how a truncated download is caught at all — one hashes to itself perfectly. **Deletes nothing** |
| `holes-run.py` | drives `audit.py --holes` over the collection **one archive at a time**, one log per archive written atomically. 2.39 TB at a measured 76 MB/s is 8.3 h, and a single process prints only at the end — so a log that exists means that archive is finished, and a restart re-does exactly the one that was interrupted. The logs are the state |
| `restate-marker.py` | moves a completion marker's counts onto the tree after a **deliberate** repair, and refuses to run without a `--reason` it writes *into* the marker. `completed` keeps the crawl's date: the archive was finished then and repaired today, and collapsing the two would age-wash the only record that says how old the mirror is |
| `containment.py` | joins every archive's `.sha256sum` to answer *does one mirror contain another?* and *what would a deduplicating packer save?* — set arithmetic over 1.40 M hashes, no tree re-read |
| `dedupe-docs.py` | deletes an outer copy, but only after re-reading both sides in full |
| `verify-content.py` | reads every byte back and checks it against the recorded SHA-256 — the bit-rot check `mirror.py --verify` structurally cannot do. Resumable; reports MISMATCH, MISSING and UNREADABLE separately; never repairs. An archive with **no** index is reported loudly and exits non-zero: silence used to be indistinguishable from success |
| `index-vs-tree.py` | path-level comparison of `.sha256sum` against the tree. Writes nothing |
| `crawl-gap-audit.py` | re-reads the stored pages with a WIDER notion of what a link is, and asks the tree about each target. Finds what the crawler could not SEE -- `<img src>`, `<frame src>`, href-not-first, dropped case collisions. Reports what needs checking, never what is lost |
| `find-html-imposters.py` | files whose bytes are an HTML error page under a binary name |
| `pdf-identify.py` | says what a PDF is when its filename does not — `/Info`, the XMP packet, the bookmark tree, the edition notice and the printer's spine copy, all at once. Filing a document into a curated directory means naming it, and on the seven filed on 2026-09-20 **no single field sufficed**: three carried `/Title Contents`, one `/Title A`, and four yielded no extractable text at all |
| `catalogue.py` | writes a self-describing CATALOGUE.md **into** the mirror tree, generated from its markers and PROVENANCE files — so a copy that outlives this repository can still say what it is |
| `measure-remote.py` | how big is a candidate **before** any disk is committed — handles directory listings and mirrored websites alike, and says which bytes it measured versus read off a listing |
| `reachability-probe.py` | can the crawler get *into* a site, or only as far as its front door |
| `wayback-salvage.py` | recovers a host that is already gone, from the Internet Archive |
| `suspect-reconsider.py` | re-checks every `.suspect` against **all** captures of its URL, not just the one that came up short. The rule it corrects — *a short transfer is final* — was true of a URL with one capture and got applied to URLs with several; 15 files came back |
| `ia-item-fetch.py` | Internet Archive items from the metadata API, with Range resume and per-file MD5 against the Archive's own. Writes the index and marker when the run is clean |
| `manifest-fetch.py` | fetches what an archive's **own** manifest names and the crawl could not reach. Distinguishes *gone from the copy* (404) from *failed* |
| `subset-refetch.py` | fetches a known-missing list into an existing archive under a **hard request budget**, for a host that limits a count per window rather than a rate. Aborts on consecutive connect failures: unspent budget is cheap, the ban that follows hammering is not. Feed it URLs a crawl **recorded as failed**, never links scraped out of pages |
| `pages-to-urllist.py` | builds a fetchable URL list from an archive's own stored pages — a list of **candidates**, never of files |
| `remove-fragment-copies.py` | removes `#`-named duplicates, and only where the non-empty stem exists as a file and its SHA-256 matches |
| `recheck-decisions.py` | probes the `LOST`, `FROZEN` and `CANDIDATES` lists — the claims about the outside world that rot while nothing on disk changes. Apex **and** `www.`; reads the page title so a parked domain is not mistaken for a return; counts what it could not resolve as drift rather than as an all-clear |
| `ask-the-source.py` | re-asks the hosts behind `ZERO_AT_SOURCE` whether they still serve those files as zeros — the only thing standing between 75 files and being reported as losses. Addresses come from `mirror.ARCHIVES`, never from guessing; keeps *the server refused* apart from *nobody answered*; touches nothing on disk |
| `sfv-verify.py` | checks files against a `.sfv` manifest — CRC32, the format RHash writes. A second opinion from a different party, not a second run of ours |
| `case-collision-recover.py` | sets the NTFS case-sensitivity flag on the affected directories, then fetches only the files a case-folding tree made the crawler drop |
| `extract-container-tar.py` | unpacks a tar that is *packaging* rather than a document into an archive of its own. Dry-run, collision check, `RENAMED.txt` and `SYMLINKS.txt` |
| `verify-extraction.py` | paths, sizes and content of an extraction against a third-party manifest |
| `unpacked-vs-archive.py` | may this unpacked copy be deleted? Reads the members **out** of the archive beside it and compares SHA-256 — because a basename match says the archive holds *a* file of that name, not *these bytes*. The first real run found `x_off/Makefile` sharing its name with a member of the tar next to it and differing in content: a name check would have called it covered and lost it. An archive it cannot open is reported UNREADABLE and covers nothing; old LZW `.Z` goes through GNU gzip when that is present, and is never guessed at when it is not |
| `http-subset-fetch.py`, `redbooks-fetch.py` | a chosen subset of a large HTTP tree, from an explicit URL list |
| `pmwiki-source.py` | copies a PmWiki as raw markup, from its own page list, without crawling |
| `dokuwiki-source.py` | the same for a DokuWiki, walking `?do=index` namespace by namespace |
| `mediawiki-source.py` | the same for a MediaWiki, through its API — every title, revid, timestamp and SHA-256 land in `MANIFEST.tsv`, because a page's on-disk filename cannot carry its real title |
| `autoindex-tls-broken.py` | an open directory whose TLS chain is incomplete, so no stdlib client will talk to it |
| `b2-cluster.py` | measures what the collection is **made of** — bytes per compressibility class and per extension — and counts the byte-identical files held more than once, from the stored digests alone. Then it checks `b2-pack.py`'s grouping against that: how much duplication sits inside a unit where a solid block collapses it, how much crosses a boundary and is paid for twice, and whether any archive is left unclaimed. It imports the units rather than restating them, because a check against its own copy of the answer checks nothing |
| `b2-pack.py` | plans the nineteen WinRAR units that carry the collection to cold storage, and **prints rather than runs** — `--execute` is opt-in. A multi-volume RAR cannot be appended to, so a unit is the unit of *rebuilding*, and the grouping follows what a project needs together rather than what compresses well. Every switch it emits was measured against a real WinRAR; two were wrong until they were. Reads only the per-archive indexes, never the collection's files |
| `find-sitemaps.py` | asks each archive's host for `robots.txt` and then, if it declares none, makes **one** guess at `/sitemap.xml` — and compares what it lists against what the mirror holds. A sitemap is the operator's own statement of what the site consists of, which is the one kind of evidence a crawl cannot produce: `measure-remote.py` follows links, so it rediscovers our own reach and charges a HEAD per file for it. 7 of 104 archives publish a readable one, 12 publish a sitemap *index* (not followed), 5 answer HTTP 200 with an HTML page |
| `blogger-sitemap.py` | a Blogger site, enumerated from `sitemap.xml` because its front page is infinite scroll |
| `nginx-autoindex-gallery.py` | a small nginx autoindex, at the `Crawl-delay` its robots.txt asks for |
| `move-mirror.py` | relocates a mirror tree between volumes, re-reading both sides rather than trusting the move |
| `refresh-table.py` | rebuilds `mirror.py`'s HELD table from the tree, carrying every hand-written note across |
| `common_test.py` | `unittest` over `common.py`, and every case is a mistake one of the copies actually made: a trailing dot surviving `long_path`, a relative path reaching `exists`, `human` being decimal while `parse_size` is binary, the agent not beginning `Mozilla/`, one own-files set. It also asserts that `mirror.py` resolves these to *this* module rather than to a copy of its own |
| `wedge_test.py` | the termination tests for `mirror.py` |
| `gone-record-test.py` | the twenty-two cases for `.mirror-gone`, the per-archive note of what the source answered 404 or 410 to. A 404 creates no file, so a list diffed against the tree names the same dead path every session — three sessions asked openpa for the same GIF, and those names sort to the front, so they were the first requests of a budget worth a few dozen. The tests pin what may **not** go in: not a timeout, and not 403 or 401, which say we may not have it rather than that it is gone |
| `manifests-test.py` | the forty-five cases for the four checksums per file. Two pin the formats — an `.sfv` writes `<path> <hash>` where `sha256sum` writes `<hash> *<path>`, and getting that backwards produces a file that still looks like an `.sfv` and verifies nothing — and the rest pin what the wiring got wrong twice: an incremental run must not shrink the manifests to whatever it happened to re-hash, and a deleted file must fall out even on the path where there is nothing to hash. It also gives `sfv-verify.py` its first test, the day its parser moved into the library |
| `exclude-honoured-test.py` | the nine cases proving a URL list cannot carry what `EXCLUDE` refuses — at both ends, because a list is a file and may come from anywhere. Built from whatever patterns the register happens to hold, so they state a property rather than a fixture. The first one tested is the *over*-refusal: `risc/images/` is not `images/`, and a file wrongly refused never appears anywhere for anyone to miss |
| `give-up-test.py` | the ten cases for `--give-up`, the rule that abandons a run whose host has stopped answering. Two of them are the point: forty consecutive 404s must **not** stop a run, because a status is the server talking and a hand-written site full of dead links is exactly what this collection mirrors. Written after a crawl spent twenty-six minutes asking a host that had gone quiet, and recorded nine subtrees as lost that were never truly asked for |
| `parse_listing_test.py` | the listing-parser tests. They check **both** directions: that the newer link and image forms are found, and that the size and date columns a real index carries are still read correctly |
| `drivers-exclude-test.py` | the 108 cases behind the `oldskool` driver exclusions. They check the **encoded** path, because `EXCLUDE` matches what the listing served — a vendor name with a space has to be written `%20` or it matches nothing |
| `trust-index-test.py` | the eight cases for `--trust-index`, the skip that makes a re-run cheap: a file named in the checksum index and present on disk is not fetched again |
| `robots_verdict_test.py` | the seven `robots.txt` readings this collection has argued about — a 188-agent blocklist that does not name us, a 45-agent block with an empty `Disallow:` whose *intent* is honoured anyway, a club that names us on one vhost and serves no file on another, and a `Disallow:` that reaches the path we actually want |

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

Every path is a parameter, and `mirror.py` in particular has **no default root** -- the subject of
the next section.

The tools added later relax this. **Thirty-three of them** default `--root` to `Q:\mirror` --
`autoindex-tls-broken.py`, `b2-cluster.py`, `b2-pack.py`, `blogger-sitemap.py`, `case-collision-recover.py`,
`containment.py`,
`converge.py`, `corpus-coverage.py`, `crawl-gap-audit.py`, `extract-container-tar.py`, `fill-from-local.py`, `find-html-imposters.py`, `find-sitemaps.py`,
`holes-run.py`, `holes-vs-source.py`, `http-subset-fetch.py`, `ia-item-fetch.py`,
`index-vs-tree.py`, `iso-second-opinion.py`, `manifest-fetch.py`,
`nginx-autoindex-gallery.py`, `page-extensions.py`,
`pages-to-urllist.py`, `recheck-decisions.py`, `redbooks-fetch.py`, `refresh-table.py`,
`remove-fragment-copies.py`, `sfv-verify.py`, `subset-refetch.py`, `suspect-reconsider.py`,
`truncated-vs-source.py`, `verify-content.py`, `verify-extraction.py`.
**Eight** demand `--root` outright (`catalogue.py`, `checksums.py`, `dedupe-docs.py`,
`dokuwiki-source.py`, `mediawiki-source.py`, `pmwiki-source.py`, `restate-marker.py`,
`wayback-salvage.py`); **two** take it without a default (`audit.py`, `mirror.py`).

**And nine take no `--root` at all** — `ask-the-source.py`, `common.py`,
`contract-mutations.py`, `listing-to-urllist.py`, `measure-remote.py`, `move-mirror.py`,
`pdf-identify.py`, `reachability-probe.py`, `unpacked-vs-archive.py` — because none of them
walks the collection.
`ask-the-source.py` is the clearest case: it reads recorded lengths from a table and bytes from a
URL, and a `--root` it never used would be an invitation to believe it had checked something on
disk. 33 + 8 + 2 + 9 = **52 scripts with an argument parser**, which is the whole set.

They are maintenance tools for one collection rather than general-purpose fetchers, and the trade
is deliberate -- but it is a trade. This paragraph named three tools for a while, then kept naming
three as the count reached eleven, and listed `catalogue.py` among the defaulting ones when it
actually refuses to run without `--root`.

**And it went stale again between those two sentences and this one**: corrected on 2026-09-16 from
eleven to seventeen, with `sfv-verify.py` moved out of the no-default group because it has since
grown one. A paragraph that documents its own tendency to rot is not thereby protected from
rotting. The lists are re-derivable and that is the point -- grep `add_argument("--root"` in each
file and classify by whether the match carries `required=True`, a `default=`, or neither. Do that
rather than trusting the three numbers above.

**And a third time, on 2026-09-21**: six to seven, because `mediawiki-source.py` was added and
this paragraph was not. The re-derivation above is what caught it, and it is worth saying how it
nearly did not: a grep read by eye gave the wrong answer twice, once missing a `required=True`
split across lines and once missing a `default=os.environ.get(...)`. Parsing the files instead --
`ast`, every `add_argument("--root")`, look at its keywords -- gave 17/7/2 and matched the named
lists exactly. The instruction stands; reading the matches by eye does not.

**A fourth time, on 2026-09-24 -- and that instruction is now a test.** The lists had reached
24/8/2 while the paragraph still said 17/7/2, and a whole group was missing: eight tools take no
`--root` at all, which nobody had ever counted. It was found while adding one line about
`ask-the-source.py`, and the first attempt to re-derive it used a regular expression -- the exact
thing two corrections up says not to do.

That is four. An instruction to check something by hand is a comment with a runtime cost, which is
what this project refuses everywhere else, so `readme-root-groups-test.py` now parses every script
with `ast` and compares the four sets against the four lists above, plus the spelled-out number in
front of each. Deliberately breaking the paragraph three ways -- a file dropped from a list, a
wrong number, a file in the wrong group -- fails it each time. The re-derivation instruction above
is kept, because it is still how somebody reads the answer; it is simply no longer the only thing
standing between this paragraph and its fifth correction.

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

**The table lives in `mirror.py`, not here** -- its opening block lists every archive with its
file count, size and the note that explains why it was taken, followed by what is deferred,
what was measured and rejected, and what an operator has forbidden. `catalogue.py` writes the
same figures into the mirror tree itself.

This sentence used to open with "Thirty-seven archives, 826 162 files, 3.51 TB" -- three
numbers, in the very paragraph that says the numbers do not live here. By 2026-09-10 the true
figures were 71, 1 394 095 and 3.71 TB, and nothing had said otherwise for weeks. The counts
are REMOVED rather than corrected: a figure that must be updated by hand in a document nobody
regenerates will simply be wrong again, and the paragraph below is about exactly that.

That is not tidiness. This file carried a second copy of the table for exactly one day before the
two disagreed: the README said 26 archives where the code said 30. A list that has to be edited in
two places to stay true will be wrong in one of them, and the stale copy reads as authoritatively
as the current one. The status now sits beside the code that produces it, where `ARCHIVES`,
`EXTERNAL` and `DO_NOT_FETCH` can be checked against it in one screen.

What follows here is the *reasoning* that does not belong in a table: the selection rule, the
archives that are exceptions to it, and the defects this tool has shipped and fixed.

One deliberate omission: `bits/NetBSD/` inside bitsavers, 606.8 GB of an operating system that is
in no danger whatsoever. It is named in `RSYNC["bitsavers"]["filter"]` rather than left to memory.

`mirror.py` is the master record, and its opening block is the place to start: a status table
covering everything held, deferred, measured-and-rejected, and forbidden by an operator, followed
by the defect classes that keep costing us whole subtrees. Sources considered and **not** taken
are there too, with the measurement behind each decision and the four premises that turned out to
be false. Read it before proposing a new source.

### Nine of them are not mirrors

`FROZEN` holds nine archives whose sources are gone. This section describes the first of them and
the shape they all share; the list itself is in `mirror.py`, which is where it stays current.

`aixtools` is in `FROZEN`, not in `RSYNC` or the crawler's set, because **its source no longer
exists**. Michael Felt's site published open-source software for AIX as installp/BFF
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

### And eighteen this tool does not fetch

`EXTERNAL` holds eighteen archives whose sources are alive and answering, but for which this
crawler is the wrong instrument. One example carries the reasoning; the list is in `mirror.py`.

`perzl-wiki` is one of them. A wiki is not a file tree. A PmWiki hands any reader its complete page list in **one request**
(`?n=Site.AllRecentChanges&action=source`) and then each page as raw markup, so the copy is a list
worked once rather than a walk over links: no `?action=edit` requests, nothing to exclude, and the
result is what the wiki actually stores rather than a skin wrapped around it.

`EXTERNAL` and `FROZEN` share a behaviour and differ in the remedy. A frozen archive can never be
improved. This one can — by re-running `pmwiki-source.py`. Pointing the crawler at it would not
fail; it would quietly build a second, worse copy beside the good one, which is the kind of
failure this file exists to catalogue.

**How it was nearly missed is worth more than the copy.** It sat in the collection's search brief
from the beginning, parked as low priority with the reason *"a wiki needs different handling from
a file tree"*. That reason expired the day `HTML_CRAWL` was added for exactly that shape — and
nothing pointed back at the entry. It was also recorded twice under two hostnames that nobody
connected: the project's vanity domain 301-redirects to the hoster's numbered vhost, so a search
for either name finds one record and not the other. It surfaced in the end by accident.

The rule that follows: **record an exclusion together with the condition that would revive it.** An
exclusion written as a fact about the target is never revisited. One written as a limit of this
tool would have been revisited the day the tool changed.

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

### What "complete" can and cannot mean

A marker rests on **link-following**: a crawl takes what pages link, and `measure-remote.py`
crawls too, so a measurement confirms the same reach at one HEAD per file and adds only byte
sizes. Neither can see a file nothing links. That was a theoretical caveat until 2026-10-02, when
`find-sitemaps.py` compared `ardent-tool` against its own `sitemap.xml` and found **32 pages the
mirror lacked** — in directories already held in full (`Apricot/prodcode` had `td,te,tf,tg.html`
and not `jp,np,qf,qp,sb.html`), none among the 42 recorded 404s, all 32 answering 200. An archive
marked COMPLETE since 11 September, found short by the first independent check ever run against
one.

So completeness here is a chain of claims, strongest first:

1. **The operator's own inventory** — `sitemap.xml`, two requests, and the only evidence that does
   not come from our own method. `openpa` settled this way: 168 of 168.
2. **Link closure** — harvest with `pages-to-urllist.py`, fetch, harvest again until no new name
   appears. Zero requests per round, because the pages are already on disk. A stored RSS feed
   counts as a second local source; `openpa.xml` named 14 files no page did.
3. **What nothing lists** — irreducible. No method available finds it, measurement included.

A marker may therefore honestly say "link- and sitemap-closed". It may not say "complete" and mean
more than that.

There is a third verdict, **ABANDONED**, and it exists because INCOMPLETE was giving the wrong
advice. A run ends abandoned when `--give-up` consecutive requests get no answer *at all* — a
timeout, a refused connection, a reset. A 404 is not one of those: a status is the server
talking, and a hand-written site full of dead links would otherwise stop a run for doing exactly
what it was asked to do.

The distinction earns its keep in what is *not* written down afterwards. An unreadable listing is
normally recorded as a lost subtree, and the advice printed beside it is "re-run to pick them up".
When the host has gone quiet those listings were never unreadable, and re-running is the last
thing anyone should do — so the warning is suppressed and the reason printed instead. On
2026-09-29 a crawl of `openpa.net` was cut off five minutes in, spent twenty-six more asking
anyway, and wrote down nine lost subtrees that were nothing of the kind.

## Checksums

Four per file, written beside each other and never instead of one another:

| file | algorithm | who else speaks it |
|---|---|---|
| `.sha256sum` | SHA-256 | **ours** — the one a verification decides on |
| `.sha1sum` | SHA-1 | Backblaze B2 records one per file (`X-Bz-Content-Sha1`) |
| `.md5sum` | MD5 | the Internet Archive publishes one for every file in an item |
| `.sfv` | CRC32 | RAR and ZIP store one per member; there is no `crc32sum(1)`, `.sfv` is the format |

**The three weaker ones are not there for strength.** They are there because the parties who could
give a second opinion about these bytes do not speak SHA-256. Measured on this collection's own
`IA-METADATA.json`: md5 present on 204 of 204 files, crc32 and sha1 on 203, **sha256 on none**. An
index of SHA-256 alone cannot be compared with the Internet Archive for a single file — and the
Archive is where this collection looks when an origin is gone.

**The cost is one read and no wall clock.** Measured on a 470 MB file with the disk out of the
picture: SHA-256 alone runs at 1551 MB/s, all four together at 309 MB/s, against a disk that
delivers 208 MB/s cold. Four digests still outrun the disk, so the pass stays disk-bound; MD5 is
the expensive one at 658 MB/s and is what takes the headroom from 2.8× down to 1.5×. The real
price is the one full re-read — about five and a half hours for 4.02 TB — which is why it is worth
doing once, properly, and then not touching the files again.

The names are the tools' own, so `sha1sum -c .sha1sum` works unchanged and OpenHashTab, QuickSFV
and TeraCopy read all three without being told anything. An archive that outlives these scripts is
still verifiable with what a system already has.

**The CSV index keeps its four columns.** Widening it would break every reader of the 113 indexes
already on disk, for three values no verification here decides on — and a standard-format manifest
is readable without these scripts, which a fifth CSV column would not be.

**An empty manifest is not written at all.** `md5sum -c` over zero lines reports success, and a
clean zero that reads as a verification is the shape this collection distrusts most. An absent
file says "not done yet".

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

**The index records what `--verify` cannot — but writing it is not the same as checking it.**
`--verify` compares file and byte counts, which finds what went missing or arrived. It cannot see
a file whose content changed while its size stayed the same, and over years and terabytes that is
the realistic failure, on archives that are in several cases the last copy in existence.

Nor does refreshing the index find it. **The refresh is deliberately skip-based** — that is the
whole point of keeping size and mtime — so a file whose bytes rotted while its size and timestamp
stayed put is skipped, keeps its old hash, and the index goes on vouching for it. The stored
checksum is a *claim*, and re-running the thing that wrote the claim cannot test it.

Only reading every byte back and re-hashing it can, which is `verify-content.py`. It has to be a
separate tool precisely because it must ignore the optimisation that makes indexing fast. Run it
before long-term archiving and after any move between volumes. The whole collection is
**3.74 TB in 1 402 661 files** as this is written; a full re-read runs at disk speed.

## What the tool learned the hard way

Sixteen defects, each found by measurement rather than reasoning, and every one of them invisible in a
progress bar. They are listed because the next archive will break the tool in some new way, and the
pattern is more useful than the individual fixes.

**A failure on your own side is not evidence about the other side.** A 568-url run ended on two
`[Errno 11001] getaddrinfo failed` and printed *"it has stopped talking. Leave it alone for
days."* Errno 11001 is a DNS lookup that failed: the owner's wifi had dropped, no request ever
left the machine, and the host answered HTTP 200 in 0.2 s a minute later. The run was right to
stop and wrong about why — and the why is what somebody acts on the next day. There are three
outcomes, not two: the server answered, the server did not, or we never reached it. A timeout
belongs to the host and justifies waiting; a dead resolver belongs to us and justifies nothing.

**A repeated experiment confirms repeatability, not the reason.** Two crawls of the same host were
cut off after roughly 60 requests each, a day apart, at the same minute. That was written down as
"this host meters requests per day, roughly 60" — in the voice of a measurement, with the
reasoning that two readings agreeing that closely could not be coincidence. They were not a
coincidence: they were the *same experiment run twice*. Nothing had yet asked the host for
anything of a different shape. When a URL list did, it got **371 consecutive requests with zero
failures** — six times the asserted ceiling. The observation was sound and the word "day" was
invented; the sentence that did the damage is the one that sounds most careful.

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
slash means "that is a directory", so the page it returns is not saved. A scan of every archive held at the
time -- twelve of them -- checked 76 000 candidates for the same shape and found no others — which fits, because
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

**A page's pictures are part of the page.** Link extraction read `<a href="…">` and nothing else —
not single quotes, not unquoted, and never `<img src>`. Across the hand-written archives, stored
pages named **10 067 inlined images that were not on disk**, and a sample HEADed against the
origins came back 200 for every one. In `ardent-tool` those are `2524_System_Board_Bottom.gif` and
`penarch.jpg`: board photographs and architecture diagrams, in an archive that exists for
board-level detail. Fixed, and the first re-crawl recovered **1 800+ files** in its opening minutes.

**A directory that serves a document cannot be enumerated at all.** On `gatekeeper.dec.com`,
`.../SRC/research-reports/SRC-021-html/` does not return a listing — it returns the research
paper. The parser read a paper as though it were an index and took the figures it links, and
everything else in that directory was simply invisible: `evolve.css`, `footnode.html`, backup
files ending in `~`, and a subdirectory confusingly named `icons.gif/`. Worse, the paper itself
was parsed and discarded, because a page is only *saved* when its URL ends in `.html` and a
directory URL ends in `/` — twelve DEC SRC papers were held as illustrations with no text.

**This is a limit, not a defect, and it is why manifests are kept.** No amount of crawling can
see what nothing links to. What closed it was `Index-byname`, the source's own listing: measured
against it, that archive was **509 files short after three runs that each reported COMPLETE with
zero failures**. Nothing had failed; the files were never requested. `manifest-fetch.py` exists
for exactly this, and the same relationship holds for bitsavers' `.tar.txt` and bullfreeware's
`.sfv`.

**And the same measurement, run the other way, refused a much larger claim.** Those pages also
carry 15 478 single-quoted or unquoted `<a href>` in `ardent-tool` alone, and one Blogspot page in
`techsysadm` has 251 `href='` against 4 `href="`. Resolved against the tree, the whole collection
was short **50 files** — 48 in one archive. Every other target had been reached another way, and
techsysadm's are absolute off-site URLs that were never archive children. A pattern count is not a
loss count, and the gap between 57 254 and 50 is the entire reason this list insists on
measurement.

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

Where the flag is absent the crawler keeps the first name, drops the second and logs
`COLLISION DROPPED`. That is the right fallback — a deterministic, logged loss beats whichever
download finished last — but it is still a loss, and nobody read those lines for six weeks.

### What auditing them actually takes

773 `COLLISION DROPPED` lines exist across the collection. They are **not** 773 losses, and
getting from one number to the other takes three steps, each of which killed a wrong answer:

1. **Ask the tree, not the log.** A DROPPED line proves a file was skipped that day. An identical
   claim about `ardent-tool` was retracted once already because a later run had healed it.
2. **Decode before comparing.** One pair was `CK_E020%20Series.pdf` against
   `CK_E020 Series.pdf` — the same URL, encoded two ways. Never a case collision at all.
3. **Fetch both spellings and compare bytes.** Of six pairs sampled from `ps-2.kev009.com`,
   **three were byte-identical** — the same file listed twice, nothing lost — and three were
   genuinely different: `epr2f.inf` is 1 155 162 bytes against 1 397 388 for `Epr2f.inf`.

The answer was **153 real losses, all in one archive**, recovered on 2026-09-08 with
`case-collision-recover.py`. Skipping step 3 would have turned that into a claim about all 765
lines in that log; skipping step 1 would have added four more that were never missing.

## Logs and file dates

One log per archive under `<root>/logs/`, named after it, append-only. Three kinds of entry meaning
three different things: `RETRY` is noise, four attempts with a growing wait, almost all recover;
`PERMFAIL` is a 403 or 404, the server's settled answer; **`LISTFAIL` is the one that matters**,
because a listing that could not be read takes its whole subtree with it. Any `LISTFAIL` or `FAIL`
makes the process exit non-zero.

The rsync progress meter is only attached when stdout is a terminal. Redirected to a file it was
36 MB of a line redrawing itself — 494 010 of 494 247 captured lines — so a redirected run gets
`--stats` instead: what was transferred, once, at the end.

**Watch `logs/<archive>.log`, not the redirected stdout.** They are not the same stream and only
one of them arrives while the run is running. Python block-buffers stdout as soon as it is a file
rather than a terminal, so `mirror.py … > run.log` can sit at 43 bytes for half an hour with the
crawl working normally behind it. The per-archive log is written line by line and is the live
one. Measured the hard way on 2026-09-29: a watcher was pointed at the redirected file, reported
nothing for thirty minutes, and the run had meanwhile been cut off by its host after five — the
tree had the answer the whole time, which is the same lesson as *ask the tree, not the log*, one
level further down.

Every mirrored file carries the date the **source** publishes, not the date it was copied. New
downloads take it from `Last-Modified`, which is exact to the second and free, since the header
arrives with the response anyway. Mirrors made before that existed were stamped afterwards from the
listings — **2 519 requests instead of 195 000**, because one listing carries the date for all its
files. The price is precision, minutes instead of seconds, which for a twenty-year-old package is
not worth 190 000 requests. The result is a real archive's date profile rather than "everything
made today": the oldest file in the oss4aix mirror is a patch from **30 August 2000**.

**Except where the source has no date to give.** `ardent-tool.com` serves its HTML pages with no
`Last-Modified` header at all, and being a hand-written site it has no directory listings to take
dates from either — so those 1 400-odd pages carry the time they were fetched, and a re-crawl
re-stamps every one of them. That is the honest outcome rather than a defect: inventing a date
would be worse. It is worth knowing before reading a date profile, and before wondering why an
incremental backup sees 1 400 changed files after a run that fetched almost nothing.

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

### Cold storage: nineteen units, and why not ninety-eight

`b2-pack.py` groups the 98 archives into nineteen WinRAR units for Backblaze B2 and a shelf of
M-Discs. The grouping is measured, not chosen:
[`measurements/collection-composition-2026-09-26.md`](measurements/collection-composition-2026-09-26.md)
counted the collection from its own indexes and found that **two thirds of it cannot be compressed
at all** — `pdf` alone is 1.21 TB of scanned paper — while **0.5 % is text**. So the compression
settings barely matter. What does matter is **171.37 GB of byte-identical duplicates**, of which
111.46 GB sits in the Bull group: `bull-rpms` is contained 100 % in `bullfreeware` *and* 100 % in
`ia-bullfreeware`. One unit, sorted so the copies are adjacent, turns 185 GB into about 70.

The constraint that decides everything else is that **a multi-volume RAR cannot be appended to**, so
a later correction repacks a whole unit. A unit is therefore a set of mirrors that belong to one
subject *and* tend to change together — which is why `fsck-aix-media` sits with AIX rather than with
its own host, so that an AIX-under-QEMU project does not fetch 404 GB of other vendors to reach
87 GB of install media.

[`measurements/winrar-recovery-2026-09-26.md`](measurements/winrar-recovery-2026-09-26.md) is the
other half: every switch put to a real WinRAR rather than remembered. Two were wrong in the tool
until then — `-scul` instead of `-scfl`, which stored **none** of five files with non-ASCII names,
and a claim that `-sv` prevents a file being split, which it does not. It also settled the rule that
costs everything if got wrong once: `-k` belongs in the packing command and must never be a separate
step, because locking afterwards rewrote every volume and left `rar rc` reporting *"Es fehlen 14
Volumen. Wiederherstellung unmöglich."*

### Nothing here may name the author's machine

`privacy-test.py` is a ratchet, and it exists because the hand sweep that produced it was not good
enough. On 2026-09-26 every script was read for private information. Four things turned up: a
private volume **and** directory in a `mirror.py` comment, an absolute path into the source tree
quoted in `refresh-table.py` while describing a bug that was already fixed, a literal **form feed**
in `common_test.py` where `\funet-unix` belonged — written through a shell that ate the backslash,
so the measurement it quotes had been unreadable for as long as it had been there — and, eleven
lines below the first one, the same drive letter again with **no separator after the colon**.

That fourth one is the whole argument. The sweep that found the other three could not see it,
because its pattern demanded a `\` or `/` after `X:`. A check that only recognises `X:\` is not a
check for a drive letter, and no amount of re-reading the file would have said so. Both halves are
now tests: each of the four findings is fed through the patterns verbatim and must be caught, and
each repaired sentence must pass — otherwise the ratchet has merely forbidden a form of words.

What it allows is named, one entry at a time, with a reason: `Q:\mirror` because it is documented in
`--help` output, `C:\Program Files\7-Zip` because that is where somebody else's installer puts a
tool, `C:\tmp` and `R:\tree` because they are synthetic and prove path handling, and `move-mirror.py`'s
bare `X: -> Q:` because that tool exists to move between volumes and naming them *is* the
explanation. A dead allowance fails the suite, so an exception cannot outlive what it excused.

The one file it does not scan is itself: a detector has to quote what it detects, and scanning it
reports its own pattern table. That is the same trap a census of `urlopen` calls here fell into when
it counted the line that named `urlopen` in order to look for it.

### Five directories of real bytes, because the thing under test is somebody else's output

[`testdata/listings/`](testdata/listings/README.md) holds 21 directory listings, one per parser
form found across 287 112 stored pages. [`testdata/heads/`](testdata/heads/README.md) holds 13
file **heads** of 512 bytes, one per way a file can lie about what it is — `magic_mismatch` reads
a head and never more, so a head is the whole of what is under test.
[`testdata/robots/`](testdata/robots/README.md) holds seven `robots.txt`, stored whole.
[`testdata/medium/`](testdata/medium/README.md) holds a 1970s OS/8 disk's block index, one real
512-byte block of it, and a derived map of which of its 737 blocks are zeros.
[`testdata/objblk/`](testdata/objblk/README.md) holds four Ultima VI map-chunk records, 3 183
bytes, one of them a byte short of what its own header demands.

**How much of somebody else's file to keep is itself a decision, and it is made the same way
every time: store what the test reads, and not the file it came out of.** A head is 512 bytes
because `magic_mismatch` never reads further. A robots.txt is stored whole because half a
statement of somebody's wishes says something different from the whole. The OS/8 disk image is
**not** stored — it is 377 344 bytes of DEC's software, 363 of its 737 blocks are zeros, and
copying a third of a megabyte to show that some of it is nothing would be copying it for no
reason; a 737-character map says everything the tests ask. What that leaves on trust — whether
the map is a true statement about the image — is checked by a test that re-derives it from the
image and skips itself where the collection is not mounted.

**The robots files were captured because half of them had already gone.** Of the four hosts whose
rules `robots_verdict_test.py` records, `irixnet.org` and `4corn.co.uk` still answer and are now
on disk; `update.uu.se` and `hpux.connect.org.uk` do not connect at all, and for those the inline
text in that test is the only record that survives. A robots.txt is a live statement of
somebody's wishes and can be rewritten tomorrow — these fixtures turn "we decided this was
permitted" into something that fails loudly when the permission changes.

Neither set could have been invented. Among the heads are a GIF missing exactly its first byte, a
JPEG whose four header bytes were overwritten while `JFIF` survives two bytes later, and an HTML
error page that opens with a **comment** before its doctype. That last one cost the collection
the most: `looks_like_html()` skipped a byte-order mark and leading whitespace and not a comment,
so the single most common error page here — found under an `.exe` name, eight `.rpm` names and 28
image names on one day — was reported as a vague signature mismatch instead of being named.

Every fixture is checked against the code that was wrong before it was added. Two of the seven
heads fail under the old `looks_like_html`, which is the difference between a fixture that guards
a fix and one that merely accompanies it.

### Where the open work is written down

There is no TODO file. There was one until 2026-09-25, and its last two items closed the
same day; the twenty-two before them had already moved into the things they were about --
see "Where the records live" above. A list of open work is worth keeping only while
something is open.

[`AUDIT-FINDINGS-2026-09-24.md`](AUDIT-FINDINGS-2026-09-24.md) is the first full `--ruins --empty`
pass over the collection, and is worth reading for one reason beyond its findings: the two raw
counts it starts from are both misleading, and it says how far and why. Its directory-pages section
now carries a **partly superseded** banner: the 32 pages it is about were restored on 2026-09-25 and
the blocker is gone, while the 341 absent files behind them are not. The table itself was left as
measured, because a record edited to match today cannot show that the fix worked.

[`ARCHIVES-NOTES-2026-09-17.md`](ARCHIVES-NOTES-2026-09-17.md) is 100 KB of snapshot and the one
file here that documents its own reason to exist wrongly. It said three comparisons had failed to
show whether the prose moved into the archives' `PROVENANCE.md` files had lost anything.
[`measurements/archives-notes-recoverable-2026-09-25.md`](measurements/archives-notes-recoverable-2026-09-25.md)
settled it: **92 of 539 sentences are in no `PROVENANCE.md` at all**, and one archive named there
was deleted and has none. What is missing is the measurement errors and the retractions — a
`PROVENANCE.md` says what an archive is, not what was believed about it on the way there.

### Two tools ask the collection instead of asserting

Most of what `mirror.py` claims is a claim about **what somebody else's server writes**, and the
collection holds 288 000 pages written by those servers. So the claims can be checked against
reality without asking a single host anything — no requests, no rate limits, no answer that
changes between two runs. Both are read-only.

- **`corpus-coverage.py`** reads every stored page and reports what `parse_listing` makes of it.
  It goes non-zero only when a page holds in-scope links the parser cannot see — the shape the
  `ps-2.kev009.com` finding had, where lighttpd listings parsed to nothing and 1 955 PDFs stayed
  missing from an archive marked COMPLETE.
- **`page-extensions.py`** asks the opposite question: which names get linked and stored, and
  which of them does nothing ever *walk*. Its finding is one sentence — a stored file whose first
  bytes are markup, under a name no page predicate accepts. Such a file was saved as content and
  never opened for links, which is exactly how sun3arc's 134 `.phtml` pages hid behind a run that
  reported COMPLETE with zero failures.

Both carry the same warning in their own words: **measure at the level the caller decides at.**
Comparing the two page predicates over raw `href`s reported 50 differences that do not exist,
because the crawler never sees a raw `href` — it sees `child`, after `urljoin`, with everything
off-host already dropped. The reasoning that had called those 50 impossible was simply wrong, and
only measuring said so.

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

---

## Where the records live

Twenty-two questions were settled about this collection in September 2026, and their
measurements are not in any document about them. Each one lives in the thing it is about,
because those homes are better than a paragraph — a table with a reason per row, a fixture,
a test that fails, a run's own logs. **Every one was checked to have such a home before the
prose describing it was removed.**

| | what it settled | where it lives now |
|---|---|---|
| A3 | `MAGIC` knew no image format | seven extensions in `common.MAGIC`, with tests |
| B1 | 33 directory pages stored as files | repaired; `restate-marker.py` + 11 tests; the 32 listings restored, `measurements/dirpages-restored-2026-09-25.md` |
| C1 | 26 280 signature mismatches, 21 real | `audit.PAGE_AT_SOURCE`, `SOURCE_CONVENTIONS` |
| C2 | 79 zero files in one capture | `audit.ZERO_IN_CAPTURE` |
| C3 | ~274 zero files, three groups | `ZERO_AT_SOURCE` (75), `ZERO_IN_THE_MEDIUM` (43), `testdata/medium/`, `testdata/objblk/` |
| C4 | `--holes` had never run whole | `measurements/holes-run/` — 99 logs + README, `holes-record-test.py` |
| C5 | 279 unidentified binaries | `testdata/heads/` — InstallShield and the source-damaged PDF as fixtures |
| C6 | 64 of C4's findings unjudged | `measurements/holes-vs-source-2026-09-25.md` |
| C8 | is anything worth re-fetching | `measurements/nothing-to-refetch-2026-09-25.md`, and `Q:\DEC` |
| D1 | `page-extensions.py` not gate-ready | `common.looks_like_a_copy_of_a_page()` |
| D2 | `--ruins` output not machine-readable | the column width is measured from the reasons present |
| D3 | two tools walked the archives themselves | both use `iter_archives` |
| D4 | `ruff` ran only in CI | installed; it found a defect that had inverted a whole tool |
| D5 | a listing's size column is not exact | `common.size_agrees()`, `listing_step()` |
| D6 | `--listed`, the first external record | built; found an HTML page under an `.exe` name |
| D7 | `mirror.py`'s exit codes | **withdrawn — the item was wrong**, and the measurement was mine |
| D8 | long checks printed nothing | `report=` on all five checks |
| D9 | nine broad catches | all narrowed; `narrowed-catches-test.py` |
| D10 | 41 `time.sleep` in 17 tools, three meanings | `common.Pacer`, `common.Backoff`, `sleeps-test.py` — 41 down to 4, each with its reason |
| D12 | a private collection's own pointer table named directories that did not exist | corrected there; the history sentence deliberately left as written |
| E1 | the chain compared the tree with itself | `--declared` and `common.declared_length` — the seventh kind of record, and the only one needing nothing but the file |
| E2 | mutations reached 2 of 7 modules | 13 mutations over all 7, generated from `LIBRARIES` |

**What is deliberately NOT here any more:** the arguments. They moved into the docstrings of the
things they are about, which is where somebody changing that code will actually read them --
`ZERO_AT_SOURCE` explains why widening `MAGIC` means re-reading it, `Pacer` explains what a delay
means, `declared_length` explains why "no opinion" and "damaged" are different answers.
