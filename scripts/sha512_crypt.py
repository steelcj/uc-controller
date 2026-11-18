#!/usr/bin/env python3
"""SHA-512 crypt ($6$) password hashes, in pure Python.

The hash format /etc/shadow, Debian's preseed (user-password-crypted) and
cloud-init's autoinstall (identity.password) accept, as made by
"openssl passwd -6" or "mkpasswd --method=sha-512". It follows Ulrich
Drepper's specification, "Unix crypt using SHA-256 and SHA-512", with the
default 5000 rounds.

Python 3.13 removed the crypt module, and passlib is not a dependency of
this repository, so the algorithm is written out here with hashlib only. It
runs on Linux, macOS and Windows. tests/test_sha512_crypt.py checks it
against the specification's test vectors and, where present, against
"openssl passwd -6".

Used as a module by new_raw_batch.py. Run directly, it reads a password on
standard input and prints its hash, for testing only.
"""
from __future__ import annotations

import hashlib
import secrets
import sys

ALPHABET = "./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
DEFAULT_ROUNDS = 5000
SALT_LENGTH = 16

# The order in which the 64 digest bytes are encoded, three at a time,
# as glibc's sha512-crypt.c writes them. The last byte is encoded alone.
_ORDER = [
    (0, 21, 42), (22, 43, 1), (44, 2, 23), (3, 24, 45), (25, 46, 4),
    (47, 5, 26), (6, 27, 48), (28, 49, 7), (50, 8, 29), (9, 30, 51),
    (31, 52, 10), (53, 11, 32), (12, 33, 54), (34, 55, 13), (56, 14, 35),
    (15, 36, 57), (37, 58, 16), (59, 17, 38), (18, 39, 60), (40, 61, 19),
    (62, 20, 41),
]


def _repeat(block: bytes, length: int) -> bytes:
    """block repeated, then cut, to exactly length bytes."""
    if length == 0:
        return b""
    times = -(-length // len(block))
    return (block * times)[:length]


def _encode(digest: bytes) -> str:
    out = []
    for b2, b1, b0 in _ORDER:
        word = (digest[b2] << 16) | (digest[b1] << 8) | digest[b0]
        for _ in range(4):
            out.append(ALPHABET[word & 0x3F])
            word >>= 6
    word = digest[63]
    for _ in range(2):
        out.append(ALPHABET[word & 0x3F])
        word >>= 6
    return "".join(out)


def new_salt() -> str:
    """A random 16-character salt from the crypt alphabet."""
    return "".join(secrets.choice(ALPHABET) for _ in range(SALT_LENGTH))


def sha512_crypt(password: str, salt: str | None = None,
                 rounds: int = DEFAULT_ROUNDS) -> str:
    """Return the $6$ hash of password.

    salt is at most 16 characters from the crypt alphabet; a random one is
    used when it is None. A rounds value other than 5000 is written into the
    hash as rounds=N, as the specification requires.
    """
    if salt is None:
        salt = new_salt()
    salt = salt[:SALT_LENGTH]
    if any(ch not in ALPHABET for ch in salt):
        raise ValueError("salt characters must be from the crypt alphabet")
    if not 1000 <= rounds <= 999_999_999:
        raise ValueError("rounds must be between 1000 and 999999999")

    p = password.encode("utf-8")
    s = salt.encode("ascii")

    b = hashlib.sha512(p + s + p).digest()

    a = hashlib.sha512(p + s)
    a.update(_repeat(b, len(p)))
    length = len(p)
    while length:
        a.update(b if length & 1 else p)
        length >>= 1
    a_digest = a.digest()

    p_seq = _repeat(hashlib.sha512(p * len(p)).digest(), len(p))
    s_seq = _repeat(hashlib.sha512(s * (16 + a_digest[0])).digest(), len(s))

    c = a_digest
    for i in range(rounds):
        ctx = hashlib.sha512(p_seq if i & 1 else c)
        if i % 3:
            ctx.update(s_seq)
        if i % 7:
            ctx.update(p_seq)
        ctx.update(c if i & 1 else p_seq)
        c = ctx.digest()

    prefix = "$6$" if rounds == DEFAULT_ROUNDS else f"$6$rounds={rounds}$"
    return f"{prefix}{salt}${_encode(c)}"


if __name__ == "__main__":
    line = sys.stdin.readline().rstrip("\r\n")
    print(sha512_crypt(line))
