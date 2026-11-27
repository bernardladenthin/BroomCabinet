# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""The viewer served from this machine: `pytaxde.py <folder> --anzeigen`.

A small HTTP server on 127.0.0.1 (nobody else can reach it) serves three things and nothing else:

    /             the viewer (taxde/viewer.html, the one copy there is)
    /daten.json   the folder's returns, computed from the YAML files on every request -- nothing is
                  written, a reload shows the YAML as it is now
    /datei/<n>    a file one of the returns names as a receipt (or the YAML itself), by number

Only files that a `belege:` list names can be fetched: the numbers come from the data just built, a
path cannot be asked for. Without the server the viewer opens a Steuererklärungen.json by drag and drop;
it shows everything then except the links to the files (a page from disk may not open other files).
"""
import json
import mimetypes
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .ergebnis import als_json
from .gesamt import bauen

VIEWER = Path(__file__).with_name("viewer.html")


def _dateien(block: dict, schluessel: str) -> list:
    out = [schluessel]
    a = block.get("anzeige") or {}
    for b in a.get("belege", []):
        out += b["dateien"]
    for ab in a.get("abschnitte", []):
        for p in ab["posten"]:
            for b in p["belege"]:
                out += b["dateien"]
    return out


def daten_mit_links(ordner):
    """The data as `--json` would write it, plus `links`: file -> its address on this server."""
    d = bauen(ordner)
    dateien = sorted({f for k, b in d["erklaerungen"].items() for f in _dateien(b, k)})
    d["links"] = {rel: f"datei/{i}" for i, rel in enumerate(dateien)}
    return d, dateien


def server(ordner, port=0):
    ordner = Path(ordner).resolve()

    class Handler(BaseHTTPRequestHandler):
        def _senden(self, code, inhalt: bytes, typ: str):
            self.send_response(code)
            self.send_header("Content-Type", typ)
            self.send_header("Content-Length", str(len(inhalt)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(inhalt)

        def do_GET(self):
            pfad = urlparse(self.path).path
            if pfad in ("/", "/index.html"):
                return self._senden(200, VIEWER.read_bytes(), "text/html; charset=utf-8")
            if pfad == "/daten.json":
                d, self.server.dateien = daten_mit_links(ordner)
                return self._senden(200, als_json(d).encode("utf-8"), "application/json; charset=utf-8")
            if pfad.startswith("/datei/") and pfad[7:].isdigit():
                n = int(pfad[7:])
                if n < len(self.server.dateien):
                    datei = (ordner / self.server.dateien[n]).resolve()
                    if datei.is_file():
                        typ = mimetypes.guess_type(datei.name)[0] or "application/octet-stream"
                        return self._senden(200, datei.read_bytes(), typ)
            self._senden(404, json.dumps({"fehler": "nicht gefunden"}).encode(), "application/json")

        def log_message(self, *args):          # quiet: the terminal shows the address, not every request
            pass

    s = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    s.dateien = daten_mit_links(ordner)[1]
    return s


def anzeigen(ordner, port=0, browser=True) -> int:
    s = server(ordner, port)
    url = f"http://127.0.0.1:{s.server_address[1]}/"
    print(f"Viewer: {url}  (Daten frisch aus den YAML-Dateien in {ordner}; beenden mit Strg+C)")
    if browser:
        webbrowser.open(url)
    try:
        s.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        s.server_close()
    return 0
