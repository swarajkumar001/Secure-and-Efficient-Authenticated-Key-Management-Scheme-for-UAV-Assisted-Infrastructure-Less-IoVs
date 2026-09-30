"""
Presentation mode - a nine-step guided demo.

Strips the dashboard down to one idea per screen, with a large headline, the
single number that matters, and a line telling you what to say. Designed to be
driven with the arrow keys while you talk.

Each step declares what must already have happened (`requires`), so the UI can
tell you "run authentication first" instead of showing an empty panel in front
of an examiner.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Step:
    n: int
    eyebrow: str
    headline: str
    body: str
    say: str
    requires: str = ""          # human-readable precondition
    check: Callable | None = None
    metric: Callable | None = None
    tab_hint: str = ""


def _has_system(s):
    return s.initialized


def _has_uavs(s):
    return bool(s.uavs)


def _has_auth(s):
    return s.last_auth is not None and s.last_auth.ok


def _has_key(s):
    return s.tuav is not None and s.tuav.group_key is not None


def _has_revoked(s):
    return bool(s.revoked)


def _has_replay(s):
    return "replay" in s.evidence


STEPS: list[Step] = [
    Step(
        1, "The premise", "The roadside is gone",
        "Every published IoV security scheme routes trust through roadside "
        "units. A disaster destroys them first - and that is exactly when "
        "coordinated vehicular communication matters most.",
        "Open with the scenario, not the cryptography. Earthquake, rescue "
        "convoys, and no verifier left standing.",
        requires="", check=lambda s: True,
        metric=lambda s: ("RSU", "OFFLINE"),
        tab_hint="Network",
    ),
    Step(
        2, "The substitute", "A drone on a leash",
        "A tethered UAV draws power up a cable from a ground truck, so it "
        "hovers indefinitely. It becomes a flying, relocatable roadside unit.",
        "Emphasise WHY the tether matters: a battery drone dies in under an "
        "hour, which disqualifies it from being infrastructure at all.",
        requires="Initialize the system.", check=_has_system,
        metric=lambda s: ("TUAV", "ONLINE"),
        tab_hint="Network",
    ),
    Step(
        3, "Registration", "Secrets issued offline",
        "The authority gives each drone a permanent identity and a partial "
        "secret, before deployment. Neither ever travels over the air again.",
        "Point out that this is Step IS2, and that it works even with the "
        "satellite link down - registration is genuinely offline.",
        requires="Register UAVs.", check=_has_uavs,
        metric=lambda s: ("Registered", str(len(s.uavs))),
        tab_hint="Network",
    ),
    Step(
        4, "Privacy", "A new name every session",
        "Each drone transmits a temporary identity derived from its real one, "
        "a fresh random value and a timestamp. Two messages from the same "
        "drone cannot be linked.",
        "Show the same UAV across sessions on the Anonymity tab. Then note "
        "the escape hatch: the authority alone can reverse it.",
        requires="Run authentication at least once.",
        check=lambda s: any(u.history for u in s.uavs),
        metric=lambda s: ("Pseudonyms observed",
                          str(sum(len(u.history) for u in s.uavs))),
        tab_hint="Anonymity",
    ),
    Step(
        5, "Group authentication", "One equation, every drone",
        "All n credentials are multiplied together and checked once. If the "
        "equation balances, every requester is legitimate.",
        "The teacher analogy: check the total of 120 scores instead of adding "
        "them one by one.",
        requires="Run authentication.", check=_has_auth,
        metric=lambda s: ("Verified by one equation",
                          str(len(s.last_auth.verified)) if s.last_auth else "0"),
        tab_hint="Protocol run",
    ),
    Step(
        6, "The hidden cost", "The pairings did not disappear",
        "Every pairing happens on the authority, not the drone. The paper "
        "reports only the drone side - which is what makes its figure small.",
        "This is the number nobody has published. Say the ratio out loud.",
        requires="Run authentication.", check=_has_auth,
        metric=lambda s: (
            "TA did this much more work",
            f"{s.last_auth.ta_ops.wall_ms / max(s.last_auth.tuav_ops.wall_ms, 1e-9):,.0f}x"
            if s.last_auth and s.last_auth.tuav_ops.wall_ms else "-"),
        tab_hint="Performance",
    ),
    Step(
        7, "Group key", "One broadcast for everyone",
        "A single polynomial is broadcast. Every verified drone substitutes "
        "its own private value and recovers the same key.",
        "The crossword analogy. Then the elegant part: revoking a member "
        "sends nothing at all to the members who remain.",
        requires="Distribute the group key.", check=_has_key,
        metric=lambda s: ("Broadcast",
                          f"{s.last_key.broadcast.size_bytes} B"
                          if (s.last_key and s.last_key.broadcast) else "-"),
        tab_hint="Group key",
    ),
    Step(
        8, "Revocation", "The stale key opens nothing",
        "Rebuild the polynomial without the revoked member. Survivors keep "
        "the material they already hold; the revoked member keeps a key that "
        "no longer works.",
        "Show the AES-GCM failure on the Secure exchange tab. It is a real "
        "authentication-tag rejection, not a string comparison.",
        requires="Revoke a UAV and update the key.", check=_has_revoked,
        metric=lambda s: ("Revoked", str(len(s.revoked))),
        tab_hint="Secure exchange",
    ),
    Step(
        9, "Two open problems", "What the paper does not address",
        "Cut the authority link and authentication does not slow down - it "
        "stops. And one forged credential rejects the entire batch, with no "
        "way to identify who sent it.",
        "Close here. These two are the research contribution, and both fall "
        "out of implementing the paper honestly.",
        requires="", check=lambda s: True,
        metric=lambda s: ("Culprit identified on failure", "NO"),
        tab_hint="Attacks",
    ),
]


def step(i: int) -> Step:
    return STEPS[max(0, min(i, len(STEPS) - 1))]


def total() -> int:
    return len(STEPS)


def readiness(sim) -> list[dict]:
    """Which steps are demonstrable right now."""
    out = []
    for s in STEPS:
        ok = True
        if s.check is not None:
            try:
                ok = bool(s.check(sim))
            except Exception:
                ok = False
        out.append({"Step": s.n, "Topic": s.headline,
                    "Ready": "yes" if ok else "no",
                    "Needs": "" if ok else s.requires})
    return out
