"""
ABSTRACTED backend - a toy bilinear group, not elliptic curves.

What it is
----------
G1 is modelled by the exponents themselves: the element k*P is represented by
the integer k mod q.  The target group is Z*_p, and the map

        e(aP, bP) := g ** (a*b mod q)  mod p

is *genuinely bilinear*, because g has order q in Z*_p.  That matters: it means
the paper's verification equation balances here for exactly the same algebraic
reason it balances on a real curve, and it fails for exactly the same reasons.
The all-or-nothing batch behaviour, the revocation behaviour and the replay
behaviour are all reproduced faithfully.

What it is NOT
--------------
It is not secure.  The discrete logarithm is trivial, because the simulator
stores the scalars directly - an "attacker" inside this process could read them
out of memory.  That is fine: this backend exists so that experiments up to
n = 1000 run instantly, not to provide security.  Anything claiming a security
property should be demonstrated on the faithful backend as well.

The UI labels this backend ABSTRACTED at all times.
"""

from __future__ import annotations

from .. import config
from .interface import Backend, OpCount


class AbstractBackend(Backend):

    NAME = "toy-bilinear (Z*_p)"
    FIDELITY = "ABSTRACTED"
    NOTE = (
        "G1 elements are represented by their scalars; the pairing is realised "
        "as exponentiation in Z*_p. Genuinely bilinear, so the protocol algebra "
        "and its failure modes are exact."
    )
    SECURITY_NOTE = (
        "NOT cryptographically secure - the discrete logarithm is trivial here. "
        "Use the faithful backend for any claim about hardness."
    )

    def __init__(self) -> None:
        self.order = config.TOY_Q
        self.p = config.TOY_P
        self.g = config.TOY_G
        self.counter = OpCount()

    # ---------------------------------------------------------------- G1 ----
    def g1_mul(self, k: int):
        self.counter.g1_mul += 1
        return k % self.order

    def g1_add(self, a, b):
        self.counter.g1_add += 1
        return (a + b) % self.order

    def g1_sub(self, a, b):
        self.counter.g1_add += 1
        return (a - b) % self.order

    def g1_point_mul(self, a, k: int):
        self.counter.g1_mul += 1
        return (a * k) % self.order

    def g1_repr(self, a) -> str:
        return f"{a % self.order:064x}"[:16].upper() + "..."

    # ----------------------------------------------------------- pairing ----
    def pair_with_P(self, a):
        # e(aP, P) = g ** a
        self.counter.pairing += 1
        return pow(self.g, a % self.order, self.p)

    def e_PP_pow(self, k: int):
        # e(P, P) ** k = g ** k
        self.counter.gt_pow += 1
        return pow(self.g, k % self.order, self.p)

    # ---------------------------------------------------------------- GT ----
    def gt_mul(self, a, b):
        self.counter.gt_mul += 1
        return (a * b) % self.p

    def gt_pow(self, a, k: int):
        self.counter.gt_pow += 1
        return pow(a, k % self.order, self.p)

    def gt_eq(self, a, b) -> bool:
        return (a % self.p) == (b % self.p)

    def gt_one(self):
        return 1
