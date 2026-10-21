#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for mstodo and pymstodoexport, on a made-up export. Standard library only: python mstodo_test.py

The export below is invented, but its shape is the real one: field names, the date objects, the
Outlook HTML of the notes, an Exchange attachment next to a dead Wunderlist record of the same file.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest

import mstodo
import pymstodoexport

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40 + b"\x00\x00\x00\x00IEND\xaeB`\x82"
PDF = b"%PDF-1.4\n" + b"x" * 500 + b"\n%%EOF\n"


def when(s, tz="UTC"):
    return {"date_time": s, "time_zone": tz}


def task(id_, list_id, title, position, created, note="", completed=False, **extra):
    t = {"id": id_, "list_id": list_id, "title": title, "position": position, "created_at": when(created),
         "note": note, "completed": completed, "importance": 0}
    t.update(extra)
    return t


def entity(id_, task_id, name, kind="file", size=None, ctype=None, **extra):
    e = {"id": id_, "task_id": task_id, "entity_type": kind, "display_name": name, "remote_id": "att-" + id_,
         "preview": {"size": size, "content_type": ctype}}
    e.update(extra)
    return e


def export() -> dict:
    return {
        "exported_at": "2026-01-02T03:04:05.000Z",
        "listGroups": [{"id": "g1", "title": "Zeitlich"}],
        "lists": [
            {"id": "l1", "title": "Haus 🏠"},
            {"id": "l2", "title": "Monatlich", "parent_group_id": "g1"},
            {"id": "l3", "title": "Leer", "is_shared_folder": True},
        ],
        "tasks": [
            task("t1", "l1", "Dach prüfen", 30, "2020-01-01T10:00:00",
                 note='<html><head><style>p{}</style></head><body><div>Erste Zeile<br>zweite&nbsp;Zeile</div>'
                      '<div><a href="https://example.org/a b">Angebot</a> und '
                      '<a href="https://example.org/x">https://example.org/x</a></div><h2>Wichtig</h2></body></html>',
                 importance=100, due_date=when("2020-02-01T00:00:00"), categories=["Blau"]),
            task("t2", "l1", "Dach prüfen", 20, "2020-03-01T10:00:00"),
            task("t3", "l1", "Fenster", 10, "2019-05-05T08:00:00", completed=True,
                 completed_at=when("2021-06-07T00:00:00"), created_by="m1", completed_by="m2"),
            task("t4", "l1", "Garage", 5, "2019-05-06T08:00:00", completed=True,
                 completed_at=when("2022-01-01T00:00:00")),
            task("t5", "l2", "Rechnung: Strom/Gas?", 1, "2021-01-01T00:00:00"),
        ],
        "steps": [],
        "linkedEntities": [
            entity("w1", "t3", "plan.png", kind="wunderlistFile", weblink="https://export.wunderlist.com/x"),
            entity("e1", "t3", "plan.png", size=len(PNG) + 30, ctype="image/png"),
            entity("e2", "t5", "rechnung.pdf", size=len(PDF) + 400, ctype="application/pdf"),
        ],
        "categories": [],
        "members": [{"id": "m1", "display_name": "Anna"}, {"id": "m2", "display_name": "Ben"}],
        "assignments": [],
    }


class Names(unittest.TestCase):
    def test_safe_name(self):
        self.assertEqual(mstodo.safe_name("Haus 🏠"), "Haus")
        self.assertEqual(mstodo.safe_name('a:b/c\\d?"e*'), "a b c d e")
        self.assertEqual(mstodo.safe_name("https://example.org/x"), "example.org x")
        self.assertEqual(mstodo.safe_name("Ende..."), "Ende")
        self.assertEqual(mstodo.safe_name("🏠"), "ohne Titel")
        self.assertEqual(len(mstodo.safe_name("x" * 200)), 80)

    def test_deeplink_uses_the_standard_base64_alphabet(self):
        url = mstodo.deeplink("AB-c_d=", "E-f")
        self.assertEqual(url, "https://outlook.live.com/mail/0/deeplink/attachment/AB%2Fc%2Bd%3D/E%2Ff/false")

    def test_structure(self):
        list_dir, task_dir = mstodo.structure(export())
        self.assertEqual(list_dir, {"l1": "Haus", "l2": "Zeitlich/Monatlich", "l3": "Leer"})
        # equal titles get a number in creation order, so the older task keeps the plain name
        self.assertEqual((task_dir["t1"], task_dir["t2"]), ("Dach prüfen", "Dach prüfen (2)"))
        self.assertEqual(task_dir["t5"], "Rechnung Strom Gas")

    def test_two_lists_in_one_folder_are_refused(self):
        d = export()
        d["lists"].append({"id": "l4", "title": "Haus"})
        with self.assertRaises(ValueError):
            mstodo.structure(d)

    def test_attachments_keep_dump_order_and_exchange_gets_the_name(self):
        att = mstodo.attachments(export())
        self.assertEqual([a["id"] for a in att], ["w1", "e1", "e2"])
        self.assertEqual(att[1]["rel_path"], "Haus/anhaenge/Fenster/plan.png")
        self.assertEqual(att[0]["rel_path"], "Haus/anhaenge/Fenster/plan (2).png")
        self.assertEqual(att[0]["url"], "https://export.wunderlist.com/x")
        self.assertTrue(att[1]["url"].endswith("/att%2Fe1/false"))


class Files(unittest.TestCase):
    def test_complete_file(self):
        self.assertTrue(mstodo.complete_file(PNG, "image/png"))
        self.assertTrue(mstodo.complete_file(PNG + b"\x00" * 8, "image/png"))
        self.assertFalse(mstodo.complete_file(PNG[:-12], "image/png"))  # cut off
        self.assertTrue(mstodo.complete_file(b"\xff\xd8\xff\xe0" + b"j" * 50 + b"\xff\xd9\x00\x00", "image/jpeg"))
        self.assertFalse(mstodo.complete_file(b"\xff\xd8\xff\xe0" + b"j" * 50, "image/jpeg"))
        self.assertTrue(mstodo.complete_file(PDF, "application/pdf"))
        self.assertFalse(mstodo.complete_file(b"<html>login</html>", "application/pdf"))
        self.assertIsNone(mstodo.complete_file(b"anything", "text/plain"))

    def test_plausible_size_allows_less_than_recorded_never_more(self):
        self.assertTrue(mstodo.plausible_size(1000, 1400, "application/pdf"))
        self.assertFalse(mstodo.plausible_size(1401, 1400, "application/pdf"))
        self.assertFalse(mstodo.plausible_size(100, 10000, "application/pdf"))
        self.assertTrue(mstodo.plausible_size(700, 1000, "image/png"))
        self.assertFalse(mstodo.plausible_size(400, 1000, "image/png"))
        self.assertFalse(mstodo.plausible_size(0, 1000, "text/plain"))


class Notes(unittest.TestCase):
    def test_note_to_md(self):
        md, hrefs = mstodo.note_to_md(export()["tasks"][0]["note"])
        self.assertEqual(md, "Erste Zeile\nzweite Zeile\n[Angebot](https://example.org/a%20b) und "
                             "<https://example.org/x>\n**Wichtig**")
        self.assertEqual(hrefs, ["https://example.org/a b", "https://example.org/x"])

    def test_a_link_whose_text_differs_from_its_address_keeps_the_text(self):
        md, _ = mstodo.note_to_md('<div><a href="https://example.org/">example.org</a></div>')
        self.assertEqual(md, "[example.org](https://example.org/)")

    def test_hard_breaks(self):
        self.assertEqual(mstodo.hard_breaks("a\nb\n\nc"), "a\\\nb\n\nc")

    def test_empty(self):
        self.assertEqual(mstodo.note_to_md("  "), ("", []))
        self.assertEqual(mstodo.note_to_md(None), ("", []))


class Cli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = self.tmp.name
        self.export = os.path.join(root, "export.json")
        self.out = os.path.join(root, "out")
        self.dl = os.path.join(root, "dl")
        os.makedirs(self.dl)
        with open(self.export, "w", encoding="utf-8") as f:
            json.dump(export(), f, ensure_ascii=False)

    def run_cli(self, *argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = pymstodoexport.main(list(argv))
        return code, buf.getvalue()

    def drop(self, name, data):
        with open(os.path.join(self.dl, name), "wb") as f:
            f.write(data)

    def test_the_whole_way(self):
        code, out = self.run_cli("links", self.export, self.out)
        self.assertEqual(code, 0)
        links = [json.loads(line) for line in out.splitlines()]
        self.assertEqual([x["index"] for x in links], [1, 2])  # the Wunderlist record has nothing to download

        code, out = self.run_cli("markdown", self.export, self.out, "--check")
        self.assertEqual(code, 1)
        self.assertIn("attachment missing", out)
        self.assertFalse(os.path.exists(self.out))  # --check writes nothing

        self.drop("plan.png", PNG)
        self.drop("rechnung (1).pdf", PDF)  # the browser renamed it
        code, out = self.run_cli("collect", self.export, self.out, "--downloads", self.dl)
        self.assertEqual(code, 1, out)  # rechnung.pdf is not there under its own name
        self.assertIn("still missing 1", out)
        code, out = self.run_cli("collect", self.export, self.out, "--downloads", self.dl, "2=rechnung (1).pdf")
        self.assertEqual(code, 0, out)
        self.assertEqual(os.listdir(self.dl), [])
        self.assertEqual(self.run_cli("links", self.export, self.out)[1], "")

        code, out = self.run_cli("markdown", self.export, self.out)
        self.assertEqual(code, 0, out)
        self.assertIn("problems: 0", out)
        with open(os.path.join(self.out, "Haus", "Haus.md"), "rb") as f:
            haus = f.read().decode("utf-8")
        self.assertNotIn("\r", haus)
        self.assertFalse(haus.startswith("﻿"))
        self.assertTrue(haus.startswith("# Haus 🏠\n\nExportiert aus Microsoft To Do am 2026-01-02 · "
                                        "4 Aufgaben (2 offen, 2 erledigt)\n"))
        # open by position, done by completion date (newest first)
        self.assertLess(haus.index("## Offen"), haus.index("### Dach prüfen"))
        self.assertLess(haus.index("### ~~Garage~~"), haus.index("### ~~Fenster~~"))
        self.assertIn("- Wichtig: ja\n- Fällig: 2020-02-01\n- Kategorien: Blau\n", haus)
        self.assertIn("- Erstellt von: Anna\n- Erledigt von: Ben\n", haus)
        self.assertIn("Erste Zeile\\\nzweite Zeile\\\n", haus)
        self.assertIn("  - [plan.png](anhaenge/Fenster/plan.png) (", haus)
        self.assertIn("alter Wunderlist-Anhang, Quelle https://export.wunderlist.com/x nicht mehr erreichbar; "
                      "identische Datei liegt als [plan.png](anhaenge/Fenster/plan.png) vor", haus)
        with open(os.path.join(self.out, "Zeitlich", "Monatlich", "Monatlich.md"), encoding="utf-8") as f:
            monat = f.read()
        self.assertIn("Gruppe: Zeitlich", monat)
        self.assertIn("  - [rechnung.pdf](anhaenge/Rechnung%20Strom%20Gas/rechnung.pdf) (516 B)", monat)
        self.assertTrue(os.path.isfile(os.path.join(self.out, "Zeitlich", "Monatlich", "anhaenge",
                                                    "Rechnung Strom Gas", "rechnung.pdf")))
        with open(os.path.join(self.out, "README.md"), encoding="utf-8") as f:
            index = f.read()
        self.assertIn("| [Zeitlich / Monatlich](Zeitlich/Monatlich/Monatlich.md) | 1 | 1 | 0 | 1 |", index)
        self.assertIn("| **Summe** | 5 | 3 | 2 | 3 |", index)
        self.assertIn("`export.json`", index)
        with open(os.path.join(self.out, "Leer", "Leer.md"), encoding="utf-8") as f:
            self.assertIn("geteilte Liste", f.read())

    def test_a_damaged_download_is_refused_and_left_in_place(self):
        self.drop("plan.png", PNG[:-12])
        code, out = self.run_cli("collect", self.export, self.out, "--downloads", self.dl, "1")
        self.assertEqual(code, 1)
        self.assertIn("REFUSED (not a complete image/png)", out)
        self.assertTrue(os.path.exists(os.path.join(self.dl, "plan.png")))

    def test_a_download_larger_than_recorded_is_refused(self):
        self.drop("rechnung.pdf", PDF + b"x" * 1000 + b"%%EOF\n")
        code, out = self.run_cli("collect", self.export, self.out, "--downloads", self.dl, "2")
        self.assertEqual(code, 1)
        self.assertIn("REFUSED (", out)

    def test_a_lost_wunderlist_file_is_a_problem(self):
        d = export()
        d["linkedEntities"] = [e for e in d["linkedEntities"] if e["id"] != "e1"]
        _, problems = mstodo.render(d, self.out, "export.json")
        self.assertIn("attachment lost: Haus 🏠 / Fenster / plan.png", problems)

    def test_a_note_the_converter_would_shorten_is_a_problem(self):
        d = export()
        # a link across a line break: its address cannot be placed in the text
        d["tasks"][1]["note"] = '<div><a href="https://example.org/z">eins<br>zwei</a></div>'
        _, problems = mstodo.render(d, self.out, "export.json")
        self.assertIn("link missing: Haus 🏠 / Dach prüfen / https://example.org/z", problems)


if __name__ == "__main__":
    unittest.main()
