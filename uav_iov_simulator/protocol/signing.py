"""
Phase B - UAV signing.  Steps US1 to US3 of the paper.

US1  Each UAV draws r_i, sets xi_i = h1(r_i) and ID_i = h3(id_i, ts2, xi_i).
US2  Each UAV computes upsilon_i = h4(ID_i, ID_tu, ts2, xi_i) and the credential

        Gamma_i = [ s_i * h3(ID_i, ts2, s_i) * R_tu - h1(s_i * xi_i) ] * P
                  - upsilon_i * h1(r_i) * Q_tu

US3  Each UAV transmits <Request, ts2, ID_i, xi_i, upsilon_i, Gamma_i>.

Two things worth noticing in Gamma_i, because they are the whole design:

  * Both halves of the certificateless key are inside it - the TA-issued s_i
    and the UAV's own r_i.  Neither party alone can produce it.

  * h1(r_i) in the last term is exactly xi_i, which is transmitted in the clear.
    That is not an accident: it is what makes the TUAV's aggregate equation
    cancel.  See protocol/authentication.py for the derivation.

Cost per UAV: two scalar multiplications, one point addition, five hashes -
which is the paper's 1.8203 ms figure in Table III.
"""

from __future__ import annotations

import secrets
import time

from ..crypto.hash_utils import h1, h3, h4
from ..crypto.interface import Backend, OpCount, Timer
from .entities import RequestPacket, TUAV, UAV, Status


def sign_one(uav: UAV, tuav: TUAV, backend: Backend, *,
             ts2: float, counter: OpCount,
             forge: bool = False,
             rng=None) -> RequestPacket:
    """Steps US1-US3 for a single UAV.

    `forge=True` produces a structurally well-formed but invalid credential.
    That is how the batch-poisoning experiment injects a bad signature without
    the packet being trivially rejectable on format alone.
    """
    rng = rng or secrets.SystemRandom()
    q = backend.order

    with Timer(counter):
        # ---- US1 -------------------------------------------------------
        uav.r = rng.randrange(1, q)
        uav.xi = h1(uav.r, order=q)
        uav.id_temp = h3(uav.id_perm, ts2, uav.xi, order=q)
        uav.ts2 = ts2
        counter.hash += 2

        # ---- US2 -------------------------------------------------------
        uav.upsilon = h4(uav.id_temp, tuav.id_temp, ts2, uav.xi, order=q)
        counter.hash += 1

        #   A_i = s_i * h3(ID_i, ts2, s_i) * R_tu
        h3_inner = h3(uav.id_temp, ts2, uav.s, order=q)
        counter.hash += 1
        A = (uav.s * h3_inner % q) * tuav.R % q

        #   B_i = h1(s_i * xi_i)
        B = h1((uav.s * uav.xi) % q, order=q)
        counter.hash += 1

        if forge:
            # A wrong secret scalar: the packet still parses, still has the
            # right shape, and still fails the aggregate check. The TUAV cannot
            # tell which member did this - that is the point of the experiment.
            A = (A + rng.randrange(1, q)) % q

        #   Gamma_i = (A - B) * P  -  (upsilon_i * xi_i) * Q_tu
        #
        # Q_tu arrives as a POINT in the Step IS5 broadcast. The UAV multiplies
        # that point; it does not know s_tu and could not rebuild Q_tu itself.
        first = backend.g1_mul((A - B) % q)
        tail_scalar = (uav.upsilon * uav.xi) % q
        second = backend.g1_point_mul(tuav.Q, tail_scalar)
        uav.gamma = backend.g1_sub(first, second)

    uav.is_forged = forge
    uav.status = Status.FORGED if forge else Status.PENDING
    uav.history.append((ts2, uav.id_temp))

    # ---- US3 -----------------------------------------------------------
    return RequestPacket(
        uav_index=uav.index,
        ts2=ts2,
        id_temp=uav.id_temp,
        xi=uav.xi,
        upsilon=uav.upsilon,
        gamma=uav.gamma,
    )


def sign_batch(uavs: list[UAV], tuav: TUAV, backend: Backend, *,
               ts2: float | None = None,
               poison_indices: set[int] | None = None,
               rng=None) -> tuple[list[RequestPacket], OpCount]:
    """Run Steps US1-US3 for every UAV in the list.

    Returns the request packets and the drone-side operation count.
    """
    ts2 = ts2 if ts2 is not None else time.time()
    poison_indices = poison_indices or set()
    counter = OpCount()

    # Snapshot the backend's primitive tally so the drone-side operation counts
    # are real, not just wall time. See the same pattern in authentication.py.
    before = backend.counter.copy()

    packets = [
        sign_one(u, tuav, backend, ts2=ts2, counter=counter,
                 forge=(u.index in poison_indices), rng=rng)
        for u in uavs
    ]

    primitives = backend.counter.minus(before)
    primitives.wall_ms = counter.wall_ms
    primitives.hash = counter.hash
    return packets, primitives
