<!--
SPDX-FileCopyrightText: 2020 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# PyImageResizer

A small image-processing toolkit with three subcommands. Every subcommand
**defaults to a dry-run preview** and only touches files when given `--execute`.

| Subcommand | Does | Needs |
|------------|------|-------|
| `resize` | Recursively thumbnail-resize images, in place or into `--output-dir`. | [Pillow](https://pypi.org/project/Pillow/) |
| `rename-to-jpg` | Normalize `.jpeg` extensions to `.jpg`. | stdlib only |
| `clean` | Delete every file that isn't a kept image extension. | stdlib only |

## Install

```bash
pip install -r requirements.txt   # Pillow (only needed for 'resize')
```

## Usage

```bash
# Preview (dry-run), then actually run with --execute
python pyimageresizer.py resize --source-dir . --max-width 800 --max-height 800 --quality 85
python pyimageresizer.py resize --output-dir out --execute      # resized copies into out/
python pyimageresizer.py rename-to-jpg --execute                # .jpeg -> .jpg
python pyimageresizer.py clean --keep-extensions .jpg .png --execute
```

Common `resize` options: `--source-dir` (default `.`), `--output-dir` (in place
if unset), `--max-width` / `--max-height` (default 800), `--quality` (default
85), `--threads`, `--extensions`, `--execute`. On Windows, `run.bat` is a
convenience launcher.

## Shell alternative (the "poor man's" version)

Before this tool, the same thing was done with ImageMagick's `mogrify`:

```bash
mogrify -resize 800x -format jpg *                                  # resize to 800px wide + convert to jpg
mogrify -resize "1000x1000>" *.jpg                                  # shrink to fit 1000x1000 (only if larger)
find . -name "*.jpg" -exec mogrify -resize "1000x1000>" -quality 95 {} \;   # recursive
```

Handy for a one-off, but `mogrify` **overwrites in place with no preview** — the
dry-run-by-default behaviour of this tool is exactly why it exists.
