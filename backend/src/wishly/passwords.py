"""Password hashing with scrypt, from Python's standard library.

scrypt is deliberately slow and memory-hungry, so guessing passwords from a
stolen hash costs an attacker real time and hardware. Each hash gets its own
random salt, so two users with the same password get different hashes.

Stored format:  scrypt$<n>$<r>$<p>$<salt hex>$<hash hex>
Keeping the parameters in the string means they can be raised later without
breaking existing hashes.
"""

import hashlib
import hmac
import secrets

N, R, P = 2**14, 8, 1  # cost: ~16 MB of memory and ~50 ms per hash
KEY_LENGTH = 32


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=N, r=R, p=P, dklen=KEY_LENGTH)
    return f"scrypt${N}${R}${P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    _, n, r, p, salt, expected = stored.split("$")
    digest = hashlib.scrypt(
        password.encode(),
        salt=bytes.fromhex(salt),
        n=int(n),
        r=int(r),
        p=int(p),
        dklen=len(expected) // 2,
    )
    # Constant-time comparison: timing can't reveal how much of the hash matched.
    return hmac.compare_digest(digest.hex(), expected)


# Verified against when the email doesn't exist, so "no such user" takes as long
# as "wrong password" and response times can't reveal which emails are signed up.
DUMMY_HASH = hash_password(secrets.token_hex(16))
