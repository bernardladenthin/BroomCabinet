<!--
SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# PyMsTodoExport — Microsoft To Do as folders of Markdown, attachments included

Microsoft To Do has no export. The official route moves the tasks into Outlook. Completed tasks
and file attachments are easy to lose that way, and what you get out is still not a file you can
keep.

This project takes everything out instead. You get one folder per list with one Markdown file
holding every task, open and completed. Each task's notes, dates, categories and attachments come
along, and the attachments are saved next to the Markdown and linked from it. Afterwards the
Markdown is checked against the raw data, so nothing is lost without being reported.

| | |
|---|---|
| `export-indexeddb.js` | browser console snippet: dumps To Do's own IndexedDB into one JSON file. Read-only |
| `download-attachment.js` | browser console snippet: presses the download button on an Outlook attachment preview |
| `mstodo.py` | the library: folder layout, attachment deep links and file checks, Outlook HTML → Markdown, rendering and checking. Standard library only |
| `pymstodoexport.py` | the command line: `links`, `collect`, `markdown` |
| `mstodo_test.py` | library and command line end to end, on a made-up export of the real shape |
| `privacy_test.py` | refuses drive letters, e-mail addresses, account ids, Exchange ids and home directories in this project |

Standard library only; no dependencies. Works on Windows and on POSIX.

## The way through

**1. Dump the data.** Open <https://to-do.live.com/tasks/> and let the lists load. Then paste
`export-indexeddb.js` into the browser console (F12). It saves `MicrosoftTODO-export-<date>.json`
and logs counts. Compare those counts with the sidebar before going on.

The web app keeps the whole account in an IndexedDB called `todo_<account id>`, and that includes
completed tasks. The snippet only reads it and makes no network request. It leaves out each list's
`sharing_link` and `invitation_token`, because anyone holding those can join a shared list. It also
leaves out the client stores `sync` and `settings`.

**2. List the attachments.** The dump holds only the records of the attachments, not the files.
The files sit in the mailbox behind the account and can be reached through Outlook deep links.

    python pymstodoexport.py links D:\data\todo\MicrosoftTODO-export-2026-01-02.json D:\data\todo

This prints one JSON object per line (`index`, `url`, `display_name`, `target`), covering every
attachment that is not yet in the output directory.

**3. Download them.** Open each `url` in a browser signed in to the same account. Then press
**Download** on the preview, or run `download-attachment.js` in that tab's console.

Chrome silently blocks every download after the first one from the same page. Allow
outlook.live.com to download multiple files first (the icon at the right of the address bar);
otherwise the files simply never arrive.

**4. Move them into place, checked.**

    python pymstodoexport.py collect D:\data\todo\MicrosoftTODO-export-2026-01-02.json D:\data\todo

This looks in `~/Downloads` (change it with `--downloads`). Every file is checked before it is
moved. It has to be a complete PNG, JPEG, GIF or PDF of the recorded type, and its size has to be
plausible. A file that fails stays where it is, and nothing is ever overwritten.

If the browser renamed a download, name it explicitly with `INDEX=NAME`, for example
`collect ... 17="plan (1).png"`. Run `links` again to see what is still missing.

**5. Write the Markdown.**

    python pymstodoexport.py markdown D:\data\todo\MicrosoftTODO-export-2026-01-02.json D:\data\todo

The command writes the files and then checks them against the dump. Its exit status is 1 if
anything is missing. `--check` reports without writing.

The output is meant to be re-created: run the command again after collecting more attachments, and
the same input gives the same bytes.

## The layout

    README.md                           index: every list with tasks, open, done, attachments
    <list>/<list>.md                    one file per list
    <group>/<list>/<list>.md            lists inside a list group
    <list>/anhaenge/<task>/<file>       attachments, linked relatively

- **Folder names** are the titles without emoji and without characters Windows refuses. The
  headings in the Markdown keep the full title.
- **Duplicate task titles:** when two tasks of a list share a title, the later ones get "(2)",
  "(3)", numbered in the order the tasks were created. A new task therefore never renames an older
  task's folder.
- **Language:** the Markdown is written in German (headings *Offen* / *Erledigt*, facts such as
  *Fällig*, *Erinnerung*, *Erstellt von*), because the lists it was made for are.
- **Task facts:** each task shows its facts as bullets: completed on, important, due, reminder,
  My Day, recurrence, categories, created, and created and completed by (for shared lists).
- **Order:** open tasks appear in the order the app shows them. Completed tasks are struck through
  and sorted newest first.
- **Notes:** To Do stores notes as Outlook HTML, and they are converted to Markdown with hard line
  breaks. A link keeps its visible text. It becomes a bare `<url>` only when the text *is* the
  address.
- **File format:** the files are UTF-8 without BOM, with LF line endings, on every platform.

## What the check covers

The check runs after every `markdown` run. It confirms that:

- every task title is in its list's file;
- every note's text matches the text taken straight from the HTML, word for word up to
  whitespace;
- every link target in a note is present;
- every attachment downloaded from Exchange is on disk;
- every task belongs to a rendered list.

The note check is independent of the converter: the reference text comes from stripping the tags
with a regular expression. So a conversion that silently drops a word shows up as
`note text differs` instead of passing.

## Things that are easy to get wrong

**Exchange's recorded size is not the file's size.** Across 97 real attachments the recorded sizes
were too large: PDFs by 300 to 450 bytes, images by up to about 30 %. The recorded number includes
stored previews. One attachment existed twice, once as an Exchange file and once as an old
Wunderlist record. The Wunderlist record carried the true size, and the downloaded file matched it
to the byte. Checking for an exact size would therefore refuse every good file, so files are
accepted on their signature plus a size range instead.

**Some cameras pad JPEGs with zero bytes.** The end-of-image marker is then not the last thing in
the file, so the check strips the trailing zero bytes before looking for it.

**Deep link ids use a different base64 alphabet.** To Do stores Exchange ids in URL-safe base64
(`-`, `_`). Outlook's deep links want the standard alphabet (`/`, `+`), percent-encoded.

**Wunderlist attachments are gone.** Tasks imported from Wunderlist can still carry records that
point at `export.wunderlist.com`, which no longer exists. The Markdown lists them as unreachable.
When the same file also exists as an Exchange attachment on the same task, the Markdown links to
that copy, and the Exchange copy takes the original file name.

**Steps (subtasks)** are dumped from the `steps` store and counted by the snippet. If that number
is not what you expect, look in the app before trusting the export. The rendering does not show
steps yet.

## The export is private, even when this project is not

The dump holds whatever was ever written into a note, and that can include addresses, account
numbers or a password. Keep the export and everything made from it out of public repositories.
`privacy_test.py` keeps this project free of the author's ids and paths. It cannot know what is in
your notes.

## Tests

    python mstodo_test.py
    python privacy_test.py
