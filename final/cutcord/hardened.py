"""Hardened admission and C4 compromise containment.

ours.py stays unchanged so that E0-E7 remain reproducible. This module closes six flaws
found in it and adds the containment tier. With no TA in the field, nobody online can
overrule a forged packet or a captured TUAV, so trust decisions must rest on evidence
that the field can check for itself.

A1  a failed signature evicted the pseudonym it named  -> a failure proves nothing about
    that pseudonym: never evict on it; keep a bounded random sample per pseudonym
A2  a ticket alone admitted a member at the new TUAV    -> the member must also sign
A3  neighbours merged eviction lists on trust           -> entries carry checkable evidence
A4  a credential did not bind a role                    -> the role is hashed into the identity
A5  an old rekey could be replayed                      -> versions must increase
A6  joiners received the key already in use             -> rekey once per window on arrival
A7  a member authenticated its new TUAV only through hk -> the new TUAV signs its reply under its
    (found by ProVerif: a captured old TUAV knows hk)       own credential, which the old TUAV cannot forge

C4  a TUAV is evicted, with the TA offline, by t votes from distinct other TUAVs.
    Detecting a capture is outside the protocol (tamper sensor, lost tether, crew report).
"""
import os
import secrets
from dataclasses import dataclass

from py_ecc import optimized_bn128 as bn

from . import ours, sym
from .ec import P, q, mul, add, eq, H, Hq, enc_point, rand_scalar, SIZE
from .ours import Credential, Request, h_bind, sign, verify, batch_verify, schnorr_pop, schnorr_pop_ok, RID_LEN

ROLE_TAG = {"join": b"U", "veh": b"V"}
TAG_ROLE = {v: k for k, v in ROLE_TAG.items()}
PER_PID = 2                                # candidates kept per pseudonym per window
VOTE_SIZE = SIZE["id"] + 3 * SIZE["G"] + SIZE["ts"] + SIZE["Zq"]   # id, X, Y, R, ts, v
HO_SIG_SIZE = SIZE["G"] + SIZE["Zq"]       # (R, v) added to the handover request
HO_REPLY_SIG_SIZE = 3 * SIZE["G"] + SIZE["Zq"]   # (X_b, Y_b, R, v) added to the handover reply


def dec_point(b):
    pt = (bn.FQ(int.from_bytes(b[:32], "big")), bn.FQ(int.from_bytes(b[32:64], "big")), bn.FQ(1))
    return pt if bn.is_on_curve(pt, bn.b) else None


def handover_msg(tuav_a, tuav_b, ticket, E):
    return b"handover" + tuav_a + tuav_b + H("HT", ticket) + enc_point(E)


def handover_reply_msg(tuav_a, tuav_b, ticket, E, E_b):
    return b"handover-reply" + tuav_a + tuav_b + H("HT", ticket) + enc_point(E) + enc_point(E_b)


def vote_msg(target):
    return b"evict-tuav" + target


# =====================================================================
# Trusted Authority: role-bound credentials, signed revocation lists
# =====================================================================
class HardenedTA(ours.TA):
    def register(self, rid, m, role="join"):
        assert len(rid) == RID_LEN
        creds = []
        for ep in range(1, m + 1):
            x = rand_scalar(); X = mul(P, x)
            pop = schnorr_pop(x, X, rid)
            assert schnorr_pop_ok(X, rid, *pop)
            rho, y = rand_scalar(), rand_scalar()
            PID1 = mul(P, rho)
            PID2 = bytes(a ^ b for a, b in zip(rid, H("H0", mul(self.Tpub, rho), ep, out=RID_LEN)))
            Y = mul(P, y)
            ident = enc_point(PID1) + PID2 + ROLE_TAG[role]    # h_bind covers ident, so the role is certified
            d = (y + self.s * h_bind(ident, ep, X, Y)) % q
            creds.append(Credential(ident, ep, X, Y, d, x, PID1, PID2))
        self.registry[rid] = [(c.ident, c.ep) for c in creds]
        return creds

    def revoke_signed(self, rid, from_epoch, now):
        hashes = sorted(self.revoke(rid, from_epoch))
        r = rand_scalar(); R = mul(P, r)
        c = Hq("TR", b"".join(hashes), now, R)
        return {"hashes": hashes, "ts": now, "R": R, "v": (r + c * self.s) % q}


def revocation_ok(Ppub, rl):
    c = Hq("TR", b"".join(rl["hashes"]), rl["ts"], rl["R"])
    return eq(mul(P, rl["v"]), add(rl["R"], mul(Ppub, c)))


# =====================================================================
# C4: quorum eviction of a TUAV
# =====================================================================
@dataclass
class Vote:
    signer: bytes
    X: tuple
    Y: tuple
    target: bytes
    ts: int
    R: tuple
    v: int

    def item(self):
        return self.signer, 0, self.X, self.Y, vote_msg(self.target), self.ts, self.R, self.v


def vote_ok(Ppub, vote):
    return vote.signer != vote.target and verify(Ppub, *vote.item())


def cert_ok(Ppub, target, votes, t):
    """t distinct TUAVs other than the target. ep = 0 is issued only to TUAVs, so a member
    credential cannot vote: its public key is bound to its own ep through h_bind."""
    signers = {v.signer for v in votes}
    if len(signers) < t or target in signers or any(v.target != target for v in votes):
        return False
    return batch_verify(Ppub, [v.item() for v in votes])


# =====================================================================
# members
# =====================================================================
class HardenedMember(ours.Member):
    def __init__(self, creds, Ppub, role="join", t=2):
        super().__init__(creds, Ppub, role)
        self.t = t
        self.blocked = set()
        self._last_req = None
        self._last_E_a = None

    def request(self, beacon, ep, now, delta=5):
        assert beacon.tuav_id not in self.blocked, "TUAV evicted"
        # never sign twice under one beacon: two distinct signed requests are evidence of cloning,
        # so this also holds after joining, or a captured TUAV could re-offer the beacon and frame us
        if self._last_req is not None and self._last_E_a is not None and eq(self._last_E_a, beacon.E) and self._last_req.ep == ep:
            return self._last_req
        self._last_req = super().request(beacon, ep, now, delta)
        self._last_E_a = beacon.E
        return self._last_req

    def receive_update(self, ack):
        got = self._open(ack, self.K, self.cred(self._ep).key)
        if got is None or got[1] <= self.nu:           # A5: versions only increase
            return False
        self.GK, self.nu = got
        return True

    def handover_request(self, tuav_a, tuav_b, now):
        self.e2 = rand_scalar(); E2 = mul(P, self.e2)
        tau = sym.mac(self.hk, self.ticket, enc_point(E2), now.to_bytes(8, "big"))
        R, v = sign(self.cred(self._ep), handover_msg(tuav_a, tuav_b, self.ticket, E2), now)
        self._ho = (tuav_a, tuav_b, self.ticket, E2)
        return {"from": tuav_a, "ticket": self.ticket, "E": E2, "ts": now, "tau": tau, "R": R, "v": v}

    def handover_finish(self, resp, tuav_b):
        # A7: hk is known to the old TUAV, so it cannot authenticate the new one; only a signature
        # under a TUAV credential the TA issued to tuav_b can. A forged reply is ignored and the
        # ephemeral is kept, so the genuine reply can still be accepted.
        tuav_a, expected_b, ticket, E2 = self._ho
        if tuav_b != expected_b or not all(k in resp for k in ("X", "Y", "R", "v")):
            return False
        if not verify(self.Ppub, tuav_b, 0, resp["X"], resp["Y"],
                      handover_reply_msg(tuav_a, tuav_b, ticket, E2, resp["E"]), resp["ts"], resp["R"], resp["v"]):
            return False
        return super().handover_finish(resp, tuav_b)

    def apply_cert(self, target, votes):
        if not cert_ok(self.Ppub, target, votes, self.t):
            return False
        self.blocked.add(target)
        return True


# =====================================================================
# TUAV
# =====================================================================
class HardenedTUAV(ours.TUAV):
    def __init__(self, tuav_id, cred, Ppub, t=2):
        super().__init__(tuav_id, cred, Ppub)
        self.t = t
        self.evidence = {}         # key -> (tuav_id, E_a, r1, r2)
        self.blocked = set()
        self.votes = {}            # target -> {signer: Vote}
        self.outbox = []           # (role, update) for members already in the cell
        self._rekeyed = {}         # role -> timestamp of the last arrival rekey

    # ---- UA3: a failed signature evicts nobody ---------------------------------
    def _sample(self, reqs, now, ep, delta):
        buckets, seen, filtered = {}, {}, 0
        for r in reqs:
            if (abs(r.ts - now) > delta or r.ep != ep or r.key in self.evicted
                    or r.ident[-1:] != ROLE_TAG.get(r.role)):
                filtered += 1
                continue
            b = buckets.setdefault(r.key, [])
            if any(o.v == r.v and eq(o.R, r.R) for o in b):       # exact copy, e.g. a link-layer retransmission
                continue
            seen[r.key] = seen.get(r.key, 0) + 1
            if len(b) < PER_PID:
                b.append(r)
            else:                                                 # reservoir: uniform over everything received
                j = secrets.randbelow(seen[r.key])
                if j < PER_PID:
                    b[j] = r
        return buckets, filtered

    def verify_window(self, reqs, now, ep, delta=5):
        buckets, filtered = self._sample(reqs, now, ep, delta)
        st = {"filtered": filtered, "batch_checks": 0, "single_checks": 0, "mode": self.mode, "rejected": 0}
        singles = [b[0] for b in buckets.values() if len(b) == 1]
        contested = [b for b in buckets.values() if len(b) > 1]
        good = []
        if singles and self.mode == "batch":
            st["batch_checks"] += 1
            if batch_verify(self.Ppub, [self._item(r) for r in singles]):
                good, singles = singles, []
        for r in singles:
            st["single_checks"] += 1
            if verify(self.Ppub, *self._item(r)):
                good.append(r)
            else:
                st["rejected"] += 1
        for b in contested:
            valid = []
            for r in b:
                st["single_checks"] += 1
                if verify(self.Ppub, *self._item(r)):
                    valid.append(r)
                else:
                    st["rejected"] += 1
            if len(valid) == 2:                                   # one credential, two signed requests: cloned
                self.evidence[valid[0].key] = (self.id, self.E_a, valid[0], valid[1])
                self.evicted.add(valid[0].key)
            elif valid:
                good.append(valid[0])
        if st["rejected"]:
            self.mode, self.clean = "individual", 0
        elif buckets:
            self.clean += 1
            if self.mode == "individual" and self.clean >= self.CLEAN_WINDOWS:
                self.mode = "batch"
        return good, st

    # ---- A3: only evidence crosses to a neighbour --------------------------------
    def evict_local(self, key):
        """an operator decision: it holds in this cell and is never forwarded"""
        self.evicted.add(key)

    def share_evictions(self, other_id=None):
        return list(self.evidence.values())

    def _evidence_ok(self, ev):
        tuav_id, E_a, r1, r2 = ev
        if r1.key != r2.key or eq(r1.E, r2.E):
            return False
        return all(verify(self.Ppub, r.ident, r.ep, r.X, r.Y, r.msg(tuav_id, E_a), r.ts, r.R, r.v) for r in (r1, r2))

    def merge_evictions(self, other_id, items):
        accepted = 0
        for ev in items:
            if self._evidence_ok(ev):
                self.evidence[ev[2].key] = ev
                self.evicted.add(ev[2].key)
                accepted += 1
        return accepted

    def apply_revocation(self, rl):
        if not revocation_ok(self.Ppub, rl):
            return False
        self.evicted |= set(rl["hashes"])
        return True

    # ---- A6 and leaving members: rekey ------------------------------------------
    def rekey(self, remove, now, role="join"):
        for k in remove:
            self.members.pop(k, None)
        if role == "join":
            self.GK, self.nu = os.urandom(16), self.nu + 1
            payload, nu = self.GK, self.nu
        else:
            self.VK, self.nuV = os.urandom(16), self.nuV + 1
            payload, nu = self.VK, self.nuV
        keys = [k for k, (_, ro, _) in self.members.items() if ro == role]
        return {"ts": now, "nu": nu, "entries": self._entries(keys, payload, nu, now)}

    def _fresh(self, role, now, arriving=()):
        """at most one rekey per window; the update goes out to members already in the cell"""
        present = [k for k, (_, ro, _) in self.members.items() if ro == role and k not in arriving]
        if not present or self._rekeyed.get(role) == now:
            return
        self.outbox.append((role, self.rekey([], now, role)))
        self._rekeyed[role] = now

    def admit(self, accepted, now):
        keys = {r.key for r in accepted}
        for role in ROLE_TAG:
            if any(r.role == role for r in accepted):
                self._fresh(role, now, keys)
        return super().admit(accepted, now)

    def depart(self, key, now):
        """a member moved away: the cell moves to a key it does not hold"""
        role = self.members[key][1]
        update = self.rekey([key], now, role)
        self.outbox.append((role, update))
        return update

    # ---- A2: HO3 needs the member's own signature --------------------------------
    def accept_handover(self, msg, now, delta=5):
        K_ab = self.links.get(msg["from"])
        if msg["from"] in self.blocked or K_ab is None or abs(msg["ts"] - now) > delta:
            return None, "no link / stale"
        body = sym.open_(K_ab, msg["ticket"], msg["from"] + self.id)
        if body is None:
            return None, "ticket forged"
        n = int.from_bytes(body[:2], "big"); ident = body[2:2 + n]; o = 2 + n
        ep = int.from_bytes(body[o:o + 4], "big"); o += 4
        X, Y = dec_point(body[o:o + 64]), dec_point(body[o + 64:o + 128]); o += 128 + 4   # the ticket's role field is not trusted
        hk, N, exp = body[o:o + 16], body[o + 16:o + 28], int.from_bytes(body[o + 28:o + 36], "big")
        role = TAG_ROLE.get(ident[-1:])
        key = H("H3", ident, ep)
        if role is None or ep < 1 or X is None or Y is None:
            return None, "not a member credential"
        if now > exp:
            return None, "ticket expired"
        if N in self.used_nonces:
            return None, "ticket replayed"
        if key in self.evicted:
            return None, "evicted"
        if not sym.mac_ok(hk, msg["tau"], msg["ticket"], enc_point(msg["E"]), msg["ts"].to_bytes(8, "big")):
            return None, "bad MAC"
        if not verify(self.Ppub, ident, ep, X, Y, handover_msg(msg["from"], self.id, msg["ticket"], msg["E"]),
                      msg["ts"], msg["R"], msg["v"]):
            return None, "bad member signature"
        self.used_nonces.add(N)
        self._fresh(role, now, {key})
        e_b = rand_scalar(); E_b = mul(P, e_b)
        K2 = sym.kdf(enc_point(mul(msg["E"], e_b)), hk, ident, self.id)
        self.members[key] = (K2, role, Request(ident, ep, X, Y, msg["E"], now, None, None, role))
        payload, nu = (self.GK, self.nu) if role == "join" else (self.VK, self.nuV)
        blob = sym.seal(K2, payload + nu.to_bytes(4, "big"), enc_point(E_b) + now.to_bytes(8, "big"))
        R_b, v_b = sign(self.cred, handover_reply_msg(msg["from"], self.id, msg["ticket"], msg["E"], E_b), now)   # A7
        return {"E": E_b, "ts": now, "blob": blob, "X": self.cred.X, "Y": self.cred.Y, "R": R_b, "v": v_b}, "ok"

    # ---- C4 ---------------------------------------------------------------------
    def vote(self, target, now):
        R, v = sign(self.cred, vote_msg(target), now)
        return Vote(self.id, self.cred.X, self.cred.Y, target, now, R, v)

    def receive_vote(self, vote):
        """collect votes as they arrive; returns the certificate once t distinct TUAVs have voted"""
        if not vote_ok(self.Ppub, vote):
            return None
        bucket = self.votes.setdefault(vote.target, {})
        bucket[vote.signer] = vote
        if len(bucket) < self.t:
            return None
        self._cut(vote.target)
        return list(bucket.values())

    def apply_cert(self, target, votes):
        if not cert_ok(self.Ppub, target, votes, self.t):
            return False
        self._cut(target)
        return True

    def _cut(self, target):
        self.blocked.add(target)
        self.links.pop(target, None)

    def link_accept(self, offer, my_offer_ts):
        assert offer["id"] not in self.blocked, "TUAV evicted"
        super().link_accept(offer, my_offer_ts)
