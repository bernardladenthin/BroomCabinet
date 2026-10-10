#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Cryptomator vaults: open, walk, decrypt -- and every inconsistency the walk must name.

The vaults here are written by VaultBuilder, the encrypting half of the format (Cryptomator's
"Vault Format 8" documentation, cipher combination SIV_GCM). The reading half was checked against
real vaults written by a Cryptomator client before this test existed: every name decrypted, every
cleartext size matched the original file to the byte, and decrypted content matched its SHA-256.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sys
import unittest
import uuid

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM, AESSIV
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    from cryptography.hazmat.primitives.keywrap import aes_key_wrap
except ImportError:
    # The CI's smoke test runs every file with --help BEFORE requirements-test.txt is installed.
    if "--help" not in sys.argv[1:]:
        raise

import cryptomator as cm

PLACEHOLDER = ".bzEmpty"


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii")  # with padding, as Cryptomator writes names


class VaultBuilder:
    """A vault as the objects a client uploads, in a dict: relative name -> bytes."""

    def __init__(self, passphrase: str = "correct horse", *, cipher_combo: str = "SIV_GCM",
                 shortening: int = 220, placeholders: bool = True) -> None:
        self.passphrase, self.shortening, self.placeholders = passphrase, shortening, placeholders
        self.enc, self.mac = os.urandom(32), os.urandom(32)
        self.siv = AESSIV(self.mac + self.enc)
        salt = os.urandom(8)
        kek = Scrypt(salt=salt, length=32, n=1024, r=8, p=1).derive(passphrase.encode())  # cheap for tests
        self.objects: dict[str, bytes] = {
            "masterkey.cryptomator": json.dumps({
                "version": 999, "scryptSalt": base64.b64encode(salt).decode(), "scryptCostParam": 1024,
                "scryptBlockSize": 8,
                "primaryMasterKey": base64.b64encode(aes_key_wrap(kek, self.enc)).decode(),
                "hmacMasterKey": base64.b64encode(aes_key_wrap(kek, self.mac)).decode(),
                "versionMac": base64.b64encode(hmac.new(self.mac, (999).to_bytes(4, "big"),
                                                        hashlib.sha256).digest()).decode()}).encode(),
            "vault.cryptomator": self.jwt({"format": 8, "shorteningThreshold": shortening,
                                           "jti": str(uuid.uuid4()), "cipherCombo": cipher_combo}),
        }
        self.ids = {"": ""}  # cleartext directory path -> directory ID
        self.make_dir_folder("")

    def jwt(self, payload: dict, key: bytes | None = None) -> bytes:
        enc = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()  # noqa: E731
        head = enc({"kid": "masterkeyfile:masterkey.cryptomator", "typ": "JWT", "alg": "HS256"})
        body = enc(payload)
        sig = hmac.new(key or self.enc + self.mac, f"{head}.{body}".encode(), hashlib.sha256).digest()
        return f"{head}.{body}.{base64.urlsafe_b64encode(sig).rstrip(b'=').decode()}".encode()

    def dir_path(self, dir_id: str) -> str:
        h = base64.b32encode(hashlib.sha1(self.siv.encrypt(dir_id.encode(), None)).digest()).decode()
        return f"d/{h[:2]}/{h[2:]}"

    def make_dir_folder(self, dir_id: str) -> None:
        base = self.dir_path(dir_id)
        if self.placeholders:
            self.objects[f"{base}/{PLACEHOLDER}"] = b""
        self.objects[f"{base}/{cm.DIR_ID_BACKUP}"] = b"(encrypted backup of the ID)"

    def entry(self, path: str) -> str:
        """The object prefix of a cleartext path's entry in its parent directory."""
        parent, _, name = path.rpartition("/")
        encrypted = b64url(self.siv.encrypt(name.encode(), [self.ids[parent].encode()])) + ".c9r"
        base = self.dir_path(self.ids[parent])
        if len(encrypted) > self.shortening:
            short = b64url(hashlib.sha1(encrypted.encode()).digest()) + ".c9s"
            self.objects[f"{base}/{short}/name.c9s"] = encrypted.encode()
            return f"{base}/{short}"
        return f"{base}/{encrypted}"

    def add_dir(self, path: str) -> str:
        parent = path.rpartition("/")[0]
        if parent not in self.ids:
            self.add_dir(parent)
        if path in self.ids:
            return self.entry(path)
        self.ids[path] = str(uuid.uuid4())
        prefix = self.entry(path)
        self.objects[f"{prefix}/dir.c9r"] = self.ids[path].encode()
        self.make_dir_folder(self.ids[path])
        return prefix

    def add_file(self, path: str, data: bytes) -> str:
        parent = path.rpartition("/")[0]
        if parent not in self.ids:
            self.add_dir(parent)
        prefix = self.entry(path)
        name = f"{prefix}/contents.c9r" if prefix.endswith(".c9s") else prefix
        self.objects[name] = self.encrypt(data)
        return name

    def encrypt(self, data: bytes) -> bytes:
        nonce, key = os.urandom(12), os.urandom(32)
        out = bytearray(nonce + AESGCM(self.enc).encrypt(nonce, b"\xff" * 8 + key, None))
        for i in range(0, len(data), cm.BLOCK_PLAIN):
            n = os.urandom(12)
            out += n + AESGCM(key).encrypt(n, data[i:i + cm.BLOCK_PLAIN],
                                           (i // cm.BLOCK_PLAIN).to_bytes(8, "big") + nonce)
        return bytes(out)

    def open(self, passphrase: str | None = None) -> cm.Vault:
        return cm.Vault.open(self.objects["masterkey.cryptomator"], self.objects["vault.cryptomator"],
                             self.passphrase if passphrase is None else passphrase)

    def walk(self) -> cm.VaultTree:
        listing = {n: len(b) for n, b in self.objects.items() if n not in cm.VAULT_FILES}
        return cm.walk(self.open(), listing, lambda n: self.objects[n], [PLACEHOLDER])


def chunked(data: bytes, size: int):
    return (data[i:i + size] for i in range(0, len(data), size))


class OpenTest(unittest.TestCase):
    def test_the_right_passphrase_opens_the_vault(self):
        v = VaultBuilder()
        vault = v.open()
        self.assertEqual((vault.enc_key, vault.mac_key), (v.enc, v.mac))

    def test_a_wrong_passphrase_is_named_as_such(self):
        with self.assertRaisesRegex(cm.VaultError, "wrong passphrase"):
            VaultBuilder().open("not it")

    def test_the_passphrase_is_normalised_to_nfc(self):
        v = VaultBuilder("Kennwort-ä")  # composed
        v.open("Kennwort-ä")  # decomposed, as some keyboards and file systems deliver it

    def test_a_changed_configuration_is_refused(self):
        v = VaultBuilder()
        v.objects["vault.cryptomator"] = v.jwt({"format": 8, "cipherCombo": "SIV_GCM"}, key=os.urandom(64))
        with self.assertRaisesRegex(cm.VaultError, "signature does not match"):
            v.open()

    def test_other_formats_are_refused_rather_than_misread(self):
        with self.assertRaisesRegex(cm.VaultError, "unsupported vault"):
            VaultBuilder(cipher_combo="SIV_CTRMAC").open()


class SizeTest(unittest.TestCase):
    def test_the_cleartext_size_follows_from_the_ciphertext_size(self):
        v = VaultBuilder()
        for n in (0, 1, cm.BLOCK_PLAIN - 1, cm.BLOCK_PLAIN, cm.BLOCK_PLAIN + 1, 3 * cm.BLOCK_PLAIN + 77):
            self.assertEqual(cm.plain_size(len(v.encrypt(os.urandom(n)))), n, n)

    def test_impossible_sizes_are_recognised(self):
        self.assertIsNone(cm.plain_size(cm.HEADER_SIZE - 1))  # not even a header
        self.assertIsNone(cm.plain_size(cm.HEADER_SIZE + cm.BLOCK_OVERHEAD))  # an empty last block


class DecryptTest(unittest.TestCase):
    def setUp(self):
        self.v = VaultBuilder()
        self.vault = self.v.open()

    def decrypt(self, cipher: bytes, chunk: int = 10_000) -> bytes:
        return b"".join(self.vault.decrypt_chunks(chunked(cipher, chunk)))

    def test_round_trip_whatever_the_chunk_size_of_the_stream(self):
        for n in (0, 5, cm.BLOCK_PLAIN, 2 * cm.BLOCK_PLAIN, 2 * cm.BLOCK_PLAIN + 1):
            data = os.urandom(n)
            cipher = self.v.encrypt(data)
            for chunk in (1, 1000, cm.BLOCK_CIPHER, 1 << 20):
                self.assertEqual(self.decrypt(cipher, chunk), data, (n, chunk))

    def test_one_flipped_bit_is_found_and_located(self):
        cipher = bytearray(self.v.encrypt(os.urandom(3 * cm.BLOCK_PLAIN)))
        cipher[cm.HEADER_SIZE + cm.BLOCK_CIPHER + 500] ^= 0x01  # inside block 1
        with self.assertRaisesRegex(cm.DamagedError, "block 1 "):
            self.decrypt(bytes(cipher))

    def test_a_missing_last_block_is_found(self):
        cipher = self.v.encrypt(os.urandom(2 * cm.BLOCK_PLAIN + 100))
        with self.assertRaises(cm.DamagedError):
            self.decrypt(cipher[:-50])  # cut inside the last block

    def test_swapped_blocks_are_found(self):
        cipher = self.v.encrypt(os.urandom(2 * cm.BLOCK_PLAIN))
        h, b = cm.HEADER_SIZE, cm.BLOCK_CIPHER
        swapped = cipher[:h] + cipher[h + b:h + 2 * b] + cipher[h:h + b]
        with self.assertRaisesRegex(cm.DamagedError, "block 0 "):
            self.decrypt(swapped)

    def test_a_damaged_header_and_a_truncated_file(self):
        cipher = bytearray(self.v.encrypt(b"x" * 100))
        cipher[20] ^= 0xFF
        with self.assertRaisesRegex(cm.DamagedError, "header"):
            self.decrypt(bytes(cipher))
        with self.assertRaisesRegex(cm.DamagedError, "truncated"):
            self.decrypt(bytes(cipher[:30]))

    def test_the_source_stream_is_closed(self):
        closed = []

        def source():
            try:
                yield self.v.encrypt(b"abc")
            finally:
                closed.append(True)

        list(self.vault.decrypt_chunks(source()))
        self.assertEqual(closed, [True])


class WalkTest(unittest.TestCase):
    def test_names_sizes_and_nesting(self):
        v = VaultBuilder()
        v.add_file("top.txt", b"hello")
        v.add_file("Series/Season 1/01 Pilot.mkv", os.urandom(70_000))
        v.add_file("Series/Season 1/Ünïcödé – name.nfo", b"")
        v.add_dir("Empty folder")
        tree = v.walk()
        self.assertEqual(tree.problems, [])
        self.assertEqual({p: f.size for p, f in tree.files.items()},
                         {"top.txt": 5, "Series/Season 1/01 Pilot.mkv": 70_000,
                          "Series/Season 1/Ünïcödé – name.nfo": 0})
        self.assertEqual(tree.directories, 3)
        self.assertEqual(tree.leftovers, [])

    def test_long_names_are_read_from_name_c9s(self):
        v = VaultBuilder(shortening=60)
        long_name = "A very long episode title that certainly exceeds the threshold.mkv"
        obj = v.add_file(f"Long dir name beyond the threshold for sure/{long_name}", b"data")
        self.assertTrue(obj.endswith(".c9s/contents.c9r"))
        tree = v.walk()
        self.assertEqual(tree.problems, [])
        self.assertIn(f"Long dir name beyond the threshold for sure/{long_name}", tree.files)

    def test_a_pointer_into_nothing(self):
        # Seen on 2026-10-09: the pointer was written, the directory under d/ never was.
        v = VaultBuilder()
        v.add_file("Show/S01E01.mkv", b"one")
        v.add_dir("Show/Extras")
        target = v.dir_path(v.ids["Show/Extras"])
        for n in [n for n in v.objects if n.startswith(target + "/")]:
            del v.objects[n]
        tree = v.walk()
        self.assertEqual(len(tree.problems), 1, tree.problems)
        self.assertIn("directory 'Show/Extras': points to", tree.problems[0])
        self.assertIn("does not exist", tree.problems[0])
        self.assertIn("Show/S01E01.mkv", tree.files)  # the rest is still read

    def test_an_entry_without_pointer_or_content(self):
        v = VaultBuilder()
        prefix = v.add_dir("Half")
        del v.objects[f"{prefix}/dir.c9r"]
        v.objects[f"{prefix}/{PLACEHOLDER}"] = b""  # what an interrupted client leaves
        tree = v.walk()
        self.assertTrue(any("'Half': an entry with neither dir.c9r nor content" in p for p in tree.problems),
                        tree.problems)
        # its directory under d/ still holds dirid.c9r, so it is an orphan with content
        self.assertTrue(any(p.startswith("orphaned directory") for p in tree.problems), tree.problems)

    def test_deleted_directories_leave_only_harmless_placeholders(self):
        v = VaultBuilder()
        prefix = v.add_dir("Gone")
        target = v.dir_path(v.ids["Gone"])
        # A client deleting a directory hides dir.c9r and dirid.c9r; B2's placeholders stay.
        del v.objects[f"{prefix}/dir.c9r"]
        del v.objects[f"{target}/{cm.DIR_ID_BACKUP}"]
        tree = v.walk()
        self.assertEqual(tree.problems, [])
        self.assertEqual(tree.leftovers, [target])

    def test_an_undecryptable_name_and_an_unexpected_object(self):
        v = VaultBuilder()
        v.add_file("ok.txt", b"ok")
        root = v.dir_path("")
        v.objects[f"{root}/{b64url(os.urandom(32))}.c9r"] = v.encrypt(b"name from another vault")
        v.objects[f"{root}/stray.tmp"] = b"x"
        tree = v.walk()
        self.assertEqual(len(tree.problems), 2, tree.problems)
        self.assertTrue(any("cannot be read" in p for p in tree.problems))
        self.assertTrue(any("unexpected object stray.tmp" in p for p in tree.problems))
        self.assertIn("ok.txt", tree.files)

    def test_a_truncated_file_is_flagged_by_its_size(self):
        v = VaultBuilder()
        obj = v.add_file("cut.bin", os.urandom(cm.BLOCK_PLAIN + 10))
        v.objects[obj] = v.objects[obj][:cm.HEADER_SIZE + cm.BLOCK_CIPHER + 5]
        tree = v.walk()
        self.assertIsNone(tree.files["cut.bin"].size)
        self.assertTrue(any("no complete encrypted file" in p for p in tree.problems))

    def test_an_empty_vault(self):
        v = VaultBuilder(placeholders=False)
        tree = v.walk()
        self.assertEqual((tree.files, tree.problems), ({}, []))


if __name__ == "__main__":
    unittest.main()
