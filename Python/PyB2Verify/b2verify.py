#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Check that local directories and their Backblaze B2 buckets hold the same bytes -- and keep
checking, on both sides, that they still do. Nothing is ever uploaded, changed or deleted in B2.

Each directory below `localRoot` belongs to the bucket of the same name. The LOCAL side is
PyFixity (../PyFixity): one read gives SHA-256, SHA-1, MD5, CRC32 and, for files B2 holds in parts,
the S3 ETag; the result is an index plus the manifests .sha256sum .sha1sum .md5sum .sfv at the
root of each bucket directory, which OpenHashTab and `sha256sum -c` read and which are uploaded
with the data. This tool adds the B2 side and the comparison:

    <stateDir>/checksums/local/<bucket>.csv     PyFixity's index, written by hash-local
    <stateDir>/checksums/b2/<bucket>.tsv        what B2 states, written by hash-b2
    <stateDir>/reports/<bucket>*.md             one Markdown report per bucket and check

COMMANDS
    check [bucket ...]          live: names and sizes, local tree against the bucket listing
        --mtime                 also compare modification times
    hash-b2 [bucket ...]        record what B2 states: SHA-1, else S3 ETag and part sizes;
                                lists uploads a dropped connection left open
        --download-unknown      download and hash files that have neither
    hash-local [bucket ...]     bring the local index up to date (only what changed) and write
                                the manifests; part sizes from hash-b2 add the ETag in the same read
        --force                 re-read everything; a saved checksum is NEVER silently replaced
                                when size and mtime are unchanged -- that is reported as damage
    verify-local [bucket ...]   re-read local files against the index, and say for each damaged
                                file whether the copy in B2 can restore it
        --quick                 names, sizes and times only; read nothing
    verify-b2 [bucket ...]      compare the current bucket listing with the saved checksums
        --download              also stream every file from B2, hash it and compare it with what
                                B2's metadata states -- straight from the network, no temp files
    compare [bucket ...]        local index against saved B2 checksums, 1:1
    vault [bucket ...]          a Cryptomator vault in B2 (see CRYPTOMATOR VAULTS below): open
                                it, decrypt the directory tree and check that it is consistent,
                                then compare names and exact sizes with the local index -- all
                                without downloading any content
        --download              also stream every file, decrypt it (which authenticates every
                                block) and compare its checksums with the local index

VERIFICATION RUNS (verify-local, verify-b2 --download, hash-b2 --download-unknown)
    --threads N                 files in parallel (default: local 1, B2 4)
    --hash-threads N            threads the digests of each file are spread over (default 5; also
                                for hash-local, which takes --threads too). The CPU, not the disk,
                                limits hashing: ~200 MB/s for all digests in one thread, ~620 in five
    --resume                    continue an interrupted run
    --older-than DAYS           only files not successfully checked for DAYS

SELECTION (check, compare, verify-local, verify-b2)
    --include REGEX             relative path; repeatable; case-insensitive
    --exclude REGEX             e.g. '\.mp4$'  '^Recordings/'  '(^|/)serial\.txt$'
    --min-size SIZE             inclusive    (500, 64K, 1M, 1.5G)
    --max-size SIZE             exclusive -- so --max-size 1M and --min-size 1M split exactly

CONFIGURATION is a properties file outside this repository, given by --config or the environment
variable B2VERIFY_CONFIG. It holds the credentials, so it must never be committed:

    keyId=<application key id>              a READ-ONLY key is enough and is recommended
    applicationKey=<application key>
    localRoot=D:/backup                     one directory per bucket below it; needed only by
                                            check, hash-local and verify-local
    stateDir=D:/backup-state                optional; default: the directory of the config file
    reportDir=D:/backup-state/reports       optional; default: <stateDir>/reports
    exclude=Thumbs.db,desktop.ini,*.lnk     optional; glob patterns, never compared
    flatBuckets=example-flat-bucket         optional; buckets uploaded without directories
    ignoreDirs=scratch                      optional; directories below localRoot that are no bucket
                                            (stateDir and reportDir are recognised by themselves)
    vaults=example-vault-bucket/films       optional; <bucket>/<directory> holding a Cryptomator
                                            vault (comma-separated), see below
    vaultKey.example-vault-bucket/films=D:/backup/films.key
                                            optional; the file with the vault's passphrase
                                            (default: <localRoot>/<bucket>/<directory>.key)

CRYPTOMATOR VAULTS. The bucket holds a vault in <directory>; locally the same files lie in clear
in <localRoot>/<bucket>/<directory>. B2's checksums describe the ciphertext, which never repeats,
so they cannot be compared with local ones. For such a bucket:

    hash-local      indexes the cleartext directory (<stateDir>/checksums/local/<bucket>-<directory>.csv)
                    and writes the manifests into it, so they are encrypted and uploaded with it
    verify-local    re-reads the cleartext directory against that index
    vault           checks the vault in B2 against that index
    hash-b2, verify-b2   work as for any bucket -- on the ciphertext, which is what B2 stores
    check, compare  skip the bucket: a ciphertext listing has nothing to compare with
The passphrase file holds the passphrase as its only line. Keep it out of every uploaded tree.
Opening a vault needs the 'cryptography' package (requirements.txt).

The four manifests are uploaded with the data but are not compared: they describe a bucket rather
than belong to it. A local checksum file of the first version (<bucket>.tsv) is moved onto the
index on first use, without reading anything; the next hash-local then adds the new digests.

Exit status: 0 everything matches / done, 1 differences found, 2 error.
"""
from __future__ import annotations

import argparse
import os
import re
import socket
import ssl
import sys
import threading
import time
from pathlib import Path
from typing import Iterator

from b2lib import (B2_NOW_VS_SAVED, CONTENT_VS_META, LOCAL_VS_B2, YES, FileEntry, SnapshotSaver,
                   b2_state, classify_unfinished, copy_entry, expected_from_metadata, is_root_manifest, load_previous, local_state, migrate_local_tsv, new_meta,
                   read_snapshot, stale_b2_hint)

import fixity  # importable once b2lib has put ../PyFixity on the path

CONFIG_ENV = "B2VERIFY_CONFIG"
# Directories below localRoot that are never a bucket. Hidden ones (".venv", ...) are skipped too,
# and so is whatever holds this tool's own checksums and reports -- see Context.local_dirs.
SKIP_DIRS = {"__pycache__"}
# The placeholder the B2 web interface creates for an empty folder.
B2_FOLDER_PLACEHOLDER = ".bzEmpty"
VAULT_SKIP = "a Cryptomator vault - B2 holds ciphertext, which is checked by 'vault' instead"
COMMANDS = ("check", "hash-local", "hash-b2", "verify-local", "verify-b2", "compare", "vault")
LOCAL_COMMANDS = {"check", "hash-local", "verify-local"}


def fail(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(2)


def load_properties(path: Path) -> dict[str, str]:
    if not path.is_file():
        fail(f"configuration not found: {path}")
    props: dict[str, str] = {}
    # utf-8-sig: Notepad and PowerShell's `Set-Content -Encoding utf8` write a byte order mark,
    # which would otherwise turn the first key into "\ufeffkeyId" and report it as missing.
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "!")):
            continue
        sep = min((i for i in (line.find("="), line.find(":")) if i >= 0), default=-1)
        if sep < 0:
            continue
        props[line[:sep].strip()] = line[sep + 1:].strip()
    for key in ("keyId", "applicationKey"):
        if not props.get(key):
            fail(f"'{key}' is missing in {path}")
    return props


def split_list(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def parse_vaults(value: str) -> dict[str, list[str]]:
    """vaults=<bucket>/<directory>,... -> bucket -> vault directories."""
    vaults: dict[str, list[str]] = {}
    for item in split_list(value):
        bucket, sep, directory = item.strip("/").partition("/")
        if not sep or not bucket or not directory.strip("/"):
            fail(f"vaults: '{item}' is not <bucket>/<directory>")
        vaults.setdefault(bucket, []).append(directory.strip("/"))
    return vaults


def slug(directory: str) -> str:
    return directory.replace("/", "-")


# --------------------------------------------------------------------------- B2 and S3

# Where the preflight knocks, and how long it waits. Module-level so a test can point it at a
# local socket that accepts and never answers.
PREFLIGHT_TARGET = ("api.backblazeb2.com", 443)
PREFLIGHT_TIMEOUT = 15.0


def preflight(target: tuple[str, int] | None = None, timeout: float | None = None) -> str | None:
    """-> None when a TLS handshake with the B2 API succeeds in time, else what went wrong.

    WHY THIS EXISTS. On 2026-10-02 a machine in a data centre reached B2 by TCP but never
    completed a TLS handshake -- with any host name, while every other site worked: the path to
    Backblaze's addresses was broken. b2sdk retries such a connection with long timeouts, so the
    tool sat silent for minutes with no CPU in use and no word on the console. Fifteen seconds
    and one sentence are a better answer than that, especially on a machine nobody watches.
    """
    host, port = target or PREFLIGHT_TARGET
    timeout = PREFLIGHT_TIMEOUT if timeout is None else timeout
    start = time.monotonic()
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
    except OSError as e:
        return f"cannot connect to {host}:{port} ({e.__class__.__name__}: {e})"
    try:
        with ssl.create_default_context().wrap_socket(sock, server_hostname=host):
            return None
    except OSError as e:  # includes TimeoutError and ssl.SSLError
        return (f"TCP to {host}:{port} works, but the TLS handshake failed after "
                f"{time.monotonic() - start:.0f} s ({e.__class__.__name__}). The network path to "
                f"B2 is broken or filtered here; this is not a problem of the key or the checksums. "
                f"The usual cause is a path-MTU black hole: large reply packets are lost on the way "
                f"back. See README.md, 'TCP connects but TLS to B2 never completes'.")
    finally:
        sock.close()


def new_b2_api(key_id: str, app_key: str):
    # IMPORTED HERE AND NOT AT THE TOP, so that `--help` works without the dependencies installed.
    # CI runs `--help` over every script with nothing from requirements.txt.
    from b2sdk.v2 import B2Api, InMemoryAccountInfo

    api = B2Api(InMemoryAccountInfo())
    api.authorize_account("production", key_id, app_key)
    return api


class S3Info:
    """ETag and part sizes through B2's S3-compatible endpoint.

    A MASTER KEY IS REFUSED THERE (403 for every request). The application key must be a normal one;
    read-only is enough.
    """

    def __init__(self, api, key_id: str, app_key: str) -> None:
        import boto3
        from botocore.config import Config

        url = api.account_info.get_s3_api_url()
        region = re.search(r"s3\.([^.]+)\.", url).group(1)
        self.client = boto3.client(
            "s3", endpoint_url=url, region_name=region,
            aws_access_key_id=key_id, aws_secret_access_key=app_key,
            config=Config(signature_version="s3v4", retries={"max_attempts": 5},
                          request_checksum_calculation="when_required",
                          response_checksum_validation="when_required"))

    def _head(self, bucket: str, e: FileEntry, part: int | None = None) -> dict:
        kwargs = {"Bucket": bucket, "Key": e.key, "VersionId": e.file_id}
        if part:
            kwargs["PartNumber"] = part
        return self.client.head_object(**kwargs)

    def etag_and_parts(self, bucket: str, e: FileEntry) -> tuple[str, list[int]]:
        h = self._head(bucket, e, part=1)
        etag = h["ETag"].strip('"')
        count = h.get("PartsCount")
        if not count or not fixity.is_multipart_etag(etag):
            return etag, [e.size]
        first = h["ContentLength"]
        rest = e.size - first * (count - 1)
        if count == 1:
            return etag, [first]
        # The usual layout: equal parts, a smaller last one. Confirmed by asking for the last part;
        # anything else is asked part by part.
        if 0 < rest <= first and self._head(bucket, e, part=count)["ContentLength"] == rest:
            return etag, [first] * (count - 1) + [rest]
        return etag, [self._head(bucket, e, part=n)["ContentLength"] for n in range(1, count + 1)]


def b2_chunks(bucket, file_id: str) -> Iterator[bytes]:
    """A B2 file's content as a stream, from the network straight into the hasher. No temp file."""
    response = bucket.download_file_by_id(file_id).response
    try:
        yield from response.iter_content(fixity.READ_CHUNK)
    finally:
        response.close()


def unfinished_uploads(bucket) -> list[str] | None:
    """Names of the bucket's unfinished large-file uploads; None if the bucket cannot be asked."""
    try:
        return sorted(fixity.norm(f.file_name) for f in bucket.list_unfinished_large_files())
    except Exception as e:  # never let a side report stop the actual check
        print(f"  note: cannot list unfinished uploads ({e})")
        return None


def unfinished_report(unfinished: list[str] | None, present: set[str]) -> list[str]:
    """Lines for the console and the report; empty when there is nothing unfinished.

    Uploads interrupted by a dropped connection do not show up in any listing, yet their parts are
    stored and billed. A read-only key cannot cancel them; a lifecycle rule on the bucket
    ("cancel unfinished large files after N days") or a key with write access can.
    """
    if not unfinished:
        return []
    leftovers, missing = classify_unfinished(unfinished, present)
    lines = [f"{len(unfinished)} unfinished large-file upload(s) - stored and billed until cancelled "
             f"(a lifecycle rule on the bucket can do that; a read-only key cannot):"]
    lines += [f"  NOT IN B2: {n}  (no finished file of that name)" for n in missing]
    lines += [f"  leftover:  {n}  (a finished file of that name exists)" for n in leftovers]
    return lines


def scan_remote(bucket, excludes: list[str]) -> list[FileEntry]:
    """The bucket's current files, without the folder placeholders, the permanent exclusions and
    the four manifests at its root."""
    files: list[FileEntry] = []
    for fv, _folder in bucket.ls(latest_only=True, recursive=True):
        if fv.action != "upload":  # hidden or deleted versions are not files
            continue
        name = fixity.norm(fv.file_name)
        if (fixity.basename(name) == B2_FOLDER_PLACEHOLDER or is_root_manifest(name)
                or fixity.is_excluded(name, excludes)):
            continue
        sha1 = fv.get_content_sha1()
        files.append(FileEntry(name, fv.size, fv.mod_time_millis, sha1=sha1,
                               source="b2" if sha1 else "", file_id=fv.id_, key=fv.file_name))
    return sorted(files, key=lambda e: e.path)


# --------------------------------------------------------------------------- output

def checksum_pair(a, b) -> tuple[str, str, str]:
    """The digest a comparison used, with both sides' values, for display."""
    used = fixity.checksums_match(a, b)[1] or "etag"
    if used == "size":
        return "size", str(a.size), str(b.size)
    return used, getattr(a, used, None) or "", getattr(b, used, None) or ""


def unknown_reason(a, b) -> str:
    if not getattr(b, "sha1", None) and not getattr(b, "etag", None) and not getattr(b, "sha256", None):
        return "no checksum recorded (hash-b2, or --download-unknown)"
    if getattr(b, "etag", None) and not getattr(b, "sha1", None) and a.parts != b.parts:
        return "part MD5s missing (run hash-local again after hash-b2)"
    return "checksum missing (run hash-local)"


def describe_duplicate(key: str, ls: list, rs: list, d: fixity.Diff) -> str:
    parts = [f"{d.labels.left} {e.path} ({fixity.fmt_size(e.size)})" for e in ls]
    parts += [f"{d.labels.right} {e.path} ({fixity.fmt_size(e.size)})" for e in rs]
    return f"{key}: " + "; ".join(parts)


def identical_text(d: fixity.Diff) -> str:
    used = ", ".join(f"{k} {v}" for k, v in sorted(d.ok.items()))
    return f"{d.identical}" + (f"  ({used})" if used else "")


def print_diff(name: str, d: fixity.Diff, limit: int, check_sum: bool) -> None:
    lb = d.labels
    status = "DIFFERENCES" if d.has_differences() else "in sync"
    mode = ", flat" if d.flat else ""
    print(f"\n=== {name}: {status}  ({lb.left} {d.left_count} files, {lb.right} {d.right_count} files{mode})")
    if check_sum:
        print(f"  checksum identical: {identical_text(d)}")
        if d.skipped:
            print(f"  not read (checked recently): {d.skipped}")

    def note(path: str) -> str:
        return f"\n        -> {d.notes[path]}" if path in d.notes else ""

    def section(title: str, rows: list[str]) -> None:
        if not rows:
            return
        print(f"  {title}: {len(rows)}")
        for r in rows[:limit] if limit else rows:
            print(f"    {r}")
        if limit and len(rows) > limit:
            print(f"    ... and {len(rows) - limit} more (--limit 0 shows all)")

    size = fixity.fmt_size
    section(f"{lb.only_left}, {fixity.total(d.only_left)}", [f"+ {e.path}" for e in d.only_left])
    section(f"{lb.only_right}, {fixity.total(d.only_right)}", [f"- {e.path}" for e in d.only_right])
    section("size differs",
            [f"~ {a.path}  {lb.left} {size(a.size)} / {lb.right} {size(b.size)}" + note(a.path) for a, b in d.size])
    section("modification time differs",
            [f"~ {a.path}  {lb.left} {fixity.fmt_ns(a.mtime_ns)} / {lb.right} {fixity.fmt_ns(b.mtime_ns)}"
             for a, b in d.mtime])
    section("checksum differs", [f"! {a.path}  ({checksum_pair(a, b)[0]})" + note(a.path) for a, b in d.checksum])
    section("read or download error", [f"X {a.path}  ({d.notes.get(a.path, '')})" for a, _b in d.errors])
    section("checksum not checkable",
            [f"? {a.path}  ({size(a.size)}, {d.notes.get(a.path) or unknown_reason(a, b)})"
             for a, b in d.checksum_unknown])
    section("name occurs more than once (not compared)",
            [f"* {describe_duplicate(k, ls, rs, d)}" for k, ls, rs in d.duplicates])


def md_cell(text: str) -> str:
    return text.replace("|", "\\|")


def write_markdown(path: Path, title: str, d: fixity.Diff, options: list[str], info: list[str]) -> None:
    lb, size, total = d.labels, fixity.fmt_size, fixity.total
    status = "differences found" if d.has_differences() else "in sync"
    out = [
        f"# {title}",
        "",
        f"- **Status:** {status}",
        f"- **Checked:** {fixity.now_ts()}",
        *info,
        f"- **Mode:** {'flat (file names only, directories ignored)' if d.flat else 'with directory structure'}",
        f"- **Compared:** {', '.join(['name', 'size'] + options)}",
        f"- **Files:** {lb.left} {d.left_count}, {lb.right} {d.right_count}",
        "",
        "| Category | Count | Volume |",
        "|---|---:|---:|",
        f"| {lb.only_left} | {len(d.only_left)} | {total(d.only_left)} |",
        f"| {lb.only_right} | {len(d.only_right)} | {total(d.only_right)} |",
        f"| Size differs | {len(d.size)} | |",
    ]
    if "modification time" in options:
        out.append(f"| Modification time differs | {len(d.mtime)} | |")
    if "checksum" in options:
        for used, count in sorted(d.ok.items()):
            out.append(f"| Checksum identical ({used}) | {count} | |")
        if d.skipped:
            out.append(f"| Not read (checked recently) | {d.skipped} | |")
        out.append(f"| Checksum differs | {len(d.checksum)} | |")
        out.append(f"| Read or download error | {len(d.errors)} | |")
        out.append(f"| Checksum not checkable | {len(d.checksum_unknown)} | "
                   f"{total([a for a, _b in d.checksum_unknown])} |")
    if d.flat:
        out.append(f"| Name occurs more than once | {len(d.duplicates)} | |")

    def table(heading: str, header: list[str], rows: list[list[str]]) -> None:
        if not rows:
            return
        out.extend(["", f"## {heading} ({len(rows)})", "",
                    "| " + " | ".join(header) + " |",
                    "|" + "|".join("---" for _ in header) + "|"])
        out.extend("| " + " | ".join(md_cell(c) for c in row) + " |" for row in rows)

    table(lb.only_left, ["File", "Size", "Modified"],
          [[f"`{e.path}`", size(e.size), fixity.fmt_ns(e.mtime_ns)] for e in d.only_left])
    table(lb.only_right, ["File", "Size", "Modified"],
          [[f"`{e.path}`", size(e.size), fixity.fmt_ns(e.mtime_ns)] for e in d.only_right])
    table("Size differs", ["File", lb.left, lb.right, "Note"],
          [[f"`{a.path}`", size(a.size), size(b.size), d.notes.get(a.path, "")] for a, b in d.size])
    table("Modification time differs", ["File", lb.left, lb.right],
          [[f"`{a.path}`", fixity.fmt_ns(a.mtime_ns), fixity.fmt_ns(b.mtime_ns)] for a, b in d.mtime])
    table("Checksum differs", ["File", "Size", "Kind", lb.left, lb.right, "Note"],
          [[f"`{a.path}`", size(a.size), *(lambda k, x, y: (k, f"`{x}`", f"`{y}`"))(*checksum_pair(a, b)),
            d.notes.get(a.path, "")] for a, b in d.checksum])
    table("Read or download error", ["File", "Size", "Error"],
          [[f"`{a.path}`", size(a.size), d.notes.get(a.path, "")] for a, _b in d.errors])
    table("Checksum not checkable", ["File", "Size", "Reason"],
          [[f"`{a.path}`", size(a.size), d.notes.get(a.path) or unknown_reason(a, b)]
           for a, b in d.checksum_unknown])
    table("Name occurs more than once (not compared)", ["Name", lb.left, lb.right],
          [[f"`{k}`",
            "<br>".join(f"`{e.path}` ({size(e.size)})" for e in ls),
            "<br>".join(f"`{e.path}` ({size(e.size)})" for e in rs)] for k, ls, rs in d.duplicates])

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def plan_text(plan: fixity.VerifyPlan, flt: fixity.FileFilter) -> list[str]:
    info = [f"- **Run started:** {plan.run_start}" + (" (resumed)" if plan.resumed else "")]
    if plan.cutoff:
        info.append(f"- **Only files not checked since:** {plan.cutoff}")
    if flt.active():
        info.append(f"- **Selection:** {flt.describe()}")
    return info


def saved_info(meta: dict[str, str]) -> str:
    line = meta.get("created", "?")
    if meta.get("complete", YES) != YES:
        line += " - INCOMPLETE"
    return line


# --------------------------------------------------------------------------- commands

class Context:
    def __init__(self, args) -> None:
        self.args = args
        config = args.config or os.environ.get(CONFIG_ENV)
        if not config:
            fail(f"no configuration: pass --config FILE or set {CONFIG_ENV}")
        config_path = Path(config).resolve()
        self.props = load_properties(config_path)
        # ONLY THE COMMANDS THAT READ THE DISK NEED A LOCAL ROOT. hash-b2, verify-b2 and compare
        # work on the bucket and the checksum files alone -- which is what lets a download-heavy
        # verify-b2 run on a machine in a data centre that holds nothing but those files.
        root = self.props.get("localRoot")
        if not root and args.command in LOCAL_COMMANDS:
            fail(f"'localRoot' is missing in {config_path} ({args.command} reads the local files)")
        self.local_root = Path(root) if root else None
        self.state_dir = Path(self.props.get("stateDir") or config_path.parent)
        self.checksum_dir = self.state_dir / "checksums"
        self.report_dir = Path(args.report_dir or self.props.get("reportDir") or self.state_dir / "reports")
        self.excludes = split_list(self.props.get("exclude", ""))
        self.flat_buckets = set(split_list(self.props.get("flatBuckets", "")))
        self.ignore_dirs = SKIP_DIRS | set(split_list(self.props.get("ignoreDirs", "")))
        self.vaults = parse_vaults(self.props.get("vaults", ""))
        self.filter = self._build_filter(args)
        self._api = None
        self._s3: S3Info | None = None
        self._thread = threading.local()

    @staticmethod
    def _build_filter(args) -> fixity.FileFilter:
        try:
            return fixity.FileFilter(
                include=getattr(args, "include", None) or [],
                exclude=getattr(args, "exclude", None) or [],
                min_size=fixity.parse_size(args.min_size) if getattr(args, "min_size", None) else None,
                max_size=fixity.parse_size(args.max_size) if getattr(args, "max_size", None) else None)
        except (ValueError, re.error) as e:
            fail(f"invalid selection: {e}")

    @property
    def api(self):
        if self._api is None:
            # Once, in the main thread, before b2sdk is even imported: every worker thread gets
            # its connection only after this has passed.
            problem = preflight()
            if problem:
                fail(f"B2 is not reachable from this machine: {problem}")
            self._api = new_b2_api(self.props["keyId"], self.props["applicationKey"])
        return self._api

    def thread_bucket(self, name: str):
        """One B2 connection per thread, for parallel downloads."""
        t = self._thread
        if not hasattr(t, "api"):
            t.api, t.buckets = new_b2_api(self.props["keyId"], self.props["applicationKey"]), {}
        if name not in t.buckets:
            t.buckets[name] = t.api.get_bucket_by_name(name)
        return t.buckets[name]

    @property
    def s3(self) -> S3Info:
        if self._s3 is None:
            self._s3 = S3Info(self.api, self.props["keyId"], self.props["applicationKey"])
        return self._s3

    def snapshot_path(self, bucket: str) -> Path:
        """What B2 states about a bucket (written by hash-b2)."""
        return self.checksum_dir / "b2" / f"{bucket}.tsv"

    def local_index(self, bucket: str) -> Path:
        """PyFixity's index of the local bucket directory. A first-version `<bucket>.tsv` beside it
        is moved onto it here, once, without reading any file."""
        index = self.checksum_dir / "local" / f"{bucket}.csv"
        legacy = index.with_suffix(".tsv")
        if not index.is_file() and legacy.is_file():
            root = self.local_root / bucket if self.local_root else None
            if root is None or not root.is_dir():
                fail(f"{legacy} needs the local directory once to move onto the new index")
            adopted, dropped = migrate_local_tsv(legacy, index, root, self.excludes)
            print(f"  moved {legacy.name} onto {index.name}: {adopted} entries adopted, "
                  f"{dropped} to be read again; the next hash-local adds SHA-256, MD5 and CRC32")
        return index

    def vault_index(self, bucket: str, directory: str) -> Path:
        """PyFixity's index of a vault's cleartext directory."""
        return self.checksum_dir / "local" / f"{bucket}-{slug(directory)}.csv"

    def vault_key(self, bucket: str, directory: str) -> Path:
        explicit = self.props.get(f"vaultKey.{bucket}/{directory}")
        if explicit:
            return Path(explicit)
        if self.local_root is None:
            fail(f"no passphrase file for the vault {bucket}/{directory}: set "
                 f"'vaultKey.{bucket}/{directory}' or 'localRoot'")
        return self.local_root / bucket / f"{directory}.key"

    def local_trees(self, name: str) -> list[tuple[str, Path, Path]]:
        """(label, directory, index) of what is indexed locally for a bucket: the bucket directory,
        or for a vault bucket each cleartext vault directory."""
        if name in self.vaults:
            return [(f"{name}/{d}", self.local_root / name / d, self.vault_index(name, d))
                    for d in self.vaults[name]]
        return [(name, self.local_root / name, self.local_index(name))]

    def b2_names(self) -> list[str]:
        return sorted(p.stem for p in (self.checksum_dir / "b2").glob("*.tsv"))

    def local_names(self) -> list[str]:
        d = self.checksum_dir / "local"
        names = {p.stem for p in d.glob("*.csv")} | {p.stem for p in d.glob("*.tsv")}
        vault_indexes = {self.vault_index(b, v).stem for b, vs in self.vaults.items() for v in vs}
        indexed_vaults = {b for b, vs in self.vaults.items() if any(self.vault_index(b, v).is_file() for v in vs)}
        return sorted((names - vault_indexes - set(self.vaults)) | indexed_vaults)

    def threads(self, default: int) -> int:
        return getattr(self.args, "threads", None) or default

    def hash_threads(self) -> int:
        return max(1, getattr(self.args, "hash_threads", None) or fixity.HASH_THREADS)

    def is_flat(self, name: str) -> bool:
        return self.args.flat or name in self.flat_buckets

    def local_dirs(self) -> set[str]:
        """The directories below localRoot that stand for a bucket.

        THE TOOL'S OWN STATE IS NEVER ONE, whatever it is called. stateDir defaults to the
        directory of the configuration, which is often localRoot itself, and a report directory
        named in the configuration lands there too. Recognising them by name ("checksums",
        "reports") missed every other name -- and `hash-local` without arguments then indexed the
        reports as if they were a bucket. So the configured paths are compared, not the names.
        """
        if self.local_root is None:
            return set()
        own = {p.resolve() for p in (self.checksum_dir, self.report_dir)}
        names = set()
        for d in self.local_root.iterdir():
            if not d.is_dir() or d.name in self.ignore_dirs or d.name.startswith("."):
                continue
            here = d.resolve()
            if any(here == p or here in p.parents for p in own):
                continue
            names.add(d.name)
        return names

    def remote_buckets(self) -> set[str]:
        try:
            return {b.name for b in self.api.list_buckets()}
        except Exception as e:  # e.g. a key restricted to one bucket
            print(f"note: cannot list buckets ({e}); using the local directories")
            return self.local_dirs()

    def report(self, name: str, diff: fixity.Diff, options: list[str], info: list[str],
               suffix: str = "", title: str = "") -> None:
        if self.filter.active() and not any(i.startswith("- **Selection:**") for i in info):
            info = info + [f"- **Selection:** {self.filter.describe()}"]
        print_diff(name, diff, self.args.limit, "checksum" in options)
        if not self.args.no_report:
            md = self.report_dir / f"{name}{suffix}.md"
            write_markdown(md, title or name, diff, options, info)
            print(f"  -> {md}")


def local_files(ctx: Context, name: str) -> list[fixity.Entry]:
    """The local bucket directory as it is now, without manifests, index and exclusions."""
    root = ctx.local_root / name
    return fixity.scan_tree(root, ctx.excludes, fixity.own_files(root, ctx.local_index(name)))


def cmd_check(ctx: Context) -> int:
    args = ctx.args
    local_dirs, remote_buckets = ctx.local_dirs(), ctx.remote_buckets()
    if args.buckets:
        names = set(args.buckets)
    else:
        for n in sorted(remote_buckets - local_dirs):
            print(f"bucket without a local directory: {n}")
        for n in sorted(local_dirs - remote_buckets):
            print(f"directory without a bucket:      {n}")
        names = local_dirs & remote_buckets
    options = ["modification time"] if args.mtime else []

    any_diff = False
    for name in sorted(names):
        if name in ctx.vaults:
            print(f"\n{name}: {VAULT_SKIP}")
            continue
        flat = ctx.is_flat(name)
        print(f"\nchecking {name}{' (flat)' if flat else ''} ...", flush=True)
        if not (ctx.local_root / name).is_dir():
            print(f"  local directory missing: {ctx.local_root / name}")
            any_diff = True
            continue
        bucket = ctx.api.get_bucket_by_name(name)
        local = ctx.filter.apply(local_files(ctx, name))
        remote = ctx.filter.apply(scan_remote(bucket, ctx.excludes))
        diff = fixity.compare(local, remote, flat, check_mtime=args.mtime,
                              mtime_tolerance_ns=int(args.mtime_tolerance * 1e9), labels=LOCAL_VS_B2)
        ctx.report(name, diff, options, ["- **Source:** live (local tree and B2 listing)"])
        any_diff |= diff.has_differences()

    print("\nresult:", "differences found." if any_diff else "everything in sync.")
    return 1 if any_diff else 0


def b2_part_layouts(ctx: Context, name: str) -> fixity.Layouts:
    """From checksums/b2: files with an ETag but no SHA-1 -> (part sizes, multipart)."""
    path = ctx.snapshot_path(name)
    if not path.is_file():
        return {}
    flat = ctx.is_flat(name)
    layouts: fixity.Layouts = {}
    for e in read_snapshot(path)[1]:
        if not e.sha1 and e.etag and e.parts:
            layouts[fixity.basename(e.path) if flat else e.path] = (e.parts, fixity.is_multipart_etag(e.etag))
    return layouts


def cmd_hash_local(ctx: Context) -> int:
    names = ctx.args.buckets or sorted(ctx.local_dirs())
    any_damage = False
    for name in names:
        vault = name in ctx.vaults
        for label, root, index in ctx.local_trees(name):
            if not root.is_dir():
                print(f"\n{label}: local directory missing ({root})")
                continue
            print(flush=True)
            if vault:
                # The B2 part layouts describe the ciphertext: nothing to hash along.
                print(f"{label}: the cleartext of a Cryptomator vault")
                layouts: fixity.Layouts = {}
            else:
                layouts = b2_part_layouts(ctx, name)
                if not layouts and not ctx.snapshot_path(name).is_file():
                    print("  note: no B2 checksums yet - large files without a SHA-1 in B2 become checkable "
                          "after 'hash-b2' and another 'hash-local'.")
            key = fixity.basename if ctx.is_flat(name) and not vault else (lambda p: p)
            # B2's real layouts first, PyFixity's default (.s3etag) for the rest. Not for a vault:
            # B2 holds its ciphertext, so an ETag of the cleartext could never be compared.
            r = fixity.update_index(root, index, ctx.excludes, layouts, key, ctx.args.force,
                                    out=lambda line: print(line, flush=True),
                                    s3=None if vault else fixity.DEFAULT_S3,
                                    threads=ctx.threads(1), hash_threads=ctx.hash_threads())
            print(f"  -> {index}  ({r.summary}){'' if r.complete else '  INCOMPLETE'}")
            for manifest, what in r.manifests.items():
                print(f"  {manifest}: {what}")
            if r.damaged:
                any_damage = True
                print(f"  WARNING: {len(r.damaged)} file(s) with different content at the same size and time "
                      f"(possible silent damage); the saved checksums were kept. Details"
                      f"{'' if vault else ' and the state in B2'}: verify-local {name}")
                for e, _new in r.damaged:
                    print(f"    ! {e.path}")
    return 1 if any_damage else 0


def cmd_hash_b2(ctx: Context) -> int:
    names = ctx.args.buckets or sorted(ctx.remote_buckets())
    for name in names:
        out = ctx.snapshot_path(name)
        prev_meta, prev = load_previous(out)
        print(f"\n{name}: listing B2 ...", flush=True)
        bucket = ctx.api.get_bucket_by_name(name)
        entries = scan_remote(bucket, ctx.excludes)
        # B2 files are immutable: the same file id means the same bytes, so earlier work carries over.
        for e in entries:
            p = prev.get(e.path)
            if p and p.file_id == e.file_id:
                e.verified = p.verified
                if not e.sha1:
                    e.sha1, e.etag, e.parts, e.source = p.sha1, p.etag, p.parts, p.source
        need_etag = [e for e in entries if not e.sha1 and not e.etag]
        print(f"  {len(entries)} files: {sum(1 for e in entries if e.sha1)} with SHA-1, "
              f"{sum(1 for e in entries if not e.sha1 and e.etag)} with ETag, "
              f"{len(need_etag)} without a checksum ({fixity.fmt_size(sum(e.size for e in need_etag))})",
              flush=True)
        for line in unfinished_report(unfinished_uploads(bucket), {e.path for e in entries}):
            print(f"  {line}")

        saver = SnapshotSaver(out, new_meta(name, "b2", prev_meta), entries)
        finished = False
        try:
            for i, e in enumerate(need_etag, 1):
                print(f"  [{i}/{len(need_etag)}] ETag {fixity.fmt_size(e.size):>9}  {e.path}", flush=True)
                try:
                    e.etag, e.parts = ctx.s3.etag_and_parts(name, e)
                    e.source = "s3"
                except Exception as ex:
                    print(f"    no ETag: {ex}")
                saver.maybe_save()
            unknown = [e for e in entries if not e.sha1 and not e.etag]
            if ctx.args.download_unknown and unknown:
                progress = fixity.Progress(len(unknown), sum(e.size for e in unknown),
                                           out=lambda line: print(line, flush=True))

                def work(e: FileEntry, stop: threading.Event) -> str:
                    digests = fixity.hash_chunks(b2_chunks(ctx.thread_bucket(name), e.file_id),
                                                 stop=stop, want=("sha1",))[0]
                    return digests["sha1"]

                def done(e: FileEntry, sha1: str | None, err: Exception | None) -> None:
                    if err:
                        progress.step("ERROR", e)
                        print(f"    {err}")
                    else:
                        e.sha1, e.source = sha1, "download"
                        progress.step("SHA-1", e)
                    saver.maybe_save()

                fixity.run_parallel(unknown, work, ctx.threads(4), done)
                print(f"  downloaded and hashed: {progress.summary()}")
            elif unknown:
                print(f"  {len(unknown)} file(s) still without a checksum (--download-unknown hashes them)")
            finished = True
        finally:
            saver.save(complete=finished)
        print(f"  -> {out}")
    return 0


def add_b2_notes(ctx: Context, diff: fixity.Diff, name: str, info: list[str]) -> None:
    """For every local checksum difference, say whether the copy in B2 is still intact."""
    flat = ctx.is_flat(name)
    bp = ctx.snapshot_path(name)
    idx = None
    if bp.is_file():
        bmeta, bentries = read_snapshot(bp)
        idx = fixity.make_index(bentries, flat)
        info.append(f"- **B2 checksums (for the notes):** {saved_info(bmeta)}")
    for now, saved in diff.checksum:
        kind = ("size and time unchanged - silent damage?" if now.mtime_ns == saved.mtime_ns
                else "the file was modified (new modification time)")
        cands = None if idx is None else idx.get(fixity.basename(saved.path) if flat else saved.path, [])
        diff.notes[now.path] = f"{kind}; {b2_state(now, saved, cands)}"


def cmd_verify_local(ctx: Context) -> int:
    """Local files against PyFixity's index: new, gone, changed, damaged."""
    names = ctx.args.buckets or ctx.local_names()
    if not names:
        print("no local checksums yet - run 'hash-local' first.")
        return 2
    any_diff = False
    for name in names:
        for label, root, index in ctx.local_trees(name):
            if not root.is_dir():
                print(f"\n{label}: local directory missing")
                any_diff = True
                continue
            if not index.is_file():
                print(f"\n{label}: no local index - run 'hash-local {name}' first")
                any_diff = True
                continue
            state = fixity.read_state(index)
            print(f"\nverifying {label} locally against its index ({saved_info(state)}) ...", flush=True)
            r = fixity.verify_tree(root, index, ctx.excludes, ctx.filter, ctx.args.quick, ctx.args.resume,
                                   ctx.args.older_than, ctx.threads(1), out=lambda line: print(line, flush=True),
                                   hash_threads=ctx.hash_threads())
            info = [f"- **Local index:** {saved_info(state)}"]
            if r.summary:
                print(f"  read: {r.summary}")
            if r.plan:
                info += plan_text(r.plan, ctx.filter)
            if r.diff.checksum and name not in ctx.vaults:  # B2's checksums of a vault are ciphertext
                add_b2_notes(ctx, r.diff, name, info)
            options = ["modification time"] + ([] if ctx.args.quick else ["checksum"])
            ctx.report(slug(label), r.diff, options, info, suffix=".local",
                       title=f"{label} - local against its index")
            any_diff |= r.diff.has_differences()
    print("\nresult:", "differences found." if any_diff else "nothing changed.")
    return 1 if any_diff else 0


def verify_b2_content(ctx: Context, name: str, meta: dict[str, str], all_saved: list[FileEntry],
                      saved: list[FileEntry], current: list[FileEntry]) -> bool:
    """Stream the B2 content, hash it and compare it with what B2's metadata states."""
    current_ids = {e.path: e.file_id for e in current}
    # Only files that still exist in B2 exactly as recorded in checksums/b2.
    candidates = [p for p in saved if current_ids.get(p.path) == p.file_id]
    plan = fixity.plan_verification(candidates, meta, ctx.args.resume, ctx.args.older_than)
    threads = ctx.threads(4)
    print(f"\nverifying the content of {name} in B2: {len(plan.todo)} files "
          f"({fixity.fmt_size(sum(p.size for p in plan.todo))}) on {threads} thread(s), {len(plan.skipped)} skipped"
          + (f" (resuming the run of {plan.run_start})" if plan.resumed else ""), flush=True)
    meta["verify_start"] = plan.run_start
    saver = SnapshotSaver(ctx.snapshot_path(name), meta, all_saved, complete_key="verify_complete")
    progress = fixity.Progress(len(plan.todo), sum(p.size for p in plan.todo), out=lambda line: print(line, flush=True))
    content: dict[str, FileEntry] = {p.path: copy_entry(p, skipped=True) for p in plan.skipped}
    errors: dict[str, str] = {}
    expected = {p.path: expected_from_metadata(p) for p in plan.todo + plan.skipped}

    def work(p: FileEntry, stop: threading.Event):
        parts = p.parts if p.etag else None
        return fixity.hash_chunks(b2_chunks(ctx.thread_bucket(name), p.file_id), parts,
                                  bool(p.etag and fixity.is_multipart_etag(p.etag)), stop, want=("sha1",),
                                  threads=fixity.hash_threads_for(p.size, ctx.hash_threads()))

    def done(p: FileEntry, result, err: Exception | None) -> None:
        if err:
            errors[p.path] = f"download error: {err}"
            content[p.path] = copy_entry(p, sha1=None, etag=None)
            progress.step("ERROR", p)
        else:
            digests, etag, size = result
            content[p.path] = got = FileEntry(p.path, size, p.mtime_ms, digests["sha1"], etag,
                                              p.parts if p.etag else None)
            match = fixity.checksums_match(got, expected[p.path])[0]
            if match and not p.sha1:
                p.sha1 = digests["sha1"]  # a real SHA-1, confirmed by the ETag -> comparable by SHA-1 from now on
            # A failed file loses its timestamp, so every later run downloads it again.
            p.verified = fixity.now_ts() if match else ""
            progress.step({True: "OK", False: "MISMATCH", None: "UNKNOWN"}[match], p)
        saver.maybe_save()

    finished = False
    try:
        fixity.run_parallel(plan.todo, work, threads, done)
        finished = True
    finally:
        saver.save(complete=finished)
    print(f"  read: {progress.summary()}")

    diff = fixity.compare([content[p] for p in expected if p in content], list(expected.values()),
                          check_sum=True, labels=CONTENT_VS_META)
    diff.attach_errors(errors)
    if diff.checksum or diff.size:
        local_index = ctx.checksum_dir / "local" / f"{name}.csv"
        flat = ctx.is_flat(name)
        idx = fixity.make_index(fixity.read_index(local_index), flat) if local_index.is_file() else None
        for got, _exp in diff.checksum + diff.size:
            cands = None if idx is None else idx.get(fixity.basename(got.path) if flat else got.path, [])
            diff.notes[got.path] = f"B2 content does not match the B2 metadata; {local_state(got, cands)}"
    info = [f"- **B2 checksums:** {saved_info(meta)}", f"- **Threads:** {threads}"] + plan_text(plan, ctx.filter)
    ctx.report(name, diff, ["checksum"], info, suffix=".b2-content", title=f"{name} - B2 content against B2 metadata")
    return diff.has_differences()


def cmd_verify_b2(ctx: Context) -> int:
    """The current B2 listing against checksums/b2; with --download also the content."""
    names = ctx.args.buckets or ctx.b2_names()
    if not names:
        print("no B2 checksums yet - run 'hash-b2' first.")
        return 2
    any_diff = False
    for name in names:
        sp = ctx.snapshot_path(name)
        if not sp.is_file():
            print(f"\n{name}: checksum file missing ({sp})")
            any_diff = True
            continue
        meta, all_saved = read_snapshot(sp)
        saved = ctx.filter.apply([e for e in all_saved
                                  if not fixity.is_excluded(e.path, ctx.excludes) and not is_root_manifest(e.path)])
        print(f"\nverifying {name} in B2 against the saved checksums ({saved_info(meta)}) ...", flush=True)
        bucket = ctx.api.get_bucket_by_name(name)
        listing = scan_remote(bucket, ctx.excludes)
        current = ctx.filter.apply(listing)
        # B2 files are immutable: the same file id means the same content.
        by_path = {e.path: e for e in saved}
        for e in current:
            p = by_path.get(e.path)
            if not e.sha1 and p and p.file_id == e.file_id:
                e.sha1, e.etag, e.parts = p.sha1, p.etag, p.parts
        info = [f"- **Saved checksums:** {saved_info(meta)}"]
        unfinished = unfinished_report(unfinished_uploads(bucket), {e.path for e in listing})
        for line in unfinished:
            print(f"  {line}")
        if unfinished:
            info.append(f"- **Unfinished uploads:** {unfinished[0]}")
            info += [f"  - {line.strip()}" for line in unfinished[1:]]
        diff = fixity.compare(current, saved, check_sum=True, labels=B2_NOW_VS_SAVED)
        ctx.report(name, diff, ["checksum"], info, suffix=".b2", title=f"{name} - B2 against saved checksums")
        any_diff |= diff.has_differences()
        if ctx.args.download:
            any_diff |= verify_b2_content(ctx, name, meta, all_saved, saved, current)
    print("\nresult:", "differences found." if any_diff else "nothing changed.")
    return 1 if any_diff else 0


def cmd_compare(ctx: Context) -> int:
    if ctx.args.buckets:
        names = ctx.args.buckets
    else:
        names = sorted(set(ctx.local_names()) | set(ctx.b2_names()))
        if not names:
            print("no checksums yet - run 'hash-b2' and 'hash-local' first.")
            return 2

    any_diff = False
    for name in names:
        if name in ctx.vaults:
            print(f"\n{name}: {VAULT_SKIP}")
            continue
        lp = ctx.checksum_dir / "local" / f"{name}.csv"
        if not lp.is_file() and lp.with_suffix(".tsv").is_file():
            lp = ctx.local_index(name)  # moves a first-version file onto the index
        rp = ctx.snapshot_path(name)
        missing = [f"{p} missing ({cmd})" for p, cmd in ((lp, "hash-local"), (rp, "hash-b2")) if not p.is_file()]
        if missing:
            print(f"\n{name}: " + "; ".join(missing))
            any_diff = True
            continue
        lstate = fixity.read_state(lp)
        rmeta, remote = read_snapshot(rp)
        local = ctx.filter.apply([e for e in fixity.read_index(lp) if not fixity.is_excluded(e.path, ctx.excludes)])
        remote = ctx.filter.apply([e for e in remote
                                   if not fixity.is_excluded(e.path, ctx.excludes) and not is_root_manifest(e.path)])
        flat = ctx.is_flat(name)
        print(f"\ncomparing checksums of {name}{' (flat)' if flat else ''} ...")
        info = []
        for label, meta in (("local", lstate), ("B2", rmeta)):
            line = saved_info(meta)
            print(f"  {label} as of: {line}")
            info.append(f"- **{label} as of:** {line}")
        diff = fixity.compare(local, remote, flat, check_sum=True, labels=LOCAL_VS_B2)
        hint = stale_b2_hint(diff, rmeta.get("created"))
        if hint:
            print(f"  hint: {hint}")
            info.append(f"- **Hint:** {hint}")
        ctx.report(name, diff, ["checksum"], info)
        any_diff |= diff.has_differences()

    print("\nresult:", "differences found." if any_diff else "everything in sync.")
    return 1 if any_diff else 0


DECRYPTED_VS_LOCAL = fixity.Labels("Decrypted", "Local", "Decrypted only", "Not decrypted")


def vault_objects(bucket, prefix: str) -> dict[str, tuple[int, str]]:
    """Every current object below a vault's root: name relative to it -> (size, file id)."""
    objects = {}
    for fv, _folder in bucket.ls(prefix, latest_only=True, recursive=True):
        if fv.action == "upload" and fv.file_name.startswith(prefix):
            objects[fv.file_name[len(prefix):]] = (fv.size, fv.id_)
    return objects


def read_passphrase(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"passphrase file missing: {path}")
    passphrase = path.read_text(encoding="utf-8-sig").rstrip("\r\n")
    if not passphrase:
        raise ValueError(f"passphrase file is empty: {path}")
    return passphrase


def vault_content(ctx: Context, cryptomator, name: str, vault, objects: dict, files: list,
                  local: dict[str, fixity.Entry]) -> fixity.Diff:
    """Stream, decrypt and hash each file; compare its checksums with the local index."""
    threads = ctx.threads(4)
    total = sum(f.cipher_size for f in files)
    print(f"  decrypting {len(files)} files ({fixity.fmt_size(total)} of ciphertext) on {threads} thread(s) ...",
          flush=True)
    progress = fixity.Progress(len(files), sum(local[f.path].size for f in files),
                               out=lambda line: print(line, flush=True))
    content: dict[str, fixity.Entry] = {}
    errors: dict[str, str] = {}

    def work(f, stop: threading.Event):
        chunks = b2_chunks(ctx.thread_bucket(name), objects[f.object_name][1])
        return fixity.hash_chunks(vault.decrypt_chunks(chunks), stop=stop,
                                  threads=fixity.hash_threads_for(f.cipher_size, ctx.hash_threads()))

    def done(f, result, err: Exception | None) -> None:
        exp = local[f.path]
        if err:
            damaged = isinstance(err, cryptomator.DamagedError)
            errors[f.path] = f"DAMAGED in B2: {err}" if damaged else f"download error: {err}"
            content[f.path] = fixity.Entry(f.path, exp.size, 0)  # nothing known -> reported as an error
            progress.step("DAMAGED" if damaged else "ERROR", exp)
            return
        digests, _etag, size = result
        content[f.path] = got = fixity.Entry(f.path, size, 0)
        got.set_digests(digests)
        match = fixity.checksums_match(got, exp)[0]
        progress.step({True: "OK", False: "MISMATCH", None: "UNKNOWN"}[match], exp)

    fixity.run_parallel(files, work, threads, done)
    print(f"  read: {progress.summary()}")
    diff = fixity.compare(list(content.values()), [local[p] for p in content], check_sum=True,
                          labels=DECRYPTED_VS_LOCAL)
    diff.attach_errors(errors)
    return diff


def check_vault(ctx: Context, cryptomator, name: str, directory: str, bucket,
                unfinished: list[str] | None) -> bool:
    """One vault: open, walk, compare with the local index; True if anything is wrong."""
    label = f"{name}/{directory}"
    print(f"\nchecking the vault {label} ...", flush=True)
    objects = vault_objects(bucket, directory + "/")
    missing = [f for f in cryptomator.VAULT_FILES if f not in objects]
    if missing:
        print(f"  no vault here: {', '.join(missing)} missing in {label}/")
        return True

    def read(rel: str) -> bytes:
        return b"".join(b2_chunks(bucket, objects[rel][1]))

    try:
        vault = cryptomator.Vault.open(read(cryptomator.VAULT_FILES[0]), read(cryptomator.VAULT_FILES[1]),
                                       read_passphrase(ctx.vault_key(name, directory)))
    except (cryptomator.VaultError, OSError, ValueError) as e:
        print(f"  cannot open the vault: {e}")
        return True
    tree = cryptomator.walk(vault, {n: s for n, (s, _id) in objects.items() if n not in cryptomator.VAULT_FILES},
                            read, [B2_FOLDER_PLACEHOLDER])
    print(f"  opened: format 8, SIV_GCM, keys and signature verified; {len(tree.files)} files in "
          f"{tree.directories} directories")
    info = [f"- **Vault:** {label}, {len(tree.files)} files in {tree.directories} directories"]
    for p in tree.problems:
        print(f"  PROBLEM: {p}")
        info.append(f"- **Problem:** {p}")
    if tree.leftovers:
        line = (f"{len(tree.leftovers)} unreferenced directory folder(s) holding only placeholders - "
                f"harmless leftovers of deleted directories")
        print(f"  note: {line}")
        info.append(f"- **Note:** {line}")
    mine = [n for n in unfinished or [] if n.startswith(directory + "/")]
    for line in unfinished_report(mine, {directory + "/" + n for n in objects}):
        print(f"  {line}")
        info.append(f"- {line.strip()}")

    index = ctx.vault_index(name, directory)
    if not index.is_file():
        print(f"  no local index ({index}) - run 'hash-local {name}' to compare names and sizes")
        return bool(tree.problems or mine)
    state = fixity.read_state(index)
    print(f"  local index as of: {saved_info(state)}")
    info.append(f"- **Local index:** {saved_info(state)}")
    keep = lambda p: not is_root_manifest(p) and not fixity.is_excluded(p, ctx.excludes)  # noqa: E731
    local = ctx.filter.apply([e for e in fixity.read_index(index) if keep(e.path)])
    # An impossible ciphertext size is already a problem; -1 makes it a size difference as well.
    remote = ctx.filter.apply([fixity.Entry(p, f.size if f.size is not None else -1, 0)
                               for p, f in tree.files.items() if keep(p)])
    diff = fixity.compare(local, remote, labels=LOCAL_VS_B2)
    ctx.report(name, diff, [], info, suffix=f".vault-{slug(directory)}",
               title=f"{label} - Cryptomator vault in B2 against the local index")
    bad = bool(tree.problems or mine) or diff.has_differences()
    if ctx.args.download:
        by_path = {e.path: e for e in local}
        same = [tree.files[e.path] for e in remote if e.path in by_path and by_path[e.path].size == e.size]
        cdiff = vault_content(ctx, cryptomator, name, vault, objects, same, by_path)
        ctx.report(name, cdiff, ["checksum"], info, suffix=f".vault-{slug(directory)}-content",
                   title=f"{label} - decrypted content against the local index")
        bad |= cdiff.has_differences()
    return bad


def cmd_vault(ctx: Context) -> int:
    import cryptomator  # imported here, like b2sdk, so that --help needs nothing
    try:
        cryptomator.require()
    except ImportError as e:
        fail(f"checking a Cryptomator vault needs the 'cryptography' package ({e}); "
             f"pip install -r requirements.txt")
    names = ctx.args.buckets or sorted(ctx.vaults)
    if not names:
        print("no vaults configured - add 'vaults=<bucket>/<directory>' to the configuration.")
        return 2
    any_bad = False
    for name in names:
        if name not in ctx.vaults:
            print(f"\n{name}: not configured as a vault (vaults=<bucket>/<directory>)")
            any_bad = True
            continue
        bucket = ctx.api.get_bucket_by_name(name)
        unfinished = unfinished_uploads(bucket)
        for directory in ctx.vaults[name]:
            any_bad |= check_vault(ctx, cryptomator, name, directory, bucket, unfinished)
    print("\nresult:", "problems found." if any_bad else "every vault is consistent and matches.")
    return 1 if any_bad else 0


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("buckets", nargs="*", help="only these buckets/directories (default: all)")
    common.add_argument("--config", help=f"properties file (default: ${CONFIG_ENV})")
    common.add_argument("--flat", action="store_true", help="ignore directories, compare file names only")
    common.add_argument("--limit", type=int, default=50, help="max. lines per category on the console (0 = all)")
    common.add_argument("--report-dir", type=Path, help="where <bucket>*.md go (default: reportDir, else <stateDir>/reports)")
    common.add_argument("--no-report", action="store_true", help="write no Markdown reports")

    selection = argparse.ArgumentParser(add_help=False)
    g = selection.add_argument_group("selection")
    g.add_argument("--include", action="append", metavar="REGEX",
                   help="only paths REGEX matches (repeat = or), e.g. '\\.mp4$' or '^Recordings/'")
    g.add_argument("--exclude", action="append", metavar="REGEX", help="leave out paths REGEX matches")
    g.add_argument("--min-size", metavar="SIZE", help="only files >= SIZE (e.g. 1M)")
    g.add_argument("--max-size", metavar="SIZE", help="only files < SIZE (e.g. 1M)")

    verify = argparse.ArgumentParser(add_help=False)
    g = verify.add_argument_group("verification run")
    g.add_argument("--threads", type=int, metavar="N", help="files in parallel (default: local 1, B2 4)")
    g.add_argument("--hash-threads", type=int, metavar="N",
                   help=f"threads per file for the digests (default {fixity.HASH_THREADS}; 1 = none)")
    g.add_argument("--resume", action="store_true", help="continue an interrupted run")
    g.add_argument("--older-than", type=float, metavar="DAYS",
                   help="only files not successfully checked for DAYS")

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("check", parents=[common, selection], help="live: names and sizes")
    p.add_argument("--mtime", action="store_true", help="also compare modification times")
    p.add_argument("--mtime-tolerance", type=float, default=2.0, help="tolerance for --mtime in seconds")
    p = sub.add_parser("hash-local", parents=[common], help="update the local index and write the manifests")
    p.add_argument("--threads", type=int, metavar="N", help="files at once, finished in their order (default 1)")
    p.add_argument("--hash-threads", type=int, metavar="N",
                   help=f"threads per file for the digests (default {fixity.HASH_THREADS}; 1 = none)")
    p.add_argument("--force", action="store_true", help="re-read every file, not only changed ones")
    p = sub.add_parser("hash-b2", parents=[common], help="record what B2 states (SHA-1, else S3 ETag)")
    p.add_argument("--download-unknown", action="store_true",
                   help="download and hash files without any checksum (costs download traffic)")
    p.add_argument("--threads", type=int, metavar="N", help="parallel downloads (default 4)")
    p = sub.add_parser("verify-local", parents=[common, selection, verify],
                       help="re-read local files against the local index")
    p.add_argument("--quick", action="store_true", help="names, sizes and times only; read nothing")
    p = sub.add_parser("verify-b2", parents=[common, selection, verify],
                       help="B2 against checksums/b2; with --download also the content")
    p.add_argument("--download", action="store_true",
                   help="stream the content from B2 and check it against the B2 metadata (costs download traffic)")
    sub.add_parser("compare", parents=[common, selection], help="local index against saved B2 checksums")
    p = sub.add_parser("vault", parents=[common, selection],
                       help="a Cryptomator vault in B2: structure, names and sizes against the local index")
    p.add_argument("--download", action="store_true",
                   help="also decrypt every file and compare its checksums (costs download traffic)")
    p.add_argument("--threads", type=int, metavar="N", help="parallel downloads with --download (default 4)")
    p.add_argument("--hash-threads", type=int, metavar="N",
                   help=f"threads per file for the digests (default {fixity.HASH_THREADS}; 1 = none)")
    return ap


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or (argv[0] not in COMMANDS and argv[0] not in ("-h", "--help")):
        argv = ["check"] + argv  # the default command
    args = build_parser().parse_args(argv)
    ctx = Context(args)
    return {"check": cmd_check, "hash-local": cmd_hash_local, "hash-b2": cmd_hash_b2,
            "verify-local": cmd_verify_local, "verify-b2": cmd_verify_b2,
            "compare": cmd_compare, "vault": cmd_vault}[args.command](ctx)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\ninterrupted (progress has been saved).", file=sys.stderr)
        sys.exit(130)
    except SystemExit:
        raise
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)
