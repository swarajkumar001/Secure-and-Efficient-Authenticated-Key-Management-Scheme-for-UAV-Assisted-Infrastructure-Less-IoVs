"""
Smoke tests for the Streamlit shell.

These do not check that the UI looks right - they check that every render path
executes without raising, including the ones that only run after a button is
pressed. Streamlit re-runs the whole script on every interaction, so a path that
is only reachable in one state is exactly the kind of thing that breaks
silently during a live demo.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from streamlit.testing.v1 import AppTest

# AppTest resolves relative paths against the CALLING file, so be absolute.
APP = str(Path(__file__).resolve().parent.parent / "app.py")
TIMEOUT = 90


def _run() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=TIMEOUT)
    at.run()
    return at


def test_app_starts_clean():
    at = _run()
    assert not at.exception, [str(e) for e in at.exception]


def test_initialize_then_authenticate_then_key():
    """The full happy path, driven through the real widgets."""
    at = _run()
    assert not at.exception

    # Initialize
    init = [b for b in at.button if b.label == "Initialize"][0]
    init.click().run()
    assert not at.exception, [str(e) for e in at.exception]

    # Authenticate
    auth = [b for b in at.button if b.label == "Start Authentication"][0]
    auth.click().run()
    assert not at.exception, [str(e) for e in at.exception]

    sim = at.session_state["sys"]
    assert sim.last_auth is not None and sim.last_auth.ok

    # Distribute the group key
    key = [b for b in at.button if b.label == "Distribute Group Key"][0]
    key.click().run()
    assert not at.exception, [str(e) for e in at.exception]

    sim = at.session_state["sys"]
    assert sim.last_key is not None and sim.last_key.ok
    assert len(sim.keyed) == len(sim.last_key.recovered)


def _btn(at: AppTest, label: str):
    """Find a button by its label. Index-based lookup is too brittle - adding
    one widget anywhere shifts every index after it."""
    matches = [b for b in at.button if b.label == label]
    assert matches, f"no button labelled {label!r}"
    return matches[0]


def _slider(at: AppTest, label: str):
    matches = [s for s in at.slider if s.label == label]
    assert matches, f"no slider labelled {label!r}"
    return matches[0]


def test_all_tabs_render_after_a_full_run():
    """Every tab must survive the post-authentication state."""
    at = _run()
    _btn(at, "Initialize").click().run()
    _btn(at, "Start Authentication").click().run()
    _btn(at, "Distribute Group Key").click().run()
    assert not at.exception, [str(e) for e in at.exception]

    # The packet inspector, the metric rows and the security board all live on
    # these tabs; a wrong formatting call surfaces here as an exception.
    assert len(at.tabs) == 11
    assert len(at.dataframe) >= 3
    assert len(at.metric) >= 4


def test_presentation_mode_renders_every_step():
    """Nine steps, driven the way they will be driven on the night."""
    at = _run()
    _btn(at, "Initialize").click().run()
    _btn(at, "Start Authentication").click().run()
    _btn(at, "Distribute Group Key").click().run()

    at.toggle[0].set_value(True).run()
    assert not at.exception, [str(e) for e in at.exception]

    for _ in range(8):
        nxt = [b for b in at.button if b.label == "Next"]
        if not nxt or nxt[0].disabled:
            break
        nxt[0].click().run()
        assert not at.exception, [str(e) for e in at.exception]

    assert at.session_state["pstep"] == 8


def test_performance_tab_and_sweeps_render():
    """The experiment sweeps and every chart built from them."""
    at = AppTest.from_file(APP, default_timeout=240)
    at.run()
    _btn(at, "Initialize").click().run()
    _btn(at, "Start Authentication").click().run()

    _btn(at, "E7 · availability cliff").click().run()
    assert not at.exception, [str(e) for e in at.exception]
    _btn(at, "E8 · batch poisoning").click().run()
    assert not at.exception, [str(e) for e in at.exception]

    assert "e7" in at.session_state
    assert "e8" in at.session_state
    assert not at.session_state["e7"].empty
    assert not at.session_state["e8"].empty


def test_link_outage_path_renders():
    """The availability-cliff branch has its own rendering path."""
    at = AppTest.from_file(APP, default_timeout=TIMEOUT)
    at.run()
    _btn(at, "Initialize").click().run()

    _slider(at, "Availability").set_value(0.0).run()
    _btn(at, "Start Authentication").click().run()
    assert not at.exception, [str(e) for e in at.exception]

    sim = at.session_state["sys"]
    assert sim.last_auth is not None
    assert not sim.last_auth.ok, "with the link down, nothing may authenticate"
    assert sim.last_auth.verified == []


# ---------------------------------------------------------------------------
# Stage 2 render paths
# ---------------------------------------------------------------------------
def test_attack_tab_paths_render():
    at = _run()
    _btn(at, "Initialize").click().run()
    _btn(at, "Start Authentication").click().run()
    _btn(at, "Distribute Group Key").click().run()

    _btn(at, "Capture packet").click().run()
    assert not at.exception, [str(e) for e in at.exception]
    _btn(at, "Replay packet").click().run()
    assert not at.exception, [str(e) for e in at.exception]
    _btn(at, "Attempt impersonation").click().run()
    assert not at.exception, [str(e) for e in at.exception]
    _btn(at, "Report on the last batch").click().run()
    assert not at.exception, [str(e) for e in at.exception]

    sim = at.session_state["sys"]
    assert sim.evidence["replay"].blocked
    assert sim.evidence["impersonation"].blocked


def test_secure_exchange_tab_renders():
    at = _run()
    _btn(at, "Initialize").click().run()
    _btn(at, "Start Authentication").click().run()
    _btn(at, "Distribute Group Key").click().run()

    _btn(at, "Encrypt and broadcast").click().run()
    assert not at.exception, [str(e) for e in at.exception]

    sim = at.session_state["sys"]
    assert sim.last_exchange is not None
    assert len(sim.last_exchange.opened_by) == len(sim.uavs)


def test_anonymity_tab_and_identity_reveal_render():
    at = _run()
    _btn(at, "Initialize").click().run()
    _btn(at, "Start Authentication").click().run()
    _btn(at, "New Session (new pseudonyms)").click().run()
    _btn(at, "Start Authentication").click().run()
    assert not at.exception, [str(e) for e in at.exception]

    _btn(at, "Reveal identity (TA only)").click().run()
    assert not at.exception, [str(e) for e in at.exception]

    sim = at.session_state["sys"]
    assert sim.revealed_identity is not None
    assert not sim.evidence["anonymity"].linkable


def test_revocation_path_renders():
    at = _run()
    [b for b in at.button if b.label == "Initialize"][0].click().run()
    [b for b in at.button if b.label == "Start Authentication"][0].click().run()
    [b for b in at.button if b.label == "Distribute Group Key"][0].click().run()

    [b for b in at.button if b.label == "Revoke"][0].click().run()
    [b for b in at.button if b.label == "Update Group Key"][0].click().run()
    assert not at.exception, [str(e) for e in at.exception]

    sim = at.session_state["sys"]
    current = sim.tuav.group_key
    holders = [u for u in sim.uavs if u.group_key == current]
    assert len(sim.revoked) >= 1
    assert all(u.status != "Revoked" for u in holders)


def test_reset_path_renders():
    at = _run()
    [b for b in at.button if b.label == "Initialize"][0].click().run()
    [b for b in at.button if b.label == "Reset"][0].click().run()
    assert not at.exception, [str(e) for e in at.exception]
    assert at.session_state["sys"].initialized is False
