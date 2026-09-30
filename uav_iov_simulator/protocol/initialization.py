"""
Phase A - system initialization.  Steps IS1 to IS5 of the paper.

IS1  TA issues <id_tu, s_tu> to the TUAV.
IS2  TA issues <id_i, s_i> to every UAV.
IS3  TA publishes the global parameters and the five hash functions.
IS4  TUAV draws r_tu and computes ID_tu, R_tu, Q_tu.
IS5  TUAV broadcasts <ts_tu, ID_tu, R_tu, Q_tu>.

Note on IS1/IS2: the paper is explicit that these secrets are distributed
offline, before deployment, and "will be safely shared only between TA and TUAV
itself during the whole time".  So registration never touches the simulated
radio link, and it works even when the TA link is down.
"""

from __future__ import annotations

import secrets
import time

from ..crypto.hash_utils import h2
from ..crypto.interface import Backend
from .entities import TA, TUAV, UAV, Status, Vehicle


def initialize_system(backend: Backend, *, seed: int | None = None) -> tuple[TA, TUAV]:
    """Steps IS1 and IS3 - create the authority and the tethered UAV."""
    rng = secrets.SystemRandom()
    if seed is not None:
        import random
        rng = random.Random(seed)

    ta = TA()
    tuav = TUAV(
        id_perm=b"TUAV-" + rng.randrange(1 << 48).to_bytes(6, "big"),
        s=rng.randrange(1, backend.order),
    )
    return ta, tuav


def register_uavs(ta: TA, n: int, backend: Backend, *,
                  start_index: int = 1, seed: int | None = None) -> list[UAV]:
    """Step IS2 - offline registration of n UAVs.

    Returns UAV objects already in the REGISTERED state.  Their secrets are on
    the object; nothing here is ever rendered.
    """
    rng = secrets.SystemRandom()
    if seed is not None:
        import random
        rng = random.Random(seed + 1000)

    uavs: list[UAV] = []
    for k in range(n):
        idx = start_index + k
        id_perm = b"UAV-" + idx.to_bytes(4, "big") + rng.randrange(1 << 32).to_bytes(4, "big")
        s = rng.randrange(1, backend.order)
        ta.registry[idx] = s
        ta.identities[idx] = id_perm
        uavs.append(UAV(index=idx, id_perm=id_perm, s=s, status=Status.REGISTERED))
    return uavs


def refresh_tuav_session(tuav: TUAV, backend: Backend, *,
                         now: float | None = None,
                         seed: int | None = None) -> dict:
    """Steps IS4 and IS5 - the TUAV refreshes its session and broadcasts.

        ID_tu = h2(id_tu, r_tu)
        R_tu  = r_tu * h2(ts_tu, s_tu)          [a scalar]
        Q_tu  = s_tu * h2(ID_tu, r_tu) * P      [a point]

    The paper notes that ID_tu is effective "only within a certain time
    interval, depending on the periodical updated r_tu" - which is what gives
    the TUAV itself anonymity, not just the UAVs.
    """
    rng = secrets.SystemRandom()
    if seed is not None:
        import random
        rng = random.Random(seed + 2000)

    q = backend.order
    tuav.ts_tu = now if now is not None else time.time()
    tuav.r = rng.randrange(1, q)

    tuav.id_temp = h2(tuav.id_perm, tuav.r, order=q)
    tuav.R = (tuav.r * h2(tuav.ts_tu, tuav.s, order=q)) % q

    tuav.H = h2(tuav.id_temp, tuav.r, order=q)      # reused in Step GA3
    tuav.Q = backend.g1_mul((tuav.s * tuav.H) % q)

    return tuav.broadcast_set()


def create_vehicles(n: int, uav_indices: list[int]) -> list[Vehicle]:
    """The vehicular network of the system model.

    Out of scope for authentication, as in the paper. Vehicles are attached to
    the nearest UAV purely so the topology diagram has something to draw.
    """
    vehicles: list[Vehicle] = []
    for k in range(n):
        served = uav_indices[k % len(uav_indices)] if uav_indices else None
        vehicles.append(Vehicle(index=k + 1, served_by=served))
    return vehicles
