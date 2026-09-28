#!/bin/sh

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

# WATCH THE FREE SPACE WHILE A LONG FETCH RUNS, and say nothing until it matters.
#
#     sh Python/PyMirror/tools/diskwatch.sh            # watches Q:/
#     sh Python/PyMirror/tools/diskwatch.sh /mnt/data  # or wherever the collection is
#
# IT SPEAKS ONLY ON A CROSSING, never on a schedule, and that is the whole design. A watcher that
# reports "still 180 GB free" every two minutes is one nobody reads by the third hour, which is
# the hour it would have mattered. Silence here means: still running, still enough room.
#
# THE THRESHOLDS GET TIGHTER AS THEY GET LOWER -- 40, 30, 25, 20, 15, 10, 5 GB -- because the
# decision they inform changes. At 40 GB the question is which archive to start next; at 5 GB it
# is whether the file in flight will finish. mirror.py stops on its own at common.MIN_FREE_BYTES
# (1 GB), with room to finish the current file and write its index; this exists so a person hears
# about it well before then.
#
# IT STOPS WHEN THE FETCH DOES, by watching for any python process rather than a specific PID.
# Crude, and right for the case it is used in: one fetch at a time on a machine where the only
# long-running python IS the fetch. With several running it will simply keep watching until the
# last one ends, which is the harmless direction to be wrong in.
set -u

ROOT="${1:-Q:/}"
LAST=999999
while true; do
  FREE=$(python -c "import shutil,sys; print(int(shutil.disk_usage(sys.argv[1]).free/1e9))" \
         "$ROOT" 2>/dev/null)
  [ -z "$FREE" ] && FREE=$LAST
  for T in 40 30 25 20 15 10 5; do
    if [ "$FREE" -le "$T" ] && [ "$LAST" -gt "$T" ]; then
      echo "SPACE: only ${FREE} GB left on ${ROOT} (dropped below ${T} GB)"
      break
    fi
  done
  LAST=$FREE
  # the fetch is the only writer; when it is gone, say so and stop watching
  if ! ps -W 2>/dev/null | grep -qi "python"; then
    echo "FETCH ENDED: no python process left, ${FREE} GB free on ${ROOT}"
    exit 0
  fi
  sleep 120
done
