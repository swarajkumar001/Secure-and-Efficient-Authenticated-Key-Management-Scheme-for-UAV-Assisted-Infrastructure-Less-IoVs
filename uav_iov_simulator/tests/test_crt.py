"""
Tests for the CRT group-key phase (Steps GD1-GD6, DU1-DU2).

These also serve as the evidence for the declared correction documented in
crypto/crt.py: read as integers, the paper's construction is correct and every
property it claims for this phase holds.
"""

from __future__ import annotations

import random

import pytest

from uav_iov_simulator.crypto import crt


def _shares(n: int, seed: int = 3) -> dict[str, crt.CRTShare]:
    rng = random.Random(seed)
    seeds = {f"UAV{i+1}": rng.randrange(1 << 60) for i in range(n)}
    return crt.build_shares(seeds)


# ---------------------------------------------------------------------------
# The construction works
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("n", [1, 2, 3, 8, 20])
def test_every_member_recovers_the_same_key(n):
    """Step GD6: kappa = Lambda(sigma_i) mod sigma_i, for every member."""
    shares = _shares(n)
    kappa = min(s.modulus for s in shares.values()) - 12345
    bc = crt.build_lambda(shares.values(), kappa)

    for share in shares.values():
        assert crt.recover(bc, share) == kappa


def test_moduli_are_pairwise_coprime():
    """Required for phi_i = omega_i^(-1) mod sigma_i to exist at all.

    The paper does not state this requirement; deriving primes guarantees it.
    """
    from math import gcd
    shares = list(_shares(12).values())
    for i, a in enumerate(shares):
        for b in shares[i + 1:]:
            assert gcd(a.modulus, b.modulus) == 1


def test_key_must_be_smaller_than_every_modulus():
    """Otherwise Step GD6 wraps around and recovery is wrong. We raise instead
    of silently returning a bad key."""
    shares = _shares(4)
    too_big = max(s.modulus for s in shares.values()) + 1
    with pytest.raises(ValueError):
        crt.build_lambda(shares.values(), too_big)


# ---------------------------------------------------------------------------
# Revocation - the property that makes this scheme worth keeping
# ---------------------------------------------------------------------------
def test_revoked_member_cannot_recover_the_new_key():
    """Steps DU1-DU2: rebuild Lambda without the revoked modulus."""
    shares = _shares(6)
    names = list(shares)
    kappa1 = min(s.modulus for s in shares.values()) - 99
    bc1 = crt.build_lambda(shares.values(), kappa1)
    assert all(crt.recover(bc1, s) == kappa1 for s in shares.values())

    revoked = names[2]
    survivors = [n for n in names if n != revoked]
    kappa2 = min(shares[n].modulus for n in survivors) - 777
    bc2 = crt.rebuild_after_change(shares, survivors, kappa2, epoch=2)

    for n in survivors:
        assert crt.recover(bc2, shares[n]) == kappa2
    assert crt.recover(bc2, shares[revoked]) != kappa2


def test_survivors_need_no_new_key_material():
    """The elegant part of the paper: revocation sends nothing to the members
    who remain. Their sigma_i is unchanged; only the broadcast differs."""
    shares = _shares(5)
    names = list(shares)
    before = {n: shares[n].modulus for n in names}

    survivors = names[:-1]
    kappa2 = min(shares[n].modulus for n in survivors) - 55
    crt.rebuild_after_change(shares, survivors, kappa2, epoch=2)

    after = {n: shares[n].modulus for n in names}
    assert before == after, "no member's private material may change on revocation"


def test_joining_member_gets_the_new_key():
    """Step DU1 also covers new participation."""
    shares = _shares(4)
    names = list(shares)
    newcomer = crt.build_shares({"UAV99": 0xABCDEF1234567})["UAV99"]
    shares["UAV99"] = newcomer

    active = names + ["UAV99"]
    kappa = min(shares[n].modulus for n in active) - 31
    bc = crt.rebuild_after_change(shares, active, kappa, epoch=3)

    assert crt.recover(bc, newcomer) == kappa
    for n in names:
        assert crt.recover(bc, shares[n]) == kappa


# ---------------------------------------------------------------------------
# An honest observation the paper does not make
# ---------------------------------------------------------------------------
def test_broadcast_size_grows_quadratically():
    """The coefficients of Lambda grow with the product of all moduli, so the
    single broadcast is O(n^2) bits overall.

    Table V of the paper accounts for the per-message fields but not for this.
    We measure it rather than assume it away - it is a real cost of the
    'one broadcast for everyone' design.
    """
    small = crt.build_lambda(_shares(5, seed=1).values(), 101)
    large = crt.build_lambda(_shares(20, seed=1).values(), 101)

    assert large.size_bytes > small.size_bytes
    ratio = large.size_bytes / small.size_bytes
    assert ratio > 8, f"expected superlinear growth, got ratio {ratio:.1f}"
