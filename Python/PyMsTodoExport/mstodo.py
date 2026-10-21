# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Microsoft To Do, from a raw IndexedDB dump to one Markdown file per list.

THE SOURCE IS THE BROWSER'S OWN COPY. to-do.live.com keeps the whole account -- every list, every
task including the completed ones, notes, attachment records, members -- in an IndexedDB named
`todo_<account id>`. `export-indexeddb.js` dumps it from the browser console into one JSON file.
Nothing here talks to Microsoft: no token, no API, no login. The JSON is the single source of truth
and everything below is a pure function of it plus the attachment files on disk.

THE LAYOUT, relative to an output directory:

    <list>/<list>.md                    one file per list: "Offen", then "Erledigt" (struck through)
    <group>/<list>/<list>.md            lists inside a list group
    <list>/anhaenge/<task>/<file>       attachments, linked relatively from the Markdown
    README.md                           an index table of all lists with their counts

Folder names are the titles without emoji and without characters Windows refuses. Two tasks of one
list with the same title get "(2)", "(3)" in the order they were created, so a folder name never
changes when a later task is added.

ATTACHMENTS ARE NOT IN THE DUMP, only their records. The bytes live in the Exchange mailbox behind
the account and are reachable through an Outlook deep link (`deeplink`) whose preview page has a
download button; `download-attachment.js` presses it. `collect` then moves each download into place
and refuses it unless its content is a complete file of the recorded type.

THE SIZE EXCHANGE RECORDS IS NOT THE FILE'S SIZE. Measured over 97 attachments: PDFs are 300 to
450 bytes smaller than recorded, images up to about 30 % smaller (the record includes stored
previews). One attachment existed twice -- as an Exchange file and as an old Wunderlist record
with the true size -- and the downloaded file matched the Wunderlist size to the byte. So a file is
accepted on its signature and a size range, never on an exact size.

WUNDERLIST RECORDS POINT AT export.wunderlist.com, which no longer exists. They are listed in the
Markdown as unreachable, with a link to an identical Exchange copy on the same task when there is one.

THE MARKDOWN IS CHECKED AGAINST THE DUMP (`render`'s problem list): every title is present, every
note's text survives the HTML conversion unchanged up to whitespace, every link target is present,
every Exchange attachment is on disk. A conversion that loses a word is a defect, not a style.
"""
from __future__ import annotations

import html
import json
import os
import posixpath
import re
import unicodedata
from html.parser import HTMLParser
from urllib.parse import quote

# The stores worth keeping. `sync` and `settings` hold client state and are left out on purpose.
STORES = ["listGroups", "lists", "tasks", "steps", "linkedEntities", "categories", "members", "assignments"]
ATTACHMENT_DIR = "anhaenge"


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------------------------
# names and paths
# ---------------------------------------------------------------------------------------------

def strip_emoji(s: str) -> str:
    out = []
    for ch in unicodedata.normalize("NFC", s):
        if unicodedata.category(ch) in ("So", "Sk", "Cs", "Mn") or ch in "‍️":
            continue
        out.append(ch)
    return "".join(out)


def safe_name(s: str, maxlen: int = 80) -> str:
    """A folder or file name that Windows accepts and that reads like the title."""
    s = strip_emoji(s)
    s = re.sub(r"https?://", "", s)
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", s)
    s = re.sub(r"\s+", " ", s).strip().rstrip(". ")
    if len(s) > maxlen:
        s = s[:maxlen].rstrip(". ")
    return s or "ohne Titel"


def outlook_id(i: str) -> str:
    """To Do stores Exchange ids in URL-safe base64; Outlook's deep links want the standard alphabet."""
    return quote(i.replace("-", "/").replace("_", "+"), safe="")


def deeplink(task_id: str, attachment_remote_id: str) -> str:
    return "https://outlook.live.com/mail/0/deeplink/attachment/%s/%s/false" % (
        outlook_id(task_id), outlook_id(attachment_remote_id))


def structure(d: dict) -> tuple[dict[str, str], dict[str, str]]:
    """List folders (relative, `/`-separated) by list id, and task folder names by task id."""
    groups = {g["id"]: safe_name(g["title"]) for g in d["listGroups"]}
    list_dir = {}
    for lst in d["lists"]:
        name = safe_name(lst["title"])
        gid = lst.get("parent_group_id")
        list_dir[lst["id"]] = posixpath.join(groups[gid], name) if gid else name
    folders = [v.lower() for v in list_dir.values()]
    if len(set(folders)) != len(folders):
        raise ValueError("two lists map to the same folder name")
    task_dir = {}
    by_list: dict[str, list] = {}
    for t in d["tasks"]:
        by_list.setdefault(t["list_id"], []).append(t)
    for ts in by_list.values():
        used = set()
        # creation order, so a later task can never rename the folder of an earlier one
        for t in sorted(ts, key=lambda t: (t["created_at"] or {}).get("date_time") or ""):
            base = safe_name(t["title"], 60)
            name, n = base, 2
            while name.lower() in used:
                name = "%s (%d)" % (base, n)
                n += 1
            used.add(name.lower())
            task_dir[t["id"]] = name
    return list_dir, task_dir


def attachments(d: dict) -> list[dict]:
    """Every attachment record with its target path, in the order of the dump (indexes are stable)."""
    list_dir, task_dir = structure(d)
    tasks = {t["id"]: t for t in d["tasks"]}
    res = {}
    used: dict[str, int] = {}
    # Exchange files are named first, so a dead Wunderlist record never takes the original name
    for e in sorted(d["linkedEntities"], key=lambda e: e["entity_type"] != "file"):
        t = tasks[e["task_id"]]
        folder = posixpath.join(list_dir[t["list_id"]], ATTACHMENT_DIR, task_dir[t["id"]])
        fname = safe_name(e["display_name"], 120)
        key = posixpath.join(folder, fname).lower()
        if key in used:
            stem, dot, ext = fname.rpartition(".")
            fname = "%s (%d).%s" % (stem, used[key] + 1, ext) if dot else fname + " (%d)" % (used[key] + 1)
        used[key] = used.get(key, 0) + 1
        preview = e.get("preview") or {}
        res[e["id"]] = {
            "id": e["id"],
            "type": e["entity_type"],
            "display_name": e["display_name"],
            "size": preview.get("size"),
            "content_type": preview.get("content_type"),
            "list_id": t["list_id"],
            "task_id": t["id"],
            "rel_path": posixpath.join(folder, fname),
            "url": deeplink(t["id"], e["remote_id"]) if e["entity_type"] == "file" else e.get("weblink"),
        }
    return [res[e["id"]] for e in d["linkedEntities"]]


def native(out_dir: str, rel: str) -> str:
    return os.path.join(out_dir, *rel.split("/"))


# ---------------------------------------------------------------------------------------------
# attachment files
# ---------------------------------------------------------------------------------------------

def complete_file(data: bytes, content_type: str | None) -> bool | None:
    """True/False for a type whose start and end can be checked, None for any other type."""
    if content_type == "image/png":
        return data[:8] == b"\x89PNG\r\n\x1a\n" and data.rstrip(b"\x00")[-8:-4] == b"IEND"
    if content_type == "image/jpeg":
        # some cameras pad the end of the file with zero bytes
        return data[:3] == b"\xff\xd8\xff" and b"\xff\xd9" in data.rstrip(b"\x00")[-1024:]
    if content_type == "image/gif":
        return data[:6] in (b"GIF87a", b"GIF89a") and data.rstrip(b"\x00")[-1:] == b"\x3b"
    if content_type == "application/pdf":
        return data[:5] == b"%PDF-" and b"%%EOF" in data[-2048:]
    return None


def plausible_size(size: int, recorded: int | None, content_type: str | None) -> bool:
    """Exchange records more than the file holds (see the module docstring), never less."""
    if not recorded:
        return size > 0
    if content_type == "application/pdf":
        return recorded - 4096 <= size <= recorded
    if content_type and content_type.startswith("image/"):
        return recorded * 0.5 <= size <= recorded
    return 0 < size <= recorded


def check_file(path: str, a: dict) -> tuple[bool, str]:
    with open(path, "rb") as f:
        data = f.read()
    sig = complete_file(data, a["content_type"])
    if sig is False:
        return False, "not a complete %s" % a["content_type"]
    if not plausible_size(len(data), a["size"], a["content_type"]):
        return False, "%d bytes, recorded %s" % (len(data), a["size"])
    return True, "ok" if sig else "size only (%s cannot be checked)" % a["content_type"]


def present(out_dir: str, a: dict) -> int | None:
    """Size of the attachment's file in the output tree, or None when it is not there (yet)."""
    if a["type"] != "file":
        return None
    path = native(out_dir, a["rel_path"])
    return os.path.getsize(path) if os.path.isfile(path) else None


# ---------------------------------------------------------------------------------------------
# notes: Outlook HTML -> Markdown
# ---------------------------------------------------------------------------------------------

class NoteParser(HTMLParser):
    """The HTML To Do writes (div, span, font, br, a, h2) as Markdown lines."""
    SKIP = {"head", "style", "script", "title"}
    BLOCK = {"div", "p", "h1", "h2", "h3", "li", "tr", "table", "body", "html"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lines = [""]
        self.skip = 0
        self.links: list[list] = []  # open <a>: [href, line index, start column]
        self.hrefs: list[str] = []

    def newline(self):
        self.lines.append("")

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif self.skip:
            return
        elif tag == "br":
            self.newline()
        elif tag in self.BLOCK:
            if self.lines[-1] != "":
                self.newline()
            if tag in ("h1", "h2", "h3"):
                self.lines[-1] += "**"
        elif tag == "a":
            href = dict(attrs).get("href") or ""
            self.links.append([href, len(self.lines) - 1, len(self.lines[-1])])

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip -= 1
        elif self.skip:
            return
        elif tag in ("h1", "h2", "h3"):
            self.lines[-1] += "**"
            self.newline()
        elif tag in self.BLOCK:
            if self.lines[-1] != "":
                self.newline()
        elif tag == "a" and self.links:
            href, li, start = self.links.pop()
            if not href:
                return
            self.hrefs.append(href)
            if li != len(self.lines) - 1:
                return  # a link across a line break keeps its text; the check finds the href missing
            text = self.lines[li][start:]
            # an autolink only when the visible text IS the address -- otherwise the text would be lost
            if text == href and re.match(r"^(https?://|mailto:)\S+$", href):
                rendered = "<%s>" % href
            else:
                rendered = "[%s](%s)" % (text, href.replace(" ", "%20").replace(")", "%29"))
            self.lines[li] = self.lines[li][:start] + rendered

    def handle_data(self, data):
        if self.skip:
            return
        data = data.replace("\r\n", "\n").replace("\r", "\n")
        if "\n" in data and not data.strip():
            return  # formatting line breaks between tags
        for i, part in enumerate(data.split("\n")):
            if i:
                self.newline()
            self.lines[-1] += part.replace("\xa0", " ")


def note_to_md(note: str | None) -> tuple[str, list[str]]:
    if not note or not note.strip():
        return "", []
    p = NoteParser()
    p.feed(note)
    p.close()
    out: list[str] = []
    for line in (x.rstrip() for x in p.lines):
        if line == "" and (not out or out[-1] == ""):
            continue  # no leading blank line, no two in a row
        out.append(line)
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out), p.hrefs


def note_plaintext(note: str) -> str:
    """The note's text taken straight from the HTML, independent of NoteParser, for the check."""
    s = re.sub(r"(?is)<(head|style|script|title)\b.*?</\1>", " ", note)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    return html.unescape(s).replace("\xa0", " ")


def md_plaintext(md: str) -> str:
    s = re.sub(r"<(https?://[^>]+|mailto:[^>]+)>", r"\1", md)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    return s.replace("\\\n", " ").replace("**", "")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def hard_breaks(text: str) -> str:
    """Single line breaks become hard breaks (backslash); blank lines stay paragraph breaks."""
    lines = text.split("\n")
    out = []
    for i, line in enumerate(lines):
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        out.append(line + ("\\" if line and nxt else ""))
    return "\n".join(out)


# ---------------------------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------------------------

def dt(v, with_time: bool = True) -> str | None:
    if not v:
        return None
    s = v.get("date_time") if isinstance(v, dict) else str(v)
    tz = v.get("time_zone") if isinstance(v, dict) else ""
    if not s:
        return None
    s = s.replace("T", " ")[:16 if with_time else 10]
    return s + (" (%s)" % tz if tz and with_time and len(s) > 10 else "")


def human_size(n: int | None) -> str:
    if n is None:
        return "?"
    for unit in ("B", "KB", "MB"):
        if n < 1024 or unit == "MB":
            return ("%d %s" % (n, unit)) if unit == "B" else ("%.1f %s" % (n, unit)).replace(".", ",")
        n /= 1024
    raise AssertionError("unreachable")


def md_link_path(rel: str) -> str:
    return rel.replace("\\", "/").replace(" ", "%20").replace("(", "%28").replace(")", "%29")


def title_of(t: dict) -> str:
    return t["title"].strip() or "(ohne Titel)"


def render(d: dict, out_dir: str, export_name: str) -> tuple[dict[str, str], list[str]]:
    """All Markdown files as {relative path: text}, and every way they fall short of the dump."""
    list_dir, _ = structure(d)
    att = attachments(d)
    export_date = (d.get("exported_at") or "")[:10] or "?"
    members = {m["id"]: m["display_name"] for m in d["members"]}
    groups = {g["id"]: g["title"] for g in d["listGroups"]}
    att_by_task: dict[str, list] = {}
    for a in att:
        att_by_task.setdefault(a["task_id"], []).append(a)
    tasks_by_list: dict[str, list] = {}
    for t in d["tasks"]:
        tasks_by_list.setdefault(t["list_id"], []).append(t)
    size_of = {a["id"]: present(out_dir, a) for a in att}

    files: dict[str, str] = {}
    problems: list[str] = []
    rows = []
    for lst in sorted(d["lists"], key=lambda x: x["title"].lower()):
        ldir = list_dir[lst["id"]]
        lname = posixpath.basename(ldir)
        # `position` descending is the order the app shows
        ts = sorted(tasks_by_list.get(lst["id"], []), key=lambda t: t["position"], reverse=True)
        open_ts = [t for t in ts if not t["completed"]]
        done_ts = sorted([t for t in ts if t["completed"]],
                         key=lambda t: (t.get("completed_at") or {}).get("date_time") or "", reverse=True)

        out = ["# %s" % lst["title"], ""]
        meta = ["Exportiert aus Microsoft To Do am %s" % export_date,
                "%d Aufgaben (%d offen, %d erledigt)" % (len(ts), len(open_ts), len(done_ts))]
        if lst.get("parent_group_id"):
            meta.append("Gruppe: %s" % groups[lst["parent_group_id"]])
        if lst.get("is_shared_folder"):
            meta.append("geteilte Liste")
        if lst.get("folder_type"):
            meta.append("Typ: %s" % lst["folder_type"])
        out += [" · ".join(meta), ""]

        def task(t: dict, done: bool) -> None:
            title = title_of(t)
            out.append("### " + ("~~%s~~" % title if done else title))
            out.append("")
            facts = []
            if done:
                facts.append("Erledigt: %s" % (dt(t.get("completed_at"), False) or "ja"))
            if t.get("importance") == 100:
                facts.append("Wichtig: ja")
            if t.get("due_date"):
                facts.append("Fällig: %s" % dt(t["due_date"], False))
            if t.get("is_reminder_on") and t.get("reminder"):
                facts.append("Erinnerung: %s" % dt((t["reminder"] or {}).get("reminder_date")))
            if t.get("committed_day"):
                facts.append("Mein Tag: %s" % dt(t["committed_day"], False))
            if t.get("recurrence"):
                facts.append("Wiederholung: `%s`" % json.dumps(t["recurrence"], ensure_ascii=False))
            if t.get("categories"):
                facts.append("Kategorien: %s" % ", ".join(t["categories"]))
            facts.append("Erstellt: %s" % dt(t.get("created_at")))
            if t.get("created_by"):
                facts.append("Erstellt von: %s" % members.get(t["created_by"], t["created_by"]))
            if t.get("completed_by"):
                facts.append("Erledigt von: %s" % members.get(t["completed_by"], t["completed_by"]))
            out.extend("- " + f for f in facts)
            atts = att_by_task.get(t["id"], [])
            if atts:
                out.append("- Anhänge:")
            for a in atts:
                rel = posixpath.relpath(a["rel_path"], ldir)
                if size_of[a["id"]] is not None:
                    out.append("  - [%s](%s) (%s)" % (a["display_name"], md_link_path(rel), human_size(size_of[a["id"]])))
                elif a["type"] == "file":
                    out.append("  - %s (fehlt: noch nicht heruntergeladen)" % a["display_name"])
                    problems.append("attachment missing: %s / %s / %s" % (lst["title"], t["title"], a["display_name"]))
                else:
                    twin = next((b for b in atts if b is not a and b["display_name"] == a["display_name"]
                                 and size_of[b["id"]] is not None), None)
                    hint = ("; identische Datei liegt als [%s](%s) vor" % (
                        twin["display_name"], md_link_path(posixpath.relpath(twin["rel_path"], ldir)))) if twin else ""
                    out.append("  - %s (alter Wunderlist-Anhang, Quelle %s nicht mehr erreichbar%s)" % (
                        a["display_name"], a["url"], hint))
                    if not twin:
                        problems.append("attachment lost: %s / %s / %s" % (lst["title"], t["title"], a["display_name"]))
            md_note, hrefs = note_to_md(t["note"])
            if md_note:
                out.append("")
                out.append(hard_breaks(md_note))
            out.append("")
            # every word and every link of the note must be in the Markdown
            if norm(note_plaintext(t["note"] or "")).replace("*", "") != norm(md_plaintext(md_note)).replace("*", ""):
                problems.append("note text differs: %s / %s" % (lst["title"], t["title"]))
            for h in hrefs:
                if h not in md_note and h.replace(" ", "%20").replace(")", "%29") not in md_note:
                    problems.append("link missing: %s / %s / %s" % (lst["title"], t["title"], h))

        if open_ts:
            out += ["## Offen", ""]
            for t in open_ts:
                task(t, False)
        if done_ts:
            out += ["## Erledigt", ""]
            for t in done_ts:
                task(t, True)
        if not ts:
            out += ["_Keine Aufgaben._", ""]

        text = "\n".join(out).rstrip("\n") + "\n"
        files[posixpath.join(ldir, lname + ".md")] = text
        problems += ["title missing: %s / %s" % (lst["title"], t["title"]) for t in ts if title_of(t) not in text]
        n_att = sum(len(att_by_task.get(t["id"], [])) for t in ts)
        rows.append((ldir, lname, len(ts), len(open_ts), len(done_ts), n_att))

    idx = ["# Microsoft To Do", "",
           "Vollständiger Export aus Microsoft To Do vom %s. Je Liste ein Ordner mit einer Markdown-Datei; "
           "Dateianhänge liegen im Unterordner `%s/<Aufgabe>/`. Die Rohdaten (inkl. Original-HTML der Notizen) "
           "stehen in `%s`." % (export_date, ATTACHMENT_DIR, export_name), "",
           "| Liste | Aufgaben | offen | erledigt | Anhänge |", "|---|---:|---:|---:|---:|"]
    for ldir, lname, n, o, dn, na in sorted(rows, key=lambda r: r[0].lower()):
        idx.append("| [%s](%s) | %d | %d | %d | %d |" % (
            ldir.replace("/", " / "), md_link_path(posixpath.join(ldir, lname + ".md")), n, o, dn, na))
    idx.append("| **Summe** | %d | %d | %d | %d |" % tuple(sum(r[i] for r in rows) for i in (2, 3, 4, 5)))
    files["README.md"] = "\n".join(idx) + "\n"

    if len(rows) != len(d["lists"]) or sum(r[2] for r in rows) != len(d["tasks"]):
        problems.append("tasks without a list: %d lists, %d of %d tasks rendered"
                        % (len(rows), sum(r[2] for r in rows), len(d["tasks"])))
    return files, problems


def write(out_dir: str, files: dict[str, str]) -> None:
    """UTF-8 without BOM, LF line endings, on every platform."""
    for rel, text in files.items():
        path = native(out_dir, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
