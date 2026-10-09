# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Read a Cryptomator vault (format 8, SIV_GCM) the way B2 holds it: open it, walk it, decrypt it.

Read-only, and independent of B2: the caller hands over the object listing and a way to read a
small object, and gets back the decrypted tree -- names, exact cleartext sizes and everything that
does not fit together. Content is decrypted as a stream, block by block, without a temp file.

WHY THIS EXISTS. B2's checksums of an encrypted file describe the ciphertext, and Cryptomator
encrypts with a random file key and random nonces, so the same file never encrypts to the same
bytes twice: a local checksum can never be compared with a B2 checksum. What can be checked:

  * the STRUCTURE, without downloading any content: every name decrypts, every directory pointer
    leads to a directory, and the cleartext size follows exactly from the ciphertext size
    (a 68-byte header, then 32 KiB blocks with 28 bytes each of nonce and tag);
  * the CONTENT, by downloading: every block carries an AES-GCM tag, so decrypting it IS the
    integrity check, and hashing the cleartext on the way compares it with the local checksums.

WHY THE STRUCTURE CHECK MATTERS. B2 has no directories and no transactions. Creating one vault
directory takes several objects -- the pointer (dir.c9r) in the parent, then the directory itself
under d/ -- and a client that stops between them leaves a pointer into nothing. Seen on
2026-10-09: an upload stalled exactly there, and the client then hung on that directory every
time it was opened or deleted. Nothing in a normal listing shows it.

The vault layout (Cryptomator's own documentation, "Vault Format 8"):

    masterkey.cryptomator   scrypt-protected encryption and MAC keys
    vault.cryptomator       JWT, signed with both keys: format, cipher combination, name length
    d/XX/YYYY...            one directory per vault directory, named by the hash of its ID
        <name>.c9r          a file, or (as a folder) a directory holding dir.c9r = the child's ID
        <hash>.c9s/         a long name: name.c9s holds it, contents.c9r or dir.c9r the rest
        dirid.c9r           a backup of the directory's own ID (newer clients); not an entry
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import unicodedata
from dataclasses import dataclass, field
from typing import Callable, Iterable, Iterator

HEADER_SIZE = 12 + 40 + 16  # nonce, encrypted (8 reserved bytes + 32-byte file key), tag
BLOCK_PLAIN = 32 * 1024
BLOCK_OVERHEAD = 12 + 16  # nonce and tag per block
BLOCK_CIPHER = BLOCK_PLAIN + BLOCK_OVERHEAD
VAULT_FILES = ("masterkey.cryptomator", "vault.cryptomator")
DIR_ID_BACKUP = "dirid.c9r"


class VaultError(Exception):
    """The vault cannot be opened: wrong passphrase, unsupported format, tampered configuration."""


class DamagedError(Exception):
    """Ciphertext that does not authenticate: changed, truncated or reordered bytes."""


def require() -> None:
    """Raise ImportError now, rather than halfway through a run, if 'cryptography' is missing.
    The package is imported where it is used, so that a caller's --help needs nothing."""
    import cryptography  # noqa: F401


def b64url_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def plain_size(cipher_size: int) -> int | None:
    """The exact cleartext size, or None for a size no complete encrypted file can have."""
    body = cipher_size - HEADER_SIZE
    if body < 0:
        return None
    full, rest = divmod(body, BLOCK_CIPHER)
    if 0 < rest <= BLOCK_OVERHEAD:
        return None  # a last block without a single byte of content: truncated
    return full * BLOCK_PLAIN + (rest - BLOCK_OVERHEAD if rest else 0)


class Vault:
    """The two master keys of an opened vault, and what can be done with them."""

    def __init__(self, enc_key: bytes, mac_key: bytes) -> None:
        from cryptography.hazmat.primitives.ciphers.aead import AESSIV
        self.enc_key, self.mac_key = enc_key, mac_key
        self._siv = AESSIV(mac_key + enc_key)  # RFC 5297 order: the S2V (MAC) key first

    @classmethod
    def open(cls, masterkey_json: bytes, vault_config: bytes, passphrase: str) -> "Vault":
        """Unlock the keys, then check the signature and the format of vault.cryptomator."""
        from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
        from cryptography.hazmat.primitives.keywrap import InvalidUnwrap, aes_key_unwrap
        try:
            mk = json.loads(masterkey_json)
            kek = Scrypt(salt=base64.b64decode(mk["scryptSalt"]), length=32, n=mk["scryptCostParam"],
                         r=mk["scryptBlockSize"], p=1).derive(unicodedata.normalize("NFC", passphrase).encode())
        except (ValueError, KeyError, TypeError) as e:
            raise VaultError(f"masterkey.cryptomator is not readable ({e})") from e
        try:
            enc = aes_key_unwrap(kek, base64.b64decode(mk["primaryMasterKey"]))
            mac = aes_key_unwrap(kek, base64.b64decode(mk["hmacMasterKey"]))
        except InvalidUnwrap:
            raise VaultError("wrong passphrase: the master keys do not unlock") from None
        version_mac = hmac.new(mac, int(mk["version"]).to_bytes(4, "big"), hashlib.sha256).digest()
        if not hmac.compare_digest(version_mac, base64.b64decode(mk["versionMac"])):
            raise VaultError("masterkey.cryptomator: the version MAC does not match")
        try:
            head, body, sig = vault_config.decode("ascii").strip().split(".")
        except (UnicodeDecodeError, ValueError):
            raise VaultError("vault.cryptomator is not a JWT") from None
        expected = hmac.new(enc + mac, f"{head}.{body}".encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, b64url_decode(sig)):
            raise VaultError("vault.cryptomator: the signature does not match these keys (changed?)")
        config = json.loads(b64url_decode(body))
        if config.get("format") != 8 or config.get("cipherCombo") != "SIV_GCM":
            raise VaultError(f"unsupported vault (format {config.get('format')}, "
                             f"{config.get('cipherCombo')}); only format 8 with SIV_GCM is read")
        return cls(enc, mac)

    def dir_path(self, dir_id: str) -> str:
        """Where a directory lives: d/ + the Base32 SHA-1 of its encrypted ID, split 2/30."""
        digest = hashlib.sha1(self._siv.encrypt(dir_id.encode(), None)).digest()
        h = base64.b32encode(digest).decode("ascii")
        return f"d/{h[:2]}/{h[2:]}"

    def decrypt_name(self, encrypted: str, parent_dir_id: str) -> str:
        """A name without its .c9r ending; the parent's ID is bound to it as associated data."""
        from cryptography.exceptions import InvalidTag
        try:
            return self._siv.decrypt(b64url_decode(encrypted), [parent_dir_id.encode()]).decode()
        except (InvalidTag, ValueError) as e:
            raise DamagedError(f"name does not decrypt ({type(e).__name__})") from None

    def decrypt_chunks(self, chunks: Iterable[bytes]) -> Iterator[bytes]:
        """Cleartext from ciphertext chunks of any size. Every 32 KiB block is authenticated, bound
        to its position and to the file header, so changed, reordered or missing blocks all fail."""
        from cryptography.exceptions import InvalidTag
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        source = iter(chunks)
        try:
            buf = bytearray()
            for piece in source:
                buf += piece
                if len(buf) >= HEADER_SIZE:
                    break
            if len(buf) < HEADER_SIZE:
                raise DamagedError(f"truncated: {len(buf)} bytes, shorter than the file header")
            header_nonce = bytes(buf[:12])
            try:
                payload = AESGCM(self.enc_key).decrypt(header_nonce, bytes(buf[12:HEADER_SIZE]), None)
            except InvalidTag:
                raise DamagedError("the file header does not authenticate") from None
            content = AESGCM(payload[8:40])
            del buf[:HEADER_SIZE]
            block = 0

            def open_block(data: bytes) -> bytes:
                if len(data) <= BLOCK_OVERHEAD:
                    raise DamagedError(f"block {block}: truncated to {len(data)} bytes")
                try:
                    return content.decrypt(data[:12], data[12:], block.to_bytes(8, "big") + header_nonce)
                except InvalidTag:
                    raise DamagedError(f"block {block} (at {block * BLOCK_PLAIN} bytes of cleartext) "
                                       f"does not authenticate") from None

            # What came with the header may already hold several blocks -- a small file arrives in
            # one piece -- so blocks are cut before the next piece is read, not only after it.
            pieces = iter(source)
            while True:
                while len(buf) > BLOCK_CIPHER:  # keep the last block until the end is known
                    yield open_block(bytes(buf[:BLOCK_CIPHER]))
                    del buf[:BLOCK_CIPHER]
                    block += 1
                piece = next(pieces, None)
                if piece is None:
                    break
                buf += piece
            if buf:
                yield open_block(bytes(buf))
        finally:
            close = getattr(source, "close", None)
            if close:
                close()


# --------------------------------------------------------------------------- the tree

@dataclass
class VaultFile:
    path: str  # cleartext path with '/'
    object_name: str  # the ciphertext object, relative to the vault root
    cipher_size: int
    size: int | None  # cleartext size; None if the ciphertext size is impossible


@dataclass
class VaultTree:
    files: dict[str, VaultFile] = field(default_factory=dict)
    directories: int = 0
    problems: list[str] = field(default_factory=list)  # what makes the vault inconsistent
    leftovers: list[str] = field(default_factory=list)  # harmless: unreferenced, placeholders only


def walk(vault: Vault, objects: dict[str, int], read: Callable[[str], bytes],
         placeholders: Iterable[str] = ()) -> VaultTree:
    """Decrypt the directory tree from a listing.

    objects: every current object below the vault root -> its size, relative names ("d/AB/...").
    read: the content of one small object (dir.c9r, name.c9s), by the same relative name.
    placeholders: names of empty-folder markers some clients write (B2's ".bzEmpty"); ignored.
    """
    ignore = set(placeholders)
    tree = VaultTree()
    children: dict[str, set[str]] = {}  # directory path -> entry names in it
    for name in objects:
        if not name.startswith("d/"):
            continue
        parts = name.split("/")
        if len(parts) >= 4:  # d/XX/YYYY.../<entry>: an object inside a directory, so it exists
            entries = children.setdefault("/".join(parts[:3]), set())
            if parts[3] not in ignore and parts[3] != DIR_ID_BACKUP:
                entries.add(parts[3])
    reached: set[str] = set()

    def visit(dir_id: str, path: str) -> None:
        base = vault.dir_path(dir_id)
        if base in reached:
            tree.problems.append(f"'{path or '/'}': a second pointer to {base} (a directory loop?)")
            return
        reached.add(base)
        if base not in children:
            if path:
                tree.problems.append(f"directory '{path}': points to {base}, which does not exist - "
                                     f"left over from an interrupted upload?")
            elif any(n.startswith("d/") for n in objects):
                tree.problems.append(f"the root directory {base} does not exist")
            return
        for entry in sorted(children[base]):
            prefix = f"{base}/{entry}"
            if not entry.endswith((".c9r", ".c9s")):
                tree.problems.append(f"'{path or '/'}': unexpected object {entry}")
                continue
            try:
                encrypted = (read(f"{prefix}/name.c9s").decode("ascii") if entry.endswith(".c9s")
                             else entry)
                name = vault.decrypt_name(encrypted[:-4], dir_id)
            except (DamagedError, KeyError, UnicodeDecodeError) as e:
                tree.problems.append(f"'{path or '/'}': the name of {entry[:24]}... cannot be read ({e})")
                continue
            full = f"{path}/{name}" if path else name
            if f"{prefix}/dir.c9r" in objects:
                tree.directories += 1
                visit(read(f"{prefix}/dir.c9r").decode("utf-8"), full)
            elif f"{prefix}/contents.c9r" in objects or prefix in objects:
                obj = f"{prefix}/contents.c9r" if f"{prefix}/contents.c9r" in objects else prefix
                size = plain_size(objects[obj])
                if size is None:
                    tree.problems.append(f"'{full}': {objects[obj]} bytes of ciphertext is no complete "
                                         f"encrypted file (truncated?)")
                tree.files[full] = VaultFile(full, obj, objects[obj], size)
            elif f"{prefix}/symlink.c9r" in objects:
                continue  # a symbolic link: nothing to compare
            else:
                tree.problems.append(f"'{full}': an entry with neither dir.c9r nor content - "
                                     f"left over from an interrupted upload or delete?")

    visit("", "")
    for base in sorted(children.keys() - reached):
        content = sorted(n for n in objects if n.startswith(base + "/")
                         and n.rsplit("/", 1)[-1] not in ignore)
        if content:
            tree.problems.append(f"orphaned directory {base} (no pointer leads to it): "
                                 f"{len(content)} object(s), e.g. {content[0][len(base) + 1:]}")
        else:
            tree.leftovers.append(base)
    return tree
