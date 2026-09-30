"""
Phase C - group authentication.  Steps GA1 to GA4 of the paper.

GA1  The TUAV extracts <ts2, ID_i, xi_i, upsilon_i> and UPLOADS IT TO THE TA.
GA2  The TA - the only party that can map ID_i back to <id_i, s_i> - computes

        sigma_i = h1(s_i * xi_i) * P
        psi_i   = e(Gamma_i + h1(s_i * xi_i) P, P)
        mu_i    = e(h3(ID_i, ts2, s_i) P, s_i P)
        delta_i = e(s_tu P, upsilon_i * xi_i * P)

     and returns <sigma_i, psi_i, mu_i, delta_i> to the TUAV.

GA3  The TUAV checks ONE equation over all n members:

        PROD psi_i * (PROD delta_i) ** h2(ID_tu, r_tu)  ==  PROD mu_i ** R_tu

GA4  If it matches, every requester is valid.


WHY THE EQUATION BALANCES
-------------------------
Writing E = e(P, P) and H = h2(ID_tu, r_tu), and using Q_tu = s_tu * H * P:

    Gamma_i + sigma_i = (A_i - B_i) P - upsilon_i xi_i Q_tu + B_i P
                      = A_i P - upsilon_i xi_i s_tu H P

    psi_i   = E ** (A_i - upsilon_i xi_i s_tu H)
    delta_i = E ** (s_tu upsilon_i xi_i)

    PROD psi_i * (PROD delta_i) ** H
        = E ** ( SUM A_i - s_tu H SUM(upsilon_i xi_i) + H s_tu SUM(upsilon_i xi_i) )
        = E ** SUM A_i

    PROD mu_i ** R_tu = E ** ( R_tu * SUM h3(ID_i, ts2, s_i) s_i )

and since A_i = s_i * h3(ID_i, ts2, s_i) * R_tu the two sides agree.

The cancellation works only because the last term of Gamma_i uses h1(r_i),
which equals the transmitted xi_i.  That is the hinge of the whole construction.


THE ARCHITECTURAL POINT
-----------------------
Note where the pairings happen: all of them are in GA2, on the TA.  The TUAV
performs only target-group multiplications and two exponentiations.  That is
exactly why the paper's reported group-authentication cost is small - and it is
also why the TUAV cannot verify anybody when the TA link is unavailable.  Both
facts are measured separately below.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from ..crypto.hash_utils import h1, h3
from ..crypto.interface import Backend, OpCount, Timer
from .entities import RequestPacket, TA, TUAV, UAV, Status
from .link import LinkResult, TALink


@dataclass
class TAResponse:
    """What Step GA2 returns to the TUAV, per UAV."""
    uav_index: int
    sigma_point: Any      # sigma_i = h1(s_i xi_i) * P
    sigma_seed: int       # h1(s_i xi_i) as an integer - the CRT seed. See crypto/crt.py
    psi: Any
    mu: Any
    delta: Any


@dataclass
class AuthResult:
    """Outcome of one group-authentication attempt."""

    ok: bool
    n_requested: int
    verified: list[int] = field(default_factory=list)
    rejected: list[int] = field(default_factory=list)
    stale: list[int] = field(default_factory=list)
    culprits_identified: bool = False
    reason: str = ""

    link: LinkResult | None = None
    ta_ops: OpCount = field(default_factory=OpCount)
    tuav_ops: OpCount = field(default_factory=OpCount)
    drone_ops: OpCount = field(default_factory=OpCount)

    ta_responses: list[TAResponse] = field(default_factory=list)

    @property
    def total_ms(self) -> float:
        link_ms = self.link.latency_ms if self.link else 0.0
        return self.ta_ops.wall_ms + self.tuav_ops.wall_ms + link_ms

    def summary(self) -> dict:
        return {
            "result": "SUCCESS" if self.ok else "FAILED",
            "requested": self.n_requested,
            "verified": len(self.verified),
            "rejected": len(self.rejected),
            "culprit identified": self.culprits_identified,
            "TUAV ms": round(self.tuav_ops.wall_ms, 3),
            "TA ms": round(self.ta_ops.wall_ms, 3),
            "link ms": round(self.link.latency_ms, 3) if self.link else 0.0,
            "end-to-end ms": round(self.total_ms, 3),
            "reason": self.reason,
        }


# ---------------------------------------------------------------------------
# Step GA1 - the timestamp check, performed by the TUAV before the offload
# ---------------------------------------------------------------------------
def check_freshness(packets: list[RequestPacket], *, now: float,
                    window_s: float) -> tuple[list[RequestPacket], list[RequestPacket]]:
    """Step GA1 begins "After checking the timestamp and the received upsilon_i".

    This is the first of the two defences behind Theorem 3 (replay resistance).
    The second is cryptographic and needs no check at all - see the note in
    group_authenticate.

    Returns (fresh, stale).
    """
    fresh, stale = [], []
    for p in packets:
        (fresh if abs(now - p.ts2) <= window_s else stale).append(p)
    return fresh, stale


# ---------------------------------------------------------------------------
# Step GA2 - performed by the TA
# ---------------------------------------------------------------------------
def ta_precompute(packets: list[RequestPacket], ta: TA, tuav: TUAV,
                  backend: Backend) -> tuple[list[TAResponse], OpCount]:
    """Every pairing in the protocol happens here, on the TA."""
    counter = OpCount()
    q = backend.order
    out: list[TAResponse] = []

    # The backend tallies primitives on its own counter. Snapshot it so the
    # returned OpCount carries the real pairing count, not just wall time -
    # "the TA computed 24 pairings, the TUAV computed 0" is the whole point.
    before = backend.counter.copy()

    with Timer(counter):
        for pkt in packets:
            s_i = ta.registry[pkt.uav_index]

            # sigma_i = h1(s_i * xi_i) * P
            sigma_seed = h1((s_i * pkt.xi) % q, order=q)
            counter.hash += 1
            sigma_pt = backend.g1_mul(sigma_seed)

            # psi_i = e(Gamma_i + sigma_i, P)   <- a genuine pairing on received bytes
            psi = backend.pair_with_P(backend.g1_add(pkt.gamma, sigma_pt))

            # mu_i = e(h3(ID_i, ts2, s_i) P, s_i P) = E ** (h3 * s_i)
            h3_inner = h3(pkt.id_temp, pkt.ts2, s_i, order=q)
            counter.hash += 1
            mu = backend.e_PP_pow((h3_inner * s_i) % q)

            # delta_i = e(s_tu P, upsilon_i xi_i P) = E ** (s_tu * upsilon_i * xi_i)
            delta = backend.e_PP_pow((tuav.s * pkt.upsilon % q) * pkt.xi % q)

            out.append(TAResponse(
                uav_index=pkt.uav_index,
                sigma_point=sigma_pt,
                sigma_seed=sigma_seed,
                psi=psi, mu=mu, delta=delta,
            ))

    primitives = backend.counter.minus(before)
    primitives.wall_ms = counter.wall_ms
    primitives.hash = counter.hash
    return out, primitives


# ---------------------------------------------------------------------------
# Step GA3 - performed by the TUAV.  No pairings here.
# ---------------------------------------------------------------------------
def tuav_aggregate_check(responses: list[TAResponse], tuav: TUAV,
                         backend: Backend) -> tuple[bool, OpCount]:
    """The single equation of Step GA3."""
    counter = OpCount()
    before = backend.counter.copy()

    with Timer(counter):
        prod_psi = backend.gt_one()
        prod_delta = backend.gt_one()
        prod_mu = backend.gt_one()
        for r in responses:
            prod_psi = backend.gt_mul(prod_psi, r.psi)
            prod_delta = backend.gt_mul(prod_delta, r.delta)
            prod_mu = backend.gt_mul(prod_mu, r.mu)
            counter.gt_mul += 3

        lhs = backend.gt_mul(prod_psi, backend.gt_pow(prod_delta, tuav.H))
        rhs = backend.gt_pow(prod_mu, tuav.R)
        counter.gt_pow += 2
        counter.gt_mul += 1

        ok = backend.gt_eq(lhs, rhs)

    primitives = backend.counter.minus(before)
    primitives.wall_ms = counter.wall_ms

    # gt_one() on the faithful backend lazily computes e(P,P) once, which the
    # backend counts as a pairing. That is setup, not verification work, and it
    # happens once per process - so it is not charged to the TUAV here.
    primitives.pairing = 0
    return ok, primitives


def verify_individually(responses: list[TAResponse], tuav: TUAV,
                        backend: Backend) -> tuple[list[int], list[int], OpCount]:
    """Single-UAV verification (the paper's 'SA' phase), applied member by member.

    This is NOT part of Steps GA1-GA4.  The paper has no failure branch at all:
    Step GA4 says only "If matches, the validity of the vehicles can be proved."
    We provide this separately so that the batch-poisoning experiment can show
    what identifying the culprit would cost, and how the published scheme cannot
    do it.
    """
    counter = OpCount()
    good: list[int] = []
    bad: list[int] = []

    with Timer(counter):
        for r in responses:
            lhs = backend.gt_mul(r.psi, backend.gt_pow(r.delta, tuav.H))
            rhs = backend.gt_pow(r.mu, tuav.R)
            counter.gt_mul += 1
            counter.gt_pow += 2
            (good if backend.gt_eq(lhs, rhs) else bad).append(r.uav_index)

    return good, bad, counter


# ---------------------------------------------------------------------------
# The whole phase
# ---------------------------------------------------------------------------
def group_authenticate(packets: list[RequestPacket], uavs: list[UAV],
                       ta: TA, tuav: TUAV, backend: Backend, *,
                       link: TALink,
                       drone_ops: OpCount | None = None,
                       identify_culprits: bool = False,
                       now: float | None = None,
                       replay_window_s: float | None = None,
                       skip_timestamp_check: bool = False) -> AuthResult:
    """Steps GA1 to GA4, including the simulated TA link.

    `identify_culprits` is OFF by default because the published scheme cannot do
    it.  Turning it on shows what a fix would cost - it is not a claim about the
    paper.

    `skip_timestamp_check` exists only for the replay demonstration.  Disabling
    the timestamp filter shows the SECOND defence behind Theorem 3: a replayed
    packet from an earlier session still fails, because R_tu and ID_tu are
    regenerated each session, so

        s_i h3(ID_i, ts2, s_i) R_tu  -  s_i h3(ID_i, ts2', s_i) R_tu'  !=  0

    and the aggregate equation cannot balance.  Freshness is enforced twice
    over, and only one of the two can be switched off.
    """
    by_index = {u.index: u for u in uavs}
    result = AuthResult(ok=False, n_requested=len(packets))
    result.drone_ops = drone_ops or OpCount()

    if not packets:
        result.reason = "no authentication requests"
        return result

    # ---- GA1a: timestamp freshness ---------------------------------------
    if not skip_timestamp_check and replay_window_s is not None:
        now = now if now is not None else time.time()
        packets, stale = check_freshness(packets, now=now, window_s=replay_window_s)
        result.stale = [p.uav_index for p in stale]
        for p in stale:
            if p.uav_index in by_index:
                by_index[p.uav_index].status = Status.FAILED
        if not packets:
            result.rejected = result.stale
            result.reason = (
                f"all {len(stale)} request(s) rejected at Step GA1: timestamp "
                f"outside the {replay_window_s:g} s acceptance window"
            )
            return result

    # ---- GA1b: the offload.  This is where the dependency lives. ----------
    link_result = link.traverse(payload_count=len(packets))
    result.link = link_result

    if not link_result.delivered:
        # The paper has no local fallback: Step GA3 cannot be evaluated at all.
        result.reason = (
            "TA unreachable - Step GA3 cannot be evaluated. The scheme has no "
            "local verification path, so authentication does not degrade, it stops."
        )
        result.rejected = [p.uav_index for p in packets]
        for p in packets:
            by_index[p.uav_index].status = Status.FAILED
        return result

    # ---- GA2: the TA does every pairing ----------------------------------
    responses, ta_ops = ta_precompute(packets, ta, tuav, backend)
    result.ta_responses = responses
    result.ta_ops = ta_ops

    # ---- GA3/GA4: one equation on the TUAV -------------------------------
    ok, tuav_ops = tuav_aggregate_check(responses, tuav, backend)
    result.tuav_ops = tuav_ops
    result.ok = ok

    if ok:
        result.verified = [p.uav_index for p in packets]
        for idx in result.verified:
            by_index[idx].status = Status.AUTHENTICATED
        result.reason = f"aggregate equation balanced - all {len(packets)} members valid"
        return result

    # ---- Failure. ---------------------------------------------------------
    if identify_culprits:
        good, bad, extra = verify_individually(responses, tuav, backend)
        result.tuav_ops = result.tuav_ops.merge(extra)
        result.verified, result.rejected = good, bad
        result.culprits_identified = True
        for idx in good:
            by_index[idx].status = Status.AUTHENTICATED
        for idx in bad:
            by_index[idx].status = Status.FAILED
        result.reason = (
            f"aggregate failed; {len(bad)} culprit(s) located by falling back to "
            f"{len(responses)} individual checks (NOT part of the published scheme)"
        )
    else:
        result.rejected = [p.uav_index for p in packets]
        for p in packets:
            by_index[p.uav_index].status = Status.FAILED
        result.reason = (
            f"aggregate equation did not balance - all {len(packets)} members "
            "rejected, culprit unknown. Step GA4 of the paper has no else-branch."
        )

    return result
