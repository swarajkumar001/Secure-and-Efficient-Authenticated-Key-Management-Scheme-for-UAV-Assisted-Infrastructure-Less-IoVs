"""
The TUAV-to-TA link.

THIS MODULE IS OUR ADDITION, NOT THE PAPER'S.
---------------------------------------------
Tan et al. describe the TA as reachable over a space/satellite channel
(Section III-D: "the space networks are adopted to provide enhanced
connectivity between TA and ECRV") but never model its latency, never model its
availability, and never include either in the cost accounting of Section VI.

Step GA1 forwards every authentication request across this link and Step GA3
cannot be evaluated until GA2 comes back.  So the link sits on the critical path
of every single verification.  Modelling it is the difference between the
paper's reported group-authentication cost and the time a UAV actually waits.

Setting availability to 0 reproduces the condition the paper's own scenario
describes - destroyed ground infrastructure, contested satellite capacity - and
shows what the scheme does then.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ..config import SIZES_BYTES


@dataclass
class LinkResult:
    """One traversal of the TUAV-TA link."""

    delivered: bool
    latency_ms: float
    bytes_up: int = 0
    bytes_down: int = 0
    note: str = ""

    @property
    def bytes_total(self) -> int:
        return self.bytes_up + self.bytes_down


class TALink:
    """A simple, honest model: fixed round-trip latency plus an availability
    probability.  No queueing, no jitter, no packet loss beyond the outage
    model - and we say so rather than implying more realism than we have.
    """

    def __init__(self, rtt_ms: float = 40.0, availability: float = 1.0,
                 rng: random.Random | None = None) -> None:
        self.rtt_ms = max(0.0, float(rtt_ms))
        self.availability = min(1.0, max(0.0, float(availability)))
        self.rng = rng or random.Random()
        self.traversals = 0
        self.failures = 0
        self.total_latency_ms = 0.0
        self.total_bytes = 0

    # ------------------------------------------------------------------
    def traverse(self, payload_count: int = 1) -> LinkResult:
        """Step GA1 uplink plus Step GA2 downlink, as one round trip."""
        self.traversals += 1

        # Uplink   : <ts2, ID_i, xi_i, upsilon_i> per UAV
        up = payload_count * (
            SIZES_BYTES["timestamp"] + SIZES_BYTES["identity"] + 2 * SIZES_BYTES["scalar"]
        )
        # Downlink : <sigma_i, psi_i, mu_i, delta_i> per UAV
        #            sigma_i is a G1 point; psi/mu/delta are target-group elements,
        #            which for an embedding degree of 12 are large. We count them
        #            generously rather than flatteringly.
        down = payload_count * (SIZES_BYTES["G1_element"] + 3 * 12 * 32)

        if self.availability < 1.0 and self.rng.random() > self.availability:
            self.failures += 1
            return LinkResult(
                delivered=False,
                latency_ms=self.rtt_ms,
                bytes_up=up,
                note=f"link outage (availability {self.availability:.0%})",
            )

        self.total_latency_ms += self.rtt_ms
        self.total_bytes += up + down
        return LinkResult(
            delivered=True,
            latency_ms=self.rtt_ms,
            bytes_up=up,
            bytes_down=down,
            note=f"round trip {self.rtt_ms:.0f} ms",
        )

    # ------------------------------------------------------------------
    def stats(self) -> dict:
        return {
            "traversals": self.traversals,
            "outages": self.failures,
            "success rate": (
                f"{(self.traversals - self.failures) / self.traversals:.0%}"
                if self.traversals else "-"
            ),
            "total link latency ms": round(self.total_latency_ms, 1),
            "total bytes over link": self.total_bytes,
        }

    def reset(self) -> None:
        self.traversals = 0
        self.failures = 0
        self.total_latency_ms = 0.0
        self.total_bytes = 0
