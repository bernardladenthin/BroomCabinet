#!/usr/bin/env python3
"""Turn a directory tree of images into a sequentially numbered copy, then
optionally encode that sequence into a video with ffmpeg.

Two subcommands, mirroring the two scripts this replaces:
  sequence  - glob + copy images into a zero-padded, sequentially numbered directory
  encode    - feed that sequence to ffmpeg to produce a video

https://video.stackexchange.com/questions/7903/how-to-losslessly-encode-a-jpg-image-sequence-to-a-video-in-ffmpeg
https://trac.ffmpeg.org/wiki/Encode/H.264
"""

import argparse
import glob
import os
import shutil
import subprocess
import sys


def cmd_sequence(args):
    os.makedirs(args.dest, exist_ok=True)
    names = sorted(glob.glob(args.source_glob, recursive=True))
    if not names:
        print(f"No files matched {args.source_glob!r}")
        return 1

    for number, name in enumerate(names):
        dest_name = f"{args.prefix}{number:0{args.zfill}d}{args.ext}"
        dest_path = os.path.join(args.dest, dest_name)
        if args.dry_run:
            print(f"[dry-run] would copy {name} -> {dest_path}")
        else:
            shutil.copy2(name, dest_path)

    verb = "Would copy" if args.dry_run else "Copied"
    print(f"{verb} {len(names)} file(s) into {args.dest}")
    return 0


def cmd_encode(args):
    pattern = os.path.join(args.source_dir, f"{args.prefix}%0{args.zfill}d{args.ext}")
    cmd = [
        args.ffmpeg,
        "-f", "image2",
        "-framerate", str(args.framerate),
        "-i", pattern,
        "-vcodec", args.codec,
        "-preset", args.preset,
        args.output,
    ]
    prefix = "[dry-run] would run: " if args.dry_run else "Running: "
    print(prefix + " ".join(cmd))
    if not args.dry_run:
        subprocess.run(cmd, check=True)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_seq = sub.add_parser("sequence", help="Glob + copy images into a sequentially numbered directory.")
    p_seq.add_argument("--source-glob", default="**/*.jpg", help="Recursive glob pattern for source images (default: **/*.jpg).")
    p_seq.add_argument("--dest", default="dst", help="Destination directory (default: dst).")
    p_seq.add_argument("--prefix", default="image-", help="Output filename prefix (default: image-).")
    p_seq.add_argument("--zfill", type=int, default=9, help="Zero-padded digit width (default: 9).")
    p_seq.add_argument("--ext", default=".jpg", help="Output extension (default: .jpg).")
    p_seq.add_argument("-n", "--dry-run", action="store_true", help="Preview without copying.")
    p_seq.set_defaults(func=cmd_sequence)

    p_enc = sub.add_parser("encode", help="Encode a sequenced image directory into a video via ffmpeg.")
    p_enc.add_argument("--ffmpeg", default=shutil.which("ffmpeg") or "ffmpeg", help="Path to the ffmpeg executable (default: resolved from PATH).")
    p_enc.add_argument("--source-dir", default="dst", help="Directory containing the sequenced images, i.e. 'sequence's --dest (default: dst).")
    p_enc.add_argument("--prefix", default="image-", help="Input filename prefix, must match 'sequence' (default: image-).")
    p_enc.add_argument("--zfill", type=int, default=9, help="Zero-padded digit width, must match 'sequence' (default: 9).")
    p_enc.add_argument("--ext", default=".jpg", help="Input extension, must match 'sequence' (default: .jpg).")
    p_enc.add_argument("--framerate", type=int, default=60, help="Output framerate (default: 60).")
    p_enc.add_argument("--codec", default="libx264", help="Video codec (default: libx264).")
    p_enc.add_argument("--preset", default="veryslow", help="Encoder preset (default: veryslow).")
    p_enc.add_argument("--output", default="output.mp4", help="Output video file (default: output.mp4).")
    p_enc.add_argument("-n", "--dry-run", action="store_true", help="Print the ffmpeg command without running it.")
    p_enc.set_defaults(func=cmd_encode)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
