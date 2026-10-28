"""Cutting the Cord -- the proposed framework (step labels follow the Phase-2 paper).

ST/RG  offline setup and registration (TA)
UA/RK  C1: beacon, signed join, local batch verification with bounded fallback,
       per-member group-key delivery, rekeying
VA     C2: vehicle admission relayed by authenticated UAVs, V2V protection
HO     C3: inter-TUAV link and ticket-based handover
TR     offline tracing and global revocation
"""
import os
import secrets
from dataclasses import dataclass, field

from . import ec, sym
from .ec import P, q, mul, small_mul, add, neg, eq, Hq, H, enc_point, rand_scalar, SIZE

RID_LEN = 16
LAMBDA_BITS = 64


# =====================================================================
# credentials and signatures
# =====================================================================
@dataclass
class Credential:
    ident: bytes          # pseudonym (PID1 || PID2) or a TUAV's public ID
    ep: int               # epoch index (0 for TUAVs)
    X: tuple
    Y: tuple
    d: int                # partial private key (TA-issued)
    x: int                # secret value (entity-only)
    PID1: tuple = None
    PID2: bytes = None

    @property
    def sk(self):
        return (self.x + self.d) % q

    @property
    def key(self):        # H3(PID): index used in lists and ACK entries
        return H("H3", self.ident, self.ep)


def h_bind(ident, ep, X, Y):
    return Hq("H1", ident, ep, X, Y)


def public_key(Ppub, ident, ep, X, Y):
    return add(add(X, Y), mul(Ppub, h_bind(ident, ep, X, Y)))


def challenge(msg, ident, ep, X, Y, R, ts):
    return Hq("H2", msg, ident, ep, X, Y, R, ts)


def sign(cred, msg, ts):
    r = rand_scalar()
    R = mul(P, r)
    c = challenge(msg, cred.ident, cred.ep, cred.X, cred.Y, R, ts)
    return R, (r + c * cred.sk) % q


def verify(Ppub, ident, ep, X, Y, msg, ts, R, v):
    c = challenge(msg, ident, ep, X, Y, R, ts)
    return eq(mul(P, v), add(R, mul(public_key(Ppub, ident, ep, X, Y), c)))


def batch_verify(Ppub, items):
    """small-exponent batch test (eq. 9). items: (ident, ep, X, Y, msg, ts, R, v)"""
    lhs_scalar, ppub_scalar = 0, 0
    rhs = ec.O
    for ident, ep, X, Y, msg, ts, R, v in items:
        lam = secrets.randbits(LAMBDA_BITS) | 1
        c = challenge(msg, ident, ep, X, Y, R, ts)
        h = h_bind(ident, ep, X, Y)
        lhs_scalar = (lhs_scalar + lam * v) % q
        ppub_scalar = (ppub_scalar + lam * c * h) % q
        rhs = add(rhs, small_mul(R, lam))
        rhs = add(rhs, mul(add(X, Y), lam * c))
    rhs = add(rhs, mul(Ppub, ppub_scalar))
    return eq(mul(P, lhs_scalar), rhs)


def schnorr_pop(x, X, rid):
    r = rand_scalar(); R = mul(P, r); c = Hq("POP", rid, X, R)
    return R, (r + c * x) % q


def schnorr_pop_ok(X, rid, R, v):
    return eq(mul(P, v), add(R, mul(X, Hq("POP", rid, X, R))))


# =====================================================================
# Phase 0: Trusted Authority (offline)
# =====================================================================
class TA:
    def __init__(self):
        self.s, self.t = rand_scalar(), rand_scalar()                       # ST1
        self.Ppub, self.Tpub = mul(P, self.s), mul(P, self.t)               # ST2
        self.registry = {}            # RID -> list of (ident, ep)
        self.records = {}             # RID -> signed RG1 records

    # RG1-RG4 for a pseudonymous entity (UAV or vehicle)
    def register(self, rid, m):
        assert len(rid) == RID_LEN
        xs = [rand_scalar() for _ in range(m)]                   # RG1: entity side
        Xs = [mul(P, x) for x in xs]
        pops = [schnorr_pop(x, X, rid) for x, X in zip(xs, Xs)]
        creds = []
        for ep, (x, X, pop) in enumerate(zip(xs, Xs, pops), start=1):   # RG2: TA side
            assert schnorr_pop_ok(X, rid, *pop)
            rho, y = rand_scalar(), rand_scalar()
            PID1 = mul(P, rho)
            PID2 = bytes(a ^ b for a, b in zip(rid, H("H0", mul(self.Tpub, rho), ep, out=RID_LEN)))
            Y = mul(P, y)
            ident = enc_point(PID1) + PID2
            d = (y + self.s * h_bind(ident, ep, X, Y)) % q
            c = Credential(ident, ep, X, Y, d, x, PID1, PID2)
            assert eq(mul(P, d), add(Y, mul(self.Ppub, h_bind(ident, ep, X, Y))))   # RG4
            creds.append(c)
        self.registry[rid] = [(c.ident, c.ep) for c in creds]
        self.records[rid] = [(X, pop) for X, pop in zip(Xs, pops)]
        return creds

    def register_tuav(self, tuav_id):
        x, y = rand_scalar(), rand_scalar()
        X, Y = mul(P, x), mul(P, y)
        ident = tuav_id.encode()
        d = (y + self.s * h_bind(ident, 0, X, Y)) % q
        return Credential(ident, 0, X, Y, d, x)

    # TR1
    def trace(self, PID1, PID2, ep):
        mask = H("H0", mul(PID1, self.t), ep, out=RID_LEN)
        return bytes(a ^ b for a, b in zip(PID2, mask))

    # TR2: hashes of all *remaining* pseudonyms of a revoked entity
    def revoke(self, rid, from_epoch):
        return {H("H3", ident, ep) for ident, ep in self.registry[rid] if ep >= from_epoch}


# =====================================================================
# messages
# =====================================================================
@dataclass
class Request:
    ident: bytes
    ep: int
    X: tuple
    Y: tuple
    E: tuple
    ts: int
    R: tuple
    v: int
    role: str = "join"

    def msg(self, tuav_id, E_a):
        return self.role.encode() + tuav_id + enc_point(E_a) + enc_point(self.E)

    @property
    def key(self):
        return H("H3", self.ident, self.ep)

    def to_bytes(self):
        return (self.ident + self.ep.to_bytes(4, "big") + enc_point(self.X) + enc_point(self.Y) + enc_point(self.E)
                + self.ts.to_bytes(8, "big") + enc_point(self.R) + self.v.to_bytes(32, "big") + self.role.encode())

    @staticmethod
    def size():   # compressed points
        return (SIZE["G"] + RID_LEN) + 4 + 4 * SIZE["G"] + SIZE["ts"] + SIZE["Zq"]


@dataclass
class Beacon:
    tuav_id: bytes
    X: tuple
    Y: tuple
    E: tuple
    ts: int
    R: tuple
    v: int

    @staticmethod
    def size():
        return SIZE["id"] + 4 * SIZE["G"] + SIZE["ts"] + SIZE["Zq"]


ENTRY = SIZE["hash"] + SIZE["nonce"] + 16 + 4 + SIZE["tag"]     # H3(PID) + AEAD(GK||nu)


# =====================================================================
# members (UAVs and vehicles)
# =====================================================================
class Member:
    def __init__(self, creds, Ppub, role="join"):
        self.creds = {c.ep: c for c in creds}
        self.Ppub, self.role = Ppub, role
        self.pending = None; self._ep = None
        self.K = None; self.tuav = None
        self.GK = None; self.nu = None
        self.hk = None; self.ticket = None

    def cred(self, ep):
        return self.creds[ep]

    # UA2 / VA2
    def request(self, beacon, ep, now, delta=5):
        assert abs(beacon.ts - now) <= delta, "stale beacon"
        assert verify(self.Ppub, beacon.tuav_id, 0, beacon.X, beacon.Y,
                      b"beacon" + beacon.tuav_id + enc_point(beacon.E), beacon.ts, beacon.R, beacon.v), "bad beacon"
        c = self.cred(ep)
        e = rand_scalar(); E = mul(P, e)
        req = Request(c.ident, ep, c.X, c.Y, E, now, None, None, self.role)
        req.R, req.v = sign(c, req.msg(beacon.tuav_id, beacon.E), now)
        self.pending = {"e": e, "E_a": beacon.E, "tuav": beacon.tuav_id, "ts": now, "ep": ep}
        return req

    # UA5 / VA5: derive K from the pending request, then open the entry
    def receive(self, ack):
        pd = self.pending
        c = self.cred(pd["ep"])
        K = sym.kdf(enc_point(mul(pd["E_a"], pd["e"])), c.ident, pd["tuav"], pd["ts"].to_bytes(8, "big"))
        got = self._open(ack, K, c.key)
        if got is None:
            return False
        self.K, self.tuav, self._ep = K, pd["tuav"], pd["ep"]
        self.GK, self.nu = got
        self.pending = None                                    # erase ephemeral e
        return True

    def _open(self, ack, K, key):
        for k, blob in ack["entries"]:
            if k == key:
                pt = sym.open_(K, blob, k + ack["nu"].to_bytes(4, "big") + ack["ts"].to_bytes(8, "big"))
                return None if pt is None else (pt[:16], int.from_bytes(pt[16:20], "big"))
        return None

    # RK2
    def receive_update(self, ack):
        got = self._open(ack, self.K, self.cred(self._ep).key)
        if got is None:
            return False
        self.GK, self.nu = got
        return True

    # VA3: a UAV relays vehicle requests in a MAC-protected bundle
    def relay(self, vehicle_reqs, now, seen=None):
        seen = set() if seen is None else seen
        kept = []
        for r in vehicle_reqs:
            if r.key not in seen:                           # 1 request per PID per window
                seen.add(r.key); kept.append(r)
        blob = b"".join(r.to_bytes() for r in kept)
        tag = sym.mac(self.K, blob, now.to_bytes(8, "big"))
        return {"relay": self.cred(self._ep).key, "ts": now, "reqs": kept, "tag": tag}

    # HO1 (member side) and HO2
    def take_ticket(self, sealed, tuav_b):
        pt = sym.open_(self.K, sealed["blob"], tuav_b)
        assert pt is not None
        ts_h = int.from_bytes(pt[:8], "big"); self.ticket = pt[8:]
        self.hk = sym.kdf(self.K, b"HO", tuav_b, ts_h.to_bytes(8, "big"))

    def handover_request(self, tuav_a, now):
        self.e2 = rand_scalar(); E2 = mul(P, self.e2)
        tau = sym.mac(self.hk, self.ticket, enc_point(E2), now.to_bytes(8, "big"))
        return {"from": tuav_a, "ticket": self.ticket, "E": E2, "ts": now, "tau": tau}

    # HO4
    def handover_finish(self, resp, tuav_b):
        c = self.cred(self._ep)
        K2 = sym.kdf(enc_point(mul(resp["E"], self.e2)), self.hk, c.ident, tuav_b)
        pt = sym.open_(K2, resp["blob"], enc_point(resp["E"]) + resp["ts"].to_bytes(8, "big"))
        self.e2 = None
        if pt is None:
            return False
        self.K, self.tuav, self.GK, self.nu = K2, tuav_b, pt[:16], int.from_bytes(pt[16:20], "big")
        return True


# =====================================================================
# TUAV
# =====================================================================
class TUAV:
    CLEAN_WINDOWS = 2

    def __init__(self, tuav_id, cred, Ppub):
        self.id, self.cred, self.Ppub = tuav_id.encode(), cred, Ppub
        self.ep = None
        self.members = {}          # key -> (K, role, Request)
        self.evicted = set()       # L
        self.GK, self.nu = os.urandom(16), 1
        self.VK, self.nuV = os.urandom(16), 1
        self.mode, self.clean = "batch", 0
        self.links = {}            # neighbour id -> K_ab
        self.used_nonces = set()
        self.stats = {}

    # UA1
    def beacon(self, now):
        self.e_a = rand_scalar(); self.E_a = mul(P, self.e_a); self.ts_a = now
        R, v = sign(self.cred, b"beacon" + self.id + enc_point(self.E_a), now)
        return Beacon(self.id, self.cred.X, self.cred.Y, self.E_a, now, R, v)

    def _item(self, r):
        return (r.ident, r.ep, r.X, r.Y, r.msg(self.id, self.E_a), r.ts, r.R, r.v)

    # UA3: filter, batch-verify, bounded fallback
    def verify_window(self, reqs, now, ep, delta=5):
        seen, cand = set(), []
        for r in reqs:
            if abs(r.ts - now) > delta or r.ep != ep or r.key in self.evicted or r.key in seen:
                continue
            seen.add(r.key); cand.append(r)
        st = {"filtered": len(reqs) - len(cand), "batch_checks": 0, "single_checks": 0, "mode": self.mode}
        if not cand:
            return [], st
        if self.mode == "batch":
            st["batch_checks"] += 1
            if batch_verify(self.Ppub, [self._item(r) for r in cand]):
                self.clean += 1
                return cand, st
        good = []
        for r in cand:
            st["single_checks"] += 1
            if verify(self.Ppub, *self._item(r)):
                good.append(r)
            else:
                self.evicted.add(r.key)
        if len(good) < len(cand):
            self.mode, self.clean = "individual", 0
        else:
            self.clean += 1
            if self.mode == "individual" and self.clean >= self.CLEAN_WINDOWS:
                self.mode = "batch"
        return good, st

    def _entries(self, keys, payload, nu, ts):
        out = []
        for k in keys:
            K = self.members[k][0]
            out.append((k, sym.seal(K, payload + nu.to_bytes(4, "big"), k + nu.to_bytes(4, "big") + ts.to_bytes(8, "big"))))
        return out

    # UA4 / VA4
    def admit(self, accepted, now):
        for r in accepted:
            K = sym.kdf(enc_point(mul(r.E, self.e_a)), r.ident, self.id, r.ts.to_bytes(8, "big"))
            self.members[r.key] = (K, r.role, r)
        uav = [r.key for r in accepted if r.role == "join"]
        veh = [r.key for r in accepted if r.role == "veh"]
        acks = {}
        if uav:
            acks["join"] = {"ts": now, "nu": self.nu, "entries": self._entries(uav, self.GK, self.nu, now)}
        if veh:
            acks["veh"] = {"ts": now, "nu": self.nuV, "entries": self._entries(veh, self.VK, self.nuV, now)}
        return acks

    # RK1
    def rekey(self, remove, now):
        for k in remove:
            self.members.pop(k, None)
        self.GK, self.nu = os.urandom(16), self.nu + 1
        keys = [k for k, (_, role, _) in self.members.items() if role == "join"]
        return {"ts": now, "nu": self.nu, "entries": self._entries(keys, self.GK, self.nu, now)}

    # VA4: accept only bundles from current UAV members
    def process_bundle(self, bundle, now, ep):
        relay = self.members.get(bundle["relay"])
        if relay is None or relay[1] != "join":
            return None, {"dropped": "relay not a member"}
        blob = b"".join(r.to_bytes() for r in bundle["reqs"])
        if not sym.mac_ok(relay[0], bundle["tag"], blob, bundle["ts"].to_bytes(8, "big")):
            return None, {"dropped": "bad relay MAC"}
        good, st = self.verify_window(bundle["reqs"], now, ep)
        return self.admit(good, now).get("veh"), st

    # HO0: inter-TUAV link (signed ECDH)
    def link_offer(self, now):
        self._e_ab = rand_scalar(); E = mul(P, self._e_ab)
        R, v = sign(self.cred, b"link" + self.id + enc_point(E), now)
        return {"id": self.id, "X": self.cred.X, "Y": self.cred.Y, "E": E, "ts": now, "R": R, "v": v}

    def link_accept(self, offer, my_offer_ts):
        assert verify(self.Ppub, offer["id"], 0, offer["X"], offer["Y"], b"link" + offer["id"] + enc_point(offer["E"]),
                      offer["ts"], offer["R"], offer["v"]), "bad link offer"
        ids = sorted([self.id, offer["id"]])
        self.links[offer["id"]] = sym.kdf(enc_point(mul(offer["E"], self._e_ab)), ids[0], ids[1])

    def share_evictions(self, other_id):
        K = self.links[other_id]
        return sym.seal(K, b"".join(sorted(self.evicted)), self.id)

    def merge_evictions(self, other_id, blob):
        pt = sym.open_(self.links[other_id], blob, other_id)
        self.evicted |= {pt[i:i + 32] for i in range(0, len(pt), 32)}

    # TR2 list from the TA, whenever it is reachable
    def apply_revocation(self, hashes):
        self.evicted |= set(hashes)

    # HO1
    def issue_ticket(self, member_key, tuav_b, now, life=30):
        K_M, role, req = self.members[member_key]
        hk = sym.kdf(K_M, b"HO", tuav_b, now.to_bytes(8, "big"))
        N = os.urandom(12)
        body = (len(req.ident).to_bytes(2, "big") + req.ident + req.ep.to_bytes(4, "big") + enc_point(req.X) + enc_point(req.Y)
                + role.encode().ljust(4, b"\0") + hk + N + (now + life).to_bytes(8, "big"))
        ticket = sym.seal(self.links[tuav_b], body, self.id + tuav_b)
        return {"blob": sym.seal(K_M, now.to_bytes(8, "big") + ticket, tuav_b)}

    # HO3
    def accept_handover(self, msg, now, delta=5):
        K_ab = self.links.get(msg["from"])
        if K_ab is None or abs(msg["ts"] - now) > delta:
            return None, "no link / stale"
        body = sym.open_(K_ab, msg["ticket"], msg["from"] + self.id)
        if body is None:
            return None, "ticket forged"
        n = int.from_bytes(body[:2], "big"); ident = body[2:2 + n]; o = 2 + n
        ep = int.from_bytes(body[o:o + 4], "big"); o += 4 + 128
        role = body[o:o + 4].rstrip(b"\0").decode(); o += 4
        hk, N, exp = body[o:o + 16], body[o + 16:o + 28], int.from_bytes(body[o + 28:o + 36], "big")
        key = H("H3", ident, ep)
        if now > exp:
            return None, "ticket expired"
        if N in self.used_nonces:
            return None, "ticket replayed"
        if key in self.evicted:
            return None, "evicted"
        if not sym.mac_ok(hk, msg["tau"], msg["ticket"], enc_point(msg["E"]), msg["ts"].to_bytes(8, "big")):
            return None, "bad MAC"
        self.used_nonces.add(N)
        e_b = rand_scalar(); E_b = mul(P, e_b)
        K2 = sym.kdf(enc_point(mul(msg["E"], e_b)), hk, ident, self.id)
        req = Request(ident, ep, None, None, msg["E"], now, None, None, role)
        self.members[key] = (K2, role, req)
        payload, nu = (self.GK, self.nu) if role == "join" else (self.VK, self.nuV)
        blob = sym.seal(K2, payload + nu.to_bytes(4, "big"), enc_point(E_b) + now.to_bytes(8, "big"))
        return {"E": E_b, "ts": now, "blob": blob}, "ok"


HO_REQ_SIZE = SIZE["id"] + (12 + 2 + 49 + 4 + 2 * SIZE["G"] + 4 + 16 + 12 + 8 + 16) + SIZE["G"] + SIZE["ts"] + 32
HO_RESP_SIZE = SIZE["G"] + SIZE["ts"] + (12 + 20 + 16)


# =====================================================================
# V2V under the regional key (routine beacons) -- event messages are signed with sign()
# =====================================================================
def v2v_tag(VK, msg, ident, ts):
    return sym.mac(VK, msg, ident, ts.to_bytes(8, "big"))
