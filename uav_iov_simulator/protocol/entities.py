"""
The four entities of the paper's system model (Section III-D).

    TA    - trusted authority, cloud. Registers everyone, holds the mapping from
            temporary identity back to true identity, performs the pairings.
    TUAV  - tethered UAV. The flying substitute for the destroyed roadside unit.
    UAV   - ordinary battery drone. Signs, gets verified, receives the group key.
    Vehicle - ground user. Out of scope in the paper; drawn, not authenticated.

Secrets live on these objects and never reach a rendering function.  The UI is
handed `public_row()` projections instead.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..crypto.hash_utils import fingerprint


# --------------------------------------------------------------------------
# Status vocabulary shown in the UI
# --------------------------------------------------------------------------
class Status:
    UNREGISTERED = "Unregistered"
    REGISTERED = "Registered"
    PENDING = "Authentication pending"
    AUTHENTICATED = "Authenticated"
    FAILED = "Authentication failed"
    KEYED = "Group key held"
    REVOKED = "Revoked"
    FORGED = "Forged credential"


@dataclass
class UAV:
    """An ordinary UAV. Steps IS2, US1-US3."""

    index: int
    id_perm: bytes                  # id_i  - never rendered
    s: int                          # s_i   - TA-issued partial secret, never rendered
    status: str = Status.UNREGISTERED

    # --- refreshed every session (Step US1) ---
    r: Optional[int] = None         # r_i   - the UAV's own random contribution
    xi: Optional[int] = None        # xi_i  = h1(r_i)
    id_temp: Optional[int] = None   # ID_i  = h3(id_i, ts2, xi_i)
    upsilon: Optional[int] = None   # upsilon_i = h4(ID_i, ID_tu, ts2, xi_i)
    gamma: Any = None               # Gamma_i - the credential, a G1 point
    ts2: Optional[float] = None

    # --- key material (Steps GD1, GD6) ---
    crt_modulus: Optional[int] = None
    group_key: Optional[int] = None
    key_epoch: Optional[int] = None

    # --- bookkeeping ---
    is_forged: bool = False         # set by the batch-poisoning experiment
    history: list = field(default_factory=list)   # (session, id_temp) pairs

    @property
    def name(self) -> str:
        return f"UAV{self.index}"

    @property
    def fingerprint(self) -> str:
        """A stable label the UI may show. Not reversible to id_perm."""
        return fingerprint(self.id_perm)

    def temp_id_hex(self, length: int = 8) -> str:
        if self.id_temp is None:
            return "-"
        return f"{self.id_temp:x}".upper()[:length].rjust(length, "0")

    def public_row(self) -> dict:
        """The ONLY projection the UI is allowed to render."""
        return {
            "UAV": self.name,
            "Permanent ID": f"hidden ({self.fingerprint})",
            "Temporary ID": f"TEMP_{self.temp_id_hex()}" if self.id_temp else "-",
            "Status": self.status,
            "Key epoch": self.key_epoch if self.key_epoch is not None else "-",
        }


@dataclass
class TUAV:
    """The tethered UAV. Steps IS1, IS4-IS5, GA1, GA3-GA4, GD1-GD5, DU1-DU2."""

    id_perm: bytes                  # id_tu - never rendered
    s: int                          # s_tu  - never rendered

    r: Optional[int] = None         # r_tu, refreshed periodically (Step IS4)
    id_temp: Optional[int] = None   # ID_tu = h2(id_tu, r_tu)
    R: Optional[int] = None         # R_tu  = r_tu * h2(ts_tu, s_tu)   [scalar]
    Q: Any = None                   # Q_tu  = s_tu * h2(ID_tu, r_tu) * P  [point]
    H: Optional[int] = None         # h2(ID_tu, r_tu), reused in GA3
    ts_tu: Optional[float] = None

    group_key: Optional[int] = None
    key_epoch: int = 0
    online: bool = True

    @property
    def name(self) -> str:
        return "TUAV"

    def temp_id_hex(self, length: int = 8) -> str:
        if self.id_temp is None:
            return "-"
        return f"{self.id_temp:x}".upper()[:length].rjust(length, "0")

    def broadcast_set(self) -> dict:
        """Step IS5: <ts_tu, ID_tu, R_tu, Q_tu> broadcast to everyone in range."""
        return {
            "ts_tu": self.ts_tu,
            "ID_tu": self.id_temp,
            "R_tu": self.R,
            "Q_tu": self.Q,
        }


@dataclass
class TA:
    """The trusted authority. Steps IS1-IS3, GA2.

    Holds the registry that maps a temporary identity back to <id_i, s_i>. This
    is what gives conditional privacy: anonymous to everyone except here.
    """

    registry: dict[int, int] = field(default_factory=dict)   # index -> s_i
    identities: dict[int, bytes] = field(default_factory=dict)
    online: bool = True

    @property
    def name(self) -> str:
        return "TA"

    def resolve(self, uav_index: int) -> tuple[bytes, int] | None:
        """The identity-retrieval capability of Theorem 4 (conditional privacy).

        Only the TA can do this, and only on request.
        """
        if uav_index in self.registry:
            return self.identities[uav_index], self.registry[uav_index]
        return None


@dataclass
class Vehicle:
    """A ground vehicle.

    The paper explicitly scopes vehicle authentication OUT (Section IV opening:
    'our design focuses on the UAV networks with TUAV assistance and is
    compatible with existing vehicular authentication schemes'). We draw them
    and let them carry group-key traffic, and we claim nothing more.
    """

    index: int
    served_by: Optional[int] = None    # UAV index

    @property
    def name(self) -> str:
        return f"VEH{self.index}"


@dataclass
class RequestPacket:
    """Step US3: <Request, ts2, ID_i, xi_i, upsilon_i, Gamma_i>."""

    uav_index: int
    ts2: float
    id_temp: int
    xi: int
    upsilon: int
    gamma: Any
    captured_at: Optional[float] = None    # set when an attacker records it

    def fields(self) -> dict:
        return {
            "Request": "AUTH",
            "ts2": self.ts2,
            "ID_i": self.id_temp,
            "xi_i": self.xi,
            "upsilon_i": self.upsilon,
            "Gamma_i": self.gamma,
        }
