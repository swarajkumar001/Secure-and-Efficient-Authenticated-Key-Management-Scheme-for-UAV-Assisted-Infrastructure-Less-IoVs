"""
Adversary simulations.

IMPORTANT FRAMING
-----------------
These demonstrate BEHAVIOUR, not proof.  The paper's Theorems 1-5 are
mathematical arguments; running an attack and watching it fail shows that the
implementation behaves as the theorem describes, which is a weaker and
different claim.  Every result object below carries that caveat in `caveat`,
and the UI prints it.

Four adversaries:

  ReplayAttack        capture a valid request, resend it later
  ImpersonationAttack forge a credential for an identity you do not own
  RevokedAccessAttack use a stale group key after revocation
  BatchPoisonAttack   inject one bad credential and stall the whole swarm
"""

from __future__ import annotations

import copy
import random
import time
from dataclasses import dataclass, field
from typing import Any

from ..protocol import authentication
from ..protocol.entities import RequestPacket, Status
from ..protocol.link import TALink


BEHAVIOUR_CAVEAT = (
    "Demonstrates protocol behaviour only. This is not a proof of the "
    "corresponding theorem in the paper."
)


@dataclass
class AttackResult:
    name: str
    blocked: bool
    stage: str = ""             # which step stopped it
    narrative: list[str] = field(default_factory=list)
    detail: dict = field(default_factory=dict)
    theorem: str = ""
    caveat: str = BEHAVIOUR_CAVEAT

    def add(self, line: str) -> None:
        self.narrative.append(line)

    @property
    def verdict(self) -> str:
        return "BLOCKED" if self.blocked else "SUCCEEDED"


# ---------------------------------------------------------------------------
# 1. Replay
# ---------------------------------------------------------------------------
def capture_packet(packets: list[RequestPacket]) -> RequestPacket | None:
    """The attacker records a valid request off the air.

    Everything in the packet is public - that is the point of the design. The
    attacker gets it all and still cannot do anything useful with it.
    """
    if not packets:
        return None
    stolen = copy.deepcopy(packets[0])
    stolen.captured_at = time.time()
    return stolen


def replay_attack(stolen: RequestPacket, sim_state, *,
                  delay_s: float,
                  bypass_timestamp: bool = False) -> AttackResult:
    """Resend a captured request `delay_s` seconds later.

    Two defences stand in the way, and the demo shows both:

      1. The timestamp window at Step GA1.
      2. If you switch that off, the credential still fails the aggregate
         equation, because R_tu and ID_tu were regenerated for the new session.
         That is the argument of Theorem 3, and it needs no check at all.
    """
    res = AttackResult(name="Replay attack", blocked=False,
                       theorem="Theorem 3 (replay attack resistance)")

    if stolen is None:
        res.blocked = True
        res.stage = "nothing captured"
        res.add("No packet was captured, so there is nothing to replay.")
        return res

    age = delay_s
    res.add(f"Captured request from UAV{stolen.uav_index} carrying timestamp "
            f"ts2 = {stolen.ts2:.3f}.")
    res.add(f"Attacker waits {age:.0f} s and retransmits the identical bytes.")

    window = sim_state.replay_window_s
    now = stolen.ts2 + age

    # ---- defence 1: the timestamp window ------------------------------
    if not bypass_timestamp:
        fresh, stale = authentication.check_freshness(
            [stolen], now=now, window_s=window)
        if stale:
            res.blocked = True
            res.stage = "GA1 - timestamp window"
            res.add(f"Step GA1 compares the timestamp against the {window:g} s "
                    f"acceptance window. Packet age is {age:.0f} s.")
            res.add("REJECTED before the request even reaches the TA.")
            res.detail = {
                "packet ts2": f"{stolen.ts2:.3f}",
                "replay at": f"{now:.3f}",
                "age": f"{age:.0f} s",
                "window": f"{window:g} s",
                "outcome": "REJECTED at Step GA1",
            }
            return res
        res.add(f"Packet age {age:.0f} s is inside the {window:g} s window, so the "
                f"timestamp filter lets it through.")
    else:
        res.add("Timestamp check DISABLED for this run, to expose the second "
                "defence underneath it.")

    # ---- defence 2: the cryptography ----------------------------------
    members = sim_state.active
    if not members:
        res.blocked = True
        res.stage = "no members"
        return res

    link = TALink(rtt_ms=0.0, availability=1.0)
    out = authentication.group_authenticate(
        [stolen], members, sim_state.ta, sim_state.tuav, sim_state.backend,
        link=link, skip_timestamp_check=True,
    )

    res.blocked = not out.ok
    if res.blocked:
        res.stage = "GA3 - aggregate equation"
        res.add("The replayed credential reaches Step GA3 and fails there anyway.")
        res.add("Reason: the TUAV regenerated r_tu for the new session, so R_tu "
                "and ID_tu differ from the values the credential was built "
                "against. The equation cannot balance.")
        res.add("This is the cryptographic half of Theorem 3 - it needs no "
                "timestamp check at all.")
    else:
        res.stage = "NOT BLOCKED"
        res.add("The replay was accepted. If you are seeing this inside the same "
                "session with the timestamp check off, that is expected: the "
                "packet genuinely is still valid for that session.")

    res.detail = {
        "packet ts2": f"{stolen.ts2:.3f}",
        "age": f"{age:.0f} s",
        "timestamp check": "bypassed" if bypass_timestamp else "passed",
        "aggregate check": "FAILED (replay rejected)" if res.blocked else "passed",
    }
    return res


# ---------------------------------------------------------------------------
# 2. Impersonation
# ---------------------------------------------------------------------------
def impersonation_attack(sim_state, *, rng: random.Random | None = None
                         ) -> AttackResult:
    """A fake UAV tries to authenticate without holding a registered secret.

    The attacker can observe everything on the air - ID_i, xi_i, upsilon_i,
    Gamma_i - and can construct a syntactically perfect request.  What it cannot
    do is produce a Gamma_i consistent with an s_i that the TA holds.
    """
    rng = rng or random.Random()
    res = AttackResult(name="Impersonation attack", blocked=False,
                       theorem="Theorem 1 (message unforgeability)")

    members = sim_state.active
    if not members or sim_state.tuav is None:
        res.blocked = True
        res.stage = "system not running"
        return res

    backend = sim_state.backend
    q = backend.order
    victim = members[0]

    res.add(f"Attacker targets {victim.name} and builds a request with the right "
            f"shape: a timestamp, a temporary identity, xi, upsilon and a Gamma.")
    res.add("Every field it needs was transmitted in the clear, so it has them all.")

    # A structurally valid packet built on a GUESSED secret.
    fake_s = rng.randrange(1, q)
    fake_xi = rng.randrange(1, q)
    fake_gamma = backend.g1_mul(rng.randrange(1, q))
    forged = RequestPacket(
        uav_index=victim.index,
        ts2=time.time(),
        id_temp=rng.randrange(1, q),
        xi=fake_xi,
        upsilon=rng.randrange(1, q),
        gamma=fake_gamma,
    )
    res.add("But Gamma must be built from s_i, which the TA issued offline and "
            "which never travelled over the air. The attacker guesses.")

    link = TALink(rtt_ms=0.0, availability=1.0)
    out = authentication.group_authenticate(
        [forged], members, sim_state.ta, sim_state.tuav, backend,
        link=link, skip_timestamp_check=True,
    )

    res.blocked = not out.ok
    res.stage = "GA2/GA3 - the TA resolves ID_i to the real s_i"
    res.add("At Step GA2 the TA looks up the real s_i for that identity and "
            "computes mu_i from it. The forged Gamma does not match.")
    res.add("Step GA3 fails. The impersonation is rejected." if res.blocked
            else "Unexpected: the forgery passed.")
    res.detail = {
        "forged fields": "ts2, ID_i, xi_i, upsilon_i, Gamma_i (all well-formed)",
        "secret used": "guessed at random",
        "outcome": "REJECTED at Step GA3" if res.blocked else "ACCEPTED",
    }
    return res


# ---------------------------------------------------------------------------
# 3. Revoked member tries to keep reading
# ---------------------------------------------------------------------------
def revoked_access_attack(sim_state) -> AttackResult:
    """A revoked UAV holds its old key and tries to open current traffic."""
    from . import datalink

    res = AttackResult(name="Revoked UAV data access", blocked=False,
                       theorem="Steps DU1-DU2 (dynamic key updating)")

    revoked = sim_state.revoked
    tuav = sim_state.tuav
    if not revoked or tuav is None or tuav.group_key is None:
        res.blocked = True
        res.stage = "nothing revoked yet"
        res.add("Revoke a UAV and update the group key first.")
        return res

    victim = revoked[0]
    message = b"ACCIDENT DETECTED - JUNCTION 14 - TWO VEHICLES"
    envelope = datalink.encrypt(tuav.group_key, message, epoch=tuav.key_epoch)

    res.add(f"{victim.name} was revoked at epoch {tuav.key_epoch}.")
    res.add("It still holds the key material it was issued - nothing was taken "
            "away from it, because the scheme never sends revoked members "
            "anything at all.")
    res.add(f"A message is encrypted under the CURRENT group key (epoch "
            f"{tuav.key_epoch}).")

    if victim.group_key is None:
        res.blocked = True
        res.stage = "no key held"
        res.add(f"{victim.name} never held a key. Nothing to try.")
        return res

    opened = datalink.try_decrypt(victim.group_key, envelope)
    res.blocked = opened is None
    res.stage = "AES-GCM authentication tag"
    if res.blocked:
        res.add("Decryption fails: the stale key produces a wrong authentication "
                "tag, so the ciphertext is rejected outright rather than "
                "decrypted into garbage.")
        res.add("ACCESS DENIED.")
    else:
        res.add("Unexpected: the revoked member opened the message.")

    res.detail = {
        "revoked member": victim.name,
        "key epoch held": victim.key_epoch,
        "current epoch": tuav.key_epoch,
        "ciphertext": envelope.ciphertext[:24].hex().upper() + "...",
        "outcome": "ACCESS DENIED" if res.blocked else "OPENED",
    }
    return res


# ---------------------------------------------------------------------------
# 4. Batch poisoning - the one the paper does not defend against
# ---------------------------------------------------------------------------
def batch_poison_attack(sim_state, *, n_forged: int = 1) -> AttackResult:
    """Inject a small number of forged credentials into an otherwise honest batch.

    Unlike the three above, this one SUCCEEDS.  That is the finding: Step GA4 of
    the paper has no else-branch, so a single malformed credential rejects the
    entire group and identifies nobody.
    """
    res = AttackResult(name="Batch poisoning", blocked=False,
                       theorem="(no corresponding theorem - this case is not "
                               "addressed in the paper)")

    last = sim_state.last_auth
    if last is None:
        res.add("Run an authentication with the adversary slider above zero.")
        return res

    n = last.n_requested
    res.add(f"{n_forged} forged credential(s) were injected into a batch of {n}.")

    if last.ok:
        res.blocked = True
        res.stage = "no forgery present"
        res.add("This batch was clean, so it passed.")
        return res

    res.blocked = False
    res.stage = "GA3 - aggregate rejects everyone"
    res.add(f"The aggregate equation failed, so all {len(last.rejected)} members "
            f"were rejected - including the {n - n_forged} honest ones.")

    if last.culprits_identified:
        res.add("Culprit identification was enabled, so the TUAV fell back to "
                f"{n} individual checks and located the bad member. That fallback "
                "is NOT part of the published scheme.")
        res.blocked = True
        res.stage = "identified, but only by leaving the paper's design"
    else:
        res.add("The scheme cannot say which member was responsible. Step GA4 "
                "reads only: 'If matches, the validity of the vehicles can be "
                "proved.' There is no else-branch anywhere in the paper.")
        res.add(f"Cost to the attacker: {n_forged} packet(s). "
                f"Cost to the swarm: total denial of authentication.")

    res.detail = {
        "batch size": n,
        "forged": n_forged,
        "honest members rejected": max(0, len(last.rejected) - n_forged),
        "culprit identified": "yes" if last.culprits_identified else "NO",
        "outcome": "DENIAL OF SERVICE" if not res.blocked else "contained",
    }
    return res


# ---------------------------------------------------------------------------
# Anonymity / unlinkability - an observation, not an attack
# ---------------------------------------------------------------------------
@dataclass
class AnonymityView:
    """What a passive eavesdropper sees across sessions."""
    observed: list[dict] = field(default_factory=list)
    linkable: bool = False
    ta_can_resolve: bool = True
    note: str = ""


def eavesdropper_view(sim_state) -> AnonymityView:
    """Collect every temporary identity a UAV has used, as an attacker would.

    The attacker sees a flat list of pseudonyms with no way to group them. The
    TA, holding the registry, can reverse any of them on request - which is the
    conditional privacy of Theorem 4.
    """
    view = AnonymityView()
    rows = []
    for u in sim_state.uavs:
        for session_ts, temp in u.history:
            rows.append({
                "Observed at": time.strftime("%H:%M:%S", time.localtime(session_ts)),
                "Temporary ID": f"TEMP_{temp:x}".upper()[:14],
                "Attacker can attribute to": "unknown",
                "_true_owner": u.name,
            })
    rows.sort(key=lambda r: r["Observed at"])
    view.observed = rows

    # Linkable only if the same pseudonym was ever reused.
    seen = [r["Temporary ID"] for r in rows]
    view.linkable = len(seen) != len(set(seen))
    view.note = (
        "Every identity is distinct, so the eavesdropper cannot group these rows "
        "by sender." if not view.linkable else
        "A pseudonym was reused - these sessions ARE linkable."
    )
    return view
