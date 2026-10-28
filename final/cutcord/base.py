"""The base scheme of Tan, Zheng & Vijayakumar (IEEE T-ITS 24(6), 2023), Section IV.

Implemented as printed, with two declared readings that the paper leaves open:
  * the decrypting key sigma_i is a point in GA2 but a CRT modulus in GD1-GD6; for GD we use
    sigma_int = nextprime(H(sigma_i)) of 160 bits (pairwise coprime, kappa < min sigma_int);
  * GA1 does not list Gamma_i although GA2 needs it; we forward it.
The TA <-> TUAV satellite link is modelled by `Link` (availability A, round-trip time).
"""
import random
from math import prod

import sympy

from . import ec
from .ec import P, P2, q, mul, mul_g2, add, neg, eq, pairing, gt_exp, rand_scalar, SIZE

h1 = lambda *a: ec.Hq("h1", *a)
h2 = lambda *a: ec.Hq("h2", *a)
h3 = lambda *a: ec.Hq("h3", *a)
h4 = lambda *a: ec.Hq("h4", *a)
HH1 = lambda *a: ec.H("H1", *a)
SIGMA_BITS = 160


class Link:
    def __init__(self, availability=1.0, rtt_ms=0.0, rng=None):
        self.A, self.rtt, self.rng = availability, rtt_ms, rng or random.Random()
        self.round_trips = 0

    def up(self):
        return self.rng.random() < self.A


class BaseTA:
    def __init__(self):
        self.db = {}                     # id_i -> s_i  (and the TUAV's)

    def register_tuav(self, id_tu):
        s = rand_scalar(); self.db[id_tu] = s; self.s_tu = s; self.s_tu_P2 = mul_g2(P2, s)
        return s                                                                   # IS1

    def register_uav(self, id_i):
        s = rand_scalar(); self.db[id_i] = (s, mul_g2(P2, s)); return s           # IS2

    # GA2 -- the TA resolves each pseudonym and computes all pairings
    def ga2(self, uploads, ids):
        out = []
        for (ts2, ID_i, xi, ups, Gamma), id_i in zip(uploads, ids):
            s_i, s_i_P2 = self.db[id_i]
            assert h3(id_i, ts2, xi) == ID_i, "pseudonym does not resolve"
            k = h1(s_i * xi % q)
            sigma = mul(P, k)
            psi = pairing(P2, add(Gamma, sigma))
            mu = pairing(s_i_P2, mul(P, h3(ID_i, ts2, s_i)))
            delta = pairing(self.s_tu_P2, mul(P, ups * xi % q))
            out.append((sigma, psi, mu, delta))
        return out


class BaseTUAV:
    def __init__(self, id_tu, s_tu):
        self.id_tu, self.s_tu = id_tu, s_tu

    def is4(self, now):                                                            # IS4-IS5
        self.r_tu = rand_scalar(); self.ts_tu = now
        self.ID_tu = h2(self.id_tu, self.r_tu)
        self.R_tu = self.r_tu * h2(now, self.s_tu) % q
        self.Q_tu = mul(P, self.s_tu * h2(self.ID_tu, self.r_tu))
        return (now, self.ID_tu, self.R_tu, self.Q_tu)

    # GA3 -- one product equation over everything the TA returned
    def ga3(self, results):
        h = h2(self.ID_tu, self.r_tu)
        lhs, dprod, rhs = ec.bn.FQ12.one(), ec.bn.FQ12.one(), ec.bn.FQ12.one()
        for _, psi, mu, delta in results:
            lhs *= psi; dprod *= delta; rhs *= mu
        return gt_exp(dprod, h) * lhs == gt_exp(rhs, self.R_tu)

    def ga3_single(self, res):
        _, psi, mu, delta = res
        return psi * gt_exp(delta, h2(self.ID_tu, self.r_tu)) == gt_exp(mu, self.R_tu)


class BaseUAV:
    def __init__(self, id_i, s_i):
        self.id_i, self.s_i = id_i, s_i

    def us(self, beacon, now):                                                     # US1-US3
        ts_tu, ID_tu, R_tu, Q_tu = beacon
        self.r_i = rand_scalar(); self.xi = h1(self.r_i); self.ts2 = now
        self.ID_i = h3(self.id_i, now, self.xi)
        ups = h4(self.ID_i, ID_tu, now, self.xi)
        a = (self.s_i * h3(self.ID_i, now, self.s_i) * R_tu - h1(self.s_i * self.xi % q)) % q
        Gamma = add(mul(P, a), neg(mul(Q_tu, ups * h1(self.r_i))))
        self.Q_tu = Q_tu
        return (now, self.ID_i, self.xi, ups, Gamma)

    def gd5(self, ack):
        ts3, ID_i, S_i, coeffs = ack
        k = h1(self.s_i * self.xi % q)
        if HH1(ts3, ID_i, mul(self.Q_tu, k)) != S_i:
            return None
        self.sigma_int = sigma_int(mul(P, k))
        return eval_poly(coeffs, self.sigma_int) % self.sigma_int


# ---------------- GD1-GD6 / DU1-DU2 (CRT) ----------------
def sigma_int(sigma_point):
    return sympy.nextprime(int.from_bytes(ec.H("sigma", sigma_point), "big") >> (256 - SIGMA_BITS) | (1 << (SIGMA_BITS - 1)))


def crt_poly(moduli, kappa):
    """coefficients a_0..a_n of Lambda(x) = kappa * sum(omega_i phi_i) + prod(x - sigma_i)"""
    M = prod(moduli)
    C = kappa * sum((M // s) * pow(M // s, -1, s) for s in moduli)
    coeffs = [1]                                        # highest degree first
    for s in moduli:
        coeffs = [a - s * b for a, b in zip(coeffs + [0], [0] + coeffs)]
    coeffs[-1] += C
    return coeffs[::-1]                                 # a_0 first


def eval_poly(coeffs, x):
    acc = 0
    for a in reversed(coeffs):
        acc = acc * x + a
    return acc


def coeff_bytes(coeffs):
    return sum((abs(c).bit_length() + 8) // 8 for c in coeffs)


def gd(tuav, results, ids_pseudo, now):
    """GD1-GD4: returns (kappa, coeffs, acks)"""
    moduli = [sigma_int(r[0]) for r in results]
    kappa = random.getrandbits(SIGMA_BITS - 2) | 1
    coeffs = crt_poly(moduli, kappa)
    h = h2(tuav.ID_tu, tuav.r_tu)
    acks = [(now, ID_i, HH1(now, ID_i, mul(r[0], tuav.s_tu * h)), coeffs) for r, ID_i in zip(results, ids_pseudo)]
    return kappa, coeffs, acks, moduli


# ---------------- sizes (measured accounting, compressed G1 points, GT = 384 B) ----------------
REQ_SIZE = SIZE["ts"] + 3 * SIZE["hash"] + SIZE["G1"]                 # <ts2, ID, xi, upsilon, Gamma>
UP_SIZE = REQ_SIZE                                                    # GA1 upload incl. Gamma
DOWN_SIZE = SIZE["G1"] + 3 * SIZE["GT"]                               # GA2 <sigma, psi, mu, delta>
BEACON_SIZE = SIZE["ts"] + 2 * SIZE["hash"] + SIZE["G1"]


# ---------------- attacks ----------------
def ta_forge(ta, beacon, id_i, now):
    """Finding 2: the TA builds a valid request for UAV id_i without the UAV"""
    s_i, _ = ta.db[id_i]
    return BaseUAV(id_i, s_i).us(beacon, now)


def revocation_attack(coeffs_old, my_sigma, coeffs_new):
    """Finding 4: a member recovers every sigma from Lambda, then opens the post-revocation polynomial"""
    C = eval_poly(coeffs_old, my_sigma)
    g = list(coeffs_old); g[0] -= C                      # = prod (x - sigma_i)
    x = sympy.symbols("x")
    poly = sympy.Poly(list(reversed(g)), x)
    roots = [int(r) for r in poly.ground_roots()]
    # every staying member's sigma yields the same value; removed members' sigmas yield noise
    votes = {}
    for s in roots:
        if s != my_sigma:
            k = eval_poly(coeffs_new, s) % s
            votes[k] = votes.get(k, 0) + 1
    best = max(votes.items(), key=lambda kv: kv[1]) if votes else (None, 0)
    return (best[0] if best[1] >= 2 else None), roots
