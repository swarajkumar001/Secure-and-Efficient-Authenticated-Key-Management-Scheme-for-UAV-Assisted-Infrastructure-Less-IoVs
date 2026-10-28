"""The base scheme works as printed -- and the findings of the Phase-2 analysis reproduce."""
import random
import pytest

from cutcord import base, ec

NOW = 2_000


@pytest.fixture(scope="module")
def run():
    ta = base.BaseTA()
    tu = base.BaseTUAV("tuav", ta.register_tuav("tuav"))
    ids = [f"uav-{i}" for i in range(5)]
    uavs = [base.BaseUAV(i, ta.register_uav(i)) for i in ids]
    beacon = tu.is4(NOW)
    reqs = [u.us(beacon, NOW) for u in uavs]
    res = ta.ga2(reqs, ids)
    return ta, tu, ids, uavs, beacon, reqs, res


def test_ga3_accepts_honest_batch(run):
    ta, tu, ids, uavs, beacon, reqs, res = run
    assert tu.ga3(res) and all(tu.ga3_single(r) for r in res)


def test_crt_key_distribution(run):
    ta, tu, ids, uavs, beacon, reqs, res = run
    kappa, coeffs, acks, moduli = base.gd(tu, res, [r[1] for r in reqs], NOW)
    assert all(u.gd5(a) == kappa for u, a in zip(uavs, acks))


def test_finding2_ta_forges_any_uav(run):
    ta, tu, ids, uavs, beacon, reqs, res = run
    forged = base.ta_forge(ta, beacon, ids[0], NOW)          # no UAV involved
    out = ta.ga2([forged], [ids[0]])
    assert tu.ga3(out)


def test_finding5_batch_cancellation(run):
    ta, tu, ids, uavs, beacon, reqs, res = run
    D = ec.mul(ec.P, 987654321)
    r0, r1 = list(reqs[0]), list(reqs[1])
    r0[4] = ec.add(r0[4], D); r1[4] = ec.add(r1[4], ec.neg(D))
    out = ta.ga2([tuple(r0), tuple(r1)] + reqs[2:], ids)
    assert tu.ga3(out)                                         # batch passes
    assert not tu.ga3_single(out[0]) and not tu.ga3_single(out[1])   # both are invalid


def test_finding1_one_bad_request_rejects_all(run):
    ta, tu, ids, uavs, beacon, reqs, res = run
    r0 = list(reqs[0]); r0[4] = ec.add(r0[4], ec.P)
    out = ta.ga2([tuple(r0)] + reqs[1:], ids)
    assert not tu.ga3(out)                                     # GA4 has no else-branch


def test_finding4_revoked_member_recovers_new_key():
    random.seed(5)
    moduli = [base.sympy.randprime(2**159, 2**160) for _ in range(8)]
    kappa = random.getrandbits(158)
    old = base.crt_poly(moduli, kappa)
    stay = moduli[:3] + moduli[5:]
    kappa2 = random.getrandbits(158)
    new = base.crt_poly(stay, kappa2)
    revoked_sigma = moduli[3]
    assert base.eval_poly(new, revoked_sigma) % revoked_sigma != kappa2       # own key fails ...
    got, roots = base.revocation_attack(old, revoked_sigma, new)
    assert sorted(roots) == sorted(moduli) and got == kappa2                  # ... a stolen one works
