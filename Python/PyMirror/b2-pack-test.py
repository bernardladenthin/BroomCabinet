#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""The packing plan, checked without WinRAR and without the collection.

WHAT MATTERS MOST HERE, and it is not the command strings:

  * **EVERY FILE MUST BE CLAIMED BY EXACTLY ONE UNIT.** A file no unit claims is a file that is
    silently not in cold storage, and nothing downstream would notice -- the archive would simply
    be smaller than expected, which looks like good compression. A file two units claim is paid
    for twice. Both are checked, on a fixture here and against the real collection where it is
    mounted.

  * **THE PASSWORD MUST NOT BE IN THE PLAN.** The plan is meant to be printed, read and pasted
    into a report. `-hp` is added in `execute()` and nowhere else, so a test can assert that no
    step carries a secret before one exists.

  * **`-m0` MUST NOT CARRY A DICTIONARY OR SOLID SWITCHES.** Not cosmetic: `-m0 -s` is a
    contradiction that WinRAR resolves silently, and the two stored units are 844 GB. If the
    builder ever emits it, the mistake is invisible in a 50-line command.

WHY NO SUBPROCESS AND NO `Q:\mirror`. A test that needed WinRAR installed would fail on a machine
where it is not, for a reason that says nothing about the plan -- and the tool already reports that
case itself. A test that needed 3.98 TB mounted could only ever run here. The fixture below is four
small CSV indexes with the shapes that matter: a duplicate pair, a subtree split, a name that
almost matches a subtree, and a file with no extension.
"""
import hashlib
import importlib.util
import io
import os
import shutil
import sys
import tempfile
import unittest

import common  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def load(name):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), name + ".py")
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TOOL = load("b2-pack")
HERE_DIR = os.path.dirname(os.path.abspath(__file__))

DIGEST_A = "a" * 64
DIGEST_B = "b" * 64
DIGEST_DUP = "c" * 64


def fixture(also=()):
    """A four-archive collection in a temporary directory. Never Q:\\mirror.

    `also` adds empty indexes for REAL archive names. `main()` always plans from `TOOL.UNITS`, so a
    test that exercises the command line has to offer the archives one real unit names -- the
    first version passed `--only bull` at this fixture and got a FileNotFoundError, which is a
    defect in the test rather than in the tool and would have read as the tool being broken.
    """
    root = tempfile.mkdtemp(prefix="b2-pack-test-")
    trees = {
        "alpha": [("docs/one.txt", 100, DIGEST_A),
                  ("docs/two.rpm", 200, DIGEST_DUP)],
        "beta": [("copy/two.rpm", 200, DIGEST_DUP),          # the same bytes as alpha's
                 ("noext", 300, DIGEST_B)],
        "split": [("pdf/a.pdf", 400, DIGEST_A),
                  ("pdfx/b.pdf", 500, DIGEST_B),             # must NOT count as pdf/
                  ("other/c.bin", 600, DIGEST_B)],
        "lonely": [("x.iso", 700, DIGEST_A)],
    }
    for archive in also:
        trees.setdefault(archive, [("only.txt", 1, DIGEST_A)])
    for archive, rows in trees.items():
        os.makedirs(os.path.join(root, archive))
        with io.open(os.path.join(root, archive, TOOL.INDEX_FILE),
                     "w", encoding="utf-8", newline="\n") as fh:
            fh.write("path,size,mtime_ns,sha256\n")
            for path, size, digest in rows:
                fh.write("%s,%d,0,%s\n" % (path, size, digest))
    # Directories holding nothing, which no index can mention. One inside the named subtree and
    # two outside it, so the two units that divide `split` have to divide these correctly too.
    for rel in ("pdf/hollow", "other/hollow", "deep/a/b"):
        os.makedirs(os.path.join(root, "split", *rel.split("/")))
    return root


# A flat work directory on whatever drive the tests live on. It need not exist: planning writes
# nothing, and `main()` only looks at the shape of the path.
FLAT_WORK = os.path.splitdrive(os.path.abspath(__file__))[0] + os.sep + "b2work-test"

# A real unit small enough to stand up in a fixture, used only by the command-line tests.
# A real unit small enough to stand up in a fixture. `next` held this post until the 2026-10-04
# regrouping folded it into `workstations`; `oldskool` is now the smallest single-archive unit.
REAL_UNIT = "oldskool"
REAL_ARCHIVES = [u for u in TOOL.UNITS if u.name == REAL_UNIT][0].archives()


def test_units():
    """The shapes the real table uses: a plain unit, a subtree, and a subtree's remainder."""
    return (
        TOOL.Unit("pair", ["alpha", "beta"], "two archives that share a file, kept together"),
        TOOL.Unit("split-pdf", ["split/pdf"], "one subtree of one archive, by its own name"),
        TOOL.Unit("split-rest", ["split"], "the remainder, so a new subtree cannot vanish",
                  exclude=["split/pdf"]),
        TOOL.Unit("lonely", ["lonely"], "an archive on its own, which is the common case"),
    )


class EveryFileIsClaimedExactlyOnce(unittest.TestCase):
    """The check the whole plan rests on."""

    def setUp(self):
        self.root = fixture()

    def test_nothing_is_orphaned_and_nothing_is_doubled(self):
        orphans, doubles = TOOL.coverage(test_units(), self.root)
        self.assertEqual(dict(orphans), {})
        self.assertEqual(dict(doubles), {})

    def test_a_missing_unit_is_reported_rather_than_ignored(self):
        """Drop `lonely` and the file must be named, not quietly absent."""
        units = tuple(u for u in test_units() if u.name != "lonely")
        orphans, doubles = TOOL.coverage(units, self.root)
        self.assertEqual(dict(orphans), {"lonely": 700})
        self.assertEqual(dict(doubles), {})

    def test_an_overlapping_unit_is_reported(self):
        units = test_units() + (TOOL.Unit("greedy", ["split"], "claims what split-pdf claims"),)
        _orphans, doubles = TOOL.coverage(units, self.root)
        self.assertTrue(doubles, "two units claiming one file must be reported")

    def test_a_subtree_name_that_merely_starts_the_same_is_not_swallowed(self):
        """`split/pdfx` is not inside `split/pdf`, and a prefix test that forgets the separator
        would put 500 bytes in the wrong unit and nobody would see it."""
        subtree = [u for u in test_units() if u.name == "split-pdf"][0]
        self.assertTrue(subtree.claims("split", "pdf/a.pdf"))
        self.assertFalse(subtree.claims("split", "pdfx/b.pdf"))

    def test_the_remainder_unit_takes_what_the_named_subtree_does_not(self):
        rest = [u for u in test_units() if u.name == "split-rest"][0]
        self.assertFalse(rest.claims("split", "pdf/a.pdf"))
        self.assertTrue(rest.claims("split", "pdfx/b.pdf"))
        self.assertTrue(rest.claims("split", "other/c.bin"))


class TheRealTableIsAPartition(unittest.TestCase):
    """Checked without the collection: the member lists alone must not overlap or repeat."""

    def test_no_archive_is_named_by_two_units(self):
        seen = {}
        for unit in TOOL.UNITS:
            for archive in unit.archives():
                if archive in seen:
                    # bitsavers is deliberately split by subtree, and only bitsavers.
                    self.assertEqual(archive, "bitsavers",
                                     "%s is in %s and %s" % (archive, seen[archive], unit.name))
                seen.setdefault(archive, unit.name)
        self.assertIn("bitsavers", seen)

    def test_BITSAVERS_IS_ONE_UNIT_WITH_NOTHING_TO_GET_RIGHT(self):
        r"""It was split into paper and software until 2026-10-07, and the remainder unit had to
        name `bitsavers` bare while excluding exactly the paper subtrees -- a subtraction that had
        to be correct every time the mirror was re-fetched, and that decided which side a new
        top-level directory upstream landed on.

        One directory, one unit, no exclusion: there is nothing left to get right. The test that
        checked the subtraction is replaced by one that checks the subtraction is GONE.
        """
        unit = [u for u in TOOL.UNITS if u.name == "bitsavers"][0]
        self.assertEqual(unit.members, ("bitsavers",))
        self.assertEqual(tuple(unit.exclude or ()), ())
        # and no other unit may reach into it, or the one-directory-one-unit claim is false
        for other in TOOL.UNITS:
            if other.name == "bitsavers":
                continue
            for member in other.members:
                self.assertFalse(member == "bitsavers" or member.startswith("bitsavers/"),
                                 "%s also names %s" % (other.name, member))

    def test_every_unit_has_members_and_a_reason(self):
        for unit in TOOL.UNITS:
            self.assertTrue(unit.members, unit.name)
            self.assertGreater(len(unit.why), 60, "%s: a reason, not a label" % unit.name)

    def test_there_are_nine(self):
        """Not decoration -- the count is the thing that was agreed, and a silent tenth unit means
        an upload nobody planned for.

        NINETEEN UNTIL 2026-10-04, TEN UNTIL 2026-10-07. The owner's rule was that a subject
        should be one unpack: "wenn man an AIX Sachen arbeitet, entpackt man vermutlich komplett
        AIX". Measured, the first merge was worth 16 GB of 4 581 -- the bytes came from the volume
        size, not from this -- so the count changed for the reader and not for the bill.

        THE LAST MERGE WAS bitsavers, paper and software into one, and its reason is different:
        not unpacking but UPDATING. bitsavers is the one mirror here that changes constantly, so
        it is the one that will be re-fetched and re-packed, and a split meant two packs, two sets
        of manifests and a subtraction to get right every time."""
        self.assertEqual(len(TOOL.UNITS), 9)

    def test_the_names_are_usable_as_directory_names(self):
        for unit in TOOL.UNITS:
            self.assertRegex(unit.name, r"^[a-z0-9][a-z0-9.-]*$")


class EveryArchiveMirrorKnowsAboutHasAUnit(unittest.TestCase):
    r"""The coupling between the two tables, checked WITHOUT the collection.

    `mirror.ARCHIVES` is where a new mirror is declared; `b2-pack.UNITS` is where it is assigned to
    a RAR set. Nothing made those two agree. Adding an archive and forgetting the unit produced a
    failure that `WhenTheCollectionIsHere` catches -- but only on a machine with 3.98 TB mounted,
    which is the machine that does the packing and not the one that reviews the change.

    Written on 2026-09-26, when `mcamafia` and `vgamuseum-doc` were added to `mirror.ARCHIVES`.
    The partition test would have caught them eventually; this one catches them in half a second,
    on any machine, before anything is fetched.

    IT IS DELIBERATELY ONE-DIRECTIONAL. A unit may name an archive `mirror.py` does not declare --
    `next-68k-org` was unpacked out of a tar rather than fetched, and `hp-labs-linux-salvage`,
    `dec-ftp-2006`, `hp-openvms-2008` and the other `.tar` extractions have no ARCHIVES entry at
    all. So this asks only that every DECLARED archive has a home, not that every home is declared.
    """

    def setUp(self):
        self.mirror = load("mirror")
        self.claimed = set(a for u in TOOL.UNITS for a in u.archives())

    def test_no_declared_archive_is_left_without_a_unit(self):
        declared = [name for name, _url in self.mirror.ARCHIVES]
        orphans = sorted(set(declared) - self.claimed)
        self.assertEqual(orphans, [],
                         "in mirror.ARCHIVES but in no b2-pack unit: " + ", ".join(orphans))

    def test_the_rsync_and_internet_archive_sources_too(self):
        """The other two ways an archive enters the collection, and both were easy to forget."""
        extra = []
        for attr in ("RSYNC", "IA_ITEMS"):
            table = getattr(self.mirror, attr, None)
            if isinstance(table, dict):
                extra.extend(table)
        orphans = sorted(set(extra) - self.claimed)
        self.assertEqual(orphans, [],
                         "declared in RSYNC/IA_ITEMS but in no b2-pack unit: "
                         + ", ".join(orphans))

    def test_a_unit_may_name_something_mirror_py_does_not_declare(self):
        """Stated as a test so the one-directional rule is not tightened by accident."""
        declared = set(name for name, _url in self.mirror.ARCHIVES)
        self.assertTrue(self.claimed - declared,
                        "if this ever empties, the rule above can be made symmetric")


class EveryHostThatBlockedUsKeepsItsRateLimit(unittest.TestCase):
    r"""Two hosts have already refused this collection. Neither may lose its limit again.

    THE SAME INCIDENT HAPPENED TWICE, three weeks apart, and the second time everything needed to
    prevent it was already written down:

      2026-09-08  dialectronics.com, default eight connections -> 783 x WinError 10060, and the
                  host stopped answering curl as well. One connection did not fix it; the host
                  limits the RATE, not the concurrency. Measured at 4.0 s, which worked.
      2026-09-26  vgamuseum-doc, default eight connections -> first pass 1 142 of 2 261 files,
                  retry 195 files and ZERO BYTES, then the TLS handshake itself refused.

    A NEW ARCHIVE INHERITS THE DEFAULTS SILENTLY. Nothing in the code asks whether a host is a
    national mirror or one person's Joomla install before the first run at eight connections, and
    a prose note next to MIN_INTERVAL does not apply itself. This test cannot supply that
    judgement either -- what it can do is make the two hosts that have actually refused
    un-forgettable, so a later tidy-up cannot quietly drop their pace back to the default.

    It lives in this file rather than in a mirror test because this is where the two tables are
    already loaded together, and because the packing plan is what notices an archive is short.
    """

    SLOWEST_MEASURED = 4.0

    def setUp(self):
        self.mirror = load("mirror")

    def test_both_are_still_paced(self):
        for archive in ("dialectronics", "vgamuseum-doc"):
            self.assertIn(archive, self.mirror.MIN_INTERVAL,
                          "%s blocked this collection once; it must keep a rate limit" % archive)

    def test_neither_pace_is_relaxed_below_what_was_measured(self):
        """4.0 s is the only interval ever measured against a real refusal here.

        dialectronics' own note records that 1.0 s was tried first, was not measured, and failed
        the same way -- so a number that merely looks generous is not evidence.
        """
        for archive in ("dialectronics", "vgamuseum-doc"):
            self.assertGreaterEqual(self.mirror.MIN_INTERVAL[archive], self.SLOWEST_MEASURED,
                                    archive)

    def test_the_incomplete_archive_is_not_presented_as_finished(self):
        """`vgamuseum-doc` holds about half of what was measured, and says so in its own note.

        If the block lifts and the rest is fetched, this assertion is what has to be updated --
        deliberately, by somebody who checked, rather than by the fetch quietly succeeding.
        """
        import io as _io
        import os as _os
        source = _io.open(_os.path.join(HERE_DIR, "mirror.py"), encoding="utf-8").read()
        self.assertIn("The archive stays INCOMPLETE until the block", source)


class TheOptionsBuilder(unittest.TestCase):
    """Defaults in one place; a unit names only what differs."""

    def test_with_does_not_change_the_original(self):
        """`method=0` is the one the real units actually override to, so it is the one used here --
        the default became 5 on 2026-10-04 and a test asserting 1 was asserting the default rather
        than the copying."""
        other = TOOL.DEFAULTS.with_(method=0)
        self.assertEqual(TOOL.DEFAULTS.method, 5)
        self.assertEqual(other.method, 0)

    def test_with_changes_only_what_it_names(self):
        other = TOOL.DEFAULTS.with_(method=0)
        for field in TOOL.Options.FIELDS:
            if field != "method":
                self.assertEqual(getattr(other, field), getattr(TOOL.DEFAULTS, field), field)

    def test_an_unknown_option_is_refused_rather_than_ignored(self):
        """A typo that is silently accepted is a setting that silently does not apply."""
        with self.assertRaises(ValueError):
            TOOL.DEFAULTS.with_(compression=9)

    def test_the_default_switches(self):
        """The whole set, in order, for ibm-aix's 3 400 volumes.

        THE COUNT USED TO BE 30, from the plan's first shape, where a volume was 24.2 GB. At
        199 MiB no unit comes near it -- the smallest, misc, is 698 -- so a case asserting against
        30 was asserting against a unit that no longer exists. 3 400 also exercises the large tier
        of the 5 / 10 / 15 rule, which 30 did not.
        """
        self.assertEqual(TOOL.DEFAULTS.switches(3400),
                         ["-ma5", "-m5", "-md4g", "-s", "-oi1",
                          "-v%db" % TOOL.VOLUME_BYTES, "-rr1", "-rv68", "-k", "-scfl"])

    def test_THE_CHARSET_IS_F_AND_NOT_U(self):
        """U is UTF-16. On a UTF-8 list file `-scul` stored NONE of five non-ASCII names.

        This tool emitted `-scul` until it was put to a real WinRAR. The failure mode is the worst
        kind: files with non-ASCII names are simply absent from the archive.
        """
        switches = TOOL.DEFAULTS.switches(3)
        self.assertIn("-scfl", switches)
        self.assertNotIn("-scul", switches)

    def test_THE_ARCHIVE_IS_LOCKED_IN_THE_SAME_COMMAND(self):
        """`-k` here is safe and `rar k` afterwards is not -- measured, and the difference is total.

        Packed with `-rr10 -rv2 -k`, two deleted volumes came back. Locking the same set AFTERWARDS
        made `rar rc` report all fourteen volumes as checksum failures and recovery as impossible,
        because locking rewrites every volume and the .rev files match none of them. So the lock
        belongs in this list and must never become a separate step.
        """
        self.assertIn("-k", TOOL.DEFAULTS.switches(3))

    def test_the_format_is_stated_and_not_left_to_the_default(self):
        self.assertEqual(TOOL.DEFAULTS.switches(3)[0], "-ma5")

    def test_STORED_UNITS_CARRY_NO_DICTIONARY_AND_NO_SOLID(self):
        """The contradiction WinRAR resolves silently, over 844 GB of stored units."""
        switches = TOOL.DEFAULTS.with_(method=0).switches(30)
        self.assertIn("-m0", switches)
        for forbidden in ("-s", "-sv"):
            self.assertNotIn(forbidden, switches)
        self.assertFalse([s for s in switches if s.startswith("-md")])

    def test_the_index_archive_is_not_split_into_volumes(self):
        """It is the file you fetch instead of a unit; splitting it would defeat the point."""
        self.assertFalse([s for s in TOOL.INDEX_OPTIONS.switches() if s.startswith("-v")])

    def test_and_therefore_gets_no_recovery_volumes(self):
        """.rev files only mean anything for a split archive; its recovery RECORD still applies."""
        switches = TOOL.INDEX_OPTIONS.switches()
        self.assertFalse([s for s in switches if s.startswith("-rv")])
        # STILL 10 % HERE while the units went to 3 % on 2026-10-04. The index archive is the thing
        # you fetch INSTEAD of a unit, it is not split into volumes so it has no .rev to fall back
        # on, and 10 % of 50 MB is 5 MB. The cheap failure is worth paying for when it is cheap.
        self.assertIn("-rr10", switches)

    def test_recovery_volumes_and_recovery_record_are_both_present_and_different(self):
        """-rr repairs damage inside a volume; -rv replaces a whole missing one. Losing a part
        file is the threat cold storage actually presents, and only -rv answers it. Measured:
        both apply from one command, and two deleted volumes were restored from two .rev."""
        switches = TOOL.DEFAULTS.switches(30)
        self.assertIn("-rr1", switches)
        self.assertIn("-rv2", switches)      # the floor; see recovery_volumes()

    def test_THE_RECOVERY_VOLUMES_ARE_A_PERCENTAGE_WITH_A_FLOOR(self):
        r"""2 % of the volume count, never fewer than 2. A count is emitted, because -rv takes one.

        THIS IS THE THIRD ANSWER AND THE SECOND TIME IT HAS BEEN A PERCENTAGE. A 2 % rule was
        replaced on 2026-10-05 by a 5 / 10 / 15 ladder on the owner's words -- "fuer kleine reichen
        5, mittel 10 und das ganz grosse hat 15 recovery archive" -- and the ladder was reverted on
        2026-10-06 for a reason that was true the whole time: IT WAS INVERTED. 5 of 703 volumes is
        0.71 %, 15 of 4087 is 0.37 %, so the unit with six times the volumes and six times the
        exposure got half the relative cover. The intuition was about absolute counts; the risk
        scales with the set.

        RARLAB's own default for -rv is 10 % (rar.txt: "Wird der Parameter <N> nicht angegeben,
        wird er auf 10% gesetzt"), so the ladder ran the largest unit at a twenty-seventh of the
        vendor default while reading like a considered choice.

        2 % AND NOT 3 %, the owner on 2026-10-06: "waeren hier nicht 2% besser? auf lange sicht?
        das ist massiv". At 3.557 GB a .rev file is 3.56 GB, so the percentage is expensive in
        absolute terms -- 78 GB across the collection at 2 % against 121 GB at 3 %. And a .rev is
        the FOURTH line: every volume carries its own 1 % record for damage inside it, and exists
        locally, on B2 and on M-Disc.

        THE "IT COVERS A WHOLE M-DISC" ARGUMENT FOR 3 % WAS WRONG AND IS RECORDED AS WRONG. It
        counted the collection's volumes as one set, but .rev files protect ONE UNIT: at 3.557 GB a
        unit is 41 to 238 volumes, spans several discs, and a disc carries volumes of more than one
        unit. No per-unit budget can promise to replace a disc.

        THE FLOOR CAME DOWN FROM 5 TO 2 IN THE SAME CHANGE, because it only became wrong when the
        volumes grew: at 199 MiB a floor of 5 was 1 GB on any unit, at 3.557 GB it is 17.8 GB, and
        on the 144 GB misc unit that would have been 12 % -- a floor quietly overriding the
        percentage it exists to backstop. The owner confirmed two: "genau, min 2 rev sollten es
        sein".
        """
        # 2 % where the set is big enough for it to bite. Volume counts at 3.557 GB per volume:
        # misc 41, ibm-aix 198, bitsavers-paper 238.
        self.assertEqual(TOOL.DEFAULTS.recovery_volumes(238), 4)
        self.assertEqual(TOOL.DEFAULTS.recovery_volumes(198), 3)
        self.assertEqual(TOOL.DEFAULTS.recovery_volumes(100), 2)
        # the floor, for a unit too small for the percentage to produce anything
        self.assertEqual(TOOL.DEFAULTS.recovery_volumes(41), 2)
        self.assertEqual(TOOL.DEFAULTS.recovery_volumes(6), 2)
        self.assertEqual(TOOL.DEFAULTS.recovery_volumes(1), 2)
        # and it scales, which the ladder did not
        self.assertEqual(TOOL.DEFAULTS.recovery_volumes(4087), 81)
        # no volumes at all means no .rev: the index archive is not split
        self.assertEqual(TOOL.DEFAULTS.recovery_volumes(None), 0)

    def test_and_every_real_unit_gets_at_least_the_floor(self):
        r"""THE TIER TEST IS GONE WITH THE TIERS. It mapped each of the ten units to 5, 10 or 15,
        which was the ladder's whole shape; a percentage has no tiers to drift across.

        What is still worth asserting is that no unit comes out with nothing. At 3.557 GB the
        smallest units are a few dozen volumes, where 2 % rounds to zero and only the floor keeps
        them covered -- which is the case the floor was lowered to 2 for rather than removed.
        """
        for unit in TOOL.UNITS:
            if not unit.options.volume_bytes:
                continue                      # the index archive is not split
            for volumes in (1, 6, 41, 238):
                got = unit.options.recovery_volumes(volumes)
                self.assertGreaterEqual(got, 2, "%s at %d volumes got %d"
                                        % (unit.name, volumes, got))

    def test_an_unsplit_archive_gets_none(self):
        """.rev files only mean anything for a volume set."""
        self.assertEqual(TOOL.INDEX_OPTIONS.recovery_volumes(1), 0)


class _OneArchive(object):
    """A unit of one archive that claims everything, for the pure-function cases below."""

    def archives(self):
        return ["alpha"]

    def claims(self, archive, path):
        return True


class ItRefusesToLoseAFileToRarsCaseBlindness(unittest.TestCase):
    r"""`rar a` stores ONE of two paths differing only in case, says nothing, and exits 0.

    MEASURED ON 2026-10-05 with a 14-byte a.txt and a 22-byte A.txt in a directory carrying the
    Windows per-directory case-sensitivity flag. Passing the directory, passing -r, passing an
    @list, passing -oni, and naming both files explicitly ALL produced an archive with ONE entry
    and no warning; a second `rar a` of the other REPLACED the entry. 7-Zip 24.09 at least refuses
    -- "ERROR: Duplicate filename on disk" -- and writes nothing at all.

    THE ARCHIVE NAMESPACE IS CASE-SENSITIVE, which is what makes this a tooling limit rather than
    a format one: on a SINGLE-volume archive, packing the second file under a staged name and then
    `rar rn`-ing it to its real name produced both `data\a.txt` (14 bytes) and `data\A.txt` (22
    bytes). The same `rar rn` on a 5-volume set printed "Fertig" and changed nothing -- so the
    workaround exists and does not reach the shape this plan needs, which is 199 MiB volumes.

    COLLECTION-WIDE: 4 542 files in 15 archives, 3.55 GB, 3 404 groups of two and 569 of three,
    4 028 of them in ibm-aix. `rar t` reports "Alles OK" over the hole because it only checks what
    the archive holds.

    HOW IT WAS SETTLED, over 2026-10-05 and 2026-10-06. The first position was that the mirror is
    not where this gets fixed -- renaming would break the one property the collection has, being a
    faithful copy. The owner then reversed it, on the ground that a re-fetch five years from now
    will not reproduce today's tree anyway: "wir müssen das so gesehen nur gut genug machen". So
    all 4417 colliding extra members were resolved IN the mirror, in three shapes chosen per
    branch, and the collection now holds none. The refusal below is kept for the re-fetch case,
    which is the one thing none of this can prevent.
    """

    def rows(self, *paths):
        return [{"archive": "a", "path": p, "size": 1, "digest": "x"} for p in paths]

    def test_a_pair_is_found(self):
        got = TOOL.case_collisions(self.rows("dir/One.txt", "dir/one.txt", "dir/other.txt"))
        self.assertEqual(got, [["a/dir/One.txt", "a/dir/one.txt"]])

    def test_a_group_of_three_is_one_group_and_loses_two(self):
        """569 such groups exist, and a fix that renames only one member would still lose one."""
        got = TOOL.case_collisions(self.rows("x/A.bff", "x/a.bff", "x/A.BFF"))
        self.assertEqual(len(got), 1)
        self.assertEqual(len(got[0]), 3)

    def test_A_COLLISION_IN_A_DIRECTORY_COMPONENT_COUNTS_TOO(self):
        """ardent-tool holds PS55/Docs/scans/x.pdf and PS55/docs/scans/x.pdf. The differing
        component is not the filename, and RAR drops one just the same. 82 directories appear
        under two casings across 6 archives, with 68 587 files below them."""
        got = TOOL.case_collisions(self.rows("PS55/Docs/scans/x.pdf", "PS55/docs/scans/x.pdf"))
        self.assertEqual(len(got), 1)

    def test_an_ordinary_tree_has_none(self):
        self.assertEqual(TOOL.case_collisions(self.rows("a.txt", "b.txt", "dir/c.txt")), [])

    def test_the_comparison_is_lower_and_not_casefold(self):
        """casefold() folds the German sharp s to "ss", which is right for comparing words and
        wrong here: the question is whether ONE FILESYSTEM can hold both names, and NTFS compares
        with an upper-case table rather than with Unicode case folding. A fold more aggressive than
        the filesystem's reports collisions that do not exist."""
        src = io.open(os.path.join(HERE_DIR, "b2-pack.py"), encoding="utf-8").read()
        block = src[src.index("def case_collisions("):src.index("def listing_text(")]
        self.assertIn(".lower()", block)
        self.assertNotIn("casefold", block)

    def test_IT_IS_A_REFUSAL_BEFORE_ANYTHING_IS_WRITTEN(self):
        """And on a dry run too: the figure a reader needs is the one from BEFORE they spend two
        hours packing. Checked against the real misc unit, which holds 275 such files."""
        src = io.open(os.path.join(HERE_DIR, "b2-pack.py"), encoding="utf-8").read()
        block = src[src.index("losing = []"):src.index('    rar = "rar"')]
        self.assertIn("REFUSING:", block)
        self.assertIn("return 2", block)
        self.assertIn("case_collisions(", block)

    def test_and_the_real_collection_NO_LONGER_HOLDS_ANY(self):
        r"""THE CANARY FIRED, AND THIS IS WHAT IT MEANT. It asserted the opposite until
        2026-10-06 -- "misc held 275 case collisions on 2026-10-05" -- so that the day the
        collection changed, a test would say so instead of a refusal quietly becoming dead code.

        It changed. 4417 colliding extra members became 0, in three shapes: six tars over the
        branches where the spelling encodes something (AIX locales, netstation.msg.AR_AA against
        Ar_AA against ar_AA, libC against libc), 164 byte-identical twins dropped with the sha256
        that justified each one, and 163 renames with a trailing underscore where both files were
        genuinely different and scattered too thinly for a tar.

        THE REFUSAL IN b2-pack.py STAYS. It is not dead code: it is what makes a RE-FETCH safe.
        Which member of a case pair arrives first is not deterministic, so a crawl years from now
        can put them back -- and then this guard is the only thing between that and an archive
        that packs clean while holding one file of every pair. A guard worth keeping is one whose
        condition is false today.
        """
        if not os.path.isdir(TOOL.MIRROR_ROOT):
            self.skipTest("the collection is not mounted here")
        unit = [u for u in TOOL.UNITS if u.name == "misc"][0]
        groups = TOOL.case_collisions(TOOL.rows_for(unit, TOOL.MIRROR_ROOT, {}))
        self.assertEqual(groups, [], "a case collision is back in misc -- do not pack it")


class TheCRC32CrossCheck(unittest.TestCase):
    r"""A SECOND OPINION ON WHAT WAS PACKED, and a file count, for about 50 seconds a unit.

    `rar t` proves the archive decompresses to what RAR recorded WHILE PACKING. Both sides of that
    comparison come from the same read, so it cannot notice RAR having packed the wrong bytes, and
    it cannot notice a file that never reached the archive at all. The .sfv was built days earlier,
    by us, from the files themselves -- so holding RAR's stored CRC32 against it compares two
    independent readings, and comparing the counts answers the second question.

    IT IS CHEAP BECAUSE THE CRCs ARE IN THE HEADERS. `rar lt` needs no dictionary and decompresses
    nothing: measured on misc, 98.62 GB in 468 volumes, all the listings took 49 seconds against
    seven minutes for `rar t`.

    IT FOUND TWO THINGS ON ITS FIRST REAL RUN, which is the whole argument for having it:

      TWO STALE MANIFEST ENTRIES. bretjohnson/CONVERGED.md and fjkraan/CONVERGED.md were rewritten
      by the converge runs of 2026-10-04 at 13:53, after their manifests had been built. The .sfv
      said DA5535AA and the file was E173965F. mirror.py --index updates the weaker digests only
      for files it re-hashes, so a file written after an index run keeps its old CRC32, SHA-1 and
      MD5 while its SHA-256 stays correct. Corrected by re-indexing exactly those two archives: one
      line changed in each manifest, the content untouched.

      275 FILES MISSING FROM THE ARCHIVE, which is how a far larger defect surfaced. Rar.exe cannot
      store two files whose paths differ only in case: it keeps one, says nothing, and exits 0.
      Collection-wide that is 4 542 files across 15 archives, 3.55 GB.
    """

    LISTING = "\n".join([
        "        Name: alpha/one.txt",
        "         Art: Datei",
        "       CRC32: AABBCCDD",
        "        Name: alpha/sub",
        "         Art: Verzeichnis",
        "        Name: alpha/TWO.txt",
        "         Art: Datei",
        "       CRC32: 11223344",
    ])

    def test_it_reads_name_and_crc_pairs_and_skips_a_directory(self):
        """A directory has a Name and no CRC32, so a pair is only taken when the CRC arrives before
        the next name -- otherwise a directory would inherit the next file's checksum."""
        got = TOOL.crc32_from_listing(self.LISTING)
        self.assertEqual(got, {"alpha/one.txt": "AABBCCDD", "alpha/TWO.txt": "11223344"})

    def test_a_backslash_becomes_a_forward_slash(self):
        r"""RAR lists `archive\path`; the .sfv and the index use forward slashes."""
        line = "        Name: a" + chr(92) + "b.txt\n       CRC32: DEADBEEF"
        self.assertEqual(TOOL.crc32_from_listing(line), {"a/b.txt": "DEADBEEF"})

    def test_A_CASE_DIFFERENCE_IS_A_MISSING_FILE_AND_MUST_FAIL(self):
        """And an earlier version of this check folded case, which would have HIDDEN the defect.

        Folding looked reasonable: NTFS is case-insensitive, RAR stores the name the filesystem
        reports, so a .sfv entry `SPAM.wiki` matching an archive entry `Spam.wiki` read like a
        bookkeeping difference. It is not. Measured: the directory carries the per-directory
        case-sensitivity flag, SPAM.wiki is 26 bytes, Spam.wiki is 30, both exist, and the archive
        holds only one. Folding would have reported OK over 4 542 missing files.
        """
        want = {"alpha/two.txt": "11223344"}
        complaint = TOOL.crc32_complaint(_OneArchive(), "no-such-root", self.LISTING, 1, want=want)
        self.assertIsNotNone(complaint)
        self.assertIn("does not hold", complaint)

    def test_a_clean_unit_says_nothing(self):
        want = {"alpha/one.txt": "AABBCCDD", "alpha/TWO.txt": "11223344"}
        self.assertIsNone(
            TOOL.crc32_complaint(_OneArchive(), "no-such-root", self.LISTING, 2, want=want))

    def test_a_differing_crc_is_named_with_the_file(self):
        want = {"alpha/one.txt": "FFFFFFFF"}
        complaint = TOOL.crc32_complaint(_OneArchive(), "no-such-root", self.LISTING, 1, want=want)
        self.assertIn("alpha/one.txt", complaint)
        self.assertIn("differs", complaint)

    def test_our_own_records_are_counted_and_not_faulted(self):
        """The 366 manifests and markers packed with a unit appear in no .sfv. They are counted in
        the note and are not a reason to stop."""
        want = {"alpha/one.txt": "AABBCCDD", "alpha/TWO.txt": "11223344"}
        listing = self.LISTING + "\n        Name: alpha/.sha256sum\n       CRC32: 99887766"
        self.assertIsNone(
            TOOL.crc32_complaint(_OneArchive(), "no-such-root", listing, 2, want=want))

    def test_EVERY_VOLUME_IS_LISTED_BECAUSE_ONE_IS_NOT_THE_SET(self):
        """`rar lt <first volume>` lists only the files whose headers sit in THAT volume.

        Measured on misc: part001 answered 67 315 files, part234 answered 127, part468 answered 10,
        against the 342 489 the set holds. A check built on the first volume alone would have
        compared 20 % of the archive and reported success.
        """
        src = io.open(os.path.join(HERE_DIR, "b2-pack.py"), encoding="utf-8").read()
        block = src[src.index("def listing_text("):src.index("def crc32_from_listing(")]
        self.assertIn("glob.glob(", block)
        self.assertIn(".part*.rar", block)

    def test_AND_THE_LISTING_IS_READ_AS_UTF8(self):
        """-scfr, or 350 files of misc do not match.

        RAR writes a pipe in the system codepage by default, so a name carrying a character cp1252
        cannot hold came back mangled and the comparison called the file missing. Same trap as
        -scfl on the @list side, measured 2026-09-26 -- `f` is UTF-8 and `u` is UTF-16 -- but on
        the reading side, where a wrong charset reads as an archive with holes in it.
        """
        src = io.open(os.path.join(HERE_DIR, "b2-pack.py"), encoding="utf-8").read()
        block = src[src.index("def listing_text("):src.index("def crc32_from_listing(")]
        self.assertIn("-scfr", block)
        self.assertIn("utf-8", block)

    def test_it_runs_after_rar_t_and_stops_the_run_on_a_mismatch(self):
        src = io.open(os.path.join(HERE_DIR, "b2-pack.py"), encoding="utf-8").read()
        block = src[src.index("checked = subprocess.run(test"):src.index("def main(")]
        self.assertIn("crc32_complaint(", block)
        self.assertIn("THE CRC32 CROSS-CHECK FAILED", block)
        self.assertLess(block.index("crc32_complaint("), block.index("return 2"))


class TheArchiveCarriesItsOwnFixityRecords(unittest.TestCase):
    r"""Without this a restored unit could be checked against SHA-256 and nothing else.

    `.sha256sum`, `.sha1sum`, `.md5sum` and `.sfv` are dotfiles in common.BOOKKEEPING_FILES, and
    mirror.py keeps them OUT of `.mirror-index.csv` deliberately: the index describes the CONTENT,
    and counting our own notes as content would make every marker wrong. The rule is right for the
    collection and wrong at the moment of packing.

    MEASURED ON 2026-10-05, after the owner asked whether the checksum files end up in the RAR:
    838 such files exist across the collection and 18 of them are in any index, so 820 were being
    left behind -- every .sha256sum, .sha1sum, .md5sum, .sfv and .mirror-index.csv in all 113
    archives, and 100 PROVENANCE.md. The unit index that IS packed carries one digest per file,
    so SHA-1, MD5 and CRC32 would not have survived the move to cold storage at all. For misc it
    is 366 files against 144.19 GB: 0.13 %.
    """

    def test_a_units_own_records_are_collected(self):
        unit = [u for u in TOOL.UNITS if u.name == "misc"][0]
        if not os.path.isdir(TOOL.MIRROR_ROOT):
            self.skipTest("the collection is not mounted here")
        rows = TOOL.rows_for(unit, TOOL.MIRROR_ROOT, {})
        got = TOOL.bookkeeping_for(unit, TOOL.MIRROR_ROOT, rows)
        # THE NAMES COME FROM THE LIBRARY, not from this file. common_test.py refuses a tool that
        # spells a bookkeeping name by hand, and it caught this case doing exactly that -- the
        # guard exists because a hand-spelled name drifts away from the set the tools act on.
        wanted = sorted(common.MANIFEST_FILES.values()) + [common.INDEX_FILE]
        self.assertEqual(len(wanted), len(common.DIGESTS) + 1)
        for name in wanted:
            self.assertTrue([q for q in got if q.endswith("/" + name)], name)

    def test_what_the_index_ALREADY_holds_is_not_added_twice(self):
        """Some notes do appear in an index -- RENAMED.txt in all seven archives that have one,
        FRAGMENT-COPIES-REMOVED.txt in four -- because the WIDE set is skipped by auditors but
        still counted by markers. So the test is per file, not per name."""
        rows = [{"archive": "a", "path": "RENAMED.txt"}]

        class OneArchive(object):
            def archives(self):
                return ["a"]

        got = TOOL.bookkeeping_for(OneArchive(), "no-such-root", rows)
        self.assertEqual(got, [])

    def test_they_go_into_the_LIST_and_not_into_the_unit_index(self):
        """The index's columns are archive, path, size and sha256, and these files have no sha256
        recorded anywhere. A row with an empty digest is one no auditor could act on."""
        src = io.open(os.path.join(HERE_DIR, "b2-pack.py"), encoding="utf-8").read()
        write_list = src[src.index("def write_list("):src.index("def report(")]
        self.assertIn('for path in step["bookkeeping"]:', write_list)
        after = write_list[write_list.index('fh.write("archive,path,size,sha256'):]
        self.assertNotIn("bookkeeping", after)

    def test_the_count_is_reported_so_a_reader_sees_it_happened(self):
        src = io.open(os.path.join(HERE_DIR, "b2-pack.py"), encoding="utf-8").read()
        self.assertIn("own record(s)", src)


class EveryDecisionOfTheOwnerIsInTheCommand(unittest.TestCase):
    r"""The settlement of 2026-10-04 and 2026-10-05, as one assertion over the emitted switches.

    EACH OF THESE WAS DECIDED SEPARATELY, several of them against something I had argued for, and
    a table of them is easier to re-read in a year than ten comments scattered through the module.
    If one is ever changed, this is where it says so.
    """

    def test_the_whole_command_for_a_large_unit(self):
        self.assertEqual(
            TOOL.DEFAULTS.switches(3400),
            ["-ma5",            # the ONLY format RAR 7.23 writes; -ma4 and -ma7 are unknown to it
             "-m5",             # maximum, because this is written once and read for decades
             "-md4g",           # as far as a dictionary goes without demanding WinRAR 7 to read
             "-s",              # solid, which already resets per volume -- -sv would be a no-op
             "-oi1",            # byte-identical files stored once, then as references
             "-v3557000000b",   # 7 per 25 GB M-Disc at 99.50 % of raw; fits FAT32 and a 4 GB stick
             "-rr1",            # ~35 MB per volume, for bit rot and bad sectors in place
             "-rv68",           # 2 % of 3 400 volumes, floor 2
             "-k",              # lock, which is what keeps the .rev files valid
             "-scfl"])          # UTF-8 for the @list file; -scul stored NOTHING when measured

    def test_and_nothing_encrypts(self):
        """Public material: a password would protect nothing and could only be lost."""
        self.assertNotIn("-hp", " ".join(TOOL.DEFAULTS.switches(3400)))
        self.assertFalse(TOOL.DEFAULTS.encrypt_headers)

    def test_THE_DETACHED_LAUNCH_IS_WRITTEN_DOWN(self):
        """A unit takes hours and a packer started from a session dies with it.

        The recipe belongs with the tool rather than in a chat log, because the next person to run
        one will read the module docstring and nothing else. Three things that bit on the first
        real run are recorded beside it: RAR does not create the destination directory, a killed
        run leaves a partial first volume that must go before restarting, and the measured memory
        at -md6g -m5 is 12.9 GB -- a figure rar.txt does not give, since it anchors only 1 GB and
        64 GB.
        """
        doc = TOOL.__doc__
        self.assertIn("Start-Process", doc)
        self.assertIn("-RedirectStandardOutput", doc)
        self.assertIn("12.9 GB", doc)
        self.assertIn("nicht erstellen", doc)

    def test_THE_LOGS_GO_WHERE_THE_WRITING_IS_ALLOWED(self):
        """One drive is read, the other is written, and the log must not blur that.

        The owner, 2026-10-05: "damit auf dem einen datenträger nur gelesen wird auf dem anderen
        geschrieben". It is what makes "the collection is read-only" checkable with a disk counter
        instead of being a promise -- and it was worth checking: the owner saw writes in Task
        Manager during the first run, and they turned out to be Windows' write-behind cache
        flushing earlier writes to the OUTPUT drive, with no file under the collection changed.

        The recipe therefore redirects both streams into --out and not into --work, even though
        --work is the scratch directory, because --work may sit anywhere while --out is by
        definition the side that receives.
        """
        doc = TOOL.__doc__
        self.assertIn("<--out>" + chr(92) + "misc-run.log", doc)
        self.assertIn("<--out>" + chr(92) + "misc-run.err", doc)
        self.assertNotIn("mirrorPackedWork" + chr(92) + "misc-run", doc)

    def test_THE_TWO_LEVELS_OF_CHECKING_ARE_WRITTEN_DOWN(self):
        """Because in twenty years the module docstring is the whole manual.

        Measured against misc on 2026-10-05: `rar l` and `rar lt` need no dictionary and no
        decompression, and `lt` yields the CRC32 of every file out of the archive headers plus the
        parameters it was packed with. `rar t` decompresses every byte, took 7 minutes and 3.8 GB,
        and REFUSES without -mdx6g.

        THE CHEAP LEVEL IS WHY THE MANIFESTS HAD TO GO IN. `lt`'s CRC32 can be held against the
        .sfv packed inside the unit -- a list we built independently from the files themselves --
        and that comparison reads no compressed data at all. Without the manifests there would be
        nothing for those CRCs to be checked against.
        """
        doc = TOOL.__doc__
        self.assertIn("rar lt", doc)
        self.assertIn("CRC32", doc)
        self.assertIn("rar t -mdx6g", doc)
        self.assertIn("rar rc", doc)
        self.assertIn("A SINGLE VOLUME CANNOT BE TESTED ON ITS OWN", doc)


class TheVolumeSizeFitsTheMedium(unittest.TestCase):

    def test_a_volume_fits_both_media(self):
        """The owner's validated size: it must fit a BD-RE as well as an M-Disc BD-R 25 GB."""
        self.assertLess(TOOL.VOLUME_BYTES, TOOL.BD_RE_BYTES)
        self.assertLess(TOOL.VOLUME_BYTES, TOOL.M_DISC_BD_R_BYTES)
        self.assertGreater(TOOL.BD_RE_BYTES - TOOL.VOLUME_BYTES, 10000000)

    def test_A_WHOLE_NUMBER_OF_VOLUMES_FILLS_EVERY_M_DISC_SIZE(self):
        """25 on a 25 GB disc, 50 on a 50 GB, 100 on a 100 GB -- inside the owner's 99.5 % margin.

        THIS IS WHY THE SIZE IS 995 000 000 AND NOT 1 000 000 000. A round gigabyte fits only 24
        volumes on a 25 GB disc and leaves 4 % of every disc empty; five million bytes less per
        volume buys back one disc in twenty-five. A disc written to its last byte is a disc that
        may not verify, which is what the 99.5 % figures are for -- they are the owner's, measured
        against real media, and this case holds the volume size against them rather than against
        raw capacity.
        """
        for gb, limit in sorted(TOOL.M_DISC_995.items()):
            fit = limit // TOOL.VOLUME_BYTES
            self.assertLessEqual(fit * TOOL.VOLUME_BYTES, limit)
            # At least 99 % of the owner's own margin is used, so the compatibility is real
            # rather than nominal: 7 volumes fill a 25 GB disc to 99.99 % of that margin.
            self.assertGreater(fit * TOOL.VOLUME_BYTES / limit, 0.99,
                              "%d GB disc holds %d volumes" % (gb, fit))

    def test_AND_NEVER_PAST_THE_OWNERS_CEILING_ON_THE_RAW_CAPACITY(self):
        r"""NO DISC IS FILLED PAST 99.7 % OF ITS RAW SIZE, which is a different question from the
        one above and the one the owner asked on 2026-10-06: "Wir duerfen die m disc aber nie zu
        100% fuellen ... 99,7 sollten wir hoechstens haben".

        The margin table is a percentage OF THE RAW CAPACITY, so filling it to 100 % puts the disc
        at 99.5 % -- fine. The failure this guards is a later volume size that tiles the margin
        neatly while pushing the disc itself to the edge. UDF also needs room for its own
        descriptors on top of the payload, and a disc written to its last byte is one that may not
        verify.

        Measured at 3 557 000 000: 7 / 14 / 28 volumes, every one of the three at 99.50 % of raw,
        leaving 120.5 / 240.9 / 482.9 MiB for UDF -- one to two MB is what seven large files need.
        """
        raw = {25: TOOL.M_DISC_BD_R_BYTES, 50: 50050629632, 100: 100102307840}
        for gb, capacity in sorted(raw.items()):
            fit = int(capacity * TOOL.M_DISC_MAX_FILL) // TOOL.VOLUME_BYTES
            used = fit * TOOL.VOLUME_BYTES
            self.assertLessEqual(used / float(capacity), TOOL.M_DISC_MAX_FILL,
                                 "%d GB disc: %d volumes fill %.2f %% of raw"
                                 % (gb, fit, 100.0 * used / capacity))
            # and the compatibility has to be worth having: at least six volumes per disc, or the
            # volume has grown so large that the disc is no longer a sensible unit.
            self.assertGreaterEqual(fit, 6, "%d GB disc holds only %d volume(s)" % (gb, fit))

    def test_A_BD_RE_IS_NOT_A_BD_R_AND_THE_TWO_FIGURES_STAY_APART(self):
        r"""A rewritable disc reserves a spare area for defect management and holds 768 MiB less.

        An ImgBurn user expected 25 025 314 816 B on a 25 GB disc and could write only
        24 220 008 448 -- which is the BD-RE figure, and is why both constants exist here. M-Disc
        is write-once BD-R and has no such reservation, so the burn margins are taken against the
        larger number. Using the BD-RE figure for M-Disc would waste 768 MiB on every disc; using
        the BD-R figure for a BD-RE would overfill it.
        """
        self.assertLess(TOOL.BD_RE_BYTES, TOOL.M_DISC_BD_R_BYTES)
        self.assertEqual(TOOL.M_DISC_BD_R_BYTES - TOOL.BD_RE_BYTES, 805306368)   # 768 MiB
        for _gb, margin in TOOL.M_DISC_995.items():
            self.assertLessEqual(margin, TOOL.M_DISC_BD_R_BYTES * 100)

    def test_A_VOLUME_FITS_FAT32_AND_A_FOUR_GB_STICK(self):
        r"""THE CEILING THAT BINDS THE SIZE DOWNWARDS, and the reason it is not 4 149 914 282.

        FAT32 cannot hold a file of 4 GiB or more: the directory entry stores the length in four
        bytes, so the maximum is 2^32 - 1 = 4 294 967 295. A nominal "4 GB" stick holds about
        4e9 bytes before any filesystem, so a volume has to stay under that too -- which rules out
        both 4 000 000 000 and the 4 149 914 282 that would have tiled a 25 GB disc exactly.

        A .rev FILE IS SLIGHTLY LARGER THAN THE VOLUME IT PROTECTS and grows with the number of
        volumes it covers, so the headroom is checked against the volume size with room to spare
        rather than against the limit exactly.
        """
        self.assertLess(TOOL.VOLUME_BYTES, TOOL.FAT32_MAX_BYTES)
        self.assertLess(TOOL.VOLUME_BYTES, 4 * 1000 ** 3,
                        "a volume must fit a nominal 4 GB device")
        headroom = TOOL.FAT32_MAX_BYTES - TOOL.VOLUME_BYTES
        self.assertGreater(headroom, 100 * 1024 * 1024,
                           "only %d B of FAT32 headroom for .rev overhead" % headroom)

    def test_THE_DICTIONARY_CLEARS_EVERY_DUPLICATE_IN_THE_COLLECTION(self):
        """4 GB against a largest measured duplicate of 2 000.5 MB -- and 4 and not 6.

        Measured 2026-10-06 at 5 GiB of input, which is the only size that proves anything because
        RAR clamps the dictionary down to the total input: `rar t` on a -md6g archive REFUSES
        without -mdx (exit 3), on -md4g it answers OK. The archive is RAR 5.0 either way; above
        4 GB it carries a minimum-version requirement that the command line turns into a refusal.

        4 GB ALSO MATCHES THE SOLID BLOCK NOW. The block is one volume, 3.56 GB, so anything above
        4 GB could never be filled -- the old 6g was unreachable twice over.

        A solid block collapses two byte-identical files only if the window still reaches back to
        the first one, and `sort_key` puts them adjacent -- so the dictionary has to be at least as
        large as the duplicate. Measured per unit on 2026-10-04: vendors 2 000.5 MB, ibm-aix
        1 997.5, ibm-aix-support 1 346.4, ibm-pc 669.5, oldskool 611.1, bitsavers-software 525.4,
        workstations 420.9, misc 152.0.

        WHICH IS ALSO WHY -oi IS NOT USED. rar.txt: where the identical files fit the dictionary,
        plain -s "kann eine anpassungsfähigere Lösung als -oi sein" -- and -oi would make a volume
        holding a reference depend on the volume holding the original, which rar.txt warns about
        for exactly our shape, "wenn die Volumen eines gesplitteten Archivs auf mehreren
        unterschiedlichen Wechselmedien gespeichert sind".
        """
        self.assertEqual(TOOL.DEFAULTS.dictionary, "4g")
        largest_duplicate_mb = 2000.5
        self.assertGreater(6 * 1024, largest_duplicate_mb)

    def test_EVERY_UNIT_IS_PACKED_THE_SAME_WAY(self):
        """The owner, 2026-10-05: "Ich will es einheitlich für alle archive".

        Two units were -m0, stored rather than compressed, because their content is already
        compressed. -m0 also switches off the solid block, so identical files are stored twice in
        full -- and measured per unit, ibm-aix-opensource is 208.0 GB holding 116.9 GB of byte-identical
        files, 56.2 %. Storing it was costing 117 GB. I had argued for -m0 there the same
        afternoon on the grounds that it "appears in none of b2-cluster.py's sharing pairs", which
        is true and was the wrong measurement: those pairs count duplication BETWEEN archives, and
        this is a package repository duplicating itself.
        """
        sets = set()
        for unit in TOOL.UNITS:
            sets.add(tuple(s for s in unit.options.switches(volumes=700) if not s.startswith("-rv")))
        self.assertEqual(len(sets), 1, sets)
        self.assertFalse([u.name for u in TOOL.UNITS if u.options.method == 0])

    def test_it_is_expressed_in_bytes_and_not_in_an_ambiguous_suffix(self):
        """`-v23000m` means different things depending on case and version. Bytes do not."""
        volume = [s for s in TOOL.DEFAULTS.switches(30) if s.startswith("-v")][0]
        self.assertTrue(volume.endswith("b"), volume)
        self.assertEqual(int(volume[2:-1]), TOOL.VOLUME_BYTES)


class ThePlanIsReadOnlyAndSecretFree(unittest.TestCase):

    def setUp(self):
        self.root = fixture()
        self.out = tempfile.mkdtemp(prefix="b2-pack-out-")
        self.work = tempfile.mkdtemp(prefix="b2-pack-work-")   # only plan(); main() refuses deep paths
        self.steps = TOOL.plan(test_units(), self.root, self.out, self.work)

    def test_NO_STEP_CARRIES_A_PASSWORD(self):
        for step in self.steps:
            for arg in step["argv"]:
                self.assertFalse(arg.startswith("-hp"), step["argv"])
                self.assertFalse(arg.startswith("-p"), step["argv"])

    def test_nothing_is_written_anywhere_while_planning(self):
        self.assertEqual(os.listdir(self.work), [])
        self.assertEqual(os.listdir(self.out), [])

    def test_no_list_or_index_file_is_placed_inside_the_collection(self):
        """The collection is read-only by rule; a list file dropped into it would be a write."""
        for step in self.steps:
            for key in ("list_path", "index_path", "archive"):
                if step[key]:
                    self.assertFalse(os.path.abspath(step[key]).startswith(
                        os.path.abspath(self.root) + os.sep), step[key])

    def test_rar_runs_with_the_collection_as_its_working_directory(self):
        """So the stored paths are `archive/...` and carry no drive letter or home directory."""
        for step in self.steps[:-1]:
            self.assertEqual(step["cwd"], self.root)


class TheCommands(unittest.TestCase):
    """What would actually be issued, asserted argument by argument."""

    def setUp(self):
        self.root = fixture()
        self.steps = TOOL.plan(test_units(), self.root, "OUT", "WORK", rar="RAR")

    def test_a_unit_command_in_full(self):
        step = self.steps[0]
        self.assertEqual(step["argv"], [
            "RAR", "a", "-ma5", "-m5", "-md4g", "-s", "-oi1",
            "-v%db" % TOOL.VOLUME_BYTES, "-rr1", "-rv2", "-k", "-scfl",
            os.path.join("OUT", "pair", "pair.rar"),
            "@" + os.path.join("WORK", "pair.list"),
            os.path.join("WORK", "pair" + TOOL.INDEX_SUFFIX),
        ])

    def test_THE_UNIT_INDEX_IS_PACKED_INTO_THE_UNIT(self):
        """Redundant with RAR's own directory, and wanted: the archive is then self-describing."""
        for step in self.steps[:-1]:
            self.assertIn(step["index_path"], step["argv"])

    def test_the_last_step_is_the_index_archive_and_packs_only_indexes(self):
        last = self.steps[-1]
        self.assertIsNone(last["unit"])
        self.assertIn("*" + TOOL.INDEX_SUFFIX, last["argv"])
        self.assertEqual(last["cwd"], os.path.join("OUT", TOOL.INDEX_DIR))
        self.assertIn("-ep", last["argv"])

    def test_there_is_one_step_per_unit_plus_the_index(self):
        self.assertEqual(len(self.steps), len(test_units()) + 1)

    def test_the_command_is_stable_across_two_plans(self):
        """Two runs must produce byte-identical commands, or a rebuild cannot be compared."""
        again = TOOL.plan(test_units(), self.root, "OUT", "WORK", rar="RAR")
        self.assertEqual([s["argv"] for s in self.steps], [s["argv"] for s in again])


class ThePackingOrderCollapsesDuplicates(unittest.TestCase):

    def setUp(self):
        self.root = fixture()

    def test_identical_files_end_up_adjacent(self):
        """The whole reason 111 GB of Bull duplicates cost almost nothing."""
        unit = test_units()[0]
        rows = TOOL.rows_for(unit, self.root)
        at = [i for i, r in enumerate(rows) if r["digest"] == DIGEST_DUP]
        self.assertEqual(len(at), 2)
        self.assertEqual(at[1] - at[0], 1, [r["path"] for r in rows])

    def test_the_order_groups_by_extension_first(self):
        rows = TOOL.rows_for(test_units()[0], self.root)
        exts = [r["path"].rsplit(".", 1)[-1] if "." in r["path"] else "" for r in rows]
        self.assertEqual(exts, sorted(exts))

    def test_a_file_without_an_extension_sorts_first_and_does_not_crash(self):
        rows = TOOL.rows_for(test_units()[0], self.root)
        self.assertEqual(rows[0]["path"], "noext")

    def test_the_list_holds_paths_relative_to_the_collection(self):
        """Absolute paths would put the machine's directory layout into the archive.

        They would also break `privacy-test.py`'s rule if such a path were ever written down.
        """
        rows = TOOL.rows_for(test_units()[0], self.root)
        for row in rows:
            line = "%s/%s" % (row["archive"], row["path"])
            self.assertFalse(os.path.isabs(line), line)
            self.assertNotIn(":", line, line)


class DirectoriesThatHoldNothing(unittest.TestCase):
    r"""The one thing `.mirror-index.csv` cannot report, and the partition test cannot see.

    The index lists FILES. A directory holding neither a file nor a subdirectory appears in no
    index, so a file list built only from indexes drops it silently -- 281 of them across the real
    collection, in 9 archives. RAR stores a directory named in a list file as a folder entry, which
    was measured, so appending the paths is the whole fix.

    Found while reading WinRAR 7.30's changelog. Nothing in that changelog applies to this plan;
    the question its `-ed1` switch raised does.
    """

    def setUp(self):
        self.root = fixture()
        self.work = tempfile.mkdtemp(prefix="b2-pack-work-")
        self.steps = TOOL.plan(test_units(), self.root, "OUT", self.work)
        self.by_name = dict((s["unit"].name, s) for s in self.steps if s["unit"])

    def test_they_are_found_at_all(self):
        found = sorted(sum((s["empty_dirs"] for s in self.steps), []))
        self.assertIn("split/pdf/hollow", found)
        self.assertIn("split/other/hollow", found)

    def test_each_goes_to_the_unit_that_claims_its_path(self):
        self.assertEqual(self.by_name["split-pdf"]["empty_dirs"], ["split/pdf/hollow"])
        self.assertIn("split/other/hollow", self.by_name["split-rest"]["empty_dirs"])
        self.assertNotIn("split/pdf/hollow", self.by_name["split-rest"]["empty_dirs"])

    def test_only_the_leaf_is_listed_and_not_its_parents(self):
        """RAR creates missing parents on extraction, so `deep/a` would be a redundant entry."""
        rest = self.by_name["split-rest"]["empty_dirs"]
        self.assertIn("split/deep/a/b", rest)
        self.assertNotIn("split/deep", rest)
        self.assertNotIn("split/deep/a", rest)

    def test_they_are_written_after_the_files_so_the_solid_order_is_untouched(self):
        step = self.by_name["split-pdf"]
        TOOL.write_list(step, dry_run=False)
        with io.open(step["list_path"], encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        # CONTENT, THEN OUR OWN RECORDS, THEN THE EMPTY DIRECTORIES. The fixture writes a real
        # .mirror-index.csv for each archive, so the middle group is not empty here -- which makes
        # this case an end-to-end check that bookkeeping_for() reaches write_list at all.
        self.assertEqual(lines[-1], "split/pdf/hollow")
        content = ["%s/%s" % (r["archive"], r["path"]) for r in step["rows"]]
        self.assertEqual(lines[:len(content)], content)
        self.assertEqual(lines[len(content):-1], step["bookkeeping"])
        self.assertIn("split/.mirror-index.csv", step["bookkeeping"])

    def test_skipping_the_walk_is_possible_and_says_so(self):
        """`--no-empty-dirs` exists for a quick look at the commands, and it DROPS them."""
        quick = TOOL.plan(test_units(), self.root, "OUT", self.work, with_dirs=False)
        self.assertEqual(sum((s["empty_dirs"] for s in quick), []), [])


class TheFilesItWritesWhenAsked(unittest.TestCase):
    """`write_list` is the only thing here that writes, and only outside the collection."""

    def setUp(self):
        self.root = fixture()
        self.work = tempfile.mkdtemp(prefix="b2-pack-work-")   # only plan(); main() refuses deep paths
        self.step = TOOL.plan(test_units(), self.root, "OUT", self.work)[0]

    def test_the_dry_run_writes_nothing(self):
        TOOL.write_list(self.step, dry_run=True)
        self.assertEqual(os.listdir(self.work), [])

    def test_the_list_is_one_path_per_line_in_packing_order(self):
        TOOL.write_list(self.step, dry_run=False)
        with io.open(self.step["list_path"], encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        content = ["%s/%s" % (r["archive"], r["path"]) for r in self.step["rows"]]
        self.assertEqual(lines, content + self.step["bookkeeping"])

    def test_the_index_carries_the_digest_and_is_sorted_for_a_human(self):
        """Packing order is for the compressor; the index is for somebody looking something up."""
        TOOL.write_list(self.step, dry_run=False)
        with io.open(self.step["index_path"], encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        self.assertEqual(lines[0], "archive,path,size,sha256")
        body = [line.split(",") for line in lines[1:]]
        self.assertEqual(body, sorted(body, key=lambda r: (r[0], r[1])))
        self.assertTrue(all(len(r[3]) == 64 for r in body), body)

    def test_the_index_names_every_file_of_the_unit(self):
        TOOL.write_list(self.step, dry_run=False)
        with io.open(self.step["index_path"], encoding="utf-8") as fh:
            lines = fh.read().splitlines()[1:]
        self.assertEqual(len(lines), len(self.step["rows"]))


class WhatItRefuses(unittest.TestCase):

    def setUp(self):
        self.root = fixture(also=REAL_ARCHIVES)

    def run_tool(self, *argv):
        out = io.StringIO()
        keep = sys.stdout
        sys.stdout = out
        try:
            code = TOOL.main(list(argv))
        finally:
            sys.stdout = keep
        return code, out.getvalue()

    def test_a_collection_that_is_not_there(self):
        code, _text = self.run_tool("--root", os.path.join(self.root, "nope"), "--work", FLAT_WORK)
        self.assertEqual(code, 2)

    def test_an_unknown_unit_name(self):
        code, text = self.run_tool("--root", self.root, "--work", FLAT_WORK, "--only", "no-such-unit")
        self.assertEqual(code, 2)
        self.assertIn("no such unit", text)

    def test_EXECUTE_WITHOUT_A_PASSWORD_FILE_IS_NOW_ALLOWED(self):
        """Because no unit asks for one any more, and the demand reads the units.

        This test asserted the OPPOSITE until 2026-10-04 -- `--execute` without `--password-file`
        was refused, correctly, while every unit encrypted its headers. The owner's decision that
        public material needs no password turned that refusal into an obstacle, so it now depends
        on `encrypt_headers` instead of being unconditional.

        WHAT IS CHECKED HERE IS THAT THE RUN GETS PAST THE PASSWORD GATE, not that it succeeds.
        It still refuses, for one of two later reasons, AND WHICH ONE DEPENDS ON THE MACHINE: with
        rar installed the fixture's missing indexes are reported, without it the missing rar is.
        The first version of this case asserted "no index" and passed here and failed on CI, where
        no rar exists -- a test that reads the environment instead of the behaviour. So it asserts
        the gate it is about, and accepts either refusal after it.
        """
        code, text = self.run_tool("--root", self.root, "--work", FLAT_WORK, "--execute")
        self.assertNotIn("--password-file", text)
        self.assertTrue("no index" in text or "no rar executable" in text, text)
        self.assertEqual(code, 2)

    def test_the_default_run_says_that_nothing_happened(self):
        code, text = self.run_tool("--root", self.root, "--work", FLAT_WORK, "--only", REAL_UNIT)
        self.assertEqual(code, 0)
        self.assertIn("NOTHING WAS RUN", text)

    def test_A_DEEP_OR_PERSONAL_WORK_DIRECTORY_IS_REFUSED(self):
        """Its path is stored inside every archive, so a profile directory leaks the account name.

        Measured: a file passed by absolute path keeps every component below the drive letter.
        """
        for bad in (os.path.join(FLAT_WORK, "a", "b"),
                    os.path.join(os.path.splitdrive(FLAT_WORK)[0] + os.sep, "Users", "x", "w")):
            code, text = self.run_tool("--root", self.root, "--work", bad, "--only", REAL_UNIT)
            self.assertEqual(code, 2, bad)
            self.assertIn("REFUSING", text)

    def test_it_prints_what_it_measured_against_the_local_rar(self):
        _code, text = self.run_tool("--root", self.root, "--work", FLAT_WORK, "--only", REAL_UNIT)
        for fact in TOOL.MEASURED_ON_THIS_MACHINE:
            self.assertIn(fact, text)


class NoPasswordAndNothingToLose(unittest.TestCase):
    r"""Decided on 2026-09-26, with its reason -- and the reason changes what must be guarded.

    The material is public, fetched from public servers, and any sharing would go to a handful of
    people and cover the whole collection. Compartmenting buys nothing; nineteen secrets would be
    nineteen chances to lose one. So the encryption keeps the storage provider from reading and
    enumerating, and **a lost or wrong password is the only real risk left**.

    That risk is silent. A truncated password file does not fail: it packs 3.98 TB that opens with a
    key nobody has, and it surfaces years later. Hence a shape check before packing and `rar t`
    after every unit.
    """

    def test_a_short_password_is_refused_rather_than_used(self):
        self.assertIsNone(TOOL.check_password("A" * 64))
        self.assertIsNotNone(TOOL.check_password("hunter2"))
        self.assertIsNotNone(TOOL.check_password(""))

    def test_stray_whitespace_is_named_and_not_silently_removed(self):
        """A password read with a trailing space is a different password, and the archive would
        open with neither the intended one nor the obvious correction."""
        self.assertIsNotNone(TOOL.check_password("A" * 64 + " "))
        self.assertIsNotNone(TOOL.check_password(" " + "A" * 64))

    def test_THE_TEST_COMMAND_CARRIES_mdx_OR_IT_READS_NOTHING(self):
        """At 6 GB, `rar t` refuses from the command line unless told the dictionary is allowed.

            Ein 6 GB grosses Woerterbuch ueberschreitet die Obergrenze von 4 GB und benoetigt mehr
            als 6 GB Speicher zum Entpacken. Verwenden Sie die Schalter -md6g oder -mdx6g, um das
            Entpacken dennoch durchzufuehren.

        AND IT LOOKED LIKE SUCCESS ON THE FIRST REAL RUN. `rar t` tested the five .rev files, which
        carry no compressed stream, printed OK five times, then said "Keine Dateien zum Entpacken"
        and exited 2 -- so 98 GB of content was never read. A check that passes over the thing it
        was meant to check is worse than no check, which is why this case asserts the switch is
        built rather than asserting that some test passed.

        -mdx AND NOT -md, because rar.txt says -mdx applies only when unpacking: it cannot change
        what a later `rar a` writes, even by accident.
        """
        src = io.open(os.path.join(HERE_DIR, "b2-pack.py"), encoding="utf-8").read()
        block = src[src.index('test = ([rar, "t"]'):src.index('say("  testing')]
        self.assertIn('"-mdx" + unit_options.dictionary', block)
        self.assertNotIn('"-md" + unit_options.dictionary', block)

    def test_AND_THE_FIRST_VOLUME_IS_FOUND_NOT_SPELLED(self):
        """RAR uses as many digits as the volume count needs, and this guessed two.

        The first real run packed misc into 468 volumes, so RAR wrote `misc.part001.rar`; `rar t`
        was pointed at `misc.part01.rar`, could not open it, and the tool announced THE ARCHIVE
        DOES NOT TEST CLEAN for a set that was intact. An alarm about the wrong thing is worse
        than no alarm, because the next one is believed less.
        """
        src = io.open(os.path.join(HERE_DIR, "b2-pack.py"), encoding="utf-8").read()
        block = src[src.index("def first_volume("):src.index("def check_password(")]
        self.assertIn("glob.glob(", block)
        self.assertNotIn('".part01.rar"', block)

    def test_the_first_volume_is_what_gets_tested(self):
        """THREE DIGITS, not two: every unit in the plan needs them. The smallest, misc, came out
        at 468 volumes, and nothing here is small enough for RAR to choose fewer. This is the
        fallback for a set that is not on disk yet -- `plan()` prints the name before packing."""
        self.assertEqual(TOOL.first_volume(os.path.join("OUT", "vendors", "vendors.rar")),
                         os.path.join("OUT", "vendors", "vendors.part001.rar"))

    def test_the_secret_is_masked_wherever_a_command_is_printed(self):
        shown = TOOL.hide_password(["rar", "a", "-hp" + "S" * 64, "x.rar"])
        self.assertEqual(shown, ["rar", "a", "-hp***", "x.rar"])
        self.assertNotIn("S" * 64, " ".join(shown))

    def test_NO_UNIT_ENCRYPTS_AND_THAT_IS_THE_DECISION(self):
        """The owner, 2026-10-04: "da es oeffentliche Daten sind brauche ich kein Passwort /
        Verschluesselung, lediglich ECC und recovery archive".

        Every archive here was fetched from a public host, so a password protects nothing and adds
        the one way this collection could become unreadable -- a lost key, twenty years from now,
        for 4 TB that is already on the open web. The earlier plan encrypted all nineteen units
        under one password and this test asserted the opposite of what it asserts now.
        """
        for unit in TOOL.UNITS:
            self.assertFalse(unit.options.encrypt_headers, unit.name)
        self.assertFalse(TOOL.INDEX_OPTIONS.encrypt_headers)

    def test_but_the_machinery_is_still_there_and_still_driven_by_the_units(self):
        """Kept rather than deleted, because the next unit might differ. If one is ever marked
        encrypt_headers=True, --execute must demand a password file again -- so the demand reads
        the units instead of being hard-coded off."""
        with io.open(os.path.join(HERE_DIR, "b2-pack.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("any(u.options.encrypt_headers for u in UNITS)", src)
        self.assertIn('argv.insert(2, "-hp" + password)', src)


class WhenTheCollectionIsHere(unittest.TestCase):
    """The partition, re-taken against the real thing -- skipped where it is not mounted."""

    def setUp(self):
        if not os.path.isdir(TOOL.MIRROR_ROOT):
            self.skipTest("the collection is not mounted here")

    def test_every_file_in_the_collection_is_claimed_exactly_once(self):
        orphans, doubles = TOOL.coverage(TOOL.UNITS, TOOL.MIRROR_ROOT)
        self.assertEqual(dict(orphans), {})
        self.assertEqual(dict(doubles), {})

    def test_every_named_archive_exists(self):
        """A renamed mirror would otherwise drop out of the plan without a word."""
        present = set(os.listdir(TOOL.MIRROR_ROOT))
        for unit in TOOL.UNITS:
            for archive in unit.archives():
                self.assertIn(archive, present, "%s names %s" % (unit.name, archive))


class TheCrossCheckUnderstandsOi1References(unittest.TestCase):
    r"""A -oi1 reference has no CRC32 of its own, and RAR writes zeros where one would be.

    MEASURED 2026-10-06: two identical 3 MiB files packed with -oi1 list as CB32BAFD and
    00000000; without -oi1 both list as CB32BAFD. The content is present either way -- `rar t`
    passes and extraction works -- but a reference's header carries nothing to compare.

    THE FIRST RUN WITH -oi1 REPORTED 8777 OF THESE IN misc, AND THAT NUMBER IS THE DEDUPLICATION.
    Reporting them as "CRC32 differs" would have taught a reader to ignore this check, which is
    the one thing it must never do: it is what found the 165 real mismatches in the first
    misc.rar, over which `rar t` had said "Alles OK" five times.

    A REFERENCE IS JUDGED THROUGH ITS TARGET, and only when a target exists. RAR wrote the
    reference because it found the content byte-identical to a file it did store, and our own
    manifests record the same digest for both -- so a zero-CRC entry whose .sfv CRC32 matches some
    really-stored entry is accounted for. One with no such partner is a genuine hole and stays a
    complaint.
    """

    def listing(self, rows):
        """rar lt output: a Name: line and a CRC32: line per entry."""
        out = []
        for name, crc in rows:
            out.append("Name: %s" % name.replace("/", "\\"))
            out.append("     CRC32: %s" % crc)
        return "\n".join(out)

    def check(self, listing, want):
        return TOOL.crc32_complaint(None, None, listing, len(want), want=dict(want))

    def test_a_reference_with_a_stored_partner_is_not_a_complaint(self):
        listing = self.listing([("a/one.bin", "CB32BAFD"), ("a/two.bin", "00000000")])
        want = {"a/one.bin": "CB32BAFD", "a/two.bin": "CB32BAFD"}
        self.assertIsNone(self.check(listing, want))

    def test_and_the_reference_count_is_reported_rather_than_hidden(self):
        listing = self.listing([("a/one.bin", "CB32BAFD"), ("a/two.bin", "00000000")])
        want = {"a/one.bin": "CB32BAFD", "a/two.bin": "CB32BAFD"}
        self.check(listing, want)
        self.assertEqual(getattr(TOOL.crc32_complaint, "references", 0), 1)

    def test_THE_CONTRACT_IS_STILL_A_COMPLAINT_OR_NONE(self):
        """An earlier draft returned "OK: n reference(s)" here, which the caller reads as failure
        and stops the run on."""
        listing = self.listing([("a/one.bin", "CB32BAFD"), ("a/two.bin", "00000000")])
        want = {"a/one.bin": "CB32BAFD", "a/two.bin": "CB32BAFD"}
        self.assertFalse(self.check(listing, want))

    def test_A_REFERENCE_WITH_NO_STORED_PARTNER_IS_STILL_A_COMPLAINT(self):
        r"""THE HOLE THIS MUST NOT SWALLOW. A zero CRC32 whose content was never stored anywhere
        is a file the archive does not really hold, and blanket-skipping zeros would pass it."""
        listing = self.listing([("a/one.bin", "CB32BAFD"), ("a/lonely.bin", "00000000")])
        want = {"a/one.bin": "CB32BAFD", "a/lonely.bin": "DEADBEEF"}
        got = self.check(listing, want)
        self.assertIsNotNone(got)
        self.assertIn("reference(s) with no stored file of the same CRC32", got)
        self.assertIn("a/lonely.bin", got)

    def test_a_real_mismatch_is_still_caught_alongside_references(self):
        """The 165 files of the first misc.rar are the reason this check exists at all."""
        listing = self.listing([("a/one.bin", "CB32BAFD"), ("a/two.bin", "00000000"),
                                ("a/wrong.bin", "11111111")])
        want = {"a/one.bin": "CB32BAFD", "a/two.bin": "CB32BAFD",
                "a/wrong.bin": "22222222"}
        got = self.check(listing, want)
        self.assertIsNotNone(got)
        self.assertIn("CRC32 differs", got)
        self.assertIn("a/wrong.bin", got)

    def test_a_missing_file_is_still_caught_alongside_references(self):
        listing = self.listing([("a/one.bin", "CB32BAFD"), ("a/two.bin", "00000000")])
        want = {"a/one.bin": "CB32BAFD", "a/two.bin": "CB32BAFD",
                "a/gone.bin": "33333333"}
        got = self.check(listing, want)
        self.assertIn("the archive does not hold", got)

    def test_AN_EMPTY_FILE_IS_NOT_A_REFERENCE_AND_NEEDS_NO_RESOLVING(self):
        r"""THE TRAP THE FIRST FIX WALKED INTO. CRC32 of zero bytes IS 00000000, so an empty file
        and a -oi1 reference look identical in the listing.

        Measured on the real misc archive: 921 of its files are 0 bytes. Our own .sfv records
        00000000 for them, RAR lists 00000000, THE TWO SIDES AGREE -- and the first version of
        this code pulled every zero out of the ordinary comparison and then reported those 921 as
        "references with no stored file of the same CRC32". A complaint manufactured from two
        sides that matched, which is the worst kind: it would have been read as damage.

        A zero in the listing is a reference only where our .sfv says something ELSE for that
        path. Where both read zero, the plain comparison is right.
        """
        listing = self.listing([("a/real.bin", "CB32BAFD"), ("a/empty.bin", "00000000")])
        want = {"a/real.bin": "CB32BAFD", "a/empty.bin": "00000000"}
        self.assertIsNone(self.check(listing, want))
        self.assertEqual(getattr(TOOL.crc32_complaint, "references", 0), 0)

    def test_an_empty_file_the_archive_got_WRONG_is_still_caught(self):
        """And the distinction must not become a way for an empty-vs-nonempty mismatch to pass:
        our .sfv says the file has content, the archive lists zero -- that is the reference case,
        and without a stored partner it is a complaint."""
        listing = self.listing([("a/real.bin", "CB32BAFD"), ("a/claimed.bin", "00000000")])
        want = {"a/real.bin": "CB32BAFD", "a/claimed.bin": "DEADBEEF"}
        got = self.check(listing, want)
        self.assertIsNotNone(got)
        self.assertIn("a/claimed.bin", got)

    def test_the_real_misc_archive_came_out_clean(self):
        r"""The numbers of the run that settled this, 2026-10-06, kept where they can be compared.

        342 336 entries listed, 341 969 expected from our .sfv, 367 of our own bookkeeping files,
        8 777 references judged through their targets, 921 empty files where both sides read zero,
        and zero differences. `rar t` said "Alles OK" over 27 volumes and both .rev files.

        8 777 IS ALSO THE FIRST REAL MEASUREMENT OF WHAT -oi1 BUYS: the unit went from 98.62 GB
        under the old switches to 93.88 GB, so those duplicates were 4.74 GB.
        """
        self.assertEqual(342336 - 341969, 367)
        self.assertEqual(TOOL.DEFAULTS.dedup_references, True)

    def test_a_listing_with_no_references_behaves_exactly_as_before(self):
        listing = self.listing([("a/one.bin", "CB32BAFD"), ("a/two.bin", "C37FB52A")])
        want = {"a/one.bin": "CB32BAFD", "a/two.bin": "C37FB52A"}
        self.assertIsNone(self.check(listing, want))
        self.assertEqual(getattr(TOOL.crc32_complaint, "references", 0), 0)


class TheOtherResourceAPackCanRunOutOf(unittest.TestCase):
    r"""Memory, which until 2026-10-06 nothing here looked at.

    WHAT HAPPENED. A workstations run was killed before it wrote a single volume: 0.52 GB free of
    63.34 GB, with an editor holding 39.59 GB. The run had not reached Rar.exe, so its own output
    said nothing at all -- the log was zero bytes -- and the cause had to be found by listing
    processes afterwards. The same shape six hours into the 638 GB vendors unit would have cost
    the six hours and left the same silence.

    The free DISK space has been in the plan since the beginning. This is the other one.
    """

    def test_free_memory_answers_a_plausible_number_here(self):
        got = TOOL.free_memory()
        if got is None:
            self.skipTest("this host does not answer")
        self.assertGreater(got, 1 << 20)                  # more than a megabyte
        self.assertLess(got, 1 << 50)                     # less than a petabyte

    def test_it_returns_None_rather_than_raising_where_it_cannot_ask(self):
        """A plan must still print when the figure is unavailable, so the failure is a None."""
        self.assertIn("or None where it cannot be asked", TOOL.free_memory.__doc__)

    def test_THE_ESTIMATE_IS_LABELLED_AS_ONE(self):
        r"""rar.txt gives two points -- about 7 GB for 1 GB and about 96 GB for 64 GB -- and calls
        both "grob geschaetzt". A straight line between two rough figures is not a measurement and
        the note says so, because the next reader will otherwise treat 12.07 GB as a requirement.
        """
        self.assertIn("rough", TOOL.memory_note("4g", free=50 * (1 << 30)))
        near = TOOL.memory_estimate("4g") / float(1 << 30)
        self.assertGreater(near, 10.0)
        self.assertLess(near, 14.0)

    def test_THE_ESTIMATE_IS_WITHIN_REACH_OF_THE_ONE_MEASUREMENT(self):
        r"""4g was measured at 10.00 GB during the workstations run of 2026-10-06, against an
        interpolation of 12.07. Slightly high rather than wrong, which is as much as a line
        between two figures the vendor calls rough can be asked for.

        The point of pinning it is the other direction: if a later change made the estimate read
        3 GB or 40 GB for 4g, the plan would be printing a number with no relation to what RAR
        actually takes, and a reader would size a machine by it.
        """
        got = TOOL.memory_estimate("4g") / float(1 << 30)
        self.assertGreater(got, 8.0)
        self.assertLess(got, 16.0)

    def test_AND_IT_RECORDS_WHEN_THE_MEMORY_IS_TAKEN(self):
        r"""0.19 GB while -oi1 pre-hashed 420 307 files, 10.00 GB once compression began. A run
        that looks harmless in its first minutes is not yet the run whose memory matters, and
        anyone watching the wrong minute concludes the dictionary costs nothing."""
        doc = TOOL.memory_estimate.__doc__
        self.assertIn("0.19 GB", doc)
        self.assertIn("10.00 GB", doc)
        flat = " ".join(doc.split())
        self.assertIn("allocated when the first block is compressed", flat)

    def test_the_estimate_follows_rar_txts_two_points(self):
        """1 GB -> about 7, 64 GB -> about 96, which is the line's definition."""
        self.assertAlmostEqual(TOOL.memory_estimate("1g") / float(1 << 30), 7.0, places=1)
        self.assertAlmostEqual(TOOL.memory_estimate("64g") / float(1 << 30), 96.0, places=1)

    def test_IT_REFUSES_ONLY_BELOW_A_FLOOR_NOTHING_CAN_ARGUE_WITH(self):
        r"""Less free memory than the dictionary itself. A 4 GB window cannot live in 3 GB.

        Not at the estimate: refusing a run on an interpolation between two figures the vendor
        calls rough would stop packs that would have worked.
        """
        self.assertIsNotNone(TOOL.memory_complaint("4g", free=3 * (1 << 30)))
        self.assertIsNone(TOOL.memory_complaint("4g", free=5 * (1 << 30)))

    def test_the_complaint_names_both_numbers(self):
        got = TOOL.memory_complaint("4g", free=2 * (1 << 30))
        self.assertIn("2.15 GB", got)
        self.assertIn("4g", got)

    def test_no_dictionary_means_no_opinion(self):
        """The index archive is packed with -m5 and no -md; there is nothing to refuse it for."""
        self.assertIsNone(TOOL.memory_complaint("", free=1 << 20))
        self.assertIsNone(TOOL.memory_complaint(None, free=1 << 20))

    def test_an_unanswerable_host_is_not_a_refusal(self):
        r"""THE FAILURE MODE TO AVOID: a tool that cannot read the figure must not therefore
        decline to pack. Refusing on a missing measurement is worse than packing without one."""
        self.assertIsNone(TOOL.memory_complaint("4g", free=None)
                          if TOOL.free_memory() is None else None)

    def source(self):
        with io.open(os.path.join(HERE_DIR, "b2-pack.py"), encoding="utf-8") as handle:
            return handle.read()

    def test_the_plan_prints_the_line_unconditionally(self):
        """Including on a dry run, which is where a reader looks before committing six hours."""
        text = self.source()
        self.assertIn("say(\"  %s\" % memory_note(", text)
        self.assertLess(text.index("memory_note(DEFAULTS.dictionary)"),
                        text.index("NOTHING WAS RUN"))

    def test_and_the_refusal_comes_before_rar_is_even_located(self):
        """So a short-memory run costs nothing, not even the search for Rar.exe."""
        text = self.source()
        self.assertLess(text.index("short = memory_complaint("), text.index("rar = find_rar()"))


class TheIndexGoesBesideTheVolumes(unittest.TestCase):
    r"""The owner's instruction on 2026-10-06: after every unit, put its index CSV next to it.

    WHY IT IS WORTH A COPY. The CSV is already INSIDE the archive -- it is the last argument of
    the pack command, so a unit describes itself -- but reading it there costs unpacking a 101 GB
    set. Beside the volumes it answers "what is in misc" for 52 MB, in a browser, without RAR,
    and it carries archive, path, size and sha256 for every file: 341 970 lines for misc.

    AND A COPY RATHER THAN A MOVE, because the work directory's copy is what the index archive is
    built from -- `rar a ... *.index.csv` over all ten units -- and taking it away would quietly
    produce an empty one.
    """

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="b2p-idx-")
        self.work = os.path.join(self.base, "work")
        # ONE FLAT DIRECTORY PER UNIT, which is the shape the owner built by hand on 2026-10-06
        # and uploads as it stands: <out>/<unit>/ holding the volumes, the .rev files, the index
        # CSV and the four manifests, all side by side.
        self.out = os.path.join(self.base, "out", "unit")
        os.makedirs(self.work)
        os.makedirs(self.out)
        self.source = os.path.join(self.work, "unit.index.csv")
        self.write(self.source, "archive,path,size,sha256\narch,a.bff,12,ab\n")
        self.step = {"index_path": self.source,
                     "archive": os.path.join(self.out, "unit.rar")}

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def write(self, path, text):
        with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)

    def read(self, path):
        with io.open(path, encoding="utf-8") as handle:
            return handle.read()

    def target(self):
        return os.path.join(self.out, "unit.index.csv")

    def source_text(self):
        with io.open(os.path.join(HERE_DIR, "b2-pack.py"), encoding="utf-8") as handle:
            return handle.read()

    def test_IT_LANDS_IN_THE_SAME_DIRECTORY_AS_THE_VOLUMES(self):
        r"""Flat, beside the .rar and .rev files. An earlier version put it one level up, on the
        assumption that the volumes had a directory of their own below the unit's -- they do not,
        and the owner flattened the three finished units by hand to prove the point. He uploads
        that directory as it stands, so anything not in it is not uploaded."""
        got = TOOL.place_index_beside(self.step, report=lambda *_a: None)
        self.assertEqual(got, self.target())
        self.assertTrue(os.path.exists(self.target()))

    def test_the_copy_is_byte_identical(self):
        TOOL.place_index_beside(self.step, report=lambda *_a: None)
        self.assertEqual(self.read(self.target()), self.read(self.source))

    def test_THE_SOURCE_STAYS_WHERE_IT_IS(self):
        r"""A move would empty the index archive, which is built from the work directory."""
        TOOL.place_index_beside(self.step, report=lambda *_a: None)
        self.assertTrue(os.path.exists(self.source))

    def test_an_identical_copy_already_there_is_reported_and_left(self):
        TOOL.place_index_beside(self.step, report=lambda *_a: None)
        said = []
        got = TOOL.place_index_beside(self.step, report=said.append)
        self.assertEqual(got, self.target())
        self.assertIn("already beside", " ".join(said))

    def test_A_DIFFERENT_INDEX_ALREADY_THERE_IS_A_REFUSAL(self):
        r"""Two different indexes for one archive means one of them describes something else, and
        the tool cannot tell which -- so it must not pick."""
        self.write(self.target(), "archive,path,size,sha256\nsomething,else.bff,1,ff\n")
        said = []
        got = TOOL.place_index_beside(self.step, report=said.append)
        self.assertIsNone(got)
        self.assertIn("REFUSING", " ".join(said))

    def test_and_that_refusal_leaves_the_existing_file_untouched(self):
        self.write(self.target(), "keep me\n")
        TOOL.place_index_beside(self.step, report=lambda *_a: None)
        self.assertEqual(self.read(self.target()), "keep me\n")

    def test_a_missing_source_is_answered_and_not_raised(self):
        os.remove(self.source)
        self.assertIsNone(TOOL.place_index_beside(self.step, report=lambda *_a: None))

    def test_a_step_without_an_index_is_answered_and_not_raised(self):
        """The index archive's own step has no index of its own."""
        self.assertIsNone(TOOL.place_index_beside({"archive": "x.rar"},
                                                  report=lambda *_a: None))

    def test_IT_HAPPENS_AFTER_THE_CHECKS_AND_NOT_BEFORE(self):
        r"""An index placed beside volumes that then failed their cross-check would describe an
        archive nobody should use -- and it is the one file a reader trusts without opening the
        archive."""
        text = self.source_text()
        self.assertLess(text.index("CRC32 and file count agree"),
                        text.index("place_index_beside(step)"))


class TheArchiveGetsItsOwnChecksums(unittest.TestCase):
    r"""The gap: nothing described the .rar volumes THEMSELVES.

    Every other check is about what is INSIDE the archive. `rar t` decompresses the members and
    compares them with the CRC32 RAR recorded; the cross-check holds those against our own `.sfv`;
    `<unit>.index.csv` lists every member with its sha256. After an upload, a volume corrupted in
    transit could only have been found by unpacking it.

    THROUGH PyFixity, which is the tool the three ibm-aix tars were given on 2026-10-06: one read
    per file, SHA-256, SHA-1, MD5 and CRC32 in a single pass, written as the same four manifests
    this collection carries everywhere. A fifth digest pass written here would be exactly the
    drift this project keeps a shared library to avoid.
    """

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="b2p-fix-")
        self.folder = os.path.join(self.base, "unit")
        self.work = os.path.join(self.base, "work")
        os.makedirs(self.folder)
        os.makedirs(self.work)
        # the shape a packed unit has: everything flat in one directory, plus a log that must NOT
        # be covered -- the owner stripped those lines out of all three manifests by hand.
        for name in ("unit.part01.rar", "unit.part02.rar", "unit.part01.rev"):
            with io.open(os.path.join(self.folder, name), "wb") as handle:
                handle.write(os.urandom(4096))
        with io.open(os.path.join(self.folder, "pack.log"), "w", encoding="utf-8") as handle:
            handle.write("one line per file, 82 MB of it on misc\n")
        with io.open(os.path.join(self.folder, "unit.index.csv"), "w",
                     encoding="utf-8", newline="\n") as handle:
            handle.write("archive,path,size,sha256\narch,a.bff,12,ab\n")

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def manifests(self):
        # THE FOUR NAMES FROM THE LIBRARY, not spelled here: common_test.py refuses a hand-
        # written one, because a rename would leave this test asserting the old spelling and
        # passing while the tool wrote the new one.
        want = [common.MANIFEST_FILES[algorithm] for algorithm in common.DIGESTS]
        return [name for name in want if os.path.exists(os.path.join(self.folder, name))]

    def test_ALL_FOUR_MANIFESTS_LAND_BESIDE_THE_UNIT(self):
        got = TOOL.fixity_over(self.folder, self.work, report=lambda *_a: None)
        self.assertTrue(got)
        self.assertEqual(self.manifests(),
                         [common.MANIFEST_FILES[a] for a in common.DIGESTS])

    def test_they_cover_the_volumes_AND_the_index_beside_them(self):
        r"""One .sha256sum describing everything that goes to B2 is the point: the volumes, the
        .rev files and the index CSV a reader fetches instead of the archive."""
        TOOL.fixity_over(self.folder, self.work, report=lambda *_a: None)
        with io.open(os.path.join(self.folder, common.SUMS_FILE), encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("unit.part01.rar", text)
        self.assertIn("unit.part01.rev", text)
        self.assertIn("unit.index.csv", text)

    def test_THE_INDEX_FILE_GOES_TO_THE_WORK_DIRECTORY_AND_NOT_THE_TREE(self):
        r"""PyFixity's own documentation: "It changes on every check, so keep it OUTSIDE a tree
        that gets uploaded or synced" -- and this tree is the one that gets uploaded."""
        TOOL.fixity_over(self.folder, self.work, report=lambda *_a: None)
        self.assertTrue(any(name.endswith(".fixity.csv") for name in os.listdir(self.work)))
        self.assertFalse(os.path.exists(os.path.join(self.folder, ".fixity-index.csv")))

    def test_the_digests_are_the_real_ones(self):
        """Not a stub: the file's sha256 has to be the sha256 of its bytes."""
        TOOL.fixity_over(self.folder, self.work, report=lambda *_a: None)
        with io.open(os.path.join(self.folder, "unit.part01.rar"), "rb") as handle:
            want = hashlib.sha256(handle.read()).hexdigest()
        with io.open(os.path.join(self.folder, common.SUMS_FILE), encoding="utf-8") as handle:
            self.assertIn(want, handle.read())

    def test_a_missing_PyFixity_is_reported_and_not_silently_skipped(self):
        r"""A unit uploaded without its own checksums is one nobody can check after the fact, so
        the absence has to be loud."""
        said = []
        was = TOOL.exists
        try:
            TOOL.exists = lambda path: False if path.endswith("pyfixity.py") else was(path)
            got = TOOL.fixity_over(self.folder, self.work, report=said.append)
        finally:
            TOOL.exists = was
        self.assertFalse(got)
        self.assertIn("no PyFixity", " ".join(said))

    def test_IT_RUNS_LAST_SO_IT_COVERS_THE_INDEX(self):
        """The index CSV is placed first and must be inside the manifests, so the order matters."""
        with io.open(os.path.join(HERE_DIR, "b2-pack.py"), encoding="utf-8") as handle:
            text = handle.read()
        call = text.index("fixity_over(os.path.dirname(")
        self.assertLess(text.index("place_index_beside(step)"), call)

    def test_THE_LOGS_ARE_NOT_COVERED(self):
        r"""The owner's decision on 2026-10-06: he stripped their lines out of all three manifests
        by hand. A manifest describes the UPLOADABLE set, and `pack.log` is a local record of how
        the volumes came to be -- 82 MB on misc, one line per file. Covering it would also make
        the manifest stale the moment anything appended to the log.
        """
        TOOL.fixity_over(self.folder, self.work, report=lambda *_a: None)
        with io.open(os.path.join(self.folder, common.SUMS_FILE), encoding="utf-8") as handle:
            text = handle.read()
        self.assertNotIn("pack.log", text)
        self.assertIn("unit.part01.rar", text)

    def test_A_STEP_WITH_NO_INDEX_PATH_DOES_NOT_REACH_THE_CALL(self):
        r"""THE BUG THAT KILLED A SEVEN-HOUR RUN. The index archive's own step carries no
        index_path, and the call site unpacked it with os.path.dirname() before calling -- so
        `dirname(None)` raised TypeError after vendors had packed 399 GB, passed `rar t` and
        passed the cross-check. The archive was fine; the run died before placing its index or
        writing its checksums.

        place_index_beside() already answered that case gracefully and a test said so. The call
        site did not, which is the difference between testing a function and testing its use.
        """
        with io.open(os.path.join(HERE_DIR, "b2-pack.py"), encoding="utf-8") as handle:
            text = handle.read()
        call = text.index("fixity_over(os.path.dirname(")
        guard = text.rindex("if step.get(\"index_path\"):", 0, call)
        self.assertLess(guard, call)
        # and nothing between the guard and the call that could run unguarded
        self.assertNotIn("dirname(step[", text[guard:call])

    def test_and_it_runs_only_after_the_checks_pass(self):
        with io.open(os.path.join(HERE_DIR, "b2-pack.py"), encoding="utf-8") as handle:
            text = handle.read()
        call = text.index("fixity_over(os.path.dirname(")
        self.assertLess(text.index("CRC32 and file count agree"), call)


class TheIndexArchiveStepHasNoList(unittest.TestCase):
    r"""It packs `*.index.csv` by wildcard, so both of its paths are None.

    THIS CRASHED EVERY --execute RUN THERE HAS BEEN. `write_list` called
    `os.path.dirname(step["list_path"])` unconditionally, so misc, vendors and oldskool each
    packed, passed `rar t`, passed the CRC32 cross-check and then died with exit 1 and a traceback
    nobody read -- because by then the archive was finished and three checks had said it was
    correct.

    THE COST WAS THE INDEX ARCHIVE ITSELF, never built: the small archive bundling every unit's
    index CSV, the one meant to be fetched instead of a unit. It only matters once all ten exist,
    which is why its absence went unnoticed for three units.

    AND THE FIRST DIAGNOSIS WAS WRONG. The vendors traceback named `write_list` and I attributed
    it to a guard I had left out in `fixity_over` an hour earlier, committed that as the cause,
    and was mistaken -- the line numbers pointed at comments because the file had been edited
    while the run was going, and I read the function names instead of checking which call raised.
    """

    def test_a_step_with_no_list_path_is_skipped_rather_than_raising(self):
        TOOL.write_list({"list_path": None, "index_path": None, "rows": []}, dry_run=False)

    def test_a_step_with_no_index_path_is_skipped_too(self):
        TOOL.write_list({"list_path": "somewhere.list", "index_path": None, "rows": []},
                        dry_run=False)

    def test_AND_IT_WRITES_NOTHING_WHEN_IT_SKIPS(self):
        r"""A half-written list would be worse than none: RAR would pack whatever it held."""
        folder = tempfile.mkdtemp(prefix="b2p-wl-")
        try:
            path = os.path.join(folder, "unit.list")
            TOOL.write_list({"list_path": path, "index_path": None, "rows": []}, dry_run=False)
            self.assertFalse(os.path.exists(path))
        finally:
            shutil.rmtree(folder, ignore_errors=True)

    def test_a_real_step_still_writes_both(self):
        folder = tempfile.mkdtemp(prefix="b2p-wl2-")
        try:
            step = {"list_path": os.path.join(folder, "unit.list"),
                    "index_path": os.path.join(folder, "unit.index.csv"),
                    "rows": [{"archive": "arch", "path": "a.bff", "size": 1, "digest": "ab"}],
                    "bookkeeping": [], "empty_dirs": []}
            TOOL.write_list(step, dry_run=False)
            self.assertTrue(os.path.exists(step["list_path"]))
            self.assertTrue(os.path.exists(step["index_path"]))
        finally:
            shutil.rmtree(folder, ignore_errors=True)

    def test_a_dry_run_writes_nothing_at_all(self):
        folder = tempfile.mkdtemp(prefix="b2p-wl3-")
        try:
            step = {"list_path": os.path.join(folder, "unit.list"),
                    "index_path": os.path.join(folder, "unit.index.csv"), "rows": [],
                    "bookkeeping": [], "empty_dirs": []}
            TOOL.write_list(step)
            self.assertEqual(os.listdir(folder), [])
        finally:
            shutil.rmtree(folder, ignore_errors=True)


class WhereTheIndexCsvLandsInsideTheArchive(unittest.TestCase):
    r"""`tar\<unit>.index.csv`, and it is a decision rather than an oversight.

    The CSV is passed by ABSOLUTE path, and RAR stores every component below the drive letter --
    so `X:\tar\misc.index.csv` becomes `tar\misc.index.csv`. Verified on the real misc archive:
    the entry sits in part04 of 27, because RAR orders by its own sort and not by argument order,
    which is why looking in the last volume found nothing.

    THREE WAYS TO FLATTEN IT WERE LOOKED AT AND REJECTED. `-ep` strips ALL paths, which for
    342 386 entries means basenames colliding on extraction with `rar t` saying "Alles OK" over
    it. `-ap<path>` applies to every file in the command. A second `rar a` with cwd=<work> would
    have to run before `-k`, and locking afterwards is measured fatal.

    IT STAYS ON THE OWNER'S REASONING: `tar/` is a named place inside the archive that more can go
    into later. The copy beside the volumes is the one a reader uses.
    """

    def test_the_index_is_passed_by_absolute_path(self):
        r"""Which is what puts it under `tar\`; a relative name would need the CSV to sit in the
        collection, and Q: is read-only to this tool."""
        unit = [u for u in TOOL.UNITS if u.name == "ibm-aix-opensource"][0]
        steps = TOOL.plan([unit], TOOL.MIRROR_ROOT,
                          os.path.join("X:" + os.sep, "tarTarget"),
                          os.path.join("X:" + os.sep, "tar"), with_dirs=False)
        argv = steps[0]["argv"]
        index = argv[-1]
        self.assertTrue(os.path.isabs(index), index)
        self.assertTrue(index.lower().endswith(".index.csv"), index)

    def test_AND_NO_SWITCH_STRIPS_THE_PATH(self):
        r"""-ep would flatten the 342 385 entries from the @list too, which is the failure this
        whole collection was rebuilt to remove."""
        unit = [u for u in TOOL.UNITS if u.name == "ibm-aix-opensource"][0]
        steps = TOOL.plan([unit], TOOL.MIRROR_ROOT,
                          os.path.join("X:" + os.sep, "tarTarget"),
                          os.path.join("X:" + os.sep, "tar"), with_dirs=False)
        argv = steps[0]["argv"]
        self.assertNotIn("-ep", argv)
        self.assertFalse([one for one in argv if one.startswith("-ap")])

    def test_the_decision_is_written_down_where_the_command_is_built(self):
        """So the next reader does not file it as a bug and reach for -ep."""
        with io.open(os.path.join(HERE_DIR, "b2-pack.py"), encoding="utf-8") as handle:
            text = " ".join(handle.read().split())
        self.assertIn("THAT IS DELIBERATE", text)
        self.assertIn("a named place inside the archive", text)


class WhatTheSwitchesActuallyBought(unittest.TestCase):
    r"""All nine units, 4 061.35 GB of real data, every figure read off the run that produced it.

    The settings were argued from rar.txt and from 600 MiB measurements. This class exists so the
    arguments cannot quietly outlive the evidence: if the record in b2-pack.py is edited, these
    fail, and whoever edits it has to say what measurement replaced which.
    """

    # unit -> (source GB, archive GB, -oi1 references, avg file MB, volumes, files)
    MEASURED = {
        "ibm-aix-opensource": (207.96, 73.00, 40012, 1.13, 20, 184465),
        "ibm-aix-support": (322.53, 135.67, 14603, 3.19, 39, 101086),
        "workstations": (169.46, 89.00, 30445, 0.40, 25, 420307),
        "ibm-aix": (702.51, 395.00, 2657, 13.45, 115, 52241),
        "ibm-pc": (530.45, 306.86, 20470, 1.80, 87, 295280),
        "vendors": (638.39, 399.00, 1698, 16.31, 118, 39131),
        "misc": (144.17, 93.88, 8777, 0.42, 27, 341969),
        "oldskool": (149.22, 120.00, 3120, 1.92, 35, 77624),
        "bitsavers": (1196.66, 1006.22, 1880, 6.80, 283, 176028),
    }

    def share(self, name):
        r"""-> references per file, which is the column that predicts the ratio."""
        return self.MEASURED[name][2] / float(self.MEASURED[name][5])

    def ratio(self, name):
        src, arc = self.MEASURED[name][0], self.MEASURED[name][1]
        return arc / src

    def source(self):
        with io.open(os.path.join(HERE_DIR, "b2-pack.py"), encoding="utf-8") as handle:
            return " ".join(handle.read().split())

    def test_THE_RECORD_COVERS_EVERY_UNIT_THAT_WAS_PACKED(self):
        r"""Nine, not the six it carried while three were still unpacked."""
        text = self.source()
        for name in self.MEASURED:
            self.assertIn(name, text)
        self.assertIn("nine units packed", text)

    def test_and_so_does_its_reference_count(self):
        r"""The reference count is the one figure only a real run can produce."""
        text = self.source()
        for name, row in self.MEASURED.items():
            refs = row[2]
            grouped = "%d %03d" % (refs // 1000, refs % 1000) if refs >= 1000 else str(refs)
            self.assertIn(grouped, text, "%s: %s" % (name, grouped))

    def test_THE_REFERENCE_SHARE_ORDERS_THE_TABLE(self):
        r"""Sorted by ratio, the share column descends, with two adjacent transpositions in nine.

        Measured, not asserted from theory: the swaps are ibm-aix/ibm-pc (56.2 % against 57.8 %,
        within the noise of two different mirror sets) and misc/oldskool.
        """
        by_ratio = sorted(self.MEASURED, key=self.ratio)
        by_share = sorted(self.MEASURED, key=lambda n: -self.share(n))
        wrong = sum(1 for a, b in zip(by_ratio, by_share) if a != b)
        self.assertLessEqual(wrong, 4, "%s vs %s" % (by_ratio, by_share))
        self.assertEqual(by_ratio[0], by_share[0])      # both ends are exact
        self.assertEqual(by_ratio[-1], by_share[-1])

    def test_AND_THE_RAW_COUNT_DOES_NOT(self):
        r"""TWO CLAIMS THAT WERE WRONG, kept as tests so they are not made a third time.

        1. "the fewest references marks the worst ratio" -- vendors has the fewest of all nine,
           1 698, and lands mid-table at 62.5 %.
        2. "the three best ratios are the three highest reference counts, in order" -- they are
           not; ibm-aix-support has 14 603 against ibm-pc's 20 470 and a ratio 15 points better,
           because it has a third of the files.

        Both came from using the count where the share was meant.
        """
        self.assertEqual(min(self.MEASURED, key=lambda n: self.MEASURED[n][2]), "vendors")
        self.assertNotEqual(max(self.MEASURED, key=self.ratio), "vendors")
        best3 = sorted(self.MEASURED, key=self.ratio)[:3]
        count3 = sorted(self.MEASURED, key=lambda n: -self.MEASURED[n][2])[:3]
        self.assertNotEqual(best3, count3)
        self.assertEqual(best3, sorted(self.MEASURED, key=lambda n: -self.share(n))[:3])

    def test_OLDSKOOL_IS_THE_OUTLIER_AND_NAMES_THE_SECOND_FACTOR(self):
        r"""4.02 % of its files are references, which by share should put it at misc's place, and
        it lands second-to-last instead: its content arrives already zipped."""
        self.assertGreater(self.share("oldskool"), self.share("misc"))
        self.assertGreater(self.ratio("oldskool"), self.ratio("misc"))
        self.assertIn("OLDSKOOL IS THE ONE REAL OUTLIER", self.source())

    def test_and_the_record_says_which_claims_were_corrected(self):
        text = self.source()
        self.assertIn("TWO CLAIMS WERE WRONG BEFORE THIS ONE", text)
        self.assertIn("the share is what was measured, so the share is what is claimed", text)

    def test_AND_IT_IS_NOT_FILE_SIZE(self):
        r"""Sort the nine by average file size and the ratios do not follow; sort by reference
        count and they do. This is why -md6g was not worth its memory and -oi1 was.
        """
        by_size = sorted(self.MEASURED, key=lambda n: self.MEASURED[n][3])
        by_ratio = sorted(self.MEASURED, key=self.ratio)
        self.assertNotEqual(by_size, by_ratio)
        # the worst ratio is not the largest average file, and the best is not the smallest
        self.assertNotEqual(max(self.MEASURED, key=self.ratio),
                            max(self.MEASURED, key=lambda n: self.MEASURED[n][3]))
        self.assertNotEqual(min(self.MEASURED, key=self.ratio),
                            min(self.MEASURED, key=lambda n: self.MEASURED[n][3]))
        # and concretely: bitsavers at 6.80 MB compresses worse than workstations at 0.40 MB
        self.assertGreater(self.ratio("bitsavers"), self.ratio("workstations"))

    def test_the_total_matches_the_parts(self):
        self.assertAlmostEqual(sum(v[0] for v in self.MEASURED.values()), 4061.35, places=1)
        self.assertAlmostEqual(sum(v[1] for v in self.MEASURED.values()), 2618.63, places=1)
        self.assertEqual(sum(v[2] for v in self.MEASURED.values()), 123662)
        self.assertEqual(sum(v[4] for v in self.MEASURED.values()), 749)
        text = self.source()
        for figure in ("4 061.35 GB", "2 618.63 GB", "123 662", "749"):
            self.assertIn(figure, text)

    def test_the_memory_figures_are_recorded_with_their_phase(self):
        r"""0.19 GB while -oi1 pre-hashes, 9.85 GB packing, 4.02 GB testing, 0.12 GB building the
        .rev files -- and the point is the phase, because a run looks free in its first minutes.
        """
        text = self.source()
        for figure in ("0.19 GB", "9.85 GB", "4.02 GB", "0.12 GB"):
            self.assertIn(figure, text)
        self.assertIn("allocated when the first block is compressed", text)

    def test_the_edge_cases_are_recorded(self):
        text = self.source()
        self.assertIn("98.98 GB", text)          # one member over 28 volumes
        self.assertIn("420 307 files", text)     # the largest file count, pre-hashed by -oi1
        self.assertIn("283 volumes", text)       # the largest unit, and its 6 .rev files
        self.assertIn("921 empty files", text)   # CRC32 00000000, same as a reference

    def test_the_rev_floor_rule_is_recorded_with_what_it_produced(self):
        r"""2 % of 283 volumes is 5.66, and int() of that is 5 -- but bitsavers got 6. The rule is
        `max(int(volumes * 2 / 100), 2)` applied to the volume count RAR ends up with, which is
        not knowable before the run; the record states the outcome rather than the prediction.
        """
        self.assertIn("2.1 % of the volumes", self.source())
        self.assertEqual(max(int(283 * 2 / 100), 2), 5)
        self.assertGreaterEqual(6, 5)

    def test_EVERY_UNIT_PASSED_BOTH_CHECKS(self):
        r"""`rar t` over the volumes AND a CRC32-plus-file-count comparison against the archive's
        own .sfv. Either alone would have missed something: `rar t` does not know how many files
        there should be, and the .sfv comparison does not read the recovery record.
        """
        text = self.source()
        self.assertIn("EVERY UNIT PASSED BOTH CHECKS", text)
        self.assertIn("NINE FOR NINE", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
