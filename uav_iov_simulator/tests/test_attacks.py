"""
Adversary tests.

These assert BEHAVIOUR. They do not prove the paper's theorems, and the module
under test says so in its own docstring. What they do give is a guarantee that
the demonstrations shown during a presentation are real - that "BLOCKED" on the
screen corresponds to an attack genuinely failing, not to a hard-coded outcome.
"""

from __future__ import annotations

import random

import pytest

from uav_iov_simulator import state as S
from uav_iov_simulator.simulation import attacks, datalink
from uav_iov_simulator.visualization import security


def _running_system(n: int = 6, keyed: bool = True) -> S.SystemState:
    st = S.SystemState()
    st.rng = random.Random(42)
    st = S.act_initialize(st, backend_name="abstract", rtt_ms=0.0, availability=1.0)
    st = S.act_register(st, n)
    st = S.act_authenticate(st)
    if keyed:
        st = S.act_distribute_key(st)
    return st


# ---------------------------------------------------------------------------
# Replay - Theorem 3
# ---------------------------------------------------------------------------
def test_replay_blocked_by_timestamp_window():
    st = _running_system()
    st = S.act_capture_packet(st)
    assert st.captured_packet is not None

    st = S.act_replay(st, delay_s=st.replay_window_s + 60)
    res = st.evidence["replay"]
    assert res.blocked
    assert "timestamp" in res.stage.lower()


def test_replay_blocked_cryptographically_when_timestamp_check_disabled():
    """The second defence behind Theorem 3.

    Switch off the timestamp filter, move to a new session, and the replayed
    credential still fails - because R_tu and ID_tu were regenerated.
    """
    st = _running_system()
    st = S.act_capture_packet(st)

    st = S.act_new_session(st)          # new r_tu -> new R_tu and ID_tu
    st = S.act_replay(st, delay_s=5.0, bypass_timestamp=True)

    res = st.evidence["replay"]
    assert res.blocked, "a replayed credential must fail in a new session"
    assert "GA3" in res.stage


def test_replay_within_the_same_session_is_not_a_forgery():
    """Honesty check on our own demo.

    Inside the same session, with the timestamp check off, the captured packet
    IS still valid - because it genuinely is. We must not dress that up as an
    attack being blocked.
    """
    st = _running_system()
    st = S.act_capture_packet(st)
    st = S.act_replay(st, delay_s=1.0, bypass_timestamp=True)

    res = st.evidence["replay"]
    assert not res.blocked
    assert "expected" in " ".join(res.narrative).lower()


# ---------------------------------------------------------------------------
# Impersonation - Theorem 1
# ---------------------------------------------------------------------------
def test_impersonation_is_rejected():
    st = _running_system()
    st = S.act_impersonate(st)
    res = st.evidence["impersonation"]
    assert res.blocked
    assert res.detail["outcome"].startswith("REJECTED")


# ---------------------------------------------------------------------------
# Revocation - Steps DU1/DU2
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not datalink.available(),
                    reason="the `cryptography` package is not installed")
def test_revoked_member_cannot_open_current_traffic():
    st = _running_system()
    victim = st.uavs[2].index
    st = S.act_remove_uav(st, [victim])
    st = S.act_update_key(st)
    st = S.act_revoked_access(st)

    res = st.evidence["revoked_access"]
    assert res.blocked
    assert res.detail["outcome"] == "ACCESS DENIED"


@pytest.mark.skipif(not datalink.available(),
                    reason="the `cryptography` package is not installed")
def test_group_broadcast_opens_for_members_only():
    st = _running_system()
    victim = st.uavs[1].index
    st = S.act_remove_uav(st, [victim])
    st = S.act_update_key(st)

    st = S.act_exchange(st, "ACCIDENT DETECTED")
    ex = st.last_exchange
    assert ex is not None
    names = {u.index: u.name for u in st.uavs}
    assert names[victim] in ex.denied
    assert len(ex.opened_by) == len(st.uavs) - 1


@pytest.mark.skipif(not datalink.available(),
                    reason="the `cryptography` package is not installed")
def test_wrong_key_fails_the_aead_tag_rather_than_producing_garbage():
    env = datalink.encrypt(123456789, b"SECRET PAYLOAD", epoch=1)
    assert datalink.try_decrypt(123456789, env) == b"SECRET PAYLOAD"
    assert datalink.try_decrypt(987654321, env) is None


# ---------------------------------------------------------------------------
# Batch poisoning - the one that succeeds
# ---------------------------------------------------------------------------
def test_batch_poisoning_succeeds_against_the_published_scheme():
    """This attack is NOT blocked, and the test asserts that it is not.

    One forged credential denies authentication to the whole swarm and the
    scheme cannot identify the culprit.
    """
    st = S.SystemState()
    st.rng = random.Random(7)
    st = S.act_initialize(st, backend_name="abstract", rtt_ms=0.0, availability=1.0)
    st = S.act_register(st, 10)
    st = S.act_authenticate(st, poison_fraction=0.1)
    st = S.act_batch_poison_report(st)

    res = st.evidence["batch_poison"]
    assert not res.blocked, "the published scheme has no defence here"
    assert res.detail["culprit identified"] == "NO"
    assert res.detail["honest members rejected"] >= 8


def test_culprit_identification_requires_leaving_the_published_scheme():
    st = S.SystemState()
    st.rng = random.Random(7)
    st = S.act_initialize(st, backend_name="abstract", rtt_ms=0.0, availability=1.0)
    st = S.act_register(st, 10)
    st = S.act_authenticate(st, poison_fraction=0.1, identify_culprits=True)
    st = S.act_batch_poison_report(st)

    res = st.evidence["batch_poison"]
    assert res.blocked
    assert "NOT part of the published scheme" in " ".join(res.narrative)


# ---------------------------------------------------------------------------
# Anonymity and unlinkability - F9, F6
# ---------------------------------------------------------------------------
def test_pseudonyms_differ_every_session():
    st = _running_system(n=4, keyed=False)
    st = S.act_new_session(st)
    st = S.act_authenticate(st)
    st = S.act_new_session(st)
    st = S.act_authenticate(st)

    for u in st.uavs:
        ids = [t for _, t in u.history]
        assert len(ids) == 3
        assert len(set(ids)) == 3, "a pseudonym was reused across sessions"


def test_eavesdropper_cannot_link_observations():
    st = _running_system(n=4, keyed=False)
    st = S.act_new_session(st)
    st = S.act_authenticate(st)

    view = attacks.eavesdropper_view(st)
    assert not view.linkable
    assert len(view.observed) == 8
    assert all(r["Attacker can attribute to"] == "unknown" for r in view.observed)


def test_only_the_ta_can_reverse_a_pseudonym():
    st = _running_system(n=3, keyed=False)
    st = S.act_reveal_identity(st, "UAV1")
    assert st.revealed_identity is not None
    assert st.evidence.get("identity_resolved") is True
    # Even here, the raw permanent identity is never exposed.
    assert "fingerprint" in " ".join(st.revealed_identity.keys()).lower()


# ---------------------------------------------------------------------------
# The security board must not overclaim
# ---------------------------------------------------------------------------
def test_security_board_never_claims_proof():
    st = _running_system()
    rows = security.evaluate(st)
    assert len(rows) == 11
    for r in rows:
        assert r.level in (security.DEMONSTRATED, security.STRUCTURAL,
                           security.NOT_SHOWN)
        assert "prove" not in r.evidence.lower()


def test_forward_secrecy_and_non_repudiation_are_marked_not_shown():
    """Two of the paper's eleven ticks are honestly left unclaimed."""
    st = _running_system()
    rows = {r.tag: r for r in security.evaluate(st)}
    assert rows["F7"].level == security.NOT_SHOWN
    assert rows["F10"].level == security.NOT_SHOWN
