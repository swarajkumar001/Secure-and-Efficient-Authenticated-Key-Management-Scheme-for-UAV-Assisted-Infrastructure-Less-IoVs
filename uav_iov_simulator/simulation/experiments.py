"""
Experiment runners E1-E8.

Each returns a tidy pandas DataFrame so the visualisation layer never has to
reshape anything. Every row carries a `source` column, so a chart can always
separate what the paper reported from what we measured.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass

import pandas as pd

from .. import config
from ..crypto.interface import get_backend
from ..paper_model import cost as paper_cost
from ..protocol import authentication, initialization, key_management, signing
from ..protocol.entities import Status
from ..protocol.link import TALink

MEASURED = "simulator (measured)"


# ---------------------------------------------------------------------------
def _fresh(backend_name: str, n: int, *, rtt_ms: float = 0.0,
           availability: float = 1.0, seed: int = 17):
    """Build an independent system with n registered UAVs."""
    backend = get_backend(backend_name)
    ta, tuav = initialization.initialize_system(backend, seed=seed)
    uavs = initialization.register_uavs(ta, n, backend, seed=seed)
    initialization.refresh_tuav_session(tuav, backend, seed=seed)
    link = TALink(rtt_ms=rtt_ms, availability=availability,
                  rng=random.Random(seed))
    return backend, ta, tuav, uavs, link


def _one_run(backend_name: str, n: int, *, rtt_ms: float = 0.0,
             availability: float = 1.0, poison_fraction: float = 0.0,
             identify: bool = False, seed: int = 17):
    backend, ta, tuav, uavs, link = _fresh(
        backend_name, n, rtt_ms=rtt_ms, availability=availability, seed=seed)
    rng = random.Random(seed + 1)

    poison = set()
    if poison_fraction > 0:
        k = max(1, int(round(n * poison_fraction)))
        poison = set(rng.sample([u.index for u in uavs], min(k, n)))

    packets, drone_ops = signing.sign_batch(
        uavs, tuav, backend, poison_indices=poison, rng=rng)
    res = authentication.group_authenticate(
        packets, uavs, ta, tuav, backend, link=link,
        drone_ops=drone_ops, identify_culprits=identify,
        skip_timestamp_check=True)
    return backend, ta, tuav, uavs, res, drone_ops, len(poison)


# ---------------------------------------------------------------------------
# E1 - scaling with the UAV population
# ---------------------------------------------------------------------------
def e1_scaling(backend_name: str = "abstract",
               n_values=(5, 10, 20, 40, 60, 90, 120),
               rtt_ms: float = 40.0) -> pd.DataFrame:
    """Sweep n and measure every phase, separating TUAV from TA from link.

    The separation is the whole point: the paper reports only the TUAV column.
    """
    rows = []
    for n in n_values:
        _, _, _, _, res, drone_ops, _ = _one_run(
            backend_name, n, rtt_ms=rtt_ms)
        if not res.ok:
            continue
        rows += [
            {"n": n, "phase": "US (signing, all n)", "actor": "drone",
             "ms": drone_ops.wall_ms, "source": MEASURED, "backend": backend_name},
            {"n": n, "phase": "GA (TUAV side)", "actor": "tuav",
             "ms": res.tuav_ops.wall_ms, "source": MEASURED, "backend": backend_name},
            {"n": n, "phase": "GA (TA side)", "actor": "ta",
             "ms": res.ta_ops.wall_ms, "source": MEASURED, "backend": backend_name},
            {"n": n, "phase": "GA (link)", "actor": "link",
             "ms": res.link.latency_ms if res.link else 0.0,
             "source": MEASURED, "backend": backend_name},
            {"n": n, "phase": "GA (end-to-end)", "actor": "total",
             "ms": res.total_ms, "source": MEASURED, "backend": backend_name},
        ]
    return pd.DataFrame(rows)


def e1_paper_curve(n_values=(5, 10, 20, 40, 60, 90, 120)) -> pd.DataFrame:
    """The same sweep, from Table III. Analytical - nothing is run."""
    rows = []
    for scheme in paper_cost.all_schemes():
        for n in n_values:
            rows.append({
                "n": n, "scheme": scheme,
                "ms": paper_cost.cost(scheme, "GA", n),
                "source": paper_cost.SOURCE,
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# E2 / E3 - joining and revocation
# ---------------------------------------------------------------------------
def e2_joining(backend_name: str = "abstract", base: int = 5,
               joins=(1, 2, 5, 10)) -> pd.DataFrame:
    rows = []
    for add in joins:
        n = base + add
        backend, ta, tuav, uavs, res, _, _ = _one_run(backend_name, n)
        if not res.ok:
            continue
        seeds = {r.uav_index: r.sigma_seed for r in res.ta_responses}
        t0 = time.perf_counter()
        kres = key_management.distribute_group_key(
            uavs, tuav, backend, sigma_seeds=seeds, epoch=1,
            rng=random.Random(3))
        ms = (time.perf_counter() - t0) * 1000
        rows.append({
            "base": base, "joined": add, "members": n,
            "rekey ms": ms,
            "broadcast bytes": kres.broadcast.size_bytes if kres.broadcast else 0,
            "messages to survivors": 0,
            "source": MEASURED,
        })
    return pd.DataFrame(rows)


def e3_revocation(backend_name: str = "abstract", n: int = 12,
                  removals=(1, 2, 4, 6)) -> pd.DataFrame:
    rows = []
    for k in removals:
        backend, ta, tuav, uavs, res, _, _ = _one_run(backend_name, n)
        if not res.ok:
            continue
        seeds = {r.uav_index: r.sigma_seed for r in res.ta_responses}
        key_management.distribute_group_key(
            uavs, tuav, backend, sigma_seeds=seeds, epoch=1,
            rng=random.Random(4))

        revoked = [u.index for u in uavs[:k]]
        for u in uavs:
            if u.index in revoked:
                u.status = Status.REVOKED
        survivors = [u.index for u in uavs if u.index not in revoked]

        t0 = time.perf_counter()
        kres = key_management.update_group_key(
            uavs, tuav, backend, active_indices=survivors, epoch=2,
            rng=random.Random(5))
        ms = (time.perf_counter() - t0) * 1000

        current = tuav.group_key
        still_in = sum(1 for u in uavs if u.group_key == current)
        rows.append({
            "started with": n, "revoked": k, "survivors": len(survivors),
            "rekey ms": ms,
            "broadcast bytes": kres.broadcast.size_bytes if kres.broadcast else 0,
            "survivors holding new key": still_in,
            "revoked holding new key": sum(
                1 for u in uavs if u.index in revoked and u.group_key == current),
            "source": MEASURED,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# E7 - the availability cliff
# ---------------------------------------------------------------------------
def e7_availability(backend_name: str = "abstract", n: int = 12,
                    availabilities=(1.0, 0.9, 0.75, 0.5, 0.25, 0.1, 0.0),
                    trials: int = 12, rtt_ms: float = 40.0) -> pd.DataFrame:
    """Authentication success rate against TA-link availability.

    This figure needs no new cryptography: it is the published scheme's own
    behaviour. Because Step GA3 cannot be evaluated without the TA's response,
    the curve goes to zero rather than degrading.
    """
    rows = []
    for a in availabilities:
        ok = 0
        for t in range(trials):
            _, _, _, _, res, _, _ = _one_run(
                backend_name, n, rtt_ms=rtt_ms, availability=a, seed=100 + t)
            ok += 1 if res.ok else 0
        rows.append({
            "availability": a,
            "success rate": ok / trials,
            "authenticated per attempt": (ok / trials) * n,
            "trials": trials,
            "source": MEASURED,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# E8 - batch poisoning
# ---------------------------------------------------------------------------
def e8_poisoning(backend_name: str = "abstract", n: int = 20,
                 fractions=(0.0, 0.05, 0.1, 0.2, 0.3, 0.5),
                 trials: int = 6) -> pd.DataFrame:
    """Goodput against the fraction of forged credentials.

    Run twice: as published (no culprit identification) and with an individual
    fallback, to show what the missing else-branch would cost.
    """
    rows = []
    for frac in fractions:
        for identify in (False, True):
            verified = 0
            for t in range(trials):
                _, _, _, _, res, _, n_forged = _one_run(
                    backend_name, n, poison_fraction=frac,
                    identify=identify, seed=200 + t)
                verified += len(res.verified)
            rows.append({
                "forged fraction": frac,
                "mode": "published scheme" if not identify
                        else "with individual fallback",
                "avg verified": verified / trials,
                "goodput": (verified / trials) / n,
                "honest members present": n - max(1, int(round(n * frac))) if frac else n,
                "source": MEASURED,
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# E5 - temporary identity across sessions
# ---------------------------------------------------------------------------
def e5_pseudonyms(backend_name: str = "abstract", n: int = 4,
                  sessions: int = 5) -> pd.DataFrame:
    backend, ta, tuav, uavs, link = _fresh(backend_name, n)
    rng = random.Random(21)
    rows = []
    for s in range(1, sessions + 1):
        initialization.refresh_tuav_session(tuav, backend)
        signing.sign_batch(uavs, tuav, backend, rng=rng)
        for u in uavs:
            rows.append({
                "session": s,
                "UAV": u.name,
                "temporary ID": f"TEMP_{u.id_temp:x}".upper()[:14],
                "source": MEASURED,
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
@dataclass
class ExperimentSpec:
    key: str
    title: str
    description: str
    runner: object
    slow: bool = False


CATALOGUE = [
    ExperimentSpec("E1", "Scaling with UAV population",
                   "Sweep n and separate TUAV, TA and link cost.",
                   e1_scaling),
    ExperimentSpec("E2", "Dynamic joining",
                   "Add members and measure the rekey.", e2_joining),
    ExperimentSpec("E3", "Revocation",
                   "Remove members; check survivors and the revoked.",
                   e3_revocation),
    ExperimentSpec("E5", "Temporary identities",
                   "One UAV across sessions - unlinkability.", e5_pseudonyms),
    ExperimentSpec("E7", "Availability cliff",
                   "Success rate against TA-link availability.", e7_availability),
    ExperimentSpec("E8", "Batch poisoning",
                   "Goodput against forged-credential fraction.", e8_poisoning),
]
