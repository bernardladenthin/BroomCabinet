# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Find files that are HTML pages wearing somebody else's extension, across a whole collection.

    python find-html-imposters.py                       # every archive
    python find-html-imposters.py --archive rs6000-microcode
    python find-html-imposters.py --csv imposters.csv   # machine-readable work-list

WHAT THIS CATCHES THAT audit.py --ruins DOES NOT. That check runs against a WHITELIST of thirteen
extensions (.bff .gz .img .iso .ova .pdf .qcow2 .rar .rpm .squash .tar .z .zip). The collection
holds 5 735 distinct extensions, and the one file known to be an imposter --
rs6000-microcode/support/micro/smp0951.bin, an XHTML error page of 9 954 bytes -- is a `.bin`,
which is not on that list. A whitelist can only find what somebody thought of in advance.

So this inverts it: check EVERY file whose extension is not one where markup is legitimate, and
say what kind of page it turned out to be. 774 661 of the collection's 826 162 files qualify.

WHY "NOT JUST ERROR PAGES". A server that is unhappy has more than one way to say so, and each
produces a different file that a fetcher accepts with a 200 status:

    soft-404      "404" / "not found" in a page served with status 200
    forbidden     403 pages, "access denied", login walls
    redirect      <meta http-equiv=refresh> or a "moved" stub instead of the content
    index         a directory listing saved where a file was expected -- audit.py's INDEX_PAGE
                  case, which additionally blocks everything below that path
    parking       the host is gone and a registrar or free-host placeholder answers
    page          real HTML, no error markers -- often legitimate, and reported separately

The classification is a HINT for triage, not a verdict. What makes a file wrong is that a `.bin`
contains markup at all; which flavour of markup only decides how it is likely to be recovered.

DELIBERATELY NOT AUTOMATIC. It reports and writes a CSV. It does not delete, rename or re-fetch,
because a mirror is not tidied by a tool that has just guessed.
"""
import argparse
import collections
import concurrent.futures
import csv
import io
import os
import sys
import time

from common import (MIRROR_ROOT, BOOKKEEPING_FILES, COMPLETE_MARKER, MARKUP_EXTENSIONS, STOCK,
                    classify_page, file_extension, is_partial, long_path,
                    looks_like_an_error_page, looks_like_markup, page_title, say)

# WHERE MARKUP IS NOT NEWS. common.MARKUP_EXTENSIONS since 2026-09-27, and derived there from
# PAGE_EXTENSIONS rather than typed out -- this file's own copy had drifted, missing `.php4`,
# `.phtm`, `.shtm` and `.xhtm`, so an HTML file named `x.php4` was reported as an imposter and a
# real error page under `.php4` was not scanned by --pages at all. Both wrong, in opposite
# directions, from one omission.
MARKUP_EXT = set(MARKUP_EXTENSIONS)

# Files this collection writes about itself.

# looks_like_markup(), MARKUP_HEADS and BINARY_MAGIC are common.py's since 2026-09-27, with the
# 18 MB ZIP that forced the container check. They are the library's hunting counterpart to
# looks_like_html(), and the note there says why the two sets must not be folded.

# The six-class table and the loop over it are common.classify_page() since 2026-09-27, beside
# the title-only table that answers the OTHER half of this tool. Keeping them apart in one file is
# what stops either being widened into the other; keeping them in two files is what let this one
# carry its own second copy of INDEX_PAGE.

def inspect(job):
    """(archive, rel, full, size) -> a finding dict, or None."""
    archive, rel, full, size = job
    try:
        with io.open(long_path(full), "rb") as fh:
            head = fh.read(4096)
    except OSError as exc:
        return {"archive": archive, "rel": rel, "size": size, "ext": "",
                "kind": "UNREADABLE", "title": exc.__class__.__name__}
    if not looks_like_markup(head):
        return None
    kind = classify_page(head)
    # common.page_title() since 2026-09-27; this was one of five hand-rolled copies, and
    # the 120-character cap that used to live in the regex is now the slice below, where a
    # reader can see it.
    title = page_title(head) or ""
    return {"archive": archive, "rel": rel, "size": size,
            "ext": file_extension(rel), "kind": kind, "title": title[:110]}


# WHETHER A WEAK FINDING COUNTS, set once from --weak before the pool starts. A list because
# the workers read it and a plain rebind in main() would not reach them.
WEAK_TOO = [False]


def inspect_page(job):
    """(archive, rel, full, size) -> a finding for a page whose own TITLE announces a failure.

    THE COMPLEMENT OF inspect(), AND THE CASE THIS TOOL COULD NOT SEE. Everything above starts
    from a name where markup does not belong. spider.seds.org/ngc/ holds eight `.cgi` files
    fetched with HTTP 200, six of them error pages -- `NGC Error !`, `Erreur NGC !`,
    `NGC/IC Error!`, `Error in revngcic.cgi` -- and `.cgi` is in MARKUP_EXT, so the default scan
    skipped them and was RIGHT to: HTML under a `.cgi` name is exactly what is expected. A wrong
    page under a right name needs a different question, and it is common.looks_like_an_error_page.

    THE TITLE ONLY, which is why this is not simply classify() over a wider file set. CLASSIFY
    matches the whole head, correctly, because by then the name has already made the file
    suspect; here the name is fine, so only what the page says ABOUT ITSELF counts. Run over a
    body, `\berror\b` would report every manual with the word in a paragraph.
    """
    archive, rel, full, size = job
    try:
        with io.open(long_path(full), "rb") as fh:
            head = fh.read(4096)
    except OSError as exc:
        return {"archive": archive, "rel": rel, "size": size, "ext": "",
                "kind": "UNREADABLE", "title": exc.__class__.__name__}
    complaint = looks_like_an_error_page(head)
    if complaint is None:
        return None
    kind, strength, title = complaint
    if strength != STOCK and not WEAK_TOO[0]:
        return None
    return {"archive": archive, "rel": rel, "size": size, "ext": file_extension(rel),
            "kind": kind if strength == STOCK else kind + "?", "title": title[:110]}


def jobs_for(root, archives, markup=False):
    """Every file worth reading. `markup` INVERTS the extension filter, which is what --pages is."""
    for archive in archives:
        base = os.path.join(root, archive)
        for dirpath, _dirs, files in os.walk(long_path(base)):
            for f in files:
                if f in BOOKKEEPING_FILES or is_partial(f):
                    continue
                ext = file_extension(f)
                if (ext in MARKUP_EXT) != markup:
                    continue
                full = os.path.join(dirpath, f)
                try:
                    size = os.path.getsize(full)
                except OSError:
                    size = -1
                rel = full[len(long_path(base)):].lstrip(os.sep).replace(os.sep, "/")
                yield archive, rel, full, size


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=MIRROR_ROOT)
    ap.add_argument("--archive", action="append", default=[])
    ap.add_argument("--csv", default=None, help="write the full work-list here")
    ap.add_argument("--workers", type=int, default=12,
                    help="parallel readers; this is seek-bound, not CPU-bound")
    ap.add_argument("--pages", action="store_true",
                    help="the OTHER half: scan the files where markup IS expected and report the "
                         "ones whose own <title> announces a failure. A wrong page under a right "
                         "name -- six of spider.seds.org's eight .cgi files are error pages, and "
                         "the default scan skips them because .cgi is a markup extension.")
    ap.add_argument("--weak", action="store_true",
                    help="with --pages, also report titles that merely CONTAIN an error word. "
                         "Measured over this collection on 2026-09-27: 82 findings without it, "
                         "2 357 with, and the 2 275 that separate them are documents -- IBM PS/2 "
                         "manuals, an AIX message reference, the Bison manual. Useful on ONE "
                         "archive, where a person reads the handful that come back; useless as a "
                         "sweep. Weak kinds are printed with a `?`.")
    ap.add_argument("--max-size", type=int, default=0,
                    help="skip files larger than this many bytes (0 = no limit). A served error "
                         "page is small, but so is nothing else about this being safe -- the "
                         "default checks everything.")
    args = ap.parse_args()

    archives = args.archive or sorted(
        d for d in os.listdir(args.root)
        if os.path.isfile(os.path.join(args.root, d, COMPLETE_MARKER)))
    print("scanning %d archives under %s" % (len(archives), args.root), flush=True)

    found = []
    n = 0
    t0 = time.time()
    gen = jobs_for(args.root, archives, markup=args.pages)
    if args.max_size:
        gen = (j for j in gen if 0 <= j[3] <= args.max_size)
    WEAK_TOO[0] = args.weak
    look = inspect_page if args.pages else inspect
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        for res in ex.map(look, gen, chunksize=64):
            n += 1
            if res:
                found.append(res)
            if n % 50000 == 0:
                print("  %d files, %d found, %.0f files/s"
                      % (n, len(found), n / max(time.time() - t0, 1e-9)), flush=True)

    print("\n%d files read, %d %s, %.1f min"
          % (n, len(found),
             "announce a failure in their own title" if args.pages
             else "are markup under a non-markup extension",
             (time.time() - t0) / 60))

    by_kind = collections.Counter(f["kind"] for f in found)
    by_arch = collections.Counter(f["archive"] for f in found)
    by_ext = collections.Counter(f["ext"] or "(none)" for f in found)
    print("\n  by kind:    %s" % dict(by_kind.most_common()))
    print("  by archive: %s" % dict(by_arch.most_common(12)))
    print("  by ext:     %s" % dict(by_ext.most_common(12)))

    # THE DURABLE ARTEFACT IS WRITTEN BEFORE THE COSMETIC ONE. The first version printed the
    # listing first and wrote the CSV after; a page title in Japanese raised UnicodeEncodeError
    # on a cp1252 console and killed the process between the two, so a completed 6.6-minute scan
    # of 774 634 files produced no work-list at all. Ordering is the fix that does not depend on
    # getting the encoding right.
    if args.csv:
        with io.open(args.csv, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, ["archive", "rel", "size", "ext", "kind", "title"])
            w.writeheader()
            for f in sorted(found, key=lambda x: (x["archive"], x["rel"])):
                w.writerow(f)
        print("\n  work-list written to %s" % args.csv)

    print("\n%-18s %-10s %10s  %s" % ("ARCHIVE", "KIND", "BYTES", "PATH / TITLE"))
    for f in sorted(found, key=lambda x: (x["kind"], x["archive"], x["rel"])):
        say("%-18s %-10s %10d  %s" % (f["archive"][:18], f["kind"], f["size"], f["rel"]))
        if f["title"]:
            say("%42s  \"%s\"" % ("", f["title"]))
    sys.exit(1 if found else 0)


if __name__ == "__main__":
    main()
