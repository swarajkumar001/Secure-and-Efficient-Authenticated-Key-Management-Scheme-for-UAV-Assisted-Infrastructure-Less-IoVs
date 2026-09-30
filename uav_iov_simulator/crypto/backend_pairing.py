"""
FAITHFUL backend - real bilinear pairings on the BN128 curve via py_ecc.

This is genuine pairing-based cryptography: G1 is the BN128 curve group, the
target group is F_{p^12}, and `pair_with_P` evaluates a real Ate pairing on a
point that arrived over the simulated network.

Two honest notes
----------------
1. Curve.  The paper uses a supersingular curve at an 80-bit security level.
   py_ecc offers BN128 (roughly 100-bit by modern estimates).  The security
   level therefore differs from the paper and is reported in the UI.

2. The mu_i / delta_i shortcut.  For those two values the TA constructs *both*
   pairing arguments itself, so it knows both scalars.  Since

        e(aP, bP) = e(P, P) ** (a*b)

   the backend computes them as one target-group exponentiation instead of one
   pairing.  This is mathematically identical, is what any real implementation
   would do, and is documented rather than hidden.  psi_i is different: its
   first argument is the credential Gamma_i that arrived from the network, so it
   is evaluated as a true pairing.  That leaves exactly one real pairing per
   UAV, which is the operation the paper offloads to the TA.

Cost on a typical laptop (pure Python): one pairing is roughly 190 ms, one
target-group exponentiation roughly 12 ms, one target-group multiplication
roughly 0.03 ms.  The TUAV performs only the last two - which is precisely the
architectural point the paper is making.
"""

from __future__ import annotations

from .interface import Backend, OpCount

try:
    from py_ecc.optimized_bn128 import (
        G1, G2, add, multiply, neg, pairing, curve_order, normalize,
    )
    _AVAILABLE = True
    _IMPORT_ERROR = ""
except Exception as exc:  # pragma: no cover - environment dependent
    _AVAILABLE = False
    _IMPORT_ERROR = str(exc)


class PairingBackendUnavailable(RuntimeError):
    pass


class PairingBackend(Backend):

    NAME = "BN128 (py_ecc)"
    FIDELITY = "FAITHFUL"
    NOTE = (
        "Real bilinear pairings on the BN128 curve. One genuine pairing per UAV "
        "(psi_i, evaluated on the received credential); mu_i and delta_i use the "
        "documented e(P,P)**k identity."
    )
    SECURITY_NOTE = (
        "BN128 is roughly 100-bit security by modern estimates; the paper uses "
        "an 80-bit supersingular setup. Not the same parameter set."
    )

    def __init__(self) -> None:
        if not _AVAILABLE:
            raise PairingBackendUnavailable(
                "py_ecc is not installed - run `pip install py_ecc`. "
                f"Import error: {_IMPORT_ERROR}"
            )
        self.order = curve_order
        self.counter = OpCount()
        self._E = None  # e(P, P), computed lazily and cached

    # ---------------------------------------------------------------- G1 ----
    def g1_mul(self, k: int):
        self.counter.g1_mul += 1
        k %= self.order
        if k == 0:
            # py_ecc returns None for the point at infinity
            return None
        return multiply(G1, k)

    def g1_add(self, a, b):
        self.counter.g1_add += 1
        if a is None:
            return b
        if b is None:
            return a
        return add(a, b)

    def g1_sub(self, a, b):
        self.counter.g1_add += 1
        if b is None:
            return a
        nb = neg(b)
        if a is None:
            return nb
        return add(a, nb)

    def g1_point_mul(self, a, k: int):
        self.counter.g1_mul += 1
        k %= self.order
        if a is None or k == 0:
            return None
        return multiply(a, k)

    def g1_repr(self, a) -> str:
        if a is None:
            return "O (infinity)"
        x, y = normalize(a)
        return f"{int(x) % (1 << 64):016X}..."

    # ----------------------------------------------------------- pairing ----
    def _E_PP(self):
        if self._E is None:
            self.counter.pairing += 1
            self._E = pairing(G2, G1)
        return self._E

    def pair_with_P(self, a):
        """e(A, P) - a genuine pairing on a received point."""
        if a is None:
            return self.gt_one()
        self.counter.pairing += 1
        # py_ecc's pairing takes (Q in G2, P in G1)
        return pairing(G2, a)

    def e_PP_pow(self, k: int):
        """e(P, P) ** k - see the module docstring for why this is legitimate."""
        self.counter.gt_pow += 1
        return self._E_PP() ** (k % self.order)

    # ---------------------------------------------------------------- GT ----
    def gt_mul(self, a, b):
        self.counter.gt_mul += 1
        return a * b

    def gt_pow(self, a, k: int):
        self.counter.gt_pow += 1
        return a ** (k % self.order)

    def gt_eq(self, a, b) -> bool:
        return a == b

    def gt_one(self):
        return self._E_PP() ** 0


def is_available() -> bool:
    return _AVAILABLE


def unavailable_reason() -> str:
    return _IMPORT_ERROR
