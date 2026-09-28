# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""The four robots.txt readings this collection has got wrong, or nearly got wrong.

Each case is a real file from a real host, reduced to the part that decides it. They are here
because in every one of them the naive reading and the correct reading disagree, and three of
the four were argued about by more than one reader before being settled.

THE CASES LIVE HERE AND NOWHERE ELSE. The function they exercise moved into common.py on
2026-09-23, because reading somebody else's refusal is not one tool's business; these cases did
not move with it and were not copied, because the same evidence in two places is evidence that
will disagree with itself.

Run: python robots_verdict_test.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from robots import robots_verdict  # noqa: E402

CASES = []

# 1. irixnet.org. The decades-old "bad bot" blocklist that circulates in webmaster forums: 188
#    named agents sharing one Disallow. archive.org_bot and ia_archiver are in it because the list
#    has carried them for years, not as a statement about preservation. THERE IS NO
#    `User-agent: *` ANYWHERE IN IT -- an agent that is not named has no rule, and we are not
#    named. Two researchers reported this host differently; both were right, about different
#    vhosts.
CASES.append((
    "irixnet 188-agent blocklist, we are not named",
    "\n".join(["User-agent: %s\nDisallow: /" % a for a in
               ("Alexibot", "BackDoorBot/1.0", "BlowFish/1.0", "BunnySlippers", "CheeseBot",
                "ia_archiver", "archive.org_bot", "Xenu's Link Sleuth", "Zeus", "Zyborg",
                "EmailCollector", "Crescent")]),
    "/sgi-irix/", "OPEN"))

# 2. 4corn.co.uk. 45 AI agents listed, EMPTY Disallow. By the letter of the standard this permits
#    everything. It is a mistake in their file, not an invitation. A machine may not read a typo
#    as consent.
CASES.append((
    "4corn: long agent list with an empty Disallow -- intent, not syntax",
    "\n".join(["User-agent: %s" % a for a in
               ("GPTBot", "ClaudeBot", "anthropic-ai", "CCBot", "Google-Extended", "Omgilibot",
                "FacebookBot", "Bytespider", "PerplexityBot", "Amazonbot", "cohere-ai",
                "Diffbot", "ImagesiftBot", "YouBot", "Applebot-Extended")]) + "\nDisallow:",
    "/archive/", "NO-OP BLOCK"))

# 3. update.uu.se web vhost. The club names us explicitly. Its FTP vhost serves no robots.txt at
#    all -- and that 404 is NOT permission, because the same organisation has said no here.
CASES.append((
    "update.uu.se: names ClaudeBot explicitly",
    "User-agent: ClaudeBot\nDisallow: /\n\nUser-agent: *\nDisallow: /cgi-bin/",
    "/pub/", "BLOCKED"))

# 4. A plain blanket refusal, which must not be confused with case 1.
CASES.append((
    "blanket User-agent: * -> Disallow: /",
    "User-agent: *\nDisallow: /", "/pub/", "BLOCKED"))

# 5. Rules exist for everyone but none reach the path we want. Reading the file as one blob
#    reports another agent's rule as ours; this is the check that the group parser works.
CASES.append((
    "rules exist, none match our path",
    "User-agent: SemrushBot\nDisallow: /\n\nUser-agent: *\nDisallow: /cgi-bin/\nDisallow: /tmp/",
    "/pub/drivers/", "OPEN"))

# 6. No robots.txt at all.
CASES.append(("no robots.txt", None, "/anything/", "OPEN"))

# 7. The path rule that DOES reach us -- hpux.connect.org.uk disallows /ftp/, which is the whole
#    reason that candidate needs an operator's permission rather than a crawl.
CASES.append((
    "hpux.connect.org.uk: Disallow: /ftp/ reaches the path we want",
    "User-agent: *\nDisallow: /ftp/", "/ftp/hpux/", "BLOCKED"))

failed = 0
for title, text, path, want in CASES:
    got, why = robots_verdict(text, path)
    ok = got == want
    failed += 0 if ok else 1
    print("%s %-56s %-12s %s" % ("ok  " if ok else "FAIL", title[:56], got, why[:52]))
    if not ok:
        print("     expected %s" % want)

print("\n%d case(s), %d failed" % (len(CASES), failed))
sys.exit(1 if failed else 0)
