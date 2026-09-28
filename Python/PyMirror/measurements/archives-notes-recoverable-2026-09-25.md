<!--
SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# Is `ARCHIVES-NOTES-2026-09-17.md` recoverable from the collection? No — 92 sentences are not

`ARCHIVES-NOTES-2026-09-17.md` is a verbatim snapshot of the per-archive prose that used to live in
`mirror.py`'s `ARCHIVES` block. On 2026-09-17 that prose moved into each archive's own
`PROVENANCE.md`, and the snapshot was kept because **three automated comparisons disagreed about
whether anything had been lost** and a fourth heuristic looked worse than a copy.

That left an open question with a real consequence: if the snapshot only repeats what the
collection already carries, 100 KB of it can leave the repository. It is answered here, because
"we have clean mirrors now" is exactly the moment the question becomes decidable.

## The answer

| | |
|---|---:|
| `PROVENANCE.md` files in the collection | 98 |
| prose units taken from the snapshot | 100 |
| sentences asked (≥ 60 characters) | 539 |
| **not found anywhere in the collection** | **92 (17.1 %)** |
| archives named in the snapshot that no longer exist | **1** (`funet-unix`) |

**The snapshot stays.** Not as a precaution — as the only copy of 92 sentences.

## Why the earlier comparisons failed, and why this one does not

All three earlier attempts matched text that had been **re-wrapped**. Re-wrapping changes nothing
but whitespace, so the fix is to collapse every run of whitespace to a single space on both sides
and ask for plain substring containment. No similarity threshold, no tuning, nothing to get wrong.

**The first run of THIS comparison was also wrong**, and in the same family. It joined every
comment line and every string literal into one stream, which glued each URL to the comment that
followed it and manufactured sentences that had never existed — 165 of them, reported as missing.
Units are now kept apart: a run of comment lines is one unit, each long string literal is one unit,
and sentences are split inside a unit so none can span two. That is a bug fix, not a fourth
heuristic; it was made once and the result did not move again.

## What the 92 actually are

Not archive descriptions. Almost every one is **the reasoning and the wrong turns**, which is
precisely the material a `PROVENANCE.md` has no place for — that file says what an archive *is*,
not what was believed about it on the way there:

- **`funet-unix`, end to end.** Registered on a two-level measurement, fetched, found to be 64.59 GB
  of which 64.55 GB was the same files repeated through a self-referential symlink in
  `tools/less/xemacs`, and deleted on 2026-09-10. The directory is gone, so there is no
  `PROVENANCE.md` to hold any of it. `looks_like_a_loop()` exists because of this, and only the
  snapshot says so.
- **Measurements that were wrong and were kept next to their correction.** A recursive pass on
  `sun/` returned 1.58 GB against 18 MB from the two-level pass — a factor of ninety. A table of
  confident zeroes from a hand-rolled regex against Apache's older `<pre>` listings. A
  `--no-follow-html` run reporting a whole tree as empty. Three in one afternoon, all the same
  shape: a tool returning confident numbers for something other than what was asked.
- **A retraction with its premise attached.** "SUPERSEDES funet-aix … can be removed once this one
  completes" became a live instruction to delete something whose condition had quietly become
  impossible. It was retracted in place rather than edited away, and the warning is the point.
- **An adversarial pass whose lesson is about ordering.** Every "nothing else has this" claim was
  refuted or survived; only two survived. The ranking had already been sent to the owner before the
  refutations were read, and the note says that plainly: an adversarial pass is worth nothing if
  its output arrives after the conclusion.

## Method

Read-only. Nothing was written to the collection.

```python
def flat(text):
    return re.sub(r"\s+", " ", text).strip()

# units: a run of `#` lines is one unit; each string literal >= 20 chars that is not a bare URL
# is one unit. Sentences are split INSIDE a unit, so none spans two.
# haystack: every Q:\mirror\*\PROVENANCE.md, concatenated and flattened the same way.
# asked: sentences >= 60 chars (shorter ones match by accident).
missing = [s for s in asked if s not in hay]
```

The script is short enough to be quoted whole rather than kept as a tool; it answers one question
once and adds nothing to the collection's 46 scripts with an argument parser.
