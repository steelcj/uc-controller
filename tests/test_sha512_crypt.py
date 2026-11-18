"""Tests for scripts/sha512_crypt.py. Standard library only.

    python3 -m unittest discover -s tests
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from sha512_crypt import ALPHABET, new_salt, sha512_crypt  # noqa: E402

# The seven SHA-512 test vectors published in Ulrich Drepper, "Unix crypt
# using SHA-256 and SHA-512" (https://www.akkadia.org/drepper/SHA-crypt.txt):
# the default rounds, custom rounds (10000, 5000 given explicitly, 1400,
# 77777, 123456), a salt cut to 16 characters, and rounds=10 raised to 1000.
SPEC_VECTORS = [
    ("$6$saltstring", "Hello world!",
     "$6$saltstring$svn8UoSVapNtMuq1ukKS4tPQd8iKwSMHWjl/O817G3uBnIFNjnQJuesI68u4OTLiBFdcbYEdFCoEOfaS35inz1"),
    ("$6$rounds=10000$saltstringsaltstring", "Hello world!",
     "$6$rounds=10000$saltstringsaltst$OW1/O6BYHV6BcXZu8QVeXbDWra3Oeqh0sbHbbMCVNSnCM/UrjmM0Dp8vOuZeHBy/YTBmSK6H9qs/y3RnOaw5v."),
    ("$6$rounds=5000$toolongsaltstring", "This is just a test",
     "$6$rounds=5000$toolongsaltstrin$lQ8jolhgVRVhY4b5pZKaysCLi0QBxGoNeKQzQ3glMhwllF7oGDZxUhx1yxdYcz/e1JSbq3y6JMxxl8audkUEm0"),
    ("$6$rounds=1400$anotherlongsaltstring", "a very much longer text to encrypt.  This one even stretches over morethan one line.",
     "$6$rounds=1400$anotherlongsalts$POfYwTEok97VWcjxIiSOjiykti.o/pQs.wPvMxQ6Fm7I6IoYN3CmLs66x9t0oSwbtEW7o7UmJEiDwGqd8p4ur1"),
    ("$6$rounds=77777$short", "we have a short salt string but not a short password",
     "$6$rounds=77777$short$WuQyW2YR.hBNpjjRhpYD/ifIw05xdfeEyQoMxIXbkvr0gge1a1x3yRULJ5CCaUeOxFmtlcGZelFl5CxtgfiAc0"),
    ("$6$rounds=123456$asaltof16chars..", "a short string",
     "$6$rounds=123456$asaltof16chars..$BtCwjqMJGx5hrJhZywWvt0RLE8uZ4oPwcelCjmw2kSYu.Ec6ycULevoBK25fs2xXgMNrCzIMVcgEJAstJeonj1"),
    ("$6$rounds=10$roundstoolow", "the minimum number is still observed",
     "$6$rounds=1000$roundstoolow$kUMsbe306n21p9R.FRkW3IGn.S9NPN0x50YhH1xhLsPuWGsUSklZt58jaTfF4ZEQpyUNGc0dqbpBYYBaHHrsX."),
]


def split(setting: str) -> tuple[str, int | None]:
    """(salt, rounds) from a setting; rounds is None when not given."""
    parts = setting.split("$")
    if parts[2].startswith("rounds="):
        return parts[3], int(parts[2][len("rounds="):])
    return parts[2], None


class SpecVectors(unittest.TestCase):
    def test_vectors(self):
        for setting, password, expected in SPEC_VECTORS:
            salt, rounds = split(setting)
            with self.subTest(setting=setting):
                self.assertEqual(sha512_crypt(password, salt, rounds), expected)


class Format(unittest.TestCase):
    def test_default_form(self):
        value = sha512_crypt("abcDEF123456789xyz")
        prefix, kind, salt, digest = value.split("$")
        self.assertEqual((prefix, kind), ("", "6"))
        self.assertEqual(len(salt), 16)
        self.assertEqual(len(digest), 86)
        self.assertTrue(set(salt + digest) <= set(ALPHABET))

    def test_salts_differ(self):
        self.assertNotEqual(new_salt(), new_salt())

    def test_salt_comes_from_secrets(self):
        with mock.patch("sha512_crypt.secrets.choice", return_value="x") as choice:
            self.assertEqual(new_salt(), "x" * 16)
            self.assertEqual(sha512_crypt("pw").split("$")[2], "x" * 16)
        self.assertEqual(choice.call_count, 32)

    def test_default_rounds_not_written(self):
        self.assertNotIn("rounds=", sha512_crypt("pw", "salt"))
        self.assertEqual(sha512_crypt("pw", "salt").split("$")[3],
                         sha512_crypt("pw", "salt", 5000).split("$")[4])

    def test_bad_salt(self):
        with self.assertRaises(ValueError):
            sha512_crypt("x", "bad salt")


@unittest.skipUnless(shutil.which("openssl"), "openssl not installed")
class AgainstOpenSSL(unittest.TestCase):
    def test_matches_openssl(self):
        for password in ("abcDEF123456789xyz", "A" * 64, "0123456789abcdefghijklmn"):
            salt = new_salt()
            result = subprocess.run(
                ["openssl", "passwd", "-6", "-salt", salt, "-stdin"],
                input=password, capture_output=True, text=True,
            )
            if result.returncode != 0:
                self.skipTest("this openssl has no passwd -6")
            with self.subTest(password=password):
                self.assertEqual(sha512_crypt(password, salt), result.stdout.strip())


if __name__ == "__main__":
    unittest.main()
