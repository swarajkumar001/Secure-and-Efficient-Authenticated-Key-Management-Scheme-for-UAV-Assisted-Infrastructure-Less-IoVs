"""
The simulator's single source of truth.

One SystemState object, one append-only event log, and one rule that Streamlit
makes it easy to break: RENDERING NEVER MUTATES. Streamlit re-runs the whole
script on every interaction, so a render function that changes state produces
behaviour that is almost impossible to debug.

All mutation happens in the `act_*` functions below, and every one of them logs
what it did.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Any

from . import config
from .crypto.interface import Backend, OpCount, get_backend
from .protocol import authentication, initialization, key_management, signing
from .protocol.entities import RequestPacket, Status, TA, TUAV, UAV, Vehicle
from .protocol.link import TALink
from .simulation import attacks, datalink


# ---------------------------------------------------------------------------
@dataclass
class Event:
    """One line of the event log."""
    when: float
    phase: str          # the paper's step label, e.g. "GA1"
    actor: str
    detail: str
    level: str = "info"   # info | good | warn | bad
    cost_ms: float | None = None

    @property
    def clock(self) -> str:
        return time.strftime("%H:%M:%S", time.localtime(self.when))

    def row(self) -> dict:
        return {
            "Time": self.clock,
            "Step": self.phase,
            "Actor": self.actor,
            "Event": self.detail,
            "ms": f"{self.cost_ms:.2f}" if self.cost_ms is not None else "",
        }


@dataclass
class Measurement:
    """One timed protocol run, for the performance tab."""
    n: int
    backend: str
    phase: str
    actor: str          # drone | tuav | ta | link
    ms: float


# ---------------------------------------------------------------------------
@dataclass
class SystemState:
    backend_name: str = config.DEFAULTS["backend"]
    backend: Backend | None = None

    ta: TA | None = None
    tuav: TUAV | None = None
    uavs: list[UAV] = field(default_factory=list)
    vehicles: list[Vehicle] = field(default_factory=list)

    link: TALink | None = None
    session: int = config.DEFAULTS["session"]
    epoch: int = 0
    next_uav_index: int = 1

    packets: list[RequestPacket] = field(default_factory=list)
    sigma_seeds: dict[int, int] = field(default_factory=dict)
    last_auth: authentication.AuthResult | None = None
    last_key: key_management.KeyDistributionResult | None = None

    events: list[Event] = field(default_factory=list)
    measurements: list[Measurement] = field(default_factory=list)

    # --- Stage 2: adversaries and evidence ---
    replay_window_s: float = config.DEFAULTS["replay_window_s"]
    captured_packet: Any = None
    evidence: dict = field(default_factory=dict)
    last_exchange: Any = None
    revealed_identity: Any = None

    initialized: bool = False
    rng: Any = field(default_factory=lambda: random.Random())

    # -------------------------------------------------------------- log ----
    def log(self, phase: str, actor: str, detail: str,
            level: str = "info", cost_ms: float | None = None) -> None:
        self.events.append(Event(time.time(), phase, actor, detail, level, cost_ms))

    def measure(self, n: int, phase: str, actor: str, ms: float) -> None:
        self.measurements.append(
            Measurement(n=n, backend=self.backend_name, phase=phase, actor=actor, ms=ms)
        )

    # ------------------------------------------------------------ views ----
    @property
    def authenticated(self) -> list[UAV]:
        return [u for u in self.uavs if u.status in (Status.AUTHENTICATED, Status.KEYED)]

    @property
    def keyed(self) -> list[UAV]:
        return [u for u in self.uavs if u.status == Status.KEYED]

    @property
    def revoked(self) -> list[UAV]:
        return [u for u in self.uavs if u.status == Status.REVOKED]

    @property
    def active(self) -> list[UAV]:
        return [u for u in self.uavs if u.status != Status.REVOKED]

    def status_banner(self) -> list[dict]:
        """Status cards for the header.

        Each carries a `tone` so the UI can colour-code state rather than
        printing eight identical grey boxes: 'bad' is red, 'good' green,
        'warn' amber, 'info' neutral.
        """
        link_tone, link_val = "info", "-"
        if self.link is not None:
            if self.link.availability <= 0:
                link_tone, link_val = "bad", "DOWN"
            elif self.link.availability < 1.0:
                link_tone = "warn"
                link_val = f"{self.link.availability:.0%} · {self.link.rtt_ms:.0f} ms"
            else:
                link_tone = "good"
                link_val = f"{self.link.availability:.0%} · {self.link.rtt_ms:.0f} ms"

        keyed = bool(self.tuav and self.tuav.group_key)
        n_auth = len(self.authenticated)

        return [
            {"label": "RSU", "value": "DESTROYED", "tone": "bad",
             "note": "the premise"},
            {"label": "TUAV", "value": "ONLINE" if (self.tuav and self.tuav.online)
                               else "OFFLINE",
             "tone": "good" if (self.tuav and self.tuav.online) else "bad",
             "note": "flying base station"},
            {"label": "TA link", "value": link_val, "tone": link_tone,
             "note": "on the critical path"},
            {"label": "UAVs", "value": str(len(self.uavs)), "tone": "info",
             "note": "registered"},
            {"label": "Authenticated", "value": str(n_auth),
             "tone": "good" if n_auth else "info",
             "note": f"of {len(self.uavs)}" if self.uavs else ""},
            {"label": "Revoked", "value": str(len(self.revoked)),
             "tone": "warn" if self.revoked else "info",
             "note": "stale keys"},
            {"label": "Group key",
             "value": f"EPOCH {self.tuav.key_epoch}" if keyed else "none",
             "tone": "good" if keyed else "info",
             "note": f"{len(self.keyed)} holders" if keyed else "not distributed"},
            {"label": "Backend",
             "value": self.backend.FIDELITY if self.backend else "-",
             "tone": "good" if (self.backend
                                and self.backend.FIDELITY == "FAITHFUL") else "warn",
             "note": self.backend.NAME if self.backend else ""},
        ]

    def uav_table(self) -> list[dict]:
        """The ONLY projection the UI may render. Secrets never appear here."""
        return [u.public_row() for u in self.uavs]


# ---------------------------------------------------------------------------
# Actions.  Every one mutates state and logs.
# ---------------------------------------------------------------------------
def act_initialize(st: SystemState, *, backend_name: str,
                   rtt_ms: float, availability: float) -> SystemState:
    """Steps IS1, IS3, IS4, IS5."""
    st.backend_name = backend_name
    st.backend = get_backend(backend_name)
    st.ta, st.tuav = initialization.initialize_system(st.backend)
    st.link = TALink(rtt_ms=rtt_ms, availability=availability, rng=st.rng)

    st.uavs.clear()
    st.vehicles.clear()
    st.packets.clear()
    st.sigma_seeds.clear()
    st.next_uav_index = 1
    st.epoch = 0
    st.last_auth = None
    st.last_key = None
    st.initialized = True

    st.log("IS1/IS3", "TA",
           f"System initialized. Backend: {st.backend.NAME} [{st.backend.FIDELITY}], "
           f"group order {st.backend.order.bit_length()} bits.", "good")

    t0 = time.perf_counter()
    initialization.refresh_tuav_session(st.tuav, st.backend)
    ms = (time.perf_counter() - t0) * 1000
    st.log("IS4/IS5", "TUAV",
           f"Session refreshed and broadcast: ID_tu = TEMP_{st.tuav.temp_id_hex()}, "
           f"plus R_tu and Q_tu.", "info", ms)
    st.log("-", "RSU", "Roadside infrastructure assumed dysfunctional - "
                       "the TUAV is its substitute.", "warn")
    return st


def act_register(st: SystemState, n: int) -> SystemState:
    """Step IS2 - offline registration. Works even with the TA link down."""
    if not st.initialized:
        return st
    t0 = time.perf_counter()
    new = initialization.register_uavs(
        st.ta, n, st.backend, start_index=st.next_uav_index
    )
    ms = (time.perf_counter() - t0) * 1000
    st.uavs.extend(new)
    st.next_uav_index += n
    st.log("IS2", "TA",
           f"Registered {n} UAV(s) offline. Secrets <id_i, s_i> issued and stored; "
           f"they never travel over the air again.", "good", ms)
    return st


def act_attach_vehicles(st: SystemState, n: int) -> SystemState:
    if not st.uavs:
        return st
    st.vehicles = initialization.create_vehicles(n, [u.index for u in st.active])
    st.log("-", "IoV", f"{n} vehicles attached to the aerial layer. "
                       f"Vehicle authentication is out of scope, as in the paper.", "info")
    return st


def act_new_session(st: SystemState) -> SystemState:
    """A fresh session: new pseudonyms everywhere. Demonstrates unlinkability."""
    st.session += 1
    t0 = time.perf_counter()
    initialization.refresh_tuav_session(st.tuav, st.backend)
    ms = (time.perf_counter() - t0) * 1000
    st.log("IS4", "TUAV",
           f"Session {st.session}: new r_tu drawn, ID_tu is now "
           f"TEMP_{st.tuav.temp_id_hex()}.", "info", ms)
    return st


def act_authenticate(st: SystemState, *, poison_fraction: float = 0.0,
                     identify_culprits: bool = False) -> SystemState:
    """Steps US1-US3 then GA1-GA4."""
    if not st.initialized or not st.active:
        return st

    members = st.active
    n = len(members)

    # --- choose which requests carry a forged credential -----------------
    poison: set[int] = set()
    if poison_fraction > 0:
        k = max(1, int(round(n * poison_fraction)))
        poison = set(st.rng.sample([u.index for u in members], min(k, n)))

    # --- Steps US1-US3 ---------------------------------------------------
    ts2 = time.time()
    packets, drone_ops = signing.sign_batch(
        members, st.tuav, st.backend, ts2=ts2, poison_indices=poison, rng=st.rng
    )
    st.packets = packets
    st.log("US1-US3", f"{n} UAVs",
           f"Signed and transmitted {n} requests. "
           + (f"{len(poison)} carry a forged credential." if poison else "All honest."),
           "warn" if poison else "info", drone_ops.wall_ms)
    st.measure(n, "US (signing)", "drone", drone_ops.wall_ms)

    # --- Steps GA1-GA4 ---------------------------------------------------
    res = authentication.group_authenticate(
        packets, members, st.ta, st.tuav, st.backend,
        link=st.link, drone_ops=drone_ops, identify_culprits=identify_culprits,
        replay_window_s=st.replay_window_s,
    )
    st.last_auth = res

    if res.stale:
        st.log("GA1", "TUAV",
               f"{len(res.stale)} request(s) rejected on timestamp before the "
               f"offload (outside the {st.replay_window_s:g} s window).", "warn")

    if res.link is not None:
        st.log("GA1", "TUAV",
               f"Offloaded {n} request(s) to the TA. {res.link.note}. "
               f"{res.link.bytes_up} B up / {res.link.bytes_down} B down.",
               "good" if res.link.delivered else "bad", res.link.latency_ms)
        st.measure(n, "GA link", "link", res.link.latency_ms)

    if not res.link or not res.link.delivered:
        st.log("GA3", "TUAV", res.reason, "bad")
        return st

    st.log("GA2", "TA",
           f"Computed {res.ta_ops.pairing} pairing(s) and returned "
           f"<sigma_i, psi_i, mu_i, delta_i> for {n} UAV(s).",
           "info", res.ta_ops.wall_ms)
    st.measure(n, "GA (TA side)", "ta", res.ta_ops.wall_ms)

    st.log("GA3/GA4", "TUAV", res.reason, "good" if res.ok else "bad",
           res.tuav_ops.wall_ms)
    st.measure(n, "GA (TUAV side)", "tuav", res.tuav_ops.wall_ms)

    if res.ok:
        st.sigma_seeds = {r.uav_index: r.sigma_seed for r in res.ta_responses}
    return st


def act_distribute_key(st: SystemState) -> SystemState:
    """Steps GD1-GD6."""
    if not st.last_auth or not st.last_auth.ok:
        st.log("GD1", "TUAV",
               "Refused: no successful group authentication to key.", "warn")
        return st

    st.epoch += 1
    res = key_management.distribute_group_key(
        st.uavs, st.tuav, st.backend,
        sigma_seeds=st.sigma_seeds, epoch=st.epoch, rng=st.rng
    )
    st.last_key = res
    st.log("GD1-GD4", "TUAV",
           f"Lambda(x) built over {len(res.members)} member(s); "
           f"{len(res.broadcast.coefficients) if res.broadcast else 0} coefficients "
           f"({res.broadcast.size_bytes if res.broadcast else 0} B) broadcast once.",
           "good", res.tuav_ops.wall_ms)
    st.log("GD5/GD6", f"{len(res.members)} UAVs",
           f"S_i verified (mutual authentication) and key recovered by "
           f"{len(res.recovered)}/{len(res.members)}.",
           "good" if res.ok else "bad", res.uav_ops.wall_ms)
    st.measure(len(res.members), "GD (key distribution)", "tuav", res.tuav_ops.wall_ms)
    return st


def act_add_uav(st: SystemState, count: int = 1) -> SystemState:
    """Step DU1 - new participation."""
    if not st.initialized:
        return st
    act_register(st, count)
    st.log("DU1", "TUAV",
           f"{count} new UAV(s) registered and awaiting authentication. "
           f"Run authentication, then update the key.", "info")
    return st


def act_remove_uav(st: SystemState, indices: list[int]) -> SystemState:
    """Step DU1 - revocation. Marks members for removal at the next rekey."""
    for u in st.uavs:
        if u.index in indices:
            u.status = Status.REVOKED
    st.log("DU1", "TUAV",
           f"Marked {len(indices)} UAV(s) for revocation: "
           f"{', '.join('UAV'+str(i) for i in indices)}.", "warn")
    return st


def act_update_key(st: SystemState) -> SystemState:
    """Step DU2 - rebuild Lambda over the survivors."""
    keyed = [u for u in st.uavs if u.crt_modulus is not None]
    if not keyed:
        st.log("DU2", "TUAV", "Refused: no keyed members yet.", "warn")
        return st

    st.epoch += 1
    active = [u.index for u in keyed if u.status != Status.REVOKED]
    old_key = st.tuav.group_key

    res = key_management.update_group_key(
        st.uavs, st.tuav, st.backend, active_indices=active,
        epoch=st.epoch, rng=st.rng
    )
    st.last_key = res
    st.log("DU1/DU2", "TUAV", res.reason, "good" if res.ok else "bad",
           res.tuav_ops.wall_ms)
    if old_key is not None and st.tuav.group_key is not None:
        st.log("DU2", "TUAV",
               f"Key rotated: epoch {st.epoch - 1} -> {st.epoch}. "
               f"Revoked members still hold the old value, which no longer opens anything.",
               "good")
    st.measure(len(active), "DU (key update)", "tuav", res.tuav_ops.wall_ms)
    return st


def act_reset(st: SystemState) -> SystemState:
    keep_backend = st.backend_name
    new = SystemState(backend_name=keep_backend)
    new.log("-", "system", "Simulator reset.", "info")
    return new


# ---------------------------------------------------------------------------
# Stage 2 - adversaries, data exchange, anonymity
# ---------------------------------------------------------------------------
def act_capture_packet(st: SystemState) -> SystemState:
    """An eavesdropper records one authentication request off the air."""
    stolen = attacks.capture_packet(st.packets)
    st.captured_packet = stolen
    if stolen is None:
        st.log("-", "attacker", "Nothing on the air to capture. "
                                "Run authentication first.", "warn")
    else:
        st.log("-", "attacker",
               f"Captured the request from UAV{stolen.uav_index} "
               f"(ts2 = {stolen.ts2:.3f}). Every field in it was public.", "warn")
    return st


def act_replay(st: SystemState, *, delay_s: float,
               bypass_timestamp: bool = False) -> SystemState:
    res = attacks.replay_attack(st.captured_packet, st,
                                delay_s=delay_s,
                                bypass_timestamp=bypass_timestamp)
    st.evidence["replay"] = res
    st.log("GA1/GA3", "attacker",
           f"Replay attack: {res.verdict} at {res.stage}.",
           "good" if res.blocked else "bad")
    return st


def act_impersonate(st: SystemState) -> SystemState:
    res = attacks.impersonation_attack(st, rng=st.rng)
    st.evidence["impersonation"] = res
    st.log("GA2/GA3", "attacker",
           f"Impersonation attack: {res.verdict} at {res.stage}.",
           "good" if res.blocked else "bad")
    return st


def act_revoked_access(st: SystemState) -> SystemState:
    res = attacks.revoked_access_attack(st)
    st.evidence["revoked_access"] = res
    st.log("DU2", "attacker",
           f"Revoked-key data access: {res.verdict}.",
           "good" if res.blocked else "bad")
    return st


def act_batch_poison_report(st: SystemState) -> SystemState:
    """Report on the poisoning that the last authentication already ran."""
    last = st.last_auth
    n_forged = 0
    if last is not None:
        n_forged = sum(1 for u in st.uavs if u.is_forged)
    res = attacks.batch_poison_attack(st, n_forged=max(1, n_forged))
    st.evidence["batch_poison"] = res
    st.log("GA3/GA4", "attacker",
           f"Batch poisoning: {res.verdict}. {res.stage}.",
           "good" if res.blocked else "bad")
    return st


def act_exchange(st: SystemState, message: str) -> SystemState:
    """Encrypt a message under the current group key and let everyone try."""
    res = datalink.broadcast_to_group(st, message)
    st.last_exchange = res
    if res is None:
        st.log("-", "IoV", "No group key established yet.", "warn")
    else:
        st.log("-", "IoV",
               f"Message encrypted under the group key (epoch "
               f"{res.envelope.epoch}). {res.summary}", "good")
    return st


def act_anonymity_view(st: SystemState) -> SystemState:
    view = attacks.eavesdropper_view(st)
    st.evidence["anonymity"] = view
    return st


def act_reveal_identity(st: SystemState, uav_name: str) -> SystemState:
    """Theorem 4 - conditional privacy. Only the TA can do this.

    This is the escape hatch that separates 'anonymous' from 'untraceable'.
    """
    target = next((u for u in st.uavs if u.name == uav_name), None)
    if target is None or st.ta is None:
        return st
    resolved = st.ta.resolve(target.index)
    if resolved is None:
        st.log("-", "TA", f"{uav_name} is not in the registry.", "warn")
        return st
    id_perm, _secret = resolved
    st.revealed_identity = {
        "UAV": target.name,
        "Temporary ID": f"TEMP_{target.temp_id_hex()}",
        "True identity fingerprint": target.fingerprint,
        "Resolved by": "TA only, on request",
    }
    st.evidence["identity_resolved"] = True
    st.log("-", "TA",
           f"Identity retrieval performed for {uav_name} "
           f"(Theorem 4, conditional privacy). No other entity can do this.",
           "warn")
    return st
