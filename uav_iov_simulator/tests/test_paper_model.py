"""
Tests for the paper's analytical model and for the experiment runners.

The most important test in this file is the transcription check: our Table III
constants must reproduce the figures the paper states in prose. If they do not,
every performance chart in the simulator is drawn from bad numbers.
"""

from __future__ import annotations

import pytest

from uav_iov_simulator.paper_model import cost, overhead
from uav_iov_simulator.simulation import experiments


# ---------------------------------------------------------------------------
# Transcription
# ---------------------------------------------------------------------------
def test_table_iii_reproduces_the_papers_stated_figures():
    """Section VI-A states 1.8203 ms, 2.1578 ms, and 151.1934 ms at n = 120."""
    for label, (got, want, ok) in cost.headline_check().items():
        assert ok, f"{label}: our model gives {got:.4f}, paper states {want:.4f}"


def test_ga_cost_is_linear_in_n():
    for scheme in cost.all_schemes():
        a = cost.cost(scheme, "GA", 10)
        b = cost.cost(scheme, "GA", 20)
        c = cost.cost(scheme, "GA", 30)
        assert abs((b - a) - (c - b)) < 1e-9


def test_proposed_scheme_has_the_smallest_slope():
    """The paper's central efficiency claim."""
    slopes = {s: cost.cost(s, "GA", 101) - cost.cost(s, "GA", 100)
              for s in cost.all_schemes()}
    assert min(slopes, key=slopes.get) == "Proposed (paper)"


def test_unknown_scheme_raises_rather_than_guessing():
    with pytest.raises(KeyError):
        cost.cost("Nonexistent et al.", "GA", 10)


# ---------------------------------------------------------------------------
# Communication overhead
# ---------------------------------------------------------------------------
def test_table_v_proposed_figure_decomposes_to_104_bytes():
    """The paper's 104 B is only reachable by counting Gamma_i in G (40 B)."""
    b = overhead.request_as_paper_counts_it()
    assert b.total == overhead.TABLE_V["Proposed (paper)"] == 104


def test_pairing_group_accounting_is_larger_and_we_say_why():
    """Step GA2 feeds Gamma_i into a pairing, which needs G1 (128 B)."""
    paper = overhead.request_as_paper_counts_it().total
    ours = overhead.request_as_pairing_requires().total
    assert ours == 192
    assert ours - paper == 88
    assert "G1" in overhead.WHY_OURS_DIFFERS


def test_uncounted_costs_are_reported_separately():
    rows = overhead.uncounted_costs(n=10, crt_broadcast_bytes=512)
    labels = {r["Cost"] for r in rows}
    assert any("GA1" in s for s in labels)
    assert any("GA2" in s for s in labels)
    assert any("GD4" in s for s in labels)
    assert all(r["Bytes"] >= 0 for r in rows)


# ---------------------------------------------------------------------------
# Experiments
# ---------------------------------------------------------------------------
def test_e1_separates_tuav_from_ta():
    df = experiments.e1_scaling("abstract", n_values=(5, 10), rtt_ms=25.0)
    assert not df.empty
    phases = set(df["phase"])
    assert "GA (TUAV side)" in phases
    assert "GA (TA side)" in phases
    assert "GA (link)" in phases
    assert set(df["source"]) == {experiments.MEASURED}


def test_e1_link_component_matches_the_configured_rtt():
    df = experiments.e1_scaling("abstract", n_values=(8,), rtt_ms=120.0)
    link = df[df["phase"] == "GA (link)"]["ms"].iloc[0]
    assert link == pytest.approx(120.0)


def test_e7_success_rate_reaches_zero_at_zero_availability():
    df = experiments.e7_availability("abstract", n=6,
                                     availabilities=(1.0, 0.0), trials=6)
    full = df[df["availability"] == 1.0]["success rate"].iloc[0]
    none = df[df["availability"] == 0.0]["success rate"].iloc[0]
    assert full == 1.0
    assert none == 0.0, "with the link down the scheme must authenticate nobody"


def test_e8_published_scheme_collapses_at_low_poison_rates():
    """One forged credential in twenty denies the whole swarm."""
    df = experiments.e8_poisoning("abstract", n=20,
                                  fractions=(0.0, 0.05), trials=3)
    pub = df[df["mode"] == "published scheme"]
    clean = pub[pub["forged fraction"] == 0.0]["goodput"].iloc[0]
    poisoned = pub[pub["forged fraction"] == 0.05]["goodput"].iloc[0]
    assert clean == 1.0
    assert poisoned == 0.0


def test_e8_fallback_recovers_the_honest_members():
    df = experiments.e8_poisoning("abstract", n=20,
                                  fractions=(0.05,), trials=3)
    fb = df[df["mode"] == "with individual fallback"]["goodput"].iloc[0]
    assert fb > 0.9


def test_e3_revocation_excludes_the_revoked_and_keeps_survivors():
    df = experiments.e3_revocation("abstract", n=10, removals=(2,))
    row = df.iloc[0]
    assert row["survivors holding new key"] == row["survivors"]
    assert row["revoked holding new key"] == 0


def test_e5_pseudonyms_are_distinct_per_session():
    df = experiments.e5_pseudonyms("abstract", n=3, sessions=4)
    for uav, group in df.groupby("UAV"):
        ids = list(group["temporary ID"])
        assert len(ids) == len(set(ids)) == 4


def test_every_experiment_row_declares_its_source():
    """No chart may ever plot a number whose provenance is unknown."""
    for df in (experiments.e1_scaling("abstract", n_values=(5,)),
               experiments.e7_availability("abstract", n=4,
                                           availabilities=(1.0,), trials=2),
               experiments.e8_poisoning("abstract", n=6,
                                        fractions=(0.0,), trials=2),
               experiments.e5_pseudonyms("abstract", n=2, sessions=2)):
        assert "source" in df.columns
        assert df["source"].notna().all()
