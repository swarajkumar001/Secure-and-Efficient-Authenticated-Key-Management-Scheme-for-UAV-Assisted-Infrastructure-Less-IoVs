"""
STEP ZERO of the whole project.

The paper's aggregate verification equation (Step GA3) must balance for honest
members, and must fail when any member is dishonest.  If these tests do not
pass, either the equation has been mis-transcribed from the PDF or the paper
contains an error - and nothing should be built on top until we know which.

Run with:   pytest uav_iov_simulator/tests -v
"""

from __future__ import annotations

import random

import pytest

from uav_iov_simulator.crypto.interface import get_backend
from uav_iov_simulator.crypto.backend_pairing import is_available as pairing_available
from uav_iov_simulator.protocol import authentication, initialization, signing
from uav_iov_simulator.protocol.entities import Status
from uav_iov_simulator.protocol.link import TALink


BACKENDS = ["abstract"] + (["faithful"] if pairing_available() else [])


def _bootstrap(backend_name: str, n: int, seed: int = 11):
    backend = get_backend(backend_name)
    ta, tuav = initialization.initialize_system(backend, seed=seed)
    uavs = initialization.register_uavs(ta, n, backend, seed=seed)
    initialization.refresh_tuav_session(tuav, backend, now=1_000_000.0, seed=seed)
    return backend, ta, tuav, uavs


# ---------------------------------------------------------------------------
# The equation balances
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("backend_name", BACKENDS)
@pytest.mark.parametrize("n", [1, 2, 5])
def test_aggregate_equation_balances(backend_name, n):
    """Step GA3 must hold for n honest members."""
    backend, ta, tuav, uavs = _bootstrap(backend_name, n)
    packets, drone_ops = signing.sign_batch(
        uavs, tuav, backend, ts2=1_000_001.0, rng=random.Random(5)
    )
    link = TALink(rtt_ms=0.0, availability=1.0)
    res = authentication.group_authenticate(
        packets, uavs, ta, tuav, backend, link=link, drone_ops=drone_ops
    )
    assert res.ok, f"aggregate equation failed for n={n}: {res.reason}"
    assert len(res.verified) == n
    assert all(u.status == Status.AUTHENTICATED for u in uavs)


@pytest.mark.parametrize("backend_name", BACKENDS)
def test_individual_verification_agrees_with_batch(backend_name):
    """Each member must also pass on its own, with the same algebra."""
    backend, ta, tuav, uavs = _bootstrap(backend_name, 4)
    packets, _ = signing.sign_batch(uavs, tuav, backend, ts2=1_000_001.0,
                                    rng=random.Random(6))
    responses, _ = authentication.ta_precompute(packets, ta, tuav, backend)
    good, bad, _ = authentication.verify_individually(responses, tuav, backend)
    assert bad == []
    assert sorted(good) == sorted(u.index for u in uavs)


# ---------------------------------------------------------------------------
# The equation fails when it should
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("backend_name", BACKENDS)
def test_one_forged_credential_breaks_the_whole_batch(backend_name):
    """The behaviour the paper never addresses.

    One malformed credential out of n must fail the aggregate - and the
    published scheme must NOT be able to say which one it was.
    """
    backend, ta, tuav, uavs = _bootstrap(backend_name, 5)
    victim = uavs[2].index
    packets, drone_ops = signing.sign_batch(
        uavs, tuav, backend, ts2=1_000_001.0,
        poison_indices={victim}, rng=random.Random(7)
    )
    link = TALink(rtt_ms=0.0, availability=1.0)
    res = authentication.group_authenticate(
        packets, uavs, ta, tuav, backend, link=link, drone_ops=drone_ops
    )

    assert not res.ok
    assert len(res.rejected) == 5, "all members must be rejected, not just the bad one"
    assert res.verified == []
    assert res.culprits_identified is False, (
        "Step GA4 has no else-branch; the scheme cannot identify the culprit"
    )


@pytest.mark.parametrize("backend_name", BACKENDS)
def test_culprit_can_be_found_only_by_leaving_the_published_scheme(backend_name):
    """Turning on individual fallback locates the culprit - at n extra checks."""
    backend, ta, tuav, uavs = _bootstrap(backend_name, 5)
    victim = uavs[1].index
    packets, drone_ops = signing.sign_batch(
        uavs, tuav, backend, ts2=1_000_001.0,
        poison_indices={victim}, rng=random.Random(8)
    )
    link = TALink(rtt_ms=0.0, availability=1.0)
    res = authentication.group_authenticate(
        packets, uavs, ta, tuav, backend, link=link,
        drone_ops=drone_ops, identify_culprits=True
    )

    assert not res.ok
    assert res.culprits_identified
    assert res.rejected == [victim]
    assert len(res.verified) == 4


# ---------------------------------------------------------------------------
# The architectural claim: no pairings on the TUAV
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("backend_name", BACKENDS)
def test_tuav_performs_no_pairings(backend_name):
    """The paper's efficiency rests entirely on this being true."""
    backend, ta, tuav, uavs = _bootstrap(backend_name, 4)
    packets, _ = signing.sign_batch(uavs, tuav, backend, ts2=1_000_001.0,
                                    rng=random.Random(9))
    _, ta_ops = authentication.ta_precompute(packets, ta, tuav, backend)
    responses, _ = authentication.ta_precompute(packets, ta, tuav, backend)
    _, tuav_ops = authentication.tuav_aggregate_check(responses, tuav, backend)

    assert tuav_ops.pairing == 0, "the TUAV must never compute a pairing"
    assert ta_ops.hash > 0


# ---------------------------------------------------------------------------
# The availability cliff
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("backend_name", BACKENDS)
def test_authentication_stops_entirely_when_ta_is_unreachable(backend_name):
    """Not 'degrades'. Stops.

    This is the finding the simulator exists to demonstrate: with the TA link
    down, Step GA3 cannot be evaluated at all, so the success rate is zero
    rather than reduced.
    """
    backend, ta, tuav, uavs = _bootstrap(backend_name, 6)
    packets, drone_ops = signing.sign_batch(uavs, tuav, backend, ts2=1_000_001.0,
                                            rng=random.Random(10))
    link = TALink(rtt_ms=40.0, availability=0.0)      # link completely down
    res = authentication.group_authenticate(
        packets, uavs, ta, tuav, backend, link=link, drone_ops=drone_ops
    )

    assert not res.ok
    assert res.verified == []
    assert len(res.rejected) == 6
    assert res.link is not None and not res.link.delivered
    assert "no local verification path" in res.reason


@pytest.mark.parametrize("backend_name", BACKENDS)
def test_link_latency_is_on_the_critical_path(backend_name):
    """End-to-end time must include the link, even though the paper omits it.

    Note on how this is asserted: we compare the link component against the
    reported end-to-end figure, NOT total wall time across two separate runs.
    Pairing cost in pure Python varies by hundreds of milliseconds run to run,
    which would swamp the signal and make the test flaky rather than meaningful.
    """
    backend, ta, tuav, uavs = _bootstrap(backend_name, 3)
    packets, drone_ops = signing.sign_batch(uavs, tuav, backend, ts2=1_000_001.0,
                                            rng=random.Random(12))
    res = authentication.group_authenticate(
        packets, uavs, ta, tuav, backend,
        link=TALink(rtt_ms=600.0), drone_ops=drone_ops)

    assert res.ok
    assert res.link is not None and res.link.delivered
    assert res.link.latency_ms == pytest.approx(600.0)

    compute_only = res.ta_ops.wall_ms + res.tuav_ops.wall_ms
    assert res.total_ms == pytest.approx(compute_only + 600.0, abs=1e-6), (
        "the TA round trip must appear in the end-to-end figure"
    )
    assert res.total_ms > compute_only


@pytest.mark.parametrize("backend_name", BACKENDS)
def test_link_bytes_are_counted_in_both_directions(backend_name):
    """The offload costs bandwidth as well as latency, and the paper's Table V
    accounts for neither."""
    backend, ta, tuav, uavs = _bootstrap(backend_name, 4)
    packets, drone_ops = signing.sign_batch(uavs, tuav, backend, ts2=1_000_001.0,
                                            rng=random.Random(13))
    res = authentication.group_authenticate(
        packets, uavs, ta, tuav, backend,
        link=TALink(rtt_ms=10.0), drone_ops=drone_ops)

    assert res.link.bytes_up > 0
    assert res.link.bytes_down > 0
    assert res.link.bytes_down > res.link.bytes_up, (
        "the TA returns target-group elements, which are larger than the request"
    )
