<!--
SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# robots.txt, captured while the hosts still answered

Seven files, stored whole, fetched on 2026-09-24. `robots-fixtures-test.py`
reads each one and checks that `robots.txt` still produces the verdict this
collection recorded for it.

## Why these are stored and the inline cases are not enough

`robots_verdict_test.py` carries its cases as strings in the file. That was
right when they were written and is not enough now: **a robots.txt is the most
perishable evidence here.** It is a live statement of somebody's wishes, it can
be rewritten tomorrow, and several of this collection's decisions rest on one.

**Two of the four hosts that file names already do not answer.**

| host | 2026-09-24 |
|---|---|
| `irixnet.org` | answers, 4 909 B — **captured** |
| `4corn.co.uk` | answers, 1 227 B — **captured** |
| `update.uu.se` | does not connect — only the inline case survives |
| `hpux.connect.org.uk` | does not connect — only the inline case survives |

Half the evidence for the rules this collection honours was already gone by the
time anybody thought to store it.

## What these prove that the inline cases cannot

The inline cases prove the FUNCTION reads a rule correctly. These prove the
DECISION still holds:

- `irixnet.org` still carries 188 named agents and **no `User-agent: *`**, so an
  agent that is not named has no rule, and we are not named;
- `4corn.co.uk` still lists 45 AI agents with an **empty `Disallow:`**, which by
  the letter of the standard permits everything and by intent does not.

If either host rewrites its file, this test fails and a person has to look —
which is the point of recording a decision about somebody else's wishes rather
than re-deriving it.

## The five others

`ps-2.kev009.com`, `ardent-tool.com`, `files.mpoli.fi` and `web-docs.gsi.de` are
hosts this collection actively fetches from, so their permission is worth having
on record. `bitsavers.org` is here for a different reason: its robots.txt is
**zero bytes**, which is not the same as no robots.txt and not the same as a
blanket refusal, and an empty file is exactly the shape a parser gets wrong.

## Adding one

Fetch it whole, drop it here, add a `.license` sidecar naming the URL and the
date, and put the host, the path that matters and the verdict in
`expected.json`. Store what the server sent, not a tidied version: the byte
count and the SHA-256 are checked, because a fixture somebody edited is a
fixture that proves what the editor believed.
