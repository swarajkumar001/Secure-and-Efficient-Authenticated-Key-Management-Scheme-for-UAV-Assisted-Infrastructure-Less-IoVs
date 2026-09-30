"""
The paper's analytical cost model - Table III of Section VI-A.

THIS IS A CALCULATOR, NOT A SIMULATION.
---------------------------------------
Nothing here runs any cryptography. It evaluates the closed-form expressions the
paper prints, using the MIRACL constants the paper borrows from its reference
[47], at an 80-bit security level on the paper's benchmark machine.

It is deliberately outside the CryptoBackend interface so that a reported number
can never be confused with a measured one. Everything this module returns is
tagged `source="paper (analytical)"`.
"""

from __future__ import annotations

from dataclasses import dataclass

from .. import config

SOURCE = "paper (analytical)"


@dataclass
class CostPoint:
    scheme: str
    phase: str
    n: int
    ms: float
    source: str = SOURCE


def cost(scheme: str, phase: str, n: int = 1) -> float:
    """Evaluate Table III for one scheme, one phase, at n UAVs.

    US and SA are per-operation and do not depend on n; GA is linear in n.
    """
    try:
        const, per_uav = config.PAPER_COSTS[scheme][phase]
    except KeyError as exc:
        raise KeyError(
            f"unknown scheme/phase {scheme!r}/{phase!r}; "
            f"schemes are {list(config.PAPER_COSTS)}"
        ) from exc
    return const + per_uav * n


def curve(scheme: str, phase: str, n_values) -> list[CostPoint]:
    return [CostPoint(scheme, phase, n, cost(scheme, phase, n)) for n in n_values]


def all_schemes() -> list[str]:
    return list(config.PAPER_COSTS)


def baselines() -> list[str]:
    return [s for s in config.PAPER_COSTS if s != "Proposed (paper)"]


def table(n: int) -> list[dict]:
    """Reproduce Table III at a given n, as the paper prints it."""
    rows = []
    for scheme in all_schemes():
        c = config.PAPER_COSTS[scheme]
        ga_const, ga_per = c["GA"]
        rows.append({
            "Scheme": scheme,
            "US (ms)": round(cost(scheme, "US"), 4),
            "SA (ms)": round(cost(scheme, "SA"), 4),
            "GA expression": f"{ga_per:g}n + {ga_const:g}",
            f"GA at n={n} (ms)": round(cost(scheme, "GA", n), 4),
        })
    return rows


def headline_check() -> dict:
    """Verify our transcription against the figures the paper states in prose.

    Section VI-A reports 1.8203 ms, 2.1578 ms, and 151.1934 ms at n = 120. If
    this does not reproduce them exactly, Table III was mis-transcribed into
    config.py and every chart drawn from it is wrong.
    """
    h = config.PAPER_HEADLINE
    got_us = cost("Proposed (paper)", "US")
    got_sa = cost("Proposed (paper)", "SA")
    got_ga = cost("Proposed (paper)", "GA", h["n"])
    return {
        "US": (got_us, h["US_ms"], abs(got_us - h["US_ms"]) < 1e-4),
        "SA": (got_sa, h["SA_ms"], abs(got_sa - h["SA_ms"]) < 1e-4),
        f"GA at n={h['n']}": (got_ga, h["GA_ms_at_120"],
                              abs(got_ga - h["GA_ms_at_120"]) < 1e-3),
    }


def improvement_vs_baselines(phase: str, n: int = 120) -> list[dict]:
    """Table IV - percentage improvement of the proposed scheme."""
    ours = cost("Proposed (paper)", phase, n)
    rows = []
    for b in baselines():
        theirs = cost(b, phase, n)
        rows.append({
            "Baseline": b,
            "Baseline (ms)": round(theirs, 3),
            "Proposed (ms)": round(ours, 3),
            "Improvement": f"{(theirs - ours) / theirs * 100:.1f}%",
        })
    return rows


WHY_NOT_COMPARABLE = (
    "These are the PAPER's numbers: MIRACL (C) at 80-bit security, on the "
    "authors' machine. Our simulator is pure Python on BN128. The absolute "
    "milliseconds are roughly two orders of magnitude apart and must never be "
    "compared directly. What IS comparable is the shape: linear in n, and the "
    "relative ordering of the slopes."
)
