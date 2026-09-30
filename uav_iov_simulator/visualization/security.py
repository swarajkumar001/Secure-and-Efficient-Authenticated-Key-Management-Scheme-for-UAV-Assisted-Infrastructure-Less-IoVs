"""
The security-property dashboard.

The paper's Table II ticks eleven properties (F1-F11).  This module reports what
the SIMULATOR can actually show for each one, and - just as importantly - what
it cannot.

Three evidence levels:

  DEMONSTRATED   an attack was run and the protocol behaved as claimed
  STRUCTURAL     the property follows from how the code is built, and a test
                 asserts it, but no adversary was run
  NOT SHOWN      a proof, or something outside this simulator's scope

Nothing here says "proved".  The paper's Theorems 1-5 are mathematical
arguments; watching an implementation behave correctly is weaker evidence and is
labelled as such.
"""

from __future__ import annotations

from dataclasses import dataclass

DEMONSTRATED = "DEMONSTRATED"
STRUCTURAL = "STRUCTURAL"
NOT_SHOWN = "NOT SHOWN"

LEVEL_HELP = {
    DEMONSTRATED: "An adversary was run against the implementation and failed.",
    STRUCTURAL: "Follows from the construction; asserted by a unit test.",
    NOT_SHOWN: "A mathematical proof, or outside this simulator's scope.",
}


@dataclass
class PropertyRow:
    tag: str
    name: str
    level: str
    evidence: str
    where: str


def evaluate(sim_state) -> list[PropertyRow]:
    """Build the dashboard from what has actually happened in this session."""
    ev = sim_state.evidence
    rows: list[PropertyRow] = []

    # ---- F1 unforgeability -------------------------------------------
    imp = ev.get("impersonation")
    rows.append(PropertyRow(
        "F1", "Unforgeability",
        DEMONSTRATED if (imp and imp.blocked) else STRUCTURAL,
        ("A forged credential built on a guessed secret was rejected at Step GA3."
         if (imp and imp.blocked) else
         "Run the impersonation attack to demonstrate this."),
        "Attacks tab",
    ))

    # ---- F2 conditional privacy --------------------------------------
    resolved = ev.get("identity_resolved")
    rows.append(PropertyRow(
        "F2", "Conditional privacy",
        DEMONSTRATED if resolved else STRUCTURAL,
        ("The TA reversed a pseudonym to its true identity on request; nobody "
         "else in the system can." if resolved else
         "Use 'Reveal identity (TA only)' on the Anonymity tab."),
        "Anonymity tab",
    ))

    # ---- F3 session / group key establishment -------------------------
    keyed = len(sim_state.keyed)
    rows.append(PropertyRow(
        "F3", "Session / group key establishment",
        DEMONSTRATED if keyed else STRUCTURAL,
        (f"{keyed} member(s) recovered the same key from one broadcast."
         if keyed else "Distribute the group key to demonstrate this."),
        "Group key tab",
    ))

    # ---- F4 key escrow resilience -------------------------------------
    rows.append(PropertyRow(
        "F4", "Key escrow resilience",
        STRUCTURAL,
        "The credential needs both s_i (TA-issued) and r_i (UAV-drawn). The TA "
        "never sees r_i, so it cannot produce a valid Gamma_i alone.",
        "protocol/signing.py",
    ))

    # ---- F5 scalability ------------------------------------------------
    n = len(sim_state.uavs)
    rows.append(PropertyRow(
        "F5", "Scalability",
        DEMONSTRATED if n >= 8 else STRUCTURAL,
        (f"{n} UAVs authenticated by a single aggregate equation."
         if n >= 8 else "Increase the UAV count to demonstrate this."),
        "Protocol run tab",
    ))

    # ---- F6 dynamic identity updating ---------------------------------
    sessions = max((len(u.history) for u in sim_state.uavs), default=0)
    rows.append(PropertyRow(
        "F6", "Dynamic identity updating",
        DEMONSTRATED if sessions >= 2 else STRUCTURAL,
        (f"A UAV used {sessions} distinct temporary identities across sessions."
         if sessions >= 2 else "Run 'New Session' twice to demonstrate this."),
        "Anonymity tab",
    ))

    # ---- F7 forward secrecy --------------------------------------------
    rows.append(PropertyRow(
        "F7", "Forward secrecy",
        NOT_SHOWN,
        "The paper claims this in Table II but does not analyse it in Section V. "
        "We do not demonstrate it either, and we do not claim it.",
        "-",
    ))

    # ---- F8 batch validation -------------------------------------------
    last = sim_state.last_auth
    rows.append(PropertyRow(
        "F8", "Batch validation",
        DEMONSTRATED if (last and last.ok) else STRUCTURAL,
        (f"{len(last.verified)} members verified by ONE equation; the TUAV "
         f"performed {last.tuav_ops.pairing} pairings."
         if (last and last.ok) else "Run authentication to demonstrate this."),
        "Protocol run tab",
    ))

    # ---- F9 unlinkability ----------------------------------------------
    anon = ev.get("anonymity")
    rows.append(PropertyRow(
        "F9", "Unlinkability",
        DEMONSTRATED if (anon and not anon.linkable) else STRUCTURAL,
        (f"{len(anon.observed)} observed pseudonyms, all distinct - an "
         f"eavesdropper cannot group them by sender."
         if (anon and not anon.linkable) else
         "Open the Anonymity tab after running several sessions."),
        "Anonymity tab",
    ))

    # ---- F10 non-repudiation -------------------------------------------
    rows.append(PropertyRow(
        "F10", "Non-repudiation",
        NOT_SHOWN,
        "Requires the TA's identity-tracing capability plus an audit record. We "
        "show the tracing half (F2) but keep no signed audit log, so we do not "
        "claim the property.",
        "-",
    ))

    # ---- F11 replay resistance -----------------------------------------
    rep = ev.get("replay")
    rows.append(PropertyRow(
        "F11", "Replay resistance",
        DEMONSTRATED if (rep and rep.blocked) else STRUCTURAL,
        (f"A captured request replayed later was blocked at: {rep.stage}."
         if (rep and rep.blocked) else
         "Capture a packet and replay it on the Attacks tab."),
        "Attacks tab",
    ))

    return rows


def summary(rows: list[PropertyRow]) -> dict:
    counts = {DEMONSTRATED: 0, STRUCTURAL: 0, NOT_SHOWN: 0}
    for r in rows:
        counts[r.level] = counts.get(r.level, 0) + 1
    return counts


HONESTY_NOTE = (
    "This dashboard reports simulator behaviour. It does not prove the paper's "
    "Theorems 1-5 - those are mathematical arguments, and an implementation "
    "behaving correctly is weaker evidence. Two of the eleven properties are "
    "marked NOT SHOWN rather than ticked."
)
