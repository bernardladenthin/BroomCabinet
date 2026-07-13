<!--
SPDX-FileCopyrightText: 2015 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# Plain-text to-do template

To-do lists and a task-card template built from Unicode ballot-box glyphs —
paste them into any editor, notes file, commit message, or code comment.

## Legend

| Glyph | Code point | Meaning |
|-------|-----------|---------|
| ☐ | U+2610 | to-do / open |
| ☑ | U+2611 | completed |
| ☒ | U+2612 | postponed / cancelled |

## Example list

```text
☐ todo   ☑ completed   ☒ postponed

☐ Item
☐ Subitem
☑ Completed item
☒ Postponed item
```

## Task-card template

```text
+------------------------------------------------------------+
| Title:
|
+------------------------------------------------------------+
| Summary:
|
|
+------------------------------------------------------------+
| Tasks:
| ☐
| ☐
| | - ☐
| | - ☐
| | - ☐
| ☐
|
|
+------------------------------------------------------------+
```

Separate multiple cards with a full-width rule of `=`.
