#!/usr/bin/env python3
"""Small image-processing toolkit: resize, normalize extensions, prune non-images.

Three subcommands, consolidating the four scripts this replaces:
  resize          - thumbnail-resize images, in place or into --output-dir
  rename-to-jpg   - normalize .jpeg extensions to .jpg
  clean           - delete every file that isn't a kept image extension

Every subcommand defaults to a dry-run preview and only touches files when
given --execute - all three can modify or delete files in place, so unlike
the lower-risk PyJcmdGcRun/PyImageSequencer tools, "do nothing until asked
twice" is the safer default here (this extends the `dry = True` default the
original scripts already had, rather than weakening it).

Needs Pillow for the 'resize' subcommand only ('pip install Pillow' or see
requirements.txt); 'rename-to-jpg' and 'clean' are stdlib-only.
"""

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

DEFAULT_IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp", ".gif"]


def cmd_resize(args):
    from PIL import Image, ImageFile

    # Allow loading very large or partially corrupted images.
    # https://stackoverflow.com/questions/25705773/image-cropping-tool-python
    Image.MAX_IMAGE_PIXELS = None
    # https://stackoverflow.com/questions/42462431/oserror-broken-data-stream-when-reading-image-file/47958486
    ImageFile.LOAD_TRUNCATED_IMAGES = True

    dry_run = not args.execute
    source_dir = Path(args.source_dir)
    output_dir = Path(args.output_dir) if args.output_dir else None
    extensions = {e.lower() for e in args.extensions}

    paths = [p for p in source_dir.rglob("*") if p.is_file() and p.suffix.lower() in extensions]
    if not paths:
        print(f"No images found under {source_dir} with extensions {sorted(extensions)}")
        return 1

    def resize_one(path):
        dest = output_dir / path.relative_to(source_dir) if output_dir is not None else path

        if dry_run:
            print(f"[dry-run] would resize {path} -> {dest}")
            return

        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(path) as im:
                exif_data = im.info.get("exif")
                im.thumbnail((args.max_width, args.max_height), Image.LANCZOS)
                fmt = im.format or path.suffix.lstrip(".").upper()
                save_kwargs = {}
                if fmt.upper() in ("JPEG", "JPG"):
                    save_kwargs["quality"] = args.quality
                    if exif_data:
                        save_kwargs["exif"] = exif_data
                im.save(dest, format=fmt, **save_kwargs)
            print(f"Resized {path} -> {dest}")
        except Exception as e:
            print(f"ERROR: could not resize {path}: {e}")

    with ThreadPoolExecutor(args.threads) as executor:
        list(executor.map(resize_one, paths))

    return 0


def cmd_rename_to_jpg(args):
    dry_run = not args.execute
    source_dir = Path(args.source_dir)

    renamed = 0
    for ext in (".jpeg", ".jpg"):
        for path in sorted(source_dir.rglob(f"*{ext}")):
            new_path = path.with_suffix(".jpg")
            if path == new_path:
                continue
            renamed += 1
            if dry_run:
                print(f"[dry-run] would rename {path} -> {new_path}")
            else:
                path.rename(new_path)
                print(f"Renamed {path} -> {new_path}")

    if renamed == 0:
        print("Nothing to rename.")
    return 0


def cmd_clean(args):
    dry_run = not args.execute
    source_dir = Path(args.source_dir)
    keep = {e.lower() for e in args.keep_extensions}

    deleted = 0
    for path in sorted(source_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() not in keep:
            deleted += 1
            if dry_run:
                print(f"[dry-run] would delete {path}")
            else:
                path.unlink()
                print(f"Deleted {path}")

    if deleted == 0:
        print("Nothing to delete.")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_resize = sub.add_parser("resize", help="Resize images (in place, or into --output-dir).")
    p_resize.add_argument("--source-dir", default=".", help="Directory to scan recursively (default: .).")
    p_resize.add_argument("--output-dir", default=None, help="If set, resized copies go here (preserving relative structure) instead of overwriting the originals in place.")
    p_resize.add_argument("--max-width", type=int, default=800)
    p_resize.add_argument("--max-height", type=int, default=800)
    p_resize.add_argument("--quality", type=int, default=85, help="JPEG save quality (default: 85).")
    p_resize.add_argument("--threads", type=int, default=os.cpu_count() or 4)
    p_resize.add_argument("--extensions", nargs="+", default=DEFAULT_IMAGE_EXTENSIONS, help=f"Extensions to process (default: {' '.join(DEFAULT_IMAGE_EXTENSIONS)}).")
    p_resize.add_argument("--execute", action="store_true", help="Actually resize. Without this flag: dry-run preview only.")
    p_resize.set_defaults(func=cmd_resize)

    p_rename = sub.add_parser("rename-to-jpg", help="Normalize .jpeg extensions to .jpg.")
    p_rename.add_argument("--source-dir", default=".", help="Directory to scan recursively (default: .).")
    p_rename.add_argument("--execute", action="store_true", help="Actually rename. Without this flag: dry-run preview only.")
    p_rename.set_defaults(func=cmd_rename_to_jpg)

    p_clean = sub.add_parser("clean", help="Delete every file that isn't a kept image extension.")
    p_clean.add_argument("--source-dir", default=".", help="Directory to scan recursively (default: .).")
    p_clean.add_argument("--keep-extensions", nargs="+", default=[".jpg", ".png"], help="Extensions to keep; everything else is deleted (default: .jpg .png).")
    p_clean.add_argument("--execute", action="store_true", help="Actually delete. Without this flag: dry-run preview only.")
    p_clean.set_defaults(func=cmd_clean)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
