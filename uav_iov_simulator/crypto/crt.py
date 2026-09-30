"""
Group key distribution by the Chinese Remainder Theorem - Steps GD1, GD2, GD6
and DU1, DU2 of the paper.

------------------------------------------------------------------------------
A DECLARED CORRECTION TO THE PAPER
------------------------------------------------------------------------------
The paper overloads the symbol sigma_i.  In Step GA2 it is a point:

        sigma_i = h1(s_i * xi_i) * P                     (an element of G1)

and psi_i = e(Gamma_i + h1(s_i xi_i) P, P) uses it that way, which is consistent.

But Step GD1 then writes

        omega_i = PRODUCT over j != i of sigma_j
        phi_i   = omega_i^(-1)  mod sigma_i

and Step GD6 computes

        kappa_tu = Lambda(sigma_i)  mod sigma_i

None of those three operations is defined for an elliptic-curve point: you
cannot multiply points together, you cannot invert modulo a point, and you
cannot reduce modulo a point.  For the group-key phase to typecheck at all,
sigma_i must be an INTEGER there.

Our interpretation, which we state openly rather than paper over:

    sigma_i^point   = h1(s_i * xi_i) * P        used in GA2  (unchanged)
    sigma_i^int     = a prime derived from h1(s_i * xi_i)    used in GD1-GD6

with the primes made pairwise distinct, which guarantees the pairwise
coprimality that phi_i = omega_i^(-1) mod sigma_i silently requires.

Under that reading the paper's construction is CORRECT and we implement it
verbatim.  The recovery works because

    Lambda(x)  =  kappa_tu * SUM_i (omega_i * phi_i)  +  PRODUCT_i (x - sigma_i)

evaluated at x = sigma_i kills the product term, and modulo sigma_i every
omega_j * phi_j with j != i vanishes (omega_j contains sigma_i as a factor)
while omega_i * phi_i == 1 by construction.  So

    Lambda(sigma_i) mod sigma_i  ==  kappa_tu       provided kappa_tu < sigma_i

which is exactly what Step GD6 claims.

------------------------------------------------------------------------------
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

from sympy import nextprime

from .. import config


@dataclass
class CRTShare:
    """One member's private CRT material."""
    uav_id: str
    modulus: int          # sigma_i as an integer (see module docstring)

    @property
    def bits(self) -> int:
        return self.modulus.bit_length()


@dataclass
class CRTBroadcast:
    """What Step GD4 actually puts on the air: only the coefficients."""
    coefficients: list[int] = field(default_factory=list)
    epoch: int = 0
    member_ids: list[str] = field(default_factory=list)

    @property
    def n_members(self) -> int:
        return len(self.member_ids)

    @property
    def size_bytes(self) -> int:
        """Honest byte count of the broadcast.

        Worth noticing: the coefficients of Lambda grow with the product of all
        moduli, so this broadcast is O(n^2) bits in total. The paper's Table V
        does not account for it. We report it rather than assume it away.
        """
        return sum(max(1, (abs(c).bit_length() + 7) // 8) for c in self.coefficients)


def derive_modulus(seed: int, *, bits: int = config.CRT_MODULUS_BITS,
                   taken: set[int] | None = None) -> int:
    """Derive sigma_i^int from h1(s_i * xi_i).

    A prime is chosen so that the moduli are pairwise coprime, which Step GD1
    requires for phi_i = omega_i^(-1) mod sigma_i to exist.
    """
    taken = taken or set()
    base = (seed % (1 << bits)) | (1 << (bits - 1))   # force the top bit
    candidate = int(nextprime(base))
    while candidate in taken:
        candidate = int(nextprime(candidate))
    return candidate


def build_shares(seeds: dict[str, int], *, bits: int = config.CRT_MODULUS_BITS
                 ) -> dict[str, CRTShare]:
    """Step GD1 - one integer modulus per authenticated UAV."""
    taken: set[int] = set()
    shares: dict[str, CRTShare] = {}
    for uav_id, seed in seeds.items():
        m = derive_modulus(seed, bits=bits, taken=taken)
        taken.add(m)
        shares[uav_id] = CRTShare(uav_id=uav_id, modulus=m)
    return shares


def _poly_from_roots(roots: Sequence[int]) -> list[int]:
    """Expand PRODUCT (x - r) into coefficient list, lowest power first."""
    coeffs = [1]
    for r in roots:
        new = [0] * (len(coeffs) + 1)
        for i, c in enumerate(coeffs):
            new[i + 1] += c          # x * c
            new[i] -= c * r          # -r * c
        coeffs = new
    return coeffs


def build_lambda(shares: Iterable[CRTShare], kappa: int) -> CRTBroadcast:
    """Steps GD1-GD2 - construct Lambda(x) and extract its coefficients.

        omega_i = PRODUCT_{j != i} sigma_j
        phi_i   = omega_i^(-1) mod sigma_i
        Lambda(x) = kappa * SUM_i(omega_i * phi_i) + PRODUCT_i(x - sigma_i)
    """
    shares = list(shares)
    if not shares:
        raise ValueError("cannot build a group key for an empty member set")

    moduli = [s.modulus for s in shares]
    total = 1
    for m in moduli:
        total *= m

    if kappa >= min(moduli):
        raise ValueError(
            f"group key {kappa} must be smaller than the smallest modulus "
            f"{min(moduli)}; recovery would wrap around"
        )

    crt_term = 0
    for m in moduli:
        omega = total // m
        phi = pow(omega, -1, m)         # omega^{-1} mod m  (Python 3.8+)
        crt_term += omega * phi

    coeffs = _poly_from_roots(moduli)   # PRODUCT (x - sigma_i)
    coeffs[0] += kappa * crt_term       # add the constant CRT term

    return CRTBroadcast(
        coefficients=coeffs,
        member_ids=[s.uav_id for s in shares],
    )


def evaluate(coefficients: Sequence[int], x: int) -> int:
    """Horner evaluation of Lambda(x)."""
    acc = 0
    for c in reversed(coefficients):
        acc = acc * x + c
    return acc


def recover(broadcast: CRTBroadcast, share: CRTShare) -> int:
    """Step GD6 - a member recovers the group key.

        kappa_tu = Lambda(sigma_i) mod sigma_i

    A revoked member still computes something; it simply will not equal the
    current group key.  That is the behaviour the revocation demo relies on.
    """
    return evaluate(broadcast.coefficients, share.modulus) % share.modulus


def rebuild_after_change(all_shares: dict[str, CRTShare],
                         active_ids: Iterable[str],
                         new_kappa: int,
                         epoch: int) -> CRTBroadcast:
    """Steps DU1-DU2 - batch join and batch revocation.

    Lambda is rebuilt over the surviving members only.  Crucially, the survivors
    need no new key material: their sigma_i is unchanged and they simply
    evaluate the new broadcast.  That property is the reason the paper's key
    management is worth keeping, and it is preserved here.
    """
    active = [all_shares[i] for i in active_ids if i in all_shares]
    bc = build_lambda(active, new_kappa)
    bc.epoch = epoch
    return bc
