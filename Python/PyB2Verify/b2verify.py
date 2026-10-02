#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Check that local directories and their Backblaze B2 buckets hold the same bytes -- and keep
checking, on both sides, that they still do. Nothing is ever uploaded, changed or deleted in B2.

Each directory below `localRoot` belongs to the bucket of the same name. Checksums are kept in two
tab-separated files per bucket, one per side, so that each side can be re-indexed or re-read on
its own and compared later:

    <stateDir>/checksums/local/<bucket>.tsv     written by hash-local, read by verify-local
    <stateDir>/checksums/b2/<bucket>.tsv        written by hash-b2,    read by verify-b2
    <stateDir>/reports/<bucket>*.md             one Markdown report per bucket and check

COMMANDS
    check [bucket ...]          live: names and sizes, local tree against the bucket listing
        --mtime                 also compare modification times
    hash-b2 [bucket ...]        record what B2 states: SHA-1, else S3 ETag and part sizes
        --download-unknown      download and hash files that have neither
    hash-local [bucket ...]     bring the local checksums up to date (only what changed)
        --force                 re-read everything; a saved checksum is NEVER silently replaced
                                when size and mtime are unchanged -- that is reported as damage
    verify-local [bucket ...]   re-read local files and compare them with the saved checksums
        --quick                 names, sizes and times only; read nothing
    verify-b2 [bucket ...]      compare the current bucket listing with the saved checksums
        --download              also stream every file from B2, hash it and compare it with what
                                B2's metadata states -- straight from the network, no temp files
    compare [bucket ...]        saved local checksums against saved B2 checksums, 1:1

VERIFICATION RUNS (verify-local, verify-b2 --download, hash-b2 --download-unknown)
    --threads N                 files in parallel (default: local 1, B2 4)
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
    localRoot=D:/backup                     one directory per bucket below it
    stateDir=D:/backup-state                optional; default: the directory of the config file
    reportDir=D:/backup-state/reports       optional; default: <stateDir>/reports
    exclude=Thumbs.db,desktop.ini,*.lnk     optional; glob patterns, never compared
    flatBuckets=example-flat-bucket         optional; buckets uploaded without directories
    ignoreDirs=scratch                      optional; directories below localRoot that are no bucket
                                            (stateDir and reportDir are recognised by themselves)

WHY THE ETAG MATTERS. B2 has no SHA-1 for most files uploaded in parts. Their S3 ETag is the MD5 of
the part MD5s; hash-b2 fetches it with the part sizes, and hash-local cuts the local file the same
way. Run hash-b2 BEFORE hash-local, so the part sizes are known when the local file is read.

Exit status: 0 everything matches / done, 1 differences found, 2 error.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import threading
import time
from pathlib import Path
from typing import Iterator

from b2lib import (CONTENT_VS_META, NOW_VS_SAVED, READ_CHUNK, YES, Diff, FileEntry, FileFilter,
                   SnapshotSaver, VerifyPlan, b2_state, basename, checksums_match, compare, copy_entry,
                   expected_from_metadata, fmt_ms, fmt_size, hash_chunks, hash_file, is_excluded,
                   is_multipart_etag, load_previous, local_state, make_index, new_meta, norm, now_ts,
                   parse_size, plan_verification, read_file_chunks, read_snapshot, run_parallel,
                   scan_local, total)

CONFIG_ENV = "B2VERIFY_CONFIG"
# Directories below localRoot that are never a bucket. Hidden ones (".venv", ...) are skipped too,
# and so is whatever holds this tool's own checksums and reports -- see Context.local_dirs.
SKIP_DIRS = {"__pycache__"}
# The placeholder the B2 web interface creates for an empty folder.
B2_FOLDER_PLACEHOLDER = ".bzEmpty"
COMMANDS = ("check", "hash-local", "hash-b2", "verify-local", "verify-b2", "compare")


def fail(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(2)


def load_properties(path: Path) -> dict[str, str]:
    if not path.is_file():
        fail(f"configuration not found: {path}")
    props: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "!")):
            continue
        sep = min((i for i in (line.find("="), line.find(":")) if i >= 0), default=-1)
        if sep < 0:
            continue
        props[line[:sep].strip()] = line[sep + 1:].strip()
    for key in ("keyId", "applicationKey", "localRoot"):
        if not props.get(key):
            fail(f"'{key}' is missing in {path}")
    return props


def split_list(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


# --------------------------------------------------------------------------- B2 and S3

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
        if not count or not is_multipart_etag(etag):
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
        yield from response.iter_content(READ_CHUNK)
    finally:
        response.close()


def scan_remote(bucket, excludes: list[str]) -> list[FileEntry]:
    files: list[FileEntry] = []
    for fv, _folder in bucket.ls(latest_only=True, recursive=True):
        if fv.action != "upload":  # hidden or deleted versions are not files
            continue
        name = norm(fv.file_name)
        if basename(name) == B2_FOLDER_PLACEHOLDER or is_excluded(name, excludes):
            continue
        sha1 = fv.get_content_sha1()
        files.append(FileEntry(name, fv.size, fv.mod_time_millis, sha1=sha1,
                               source="b2" if sha1 else "", file_id=fv.id_, key=fv.file_name))
    return sorted(files, key=lambda e: e.path)


# --------------------------------------------------------------------------- output

def checksum_pair(lf: FileEntry, rf: FileEntry) -> tuple[str, str, str]:
    if lf.sha1 and rf.sha1:
        return "SHA-1", lf.sha1, rf.sha1
    return "ETag", lf.etag or "", rf.etag or ""


def unknown_reason(lf: FileEntry, rf: FileEntry) -> str:
    if not rf.sha1 and not rf.etag:
        return "no checksum recorded (hash-b2, or --download-unknown)"
    if rf.etag and not rf.sha1 and lf.parts != rf.parts:
        return "part MD5s missing (run hash-local again after hash-b2)"
    return "checksum missing (run hash-local)"


def describe_duplicate(key: str, ls: list[FileEntry], rs: list[FileEntry], d: Diff) -> str:
    parts = [f"{d.labels.left} {e.path} ({fmt_size(e.size)})" for e in ls]
    parts += [f"{d.labels.right} {e.path} ({fmt_size(e.size)})" for e in rs]
    return f"{key}: " + "; ".join(parts)


def print_diff(name: str, d: Diff, limit: int, check_sum: bool) -> None:
    lb = d.labels
    status = "DIFFERENCES" if d.has_differences() else "in sync"
    mode = ", flat" if d.flat else ""
    print(f"\n=== {name}: {status}  ({lb.left} {d.left_count} files, {lb.right} {d.right_count} files{mode})")
    if check_sum:
        print(f"  checksum identical: {d.sha1_ok + d.etag_ok}  (SHA-1 {d.sha1_ok}, ETag/part MD5 {d.etag_ok})")
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

    section(f"{lb.only_left}, {total(d.only_left)}", [f"+ {e.path}" for e in d.only_left])
    section(f"{lb.only_right}, {total(d.only_right)}", [f"- {e.path}" for e in d.only_right])
    section("size differs",
            [f"~ {a.path}  {lb.left} {fmt_size(a.size)} / {lb.right} {fmt_size(b.size)}" + note(a.path)
             for a, b in d.size])
    section("modification time differs",
            [f"~ {a.path}  {lb.left} {fmt_ms(a.mtime_ms)} / {lb.right} {fmt_ms(b.mtime_ms)}" for a, b in d.mtime])
    section("checksum differs", [f"! {a.path}  ({checksum_pair(a, b)[0]})" + note(a.path) for a, b in d.checksum])
    section("read or download error", [f"X {a.path}  ({d.notes.get(a.path, '')})" for a, _b in d.errors])
    section("checksum not checkable",
            [f"? {a.path}  ({fmt_size(a.size)}, {d.notes.get(a.path) or unknown_reason(a, b)})"
             for a, b in d.checksum_unknown])
    section("name occurs more than once (not compared)",
            [f"* {describe_duplicate(k, ls, rs, d)}" for k, ls, rs in d.duplicates])


def md_cell(text: str) -> str:
    return text.replace("|", "\\|")


def write_markdown(path: Path, title: str, d: Diff, options: list[str], info: list[str]) -> None:
    lb = d.labels
    status = "differences found" if d.has_differences() else "in sync"
    out = [
        f"# {title}",
        "",
        f"- **Status:** {status}",
        f"- **Checked:** {now_ts()}",
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
        out.append(f"| Checksum identical (SHA-1) | {d.sha1_ok} | |")
        out.append(f"| Checksum identical (ETag/part MD5) | {d.etag_ok} | |")
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
          [[f"`{e.path}`", fmt_size(e.size), fmt_ms(e.mtime_ms)] for e in d.only_left])
    table(lb.only_right, ["File", "Size", "Modified"],
          [[f"`{e.path}`", fmt_size(e.size), fmt_ms(e.mtime_ms)] for e in d.only_right])
    table("Size differs", ["File", lb.left, lb.right, "Note"],
          [[f"`{a.path}`", fmt_size(a.size), fmt_size(b.size), d.notes.get(a.path, "")] for a, b in d.size])
    table("Modification time differs", ["File", lb.left, lb.right],
          [[f"`{a.path}`", fmt_ms(a.mtime_ms), fmt_ms(b.mtime_ms)] for a, b in d.mtime])
    table("Checksum differs", ["File", "Size", "Kind", lb.left, lb.right, "Note"],
          [[f"`{a.path}`", fmt_size(a.size), *(lambda k, x, y: (k, f"`{x}`", f"`{y}`"))(*checksum_pair(a, b)),
            d.notes.get(a.path, "")] for a, b in d.checksum])
    table("Read or download error", ["File", "Size", "Error"],
          [[f"`{a.path}`", fmt_size(a.size), d.notes.get(a.path, "")] for a, _b in d.errors])
    table("Checksum not checkable", ["File", "Size", "Reason"],
          [[f"`{a.path}`", fmt_size(a.size), d.notes.get(a.path) or unknown_reason(a, b)]
           for a, b in d.checksum_unknown])
    table("Name occurs more than once (not compared)", ["Name", lb.left, lb.right],
          [[f"`{k}`",
            "<br>".join(f"`{e.path}` ({fmt_size(e.size)})" for e in ls),
            "<br>".join(f"`{e.path}` ({fmt_size(e.size)})" for e in rs)] for k, ls, rs in d.duplicates])

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


class Progress:
    """One line per finished file in a (parallel) run. Called from the main thread only."""

    def __init__(self, total_files: int, total_bytes: int) -> None:
        self.n, self.total_files, self.total_bytes = 0, total_files, total_bytes
        self.bytes, self.start = 0, time.monotonic()

    def step(self, status: str, e: FileEntry) -> None:
        self.n += 1
        self.bytes += e.size
        print(f"  [{self.n}/{self.total_files}] {status:<9} {fmt_size(e.size):>9}  {e.path}", flush=True)

    def summary(self) -> str:
        secs = time.monotonic() - self.start
        speed = f", {fmt_size(self.bytes / secs)}/s" if secs > 1 else ""
        return f"{fmt_size(self.bytes)} in {secs:.0f} s{speed}"


def plan_text(plan: VerifyPlan, flt: FileFilter) -> list[str]:
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
        self.local_root = Path(self.props["localRoot"])
        self.state_dir = Path(self.props.get("stateDir") or config_path.parent)
        self.checksum_dir = self.state_dir / "checksums"
        self.report_dir = Path(args.report_dir or self.props.get("reportDir") or self.state_dir / "reports")
        self.excludes = split_list(self.props.get("exclude", ""))
        self.flat_buckets = set(split_list(self.props.get("flatBuckets", "")))
        self.ignore_dirs = SKIP_DIRS | set(split_list(self.props.get("ignoreDirs", "")))
        self.filter = self._build_filter(args)
        self._api = None
        self._s3: S3Info | None = None
        self._thread = threading.local()

    @staticmethod
    def _build_filter(args) -> FileFilter:
        try:
            return FileFilter(
                include=getattr(args, "include", None) or [],
                exclude=getattr(args, "exclude", None) or [],
                min_size=parse_size(args.min_size) if getattr(args, "min_size", None) else None,
                max_size=parse_size(args.max_size) if getattr(args, "max_size", None) else None)
        except (ValueError, re.error) as e:
            fail(f"invalid selection: {e}")

    @property
    def api(self):
        if self._api is None:
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

    def snapshot_path(self, side: str, bucket: str) -> Path:
        return self.checksum_dir / side / f"{bucket}.tsv"

    def snapshot_names(self, *sides: str) -> list[str]:
        return sorted({p.stem for side in sides for p in (self.checksum_dir / side).glob("*.tsv")})

    def threads(self, default: int) -> int:
        return getattr(self.args, "threads", None) or default

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

    def report(self, name: str, diff: Diff, options: list[str], info: list[str],
               suffix: str = "", title: str = "") -> None:
        if self.filter.active() and not any(i.startswith("- **Selection:**") for i in info):
            info = info + [f"- **Selection:** {self.filter.describe()}"]
        print_diff(name, diff, self.args.limit, "checksum" in options)
        if not self.args.no_report:
            md = self.report_dir / f"{name}{suffix}.md"
            write_markdown(md, title or name, diff, options, info)
            print(f"  -> {md}")


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
        flat = ctx.is_flat(name)
        print(f"\nchecking {name}{' (flat)' if flat else ''} ...", flush=True)
        local_path = ctx.local_root / name
        if not local_path.is_dir():
            print(f"  local directory missing: {local_path}")
            any_diff = True
            continue
        bucket = ctx.api.get_bucket_by_name(name)
        local = ctx.filter.apply(scan_local(local_path, ctx.excludes))
        remote = ctx.filter.apply(scan_remote(bucket, ctx.excludes))
        diff = compare(local, remote, flat, check_mtime=args.mtime,
                       mtime_tolerance_ms=int(args.mtime_tolerance * 1000))
        ctx.report(name, diff, options, ["- **Source:** live (local tree and B2 listing)"])
        any_diff |= diff.has_differences()

    print("\nresult:", "differences found." if any_diff else "everything in sync.")
    return 1 if any_diff else 0


def b2_part_layouts(ctx: Context, name: str, flat: bool) -> dict[str, tuple[list[int], bool]]:
    """From checksums/b2: files with an ETag but no SHA-1 -> (part sizes, multipart)."""
    path = ctx.snapshot_path("b2", name)
    if not path.is_file():
        return {}
    layouts = {}
    for e in read_snapshot(path)[1]:
        if not e.sha1 and e.etag and e.parts:
            layouts[basename(e.path) if flat else e.path] = (e.parts, is_multipart_etag(e.etag))
    return layouts


def cmd_hash_local(ctx: Context) -> int:
    names = ctx.args.buckets or sorted(ctx.local_dirs())
    any_damage = False
    for name in names:
        local_path = ctx.local_root / name
        if not local_path.is_dir():
            print(f"\n{name}: local directory missing ({local_path})")
            continue
        flat = ctx.is_flat(name)
        out = ctx.snapshot_path("local", name)
        prev_meta, prev = load_previous(out)
        layouts = b2_part_layouts(ctx, name, flat)
        entries = scan_local(local_path, ctx.excludes)
        todo: list[tuple[FileEntry, list[int] | None, bool]] = []
        for e in entries:
            parts, multipart = layouts.get(basename(e.path) if flat else e.path, (None, False))
            if parts and sum(parts) != e.size:
                parts = None  # the size differs, so the file differs anyway
            p = prev.get(e.path)
            same_file = bool(p and p.sha1 and p.size == e.size and p.mtime_ms == e.mtime_ms)
            if same_file:
                e.verified = p.verified
            if same_file and not ctx.args.force and (not parts or (p.etag and p.parts == parts)):
                e.sha1, e.etag, e.parts = p.sha1, p.etag, p.parts
            else:
                todo.append((e, parts, multipart))
        todo_bytes = sum(e.size for e, _p, _m in todo)
        with_parts = sum(1 for _e, p, _m in todo if p)
        print(f"\n{name}: {len(entries)} files, {len(entries) - len(todo)} unchanged, "
              f"{len(todo)} to hash ({fmt_size(todo_bytes)}, {with_parts} of them with part MD5s for the ETag)",
              flush=True)
        if not layouts and not ctx.snapshot_path("b2", name).is_file():
            print("  note: no B2 checksums yet - large files without a SHA-1 in B2 become checkable "
                  "after 'hash-b2' and another 'hash-local'.")

        saver = SnapshotSaver(out, new_meta(name, "local", prev_meta), entries, keep=lambda e: e.sha1)
        start, done_bytes = time.monotonic(), 0
        damaged: list[FileEntry] = []
        try:
            for i, (e, parts, multipart) in enumerate(todo, 1):
                print(f"  [{i}/{len(todo)}] {fmt_size(e.size):>9}  {e.path}", flush=True)
                sha1, etag = hash_file(e.abs_path, parts, multipart)
                p = prev.get(e.path)
                if p and p.sha1 and p.size == e.size and p.mtime_ms == e.mtime_ms and p.sha1 != sha1:
                    # Same size, same mtime, different bytes: keep the saved checksum and say so.
                    print(f"    DAMAGE? saved {p.sha1}, read {sha1} - the saved checksum is kept")
                    e.sha1, e.etag, e.parts, e.verified = p.sha1, p.etag, p.parts, ""
                    damaged.append(e)
                else:
                    e.sha1, e.etag, e.parts, e.verified = sha1, etag, parts, now_ts()
                done_bytes += e.size
                saver.maybe_save()
        finally:
            saver.save(complete=all(e.sha1 for e in entries))
        secs = time.monotonic() - start
        speed = f", {fmt_size(done_bytes / secs)}/s" if secs > 1 else ""
        print(f"  -> {out}  ({secs:.0f} s{speed})")
        if damaged:
            any_damage = True
            print(f"  WARNING: {len(damaged)} file(s) with different content at the same size and time "
                  f"(possible silent damage). Details and the state in B2: verify-local {name}")
            for e in damaged:
                print(f"    ! {e.path}")
    return 1 if any_damage else 0


def cmd_hash_b2(ctx: Context) -> int:
    names = ctx.args.buckets or sorted(ctx.remote_buckets())
    for name in names:
        out = ctx.snapshot_path("b2", name)
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
              f"{len(need_etag)} without a checksum ({fmt_size(sum(e.size for e in need_etag))})", flush=True)

        saver = SnapshotSaver(out, new_meta(name, "b2", prev_meta), entries)
        finished = False
        try:
            for i, e in enumerate(need_etag, 1):
                print(f"  [{i}/{len(need_etag)}] ETag {fmt_size(e.size):>9}  {e.path}", flush=True)
                try:
                    e.etag, e.parts = ctx.s3.etag_and_parts(name, e)
                    e.source = "s3"
                except Exception as ex:
                    print(f"    no ETag: {ex}")
                saver.maybe_save()
            unknown = [e for e in entries if not e.sha1 and not e.etag]
            if ctx.args.download_unknown and unknown:
                progress = Progress(len(unknown), sum(e.size for e in unknown))

                def work(e: FileEntry, stop: threading.Event) -> str:
                    return hash_chunks(b2_chunks(ctx.thread_bucket(name), e.file_id), stop=stop)[0]

                def done(e: FileEntry, sha1: str | None, err: Exception | None) -> None:
                    if err:
                        progress.step("ERROR", e)
                        print(f"    {err}")
                    else:
                        e.sha1, e.source = sha1, "download"
                        progress.step("SHA-1", e)
                    saver.maybe_save()

                run_parallel(unknown, work, ctx.threads(4), done)
                print(f"  downloaded and hashed: {progress.summary()}")
            elif unknown:
                print(f"  {len(unknown)} file(s) still without a checksum (--download-unknown hashes them)")
            finished = True
        finally:
            saver.save(complete=finished)
        print(f"  -> {out}")
    return 0


def add_b2_notes(ctx: Context, diff: Diff, name: str, info: list[str]) -> None:
    """For every local checksum difference, say whether the copy in B2 is still intact."""
    flat = ctx.is_flat(name)
    bp = ctx.snapshot_path("b2", name)
    idx = None
    if bp.is_file():
        bmeta, bentries = read_snapshot(bp)
        idx = make_index(bentries, flat)
        info.append(f"- **B2 checksums (for the notes):** {saved_info(bmeta)}")
    for now, saved in diff.checksum:
        kind = ("size and time unchanged - silent damage?" if now.mtime_ms == saved.mtime_ms
                else "the file was modified (new modification time)")
        cands = None if idx is None else idx.get(basename(saved.path) if flat else saved.path, [])
        diff.notes[now.path] = f"{kind}; {b2_state(now, saved, cands)}"


def cmd_verify_local(ctx: Context) -> int:
    """Local files against checksums/local: new, gone, changed, damaged."""
    names = ctx.args.buckets or ctx.snapshot_names("local")
    if not names:
        print("no local checksums yet - run 'hash-local' first.")
        return 2
    any_diff = False
    for name in names:
        sp, local_path = ctx.snapshot_path("local", name), ctx.local_root / name
        if not sp.is_file() or not local_path.is_dir():
            print(f"\n{name}: {'checksum file' if not sp.is_file() else 'local directory'} missing")
            any_diff = True
            continue
        meta, all_saved = read_snapshot(sp)
        saved = ctx.filter.apply([e for e in all_saved if not is_excluded(e.path, ctx.excludes)])
        by_path = {e.path: e for e in saved}
        current = ctx.filter.apply(scan_local(local_path, ctx.excludes))
        print(f"\nverifying {name} locally against the saved checksums ({saved_info(meta)}) ...", flush=True)
        info = [f"- **Saved checksums:** {saved_info(meta)}"]
        errors: dict[str, str] = {}
        if not ctx.args.quick:
            # Only files of unchanged size are read; new, gone or resized ones are reported anyway.
            pairs = {e.path: (e, by_path[e.path]) for e in current
                     if e.path in by_path and by_path[e.path].size == e.size}
            plan = plan_verification([p for _e, p in pairs.values()], meta, ctx.args.resume, ctx.args.older_than)
            for p in plan.skipped:
                e = pairs[p.path][0]
                e.sha1, e.skipped = p.sha1, True
            if plan.resumed:
                print(f"  resuming the run of {plan.run_start}")
            todo = [pairs[p.path] for p in plan.todo]
            print(f"  reading {len(todo)} files ({fmt_size(sum(e.size for e, _p in todo))}) on "
                  f"{ctx.threads(1)} thread(s), {len(plan.skipped)} skipped ...", flush=True)
            meta["verify_start"] = plan.run_start
            saver = SnapshotSaver(sp, meta, all_saved, complete_key="verify_complete")
            progress = Progress(len(todo), sum(e.size for e, _p in todo))

            def work(pair: tuple[FileEntry, FileEntry], stop: threading.Event):
                e, p = pair
                # Known part sizes are hashed along, so a difference can be judged against B2's ETag.
                parts = p.parts if p.etag else None
                return hash_chunks(read_file_chunks(e.abs_path), parts,
                                   bool(p.etag and is_multipart_etag(p.etag)), stop)

            def done(pair: tuple[FileEntry, FileEntry], result, err: Exception | None) -> None:
                e, p = pair
                if err:
                    errors[e.path] = f"read error: {err}"
                    p.verified = ""
                    progress.step("ERROR", e)
                else:
                    e.sha1, e.etag, _size = result
                    e.parts = p.parts if p.etag else None
                    ok = e.sha1 == p.sha1
                    # A failed file loses its timestamp, so every later run reads it again.
                    p.verified = now_ts() if ok else ""
                    progress.step("OK" if ok else "MISMATCH", e)
                saver.maybe_save()

            finished = False
            try:
                run_parallel(todo, work, ctx.threads(1), done)
                finished = True
            finally:
                saver.save(complete=finished)
            print(f"  read: {progress.summary()}")
            info += plan_text(plan, ctx.filter)
        diff = compare(current, saved, flat=False, check_mtime=True, mtime_tolerance_ms=0,
                       check_sum=not ctx.args.quick, labels=NOW_VS_SAVED)
        diff.attach_errors(errors)
        if diff.checksum:
            add_b2_notes(ctx, diff, name, info)
        options = ["modification time"] + ([] if ctx.args.quick else ["checksum"])
        ctx.report(name, diff, options, info, suffix=".local", title=f"{name} - local against saved checksums")
        any_diff |= diff.has_differences()
    print("\nresult:", "differences found." if any_diff else "nothing changed.")
    return 1 if any_diff else 0


def verify_b2_content(ctx: Context, name: str, meta: dict[str, str], all_saved: list[FileEntry],
                      saved: list[FileEntry], current: list[FileEntry]) -> bool:
    """Stream the B2 content, hash it and compare it with what B2's metadata states."""
    current_ids = {e.path: e.file_id for e in current}
    # Only files that still exist in B2 exactly as recorded in checksums/b2.
    candidates = [p for p in saved if current_ids.get(p.path) == p.file_id]
    plan = plan_verification(candidates, meta, ctx.args.resume, ctx.args.older_than)
    threads = ctx.threads(4)
    print(f"\nverifying the content of {name} in B2: {len(plan.todo)} files "
          f"({fmt_size(sum(p.size for p in plan.todo))}) on {threads} thread(s), {len(plan.skipped)} skipped"
          + (f" (resuming the run of {plan.run_start})" if plan.resumed else ""), flush=True)
    meta["verify_start"] = plan.run_start
    saver = SnapshotSaver(ctx.snapshot_path("b2", name), meta, all_saved, complete_key="verify_complete")
    progress = Progress(len(plan.todo), sum(p.size for p in plan.todo))
    content: dict[str, FileEntry] = {p.path: copy_entry(p, skipped=True) for p in plan.skipped}
    errors: dict[str, str] = {}
    expected = {p.path: expected_from_metadata(p) for p in plan.todo + plan.skipped}

    def work(p: FileEntry, stop: threading.Event):
        parts = p.parts if p.etag else None
        return hash_chunks(b2_chunks(ctx.thread_bucket(name), p.file_id), parts,
                           bool(p.etag and is_multipart_etag(p.etag)), stop)

    def done(p: FileEntry, result, err: Exception | None) -> None:
        if err:
            errors[p.path] = f"download error: {err}"
            content[p.path] = copy_entry(p, sha1=None, etag=None)
            progress.step("ERROR", p)
        else:
            sha1, etag, size = result
            content[p.path] = got = FileEntry(p.path, size, p.mtime_ms, sha1, etag, p.parts if p.etag else None)
            match = checksums_match(got, expected[p.path])
            if match and not p.sha1:
                p.sha1 = sha1  # a real SHA-1, confirmed by the ETag -> comparable by SHA-1 from now on
            # A failed file loses its timestamp, so every later run downloads it again.
            p.verified = now_ts() if match else ""
            progress.step({True: "OK", False: "MISMATCH", None: "UNKNOWN"}[match], p)
        saver.maybe_save()

    finished = False
    try:
        run_parallel(plan.todo, work, threads, done)
        finished = True
    finally:
        saver.save(complete=finished)
    print(f"  read: {progress.summary()}")

    diff = compare([content[p] for p in expected if p in content], list(expected.values()),
                   flat=False, check_sum=True, labels=CONTENT_VS_META)
    diff.attach_errors(errors)
    if diff.checksum or diff.size:
        local_sp = ctx.snapshot_path("local", name)
        flat = ctx.is_flat(name)
        idx = make_index(read_snapshot(local_sp)[1], flat) if local_sp.is_file() else None
        for got, _exp in diff.checksum + diff.size:
            cands = None if idx is None else idx.get(basename(got.path) if flat else got.path, [])
            diff.notes[got.path] = f"B2 content does not match the B2 metadata; {local_state(got, cands)}"
    info = [f"- **B2 checksums:** {saved_info(meta)}", f"- **Threads:** {threads}"] + plan_text(plan, ctx.filter)
    ctx.report(name, diff, ["checksum"], info, suffix=".b2-content", title=f"{name} - B2 content against B2 metadata")
    return diff.has_differences()


def cmd_verify_b2(ctx: Context) -> int:
    """The current B2 listing against checksums/b2; with --download also the content."""
    names = ctx.args.buckets or ctx.snapshot_names("b2")
    if not names:
        print("no B2 checksums yet - run 'hash-b2' first.")
        return 2
    any_diff = False
    for name in names:
        sp = ctx.snapshot_path("b2", name)
        if not sp.is_file():
            print(f"\n{name}: checksum file missing ({sp})")
            any_diff = True
            continue
        meta, all_saved = read_snapshot(sp)
        saved = ctx.filter.apply([e for e in all_saved if not is_excluded(e.path, ctx.excludes)])
        print(f"\nverifying {name} in B2 against the saved checksums ({saved_info(meta)}) ...", flush=True)
        current = ctx.filter.apply(scan_remote(ctx.api.get_bucket_by_name(name), ctx.excludes))
        # B2 files are immutable: the same file id means the same content.
        by_path = {e.path: e for e in saved}
        for e in current:
            p = by_path.get(e.path)
            if not e.sha1 and p and p.file_id == e.file_id:
                e.sha1, e.etag, e.parts = p.sha1, p.etag, p.parts
        diff = compare(current, saved, flat=False, check_sum=True, labels=NOW_VS_SAVED)
        ctx.report(name, diff, ["checksum"], [f"- **Saved checksums:** {saved_info(meta)}"],
                   suffix=".b2", title=f"{name} - B2 against saved checksums")
        any_diff |= diff.has_differences()
        if ctx.args.download:
            any_diff |= verify_b2_content(ctx, name, meta, all_saved, saved, current)
    print("\nresult:", "differences found." if any_diff else "nothing changed.")
    return 1 if any_diff else 0


def cmd_compare(ctx: Context) -> int:
    if ctx.args.buckets:
        names = ctx.args.buckets
    else:
        names = ctx.snapshot_names("local", "b2")
        if not names:
            print("no checksums yet - run 'hash-b2' and 'hash-local' first.")
            return 2

    any_diff = False
    for name in names:
        lp, rp = ctx.snapshot_path("local", name), ctx.snapshot_path("b2", name)
        missing = [f"{p} missing ({cmd})" for p, cmd in ((lp, "hash-local"), (rp, "hash-b2")) if not p.is_file()]
        if missing:
            print(f"\n{name}: " + "; ".join(missing))
            any_diff = True
            continue
        lmeta, local = read_snapshot(lp)
        rmeta, remote = read_snapshot(rp)
        local = ctx.filter.apply([e for e in local if not is_excluded(e.path, ctx.excludes)])
        remote = ctx.filter.apply([e for e in remote if not is_excluded(e.path, ctx.excludes)])
        flat = ctx.is_flat(name)
        print(f"\ncomparing checksums of {name}{' (flat)' if flat else ''} ...")
        info = []
        for label, meta in (("local", lmeta), ("B2", rmeta)):
            line = saved_info(meta)
            print(f"  {label} as of: {line}")
            info.append(f"- **{label} as of:** {line}")
        diff = compare(local, remote, flat, check_sum=True)
        ctx.report(name, diff, ["checksum"], info)
        any_diff |= diff.has_differences()

    print("\nresult:", "differences found." if any_diff else "everything in sync.")
    return 1 if any_diff else 0


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
    g.add_argument("--resume", action="store_true", help="continue an interrupted run")
    g.add_argument("--older-than", type=float, metavar="DAYS",
                   help="only files not successfully checked for DAYS")

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("check", parents=[common, selection], help="live: names and sizes")
    p.add_argument("--mtime", action="store_true", help="also compare modification times")
    p.add_argument("--mtime-tolerance", type=float, default=2.0, help="tolerance for --mtime in seconds")
    p = sub.add_parser("hash-local", parents=[common], help="bring the local checksums up to date")
    p.add_argument("--force", action="store_true", help="re-read every file, not only changed ones")
    p = sub.add_parser("hash-b2", parents=[common], help="record what B2 states (SHA-1, else S3 ETag)")
    p.add_argument("--download-unknown", action="store_true",
                   help="download and hash files without any checksum (costs download traffic)")
    p.add_argument("--threads", type=int, metavar="N", help="parallel downloads (default 4)")
    p = sub.add_parser("verify-local", parents=[common, selection, verify],
                       help="re-read local files against checksums/local")
    p.add_argument("--quick", action="store_true", help="names, sizes and times only; read nothing")
    p = sub.add_parser("verify-b2", parents=[common, selection, verify],
                       help="B2 against checksums/b2; with --download also the content")
    p.add_argument("--download", action="store_true",
                   help="stream the content from B2 and check it against the B2 metadata (costs download traffic)")
    sub.add_parser("compare", parents=[common, selection], help="saved local against saved B2 checksums")
    return ap


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or (argv[0] not in COMMANDS and argv[0] not in ("-h", "--help")):
        argv = ["check"] + argv  # the default command
    args = build_parser().parse_args(argv)
    ctx = Context(args)
    return {"check": cmd_check, "hash-local": cmd_hash_local, "hash-b2": cmd_hash_b2,
            "verify-local": cmd_verify_local, "verify-b2": cmd_verify_b2,
            "compare": cmd_compare}[args.command](ctx)


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
