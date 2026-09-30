"""
Secure data exchange under the group key.

SCOPE NOTE
----------
The paper establishes a group key kappa_tu and stops there - it does not specify
a bulk cipher, and Section VI costs no data-plane encryption at all.  AES-GCM is
OUR choice, made so that the demonstration is real rather than mimed: the
"ACCESS DENIED" for a revoked member is a genuine AEAD tag failure, not a
string comparison the simulator decided to fail.

The group key is an integer of roughly 64 bits in this simulator (it must be
smaller than every CRT modulus - see crypto/crt.py). That is a demonstration
parameter, not a deployment one: a real system would size the moduli so that
kappa_tu carries at least 128 bits of entropy. We state that rather than let a
viewer assume otherwise.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    _AVAILABLE = True
except Exception:  # pragma: no cover
    _AVAILABLE = False


KEY_ENTROPY_NOTE = (
    "kappa_tu is ~64 bits here because it must be smaller than every CRT "
    "modulus. Demonstration parameter, not a deployment one."
)


@dataclass
class Envelope:
    """What actually travels between a vehicle and a UAV."""
    nonce: bytes
    ciphertext: bytes
    epoch: int
    aad: bytes = b""

    @property
    def size_bytes(self) -> int:
        return len(self.nonce) + len(self.ciphertext)

    def hex_preview(self, n: int = 32) -> str:
        h = self.ciphertext.hex().upper()
        return h[:n] + ("..." if len(h) > n else "")


def derive_aes_key(group_key: int, *, epoch: int = 0) -> bytes:
    """Stretch the integer group key into a 256-bit AES key.

    Binding the epoch in means that even if two epochs ever produced the same
    kappa_tu, the derived traffic keys would still differ.
    """
    material = (
        b"TUAV-IoV/groupkey/v1"
        + int(group_key).to_bytes(32, "big", signed=False)
        + int(epoch).to_bytes(4, "big")
    )
    return hashlib.sha256(material).digest()


def available() -> bool:
    return _AVAILABLE


def encrypt(group_key: int, plaintext: bytes, *, epoch: int = 0,
            aad: bytes = b"") -> Envelope:
    """Encrypt under the current group key."""
    if not _AVAILABLE:
        raise RuntimeError("the `cryptography` package is required for AES-GCM")
    key = derive_aes_key(group_key, epoch=epoch)
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, plaintext, aad or None)
    return Envelope(nonce=nonce, ciphertext=ct, epoch=epoch, aad=aad)


def try_decrypt(group_key: int | None, envelope: Envelope) -> bytes | None:
    """Attempt decryption. Returns None on failure rather than raising.

    A wrong key fails the GCM authentication tag, so the result is rejection
    rather than plausible-looking garbage. That distinction is the whole reason
    to use an AEAD here.
    """
    if not _AVAILABLE or group_key is None:
        return None
    key = derive_aes_key(group_key, epoch=envelope.epoch)
    try:
        return AESGCM(key).decrypt(envelope.nonce, envelope.ciphertext,
                                   envelope.aad or None)
    except Exception:
        return None


@dataclass
class ExchangeResult:
    message: str
    envelope: Envelope
    opened_by: list[str]
    denied: list[str]

    @property
    def summary(self) -> str:
        return (f"{len(self.opened_by)} member(s) decrypted the message; "
                f"{len(self.denied)} could not.")


def broadcast_to_group(sim_state, message: str) -> ExchangeResult | None:
    """Encrypt one message under the current group key and let every UAV try.

    Members holding the current key open it. Revoked members, and any UAV that
    never completed key distribution, do not.
    """
    tuav = sim_state.tuav
    if tuav is None or tuav.group_key is None:
        return None

    env = encrypt(tuav.group_key, message.encode("utf-8"), epoch=tuav.key_epoch)

    opened, denied = [], []
    for u in sim_state.uavs:
        plain = try_decrypt(u.group_key, env)
        (opened if plain == message.encode("utf-8") else denied).append(u.name)

    return ExchangeResult(message=message, envelope=env,
                          opened_by=opened, denied=denied)
