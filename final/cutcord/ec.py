"""Group operations and hashing shared by both schemes.

G1 of BN254 (py_ecc.optimized_bn128) is the elliptic-curve group G of our scheme and
the group G1 of the base scheme. The base scheme's symmetric pairing e: G1 x G1 -> G2
is realised with the asymmetric BN pairing by keeping a G2 copy of the generator; the
TA, which knows every scalar involved, places the right-hand argument in G2.
"""
import hashlib
import secrets

from py_ecc import optimized_bn128 as bn

q = bn.curve_order
P = bn.G1                    # generator of G (our scheme) / G1 (base scheme)
P2 = bn.G2                   # generator of the G2 copy used for the base scheme's pairing
O = bn.Z1                    # point at infinity

# ---- counters: every protocol step reports what it computed ----
COUNT = {"mul": 0, "small_mul": 0, "add": 0, "pairing": 0, "gt_exp": 0, "mul_g2": 0}


def reset_counts():
    for k in COUNT:
        COUNT[k] = 0


def mul(pt, k):
    k %= q
    COUNT["mul"] += 1
    return bn.multiply(pt, k)


def small_mul(pt, k):
    COUNT["small_mul"] += 1
    return bn.multiply(pt, k)


def mul_g2(pt, k):
    COUNT["mul_g2"] += 1
    return bn.multiply(pt, k % q)


def add(a, b):
    COUNT["add"] += 1
    return bn.add(a, b)


def neg(a):
    return bn.neg(a)


def eq(a, b):
    return bn.eq(a, b)


def pairing(g2_pt, g1_pt):
    COUNT["pairing"] += 1
    return bn.pairing(g2_pt, g1_pt)


def gt_exp(x, k):
    COUNT["gt_exp"] += 1
    return x ** (k % q)


def rand_scalar():
    return secrets.randbelow(q - 1) + 1


def enc_point(pt):
    """canonical affine encoding (used inside hashes and KDF inputs)"""
    if bn.is_inf(pt):
        return b"\x00" * 64
    x, y = bn.normalize(pt)
    return int(x).to_bytes(32, "big") + int(y).to_bytes(32, "big")


def _enc(item):
    if isinstance(item, bytes):
        return item
    if isinstance(item, str):
        return item.encode()
    if isinstance(item, int):
        return item.to_bytes((max(item.bit_length(), 1) + 7) // 8, "big")
    if isinstance(item, tuple) and len(item) == 3:      # Jacobian point
        return enc_point(item)
    raise TypeError(type(item))


def H(tag, *items, out=32):
    """domain-separated SHA-256 over length-prefixed items"""
    h = hashlib.sha256(tag.encode() + b"|")
    for it in items:
        b = _enc(it)
        h.update(len(b).to_bytes(4, "big") + b)
    return h.digest()[:out]


def Hq(tag, *items):
    """hash to Z_q^*"""
    return int.from_bytes(hashlib.sha512(H(tag, *items)).digest(), "big") % (q - 1) + 1


# ---- sizes used for measured byte accounting ----
SIZE = {"G": 33, "G1": 33, "GT": 384, "Zq": 32, "hash": 32, "ts": 8, "tag": 16, "nonce": 12, "id": 16}
