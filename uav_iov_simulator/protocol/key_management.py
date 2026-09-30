"""
Phase D - group key distribution and dynamic updating.
Steps GD1 to GD6 and DU1 to DU2 of the paper.

GD1  TUAV derives the decrypting value sigma_i per member and picks kappa_tu.
GD2  TUAV constructs Lambda(x) and extracts the coefficient set {a_i}.
GD3  TUAV computes S_i = H1(ts3, ID_i, s_tu * h2(ID_tu, r_tu) * sigma_i).
GD4  TUAV broadcasts <ACK, ts3, ID_i, S_i, {a_i}>.
GD5  Each UAV checks S_i.  This is the MUTUAL half - the UAV now believes the
     TUAV is genuine, because only the real TUAV knows s_tu.
GD6  Each UAV recovers kappa_tu = Lambda(sigma_i) mod sigma_i.

DU1  New key kappa', Lambda rebuilt over the surviving members only.
DU2  Survivors extract the new key with the material they already hold.

The property that makes this worth preserving: a revocation costs one broadcast
and sends nothing at all to the members who remain.

On sigma_i being an integer here, see the declared correction in crypto/crt.py.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field

from ..crypto import crt
from ..crypto.hash_utils import H1
from ..crypto.interface import Backend, OpCount, Timer
from .entities import Status, TUAV, UAV


@dataclass
class KeyDistributionResult:
    ok: bool
    epoch: int
    broadcast: crt.CRTBroadcast | None = None
    members: list[int] = field(default_factory=list)
    recovered: list[int] = field(default_factory=list)
    failed: list[int] = field(default_factory=list)
    mutual_auth_failed: list[int] = field(default_factory=list)
    tuav_ops: OpCount = field(default_factory=OpCount)
    uav_ops: OpCount = field(default_factory=OpCount)
    reason: str = ""

    def summary(self) -> dict:
        return {
            "epoch": self.epoch,
            "members": len(self.members),
            "recovered key": len(self.recovered),
            "failed": len(self.failed),
            "broadcast bytes": self.broadcast.size_bytes if self.broadcast else 0,
            "TUAV ms": round(self.tuav_ops.wall_ms, 3),
            "UAV ms (all members)": round(self.uav_ops.wall_ms, 3),
            "reason": self.reason,
        }


def _pick_group_key(shares, rng) -> int:
    """kappa_tu must be smaller than every modulus for Step GD6 to be exact."""
    smallest = min(s.modulus for s in shares)
    return rng.randrange(2, smallest)


def distribute_group_key(uavs: list[UAV], tuav: TUAV, backend: Backend, *,
                         sigma_seeds: dict[int, int],
                         epoch: int,
                         ts3: float | None = None,
                         rng=None) -> KeyDistributionResult:
    """Steps GD1 to GD6 for the members that passed group authentication.

    `sigma_seeds` maps UAV index -> h1(s_i * xi_i), which the TA returned in
    Step GA2.  That is genuinely how the TUAV obtains it: it does not know s_i.
    """
    rng = rng or secrets.SystemRandom()
    ts3 = ts3 if ts3 is not None else time.time()
    q = backend.order

    members = [u for u in uavs if u.status == Status.AUTHENTICATED and u.index in sigma_seeds]
    result = KeyDistributionResult(ok=False, epoch=epoch,
                                   members=[u.index for u in members])

    if not members:
        result.reason = "no authenticated members to key"
        return result

    tuav_ops = OpCount()
    with Timer(tuav_ops):
        # ---- GD1 ---------------------------------------------------------
        shares = crt.build_shares(
            {u.name: sigma_seeds[u.index] for u in members}
        )
        for u in members:
            u.crt_modulus = shares[u.name].modulus

        kappa = _pick_group_key(list(shares.values()), rng)

        # ---- GD2 ---------------------------------------------------------
        broadcast = crt.build_lambda(shares.values(), kappa)
        broadcast.epoch = epoch

        # ---- GD3 : the acknowledgment that gives MUTUAL authentication ----
        acks: dict[int, int] = {}
        for u in members:
            acks[u.index] = H1(ts3, u.id_temp,
                               (tuav.s * tuav.H % q) * u.crt_modulus % q,
                               order=q)
            tuav_ops.hash += 1

    result.broadcast = broadcast
    result.tuav_ops = tuav_ops

    # ---- GD5 / GD6 : every member checks S_i, then recovers the key -------
    uav_ops = OpCount()
    with Timer(uav_ops):
        for u in members:
            # GD5 - recompute S_i. A UAV that cannot reproduce it is talking to
            # something that is not the real TUAV.
            expected = H1(ts3, u.id_temp,
                          (tuav.s * tuav.H % q) * u.crt_modulus % q,
                          order=q)
            uav_ops.hash += 1
            if expected != acks[u.index]:
                result.mutual_auth_failed.append(u.index)
                result.failed.append(u.index)
                continue

            # GD6 - kappa = Lambda(sigma_i) mod sigma_i
            recovered = crt.recover(broadcast, shares[u.name])
            if recovered == kappa:
                u.group_key = recovered
                u.key_epoch = epoch
                u.status = Status.KEYED
                result.recovered.append(u.index)
            else:
                result.failed.append(u.index)

    result.uav_ops = uav_ops
    tuav.group_key = kappa
    tuav.key_epoch = epoch
    result.ok = len(result.recovered) == len(members)
    result.reason = (
        f"group key distributed to {len(result.recovered)}/{len(members)} members "
        f"in one broadcast of {broadcast.size_bytes} bytes"
    )
    return result


def update_group_key(all_uavs: list[UAV], tuav: TUAV, backend: Backend, *,
                     active_indices: list[int],
                     epoch: int,
                     rng=None) -> KeyDistributionResult:
    """Steps DU1 and DU2 - batch join and batch revocation in one operation.

    Members whose index is not in `active_indices` are revoked: Lambda is simply
    rebuilt without their modulus.  They are sent nothing, and they keep their
    old key material - which no longer opens anything.
    """
    rng = rng or secrets.SystemRandom()

    keyed = {u.index: u for u in all_uavs if u.crt_modulus is not None}
    active = [keyed[i] for i in active_indices if i in keyed]

    result = KeyDistributionResult(ok=False, epoch=epoch,
                                   members=[u.index for u in active])
    if not active:
        result.reason = "no active members remain"
        return result

    shares = {u.name: crt.CRTShare(uav_id=u.name, modulus=u.crt_modulus) for u in active}

    tuav_ops = OpCount()
    with Timer(tuav_ops):
        kappa = _pick_group_key(list(shares.values()), rng)
        broadcast = crt.build_lambda(shares.values(), kappa)
        broadcast.epoch = epoch

    result.broadcast = broadcast
    result.tuav_ops = tuav_ops

    uav_ops = OpCount()
    with Timer(uav_ops):
        for u in active:
            recovered = crt.recover(broadcast, shares[u.name])
            if recovered == kappa:
                u.group_key = recovered
                u.key_epoch = epoch
                u.status = Status.KEYED
                result.recovered.append(u.index)
            else:
                result.failed.append(u.index)

    # Revoked members keep whatever they had; it no longer matches.
    revoked = [u for u in all_uavs
               if u.crt_modulus is not None and u.index not in active_indices]
    for u in revoked:
        u.status = Status.REVOKED

    result.uav_ops = uav_ops
    tuav.group_key = kappa
    tuav.key_epoch = epoch
    result.ok = len(result.recovered) == len(active)
    result.reason = (
        f"epoch {epoch}: {len(active)} active, {len(revoked)} revoked. "
        f"Survivors needed no new key material - one broadcast of "
        f"{broadcast.size_bytes} bytes and nothing sent to them individually."
    )
    return result


def can_open(uav: UAV, tuav: TUAV) -> bool:
    """Does this UAV hold the *current* group key?"""
    return (
        uav.group_key is not None
        and tuav.group_key is not None
        and uav.group_key == tuav.group_key
        and uav.key_epoch == tuav.key_epoch
    )
