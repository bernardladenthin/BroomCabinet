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
import importlib.util
import io
import os
import sys
import tempfile
import unittest

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

    def test_the_bitsavers_split_is_exhaustive_by_construction(self):
        """The remainder unit must name `bitsavers` bare and exclude exactly the named subtrees."""
        rest = [u for u in TOOL.UNITS if u.name == "bitsavers-software"][0]
        self.assertEqual(rest.members, ("bitsavers",))
        named = set()
        for unit in TOOL.UNITS:
            for m in unit.members:
                if m.startswith("bitsavers/"):
                    named.add(m)
        self.assertEqual(set(rest.exclude), named)

    def test_every_unit_has_members_and_a_reason(self):
        for unit in TOOL.UNITS:
            self.assertTrue(unit.members, unit.name)
            self.assertGreater(len(unit.why), 60, "%s: a reason, not a label" % unit.name)

    def test_there_are_ten(self):
        """Not decoration -- the count is the thing that was agreed, and a silent eleventh unit
        means an upload nobody planned for.

        NINETEEN UNTIL 2026-10-04. The owner's rule was that a subject should be one unpack:
        "wenn man an AIX Sachen arbeitet, entpackt man vermutlich komplett AIX". Measured, the
        merge is worth 16 GB of 4 581 -- the bytes came from the volume size, not from this -- so
        the count changed for the reader and not for the bill."""
        self.assertEqual(len(TOOL.UNITS), 10)

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
                         ["-ma5", "-m5", "-md6g", "-s",
                          "-v%db" % TOOL.VOLUME_BYTES, "-rr1", "-rv15", "-k", "-scfl"])

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
        self.assertIn("-rv5", switches)

    def test_THE_RECOVERY_VOLUMES_FOLLOW_THE_OWNERS_5_10_15_RULE(self):
        """Counts and not a percentage, because `-rv` takes a count.

        The owner, 2026-10-05: "für kleine reichen 5, mittel 10 und das ganz große hat 15 recovery
        archive". The thresholds are in volumes -- what a .rev actually replaces -- and they fall
        between the real units rather than being round for their own sake:

            small   < 1 200   misc 698, oldskool 722, workstations 820, aix-opensource 1 007
            medium  < 3 000   aix-support 1 561, bitsavers-software 1 705, ibm-pc 2 568
            large   >=3 000   vendors 3 090, ibm-aix 3 400, bitsavers-paper 4 087

        IT IS LESS REDUNDANCY THAN THE 2 % IT REPLACED and that is the decision, not an oversight:
        95 .rev in all against 398, 19.8 GB against 83, and for bitsavers-paper 15 replaceable
        volumes out of 4 087 -- 0.37 % rather than 2 %. The owner's reason is that a .rev is the
        THIRD line: every volume carries its own 1 % record, every volume exists locally AND on B2,
        and a .rev answers the case where both have failed on the same part.
        """
        self.assertEqual(TOOL.DEFAULTS.recovery_volumes(698), 5)
        self.assertEqual(TOOL.DEFAULTS.recovery_volumes(1199), 5)
        self.assertEqual(TOOL.DEFAULTS.recovery_volumes(1200), 10)
        self.assertEqual(TOOL.DEFAULTS.recovery_volumes(2999), 10)
        self.assertEqual(TOOL.DEFAULTS.recovery_volumes(3000), 15)
        self.assertEqual(TOOL.DEFAULTS.recovery_volumes(4087), 15)

    def test_and_each_real_unit_lands_in_the_tier_it_was_sized_for(self):
        """The thresholds were chosen against these ten; a unit drifting across one is worth
        knowing about, because it changes how much of it can be lost."""
        want = {"misc": 5, "oldskool": 5, "workstations": 5, "aix-opensource": 5,
                "aix-support": 10, "bitsavers-software": 10, "ibm-pc": 10,
                "vendors": 15, "ibm-aix": 15, "bitsavers-paper": 15}
        self.assertEqual(sorted(want), sorted(u.name for u in TOOL.UNITS))

    def test_an_unsplit_archive_gets_none(self):
        """.rev files only mean anything for a volume set."""
        self.assertEqual(TOOL.INDEX_OPTIONS.recovery_volumes(1), 0)


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
            # At least 99 % of the owner's own margin is used, so the compatibility is real rather
            # than nominal: 119 volumes on a 25 GB disc fill 99.73 % of it.
            self.assertGreater(fit * TOOL.VOLUME_BYTES / limit, 0.99,
                              "%d GB disc holds %d volumes" % (gb, fit))

    def test_AND_B2_TAKES_A_VOLUME_IN_ONE_PIECE(self):
        """Under B2's single-part limit, so every volume carries its own whole-file SHA-1.

        A file that goes up through the large-file API is stored as parts and the whole-file digest
        is only present if the uploader set `large_file_sha1`; PyB2Verify then has to rebuild an
        S3 ETag from part MD5s to check it. At 995 MB nothing is split, so the check is a plain
        comparison. One gigabyte is the round number to stay under and leaves the real limit far
        above -- this asserts the comfortable bound, not the API's edge.
        """
        self.assertLess(TOOL.VOLUME_BYTES, 1000000000)

    def test_THE_DICTIONARY_CLEARS_EVERY_DUPLICATE_IN_THE_COLLECTION(self):
        """6 GB against a largest measured duplicate of 2 000.5 MB.

        A solid block collapses two byte-identical files only if the window still reaches back to
        the first one, and `sort_key` puts them adjacent -- so the dictionary has to be at least as
        large as the duplicate. Measured per unit on 2026-10-04: vendors 2 000.5 MB, ibm-aix
        1 997.5, aix-support 1 346.4, ibm-pc 669.5, oldskool 611.1, bitsavers-software 525.4,
        workstations 420.9, misc 152.0.

        WHICH IS ALSO WHY -oi IS NOT USED. rar.txt: where the identical files fit the dictionary,
        plain -s "kann eine anpassungsfähigere Lösung als -oi sein" -- and -oi would make a volume
        holding a reference depend on the volume holding the original, which rar.txt warns about
        for exactly our shape, "wenn die Volumen eines gesplitteten Archivs auf mehreren
        unterschiedlichen Wechselmedien gespeichert sind".
        """
        self.assertEqual(TOOL.DEFAULTS.dictionary, "6g")
        largest_duplicate_mb = 2000.5
        self.assertGreater(6 * 1024, largest_duplicate_mb)

    def test_EVERY_UNIT_IS_PACKED_THE_SAME_WAY(self):
        """The owner, 2026-10-05: "Ich will es einheitlich für alle archive".

        Two units were -m0, stored rather than compressed, because their content is already
        compressed. -m0 also switches off the solid block, so identical files are stored twice in
        full -- and measured per unit, aix-opensource is 208.0 GB holding 116.9 GB of byte-identical
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
            "RAR", "a", "-ma5", "-m5", "-md6g", "-s",
            "-v%db" % TOOL.VOLUME_BYTES, "-rr1", "-rv5", "-k", "-scfl",
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
        self.assertEqual(lines[-1], "split/pdf/hollow")
        self.assertEqual(lines[:-1], ["%s/%s" % (r["archive"], r["path"]) for r in step["rows"]])

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
        self.assertEqual(lines, ["%s/%s" % (r["archive"], r["path"]) for r in self.step["rows"]])

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

    def test_the_first_volume_is_what_gets_tested(self):
        self.assertEqual(TOOL.first_volume(os.path.join("OUT", "vendors", "vendors.rar")),
                         os.path.join("OUT", "vendors", "vendors.part01.rar"))

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
