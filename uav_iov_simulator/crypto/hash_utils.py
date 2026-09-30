"""
The five hash functions the paper declares in Step IS3.

The paper (Step IS3) defines:

    H1 : {0,1}* x {0,1}* x G1  -> Z_q
    h1 : {0,1}*                -> Z_q
    h2 : {0,1}* x {0,1}*       -> Z_q
    h3 : {0,1}* x {0,1}* x {0,1}* -> Z_q
    h4 : {0,1}* x {0,1}* x {0,1}* x {0,1}* -> Z_q

All five are instantiated here from SHA-256 with *domain separation* - each
function prefixes a distinct tag before hashing, so that h1(x) and h2(x, y) can
never collide by accident.  The paper does not specify an instantiation; this is
a standard and conservative choice.
"""

from __future__ import annotations

import hashlib
from typing import Any


def _encode(part: Any) -> bytes:
    """Encode one argument unambiguously (length-prefixed, so concatenation
    cannot be confused)."""
    if isinstance(part, bytes):
        raw = part
    elif isinstance(part, str):
        raw = part.encode("utf-8")
    elif isinstance(part, bool):
        raw = b"\x01" if part else b"\x00"
    elif isinstance(part, int):
        n = max(1, (part.bit_length() + 7) // 8)
        raw = part.to_bytes(n, "big", signed=part < 0)
    elif isinstance(part, float):
        raw = repr(part).encode("ascii")
    else:
        raw = repr(part).encode("utf-8")
    return len(raw).to_bytes(4, "big") + raw


def _digest_int(tag: bytes, parts: tuple, order: int) -> int:
    """SHA-256 over the tag and the length-prefixed parts, reduced mod order.

    Rejection is unnecessary here: the bias from reducing a 256-bit digest mod a
    256-bit prime is negligible for a simulator, and we note it rather than
    pretend otherwise.
    """
    h = hashlib.sha256()
    h.update(len(tag).to_bytes(4, "big") + tag)
    for p in parts:
        h.update(_encode(p))
    value = int.from_bytes(h.digest(), "big")
    return value % order


# --------------------------------------------------------------------------
# The five functions of Step IS3
# --------------------------------------------------------------------------

def h1(x: Any, *, order: int) -> int:
    """h1 : {0,1}* -> Z_q.  Used for xi_i = h1(r_i) and for h1(s_i * xi_i)."""
    return _digest_int(b"TUAV-IoV/h1", (x,), order)


def h2(a: Any, b: Any, *, order: int) -> int:
    """h2 : {0,1}* x {0,1}* -> Z_q.  Used for ID_tu and for R_tu, Q_tu."""
    return _digest_int(b"TUAV-IoV/h2", (a, b), order)


def h3(a: Any, b: Any, c: Any, *, order: int) -> int:
    """h3 : {0,1}* x {0,1}* x {0,1}* -> Z_q.  Used for ID_i and inside Gamma_i."""
    return _digest_int(b"TUAV-IoV/h3", (a, b, c), order)


def h4(a: Any, b: Any, c: Any, d: Any, *, order: int) -> int:
    """h4 : {0,1}*^4 -> Z_q.  Used for upsilon_i = h4(ID_i, ID_tu, ts2, xi_i)."""
    return _digest_int(b"TUAV-IoV/h4", (a, b, c, d), order)


def H1(a: Any, b: Any, c: Any, *, order: int) -> int:
    """H1 : {0,1}* x {0,1}* x G1 -> Z_q.  Used for the acknowledgment S_i in
    Step GD3, which is what gives the UAV mutual authentication of the TUAV."""
    return _digest_int(b"TUAV-IoV/H1", (a, b, c), order)


# --------------------------------------------------------------------------
# Display helper
# --------------------------------------------------------------------------

def fingerprint(value: Any, length: int = 8) -> str:
    """A short, stable, non-reversible label for the UI.

    Permanent identities and secrets are never rendered; this is what the tables
    show instead, so that a viewer can follow an entity across sessions without
    the simulator leaking the value.
    """
    h = hashlib.sha256(_encode(value)).hexdigest().upper()
    return h[:length]
