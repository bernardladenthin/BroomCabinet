#!/bin/sh

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

# THE FULL LOCAL GATE over both Python projects. Nothing here writes to the collection.
#
#     sh Python/PyMirror/tools/gate.sh
#
# WHY IT EXISTS BESIDE CI, and what it adds. `.github/workflows/python-ci.yml` runs ruff, a
# `--help` over every script, and every test file by name. This runs those too -- so a red gate
# here is a red CI there -- and adds the two checks CI does not have:
#
#   compileall -W error::SyntaxWarning   A SyntaxWarning is not a lint finding. On 2026-09-27 a
#                                        test file went in with `"C:\mirror\\"` and ruff passed
#                                        it; only this caught it. `W605` has since been added to
#                                        ruff.toml, which closes that particular class in CI --
#                                        this stays because compileall catches the whole family
#                                        and a rule list only catches what is listed.
#
#   contract-mutations.py --apply        Breaks each library rule on purpose and checks that the
#                                        suite notices. It EDITS FILES IN PLACE and restores
#                                        them, so it cannot run on a shared runner, and two of it
#                                        at once is not a slow run but a corrupt one -- see that
#                                        script's own lock. That is why it is local-only.
#
# IT LIVED IN A TEMPORARY DIRECTORY UNTIL 2026-09-27, which made the sharpest part of the gate
# depend on a scratch file that any cleanup would delete.
set -u

HERE=$(cd "$(dirname "$0")" && pwd)
PM="$HERE/.."
PS="$HERE/../../PySweeper"

cd "$PM" || exit 1
fail=0
n=0
for t in *test*.py; do
    n=$((n + 1))
    if ! python "$t" >/dev/null 2>&1; then
        echo "  FAILED $t"
        python "$t" 2>&1 | grep -E "^(FAIL|ERROR):" | head -5
        fail=$((fail + 1))
    fi
done
echo "PyMirror: $n test files, $fail failed"

python -W error::SyntaxWarning -m compileall -q . >/dev/null 2>&1 \
    && echo "  compile: clean" || echo "  compile: FAILED"
ruff check . || echo "  ruff: FAILED"

for f in *.py; do
    case "$f" in *test*) continue;; esac
    grep -q argparse "$f" || continue
    python "$f" --help >/dev/null 2>&1 || echo "  --help FAILED: $f"
done
echo "  --help: through"

python contract-mutations.py --apply 2>&1 | tail -3

echo "PySweeper:"
cd "$PS" || exit 1
ruff check . || echo "  ruff: FAILED"
for t in *test*.py; do
    if python "$t" >/dev/null 2>&1; then
        echo "  $t ok"
    else
        echo "  $t FAILED"
        python "$t" 2>&1 | grep -E "^(FAIL|ERROR):" | head -5
    fi
done
