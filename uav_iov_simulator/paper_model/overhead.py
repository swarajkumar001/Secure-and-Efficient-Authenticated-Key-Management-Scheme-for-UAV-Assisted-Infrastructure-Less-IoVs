"""
Communication overhead - Table V of Section VI-B.

The paper's Table V, transcribed exactly:

    Scheme     [7]     [10]    [14]    [18]    Proposed
    SA         680     536     536     404     104
    GA         680n    536n    536n    404n    104n        (bytes)

with element sizes stated in the text: |G1| = 128 B, |G| = 40 B, hash = 20 B,
timestamp = 4 B.

------------------------------------------------------------------------------
AN OBSERVATION ABOUT THE PROPOSED SCHEME'S 104 BYTES
------------------------------------------------------------------------------
The request packet of Step US3 is <Request, ts2, ID_i, xi_i, upsilon_i, Gamma_i>.
Decomposing the paper's own figure:

        4  timestamp
   +   20  ID_i        (hash output)
   +   20  xi_i        (element of Z_q)
   +   20  upsilon_i   (element of Z_q)
   +   40  Gamma_i     <-- counted as an element of G, the 160-bit curve
   -----
      104  bytes

So Gamma_i is counted at 40 bytes, i.e. as living in the plain elliptic-curve
group G. But Step GA2 computes

        psi_i = e(Gamma_i + h1(s_i xi_i) P,  P)

and a bilinear pairing argument must live in G1, which the same section sizes at
128 bytes. Gamma_i cannot simultaneously be a 40-byte element of G and a valid
pairing argument in G1.

The same conflation appears in Table III, where the proposed scheme's signing
cost uses the plain-EC constants (T_SM_E, T_PA_E) rather than the pairing-group
ones (T_SM_P, T_PA_P).

We do not assert that the paper is wrong - the two groups are both defined in
Section VI-A and the intent may be a construction we cannot recover from the
text. What we do is report BOTH accountings and label them, because a reader
comparing our simulator's byte counts against Table V deserves to know why they
differ by 88 bytes per request.

This is the same class of issue as the sigma_i overloading in the CRT phase
(see crypto/crt.py): a symbol used in two groups at once.
"""

from __future__ import annotations

from dataclasses import dataclass

from .. import config

SOURCE_PAPER = "paper (Table V)"
SOURCE_MEASURED = "our accounting"

# Table V, exactly as printed. Bytes per authenticated UAV.
TABLE_V = {
    "Mei et al. [7]": 680,
    "Kumar et al. [10]": 536,
    "Ali et al. [14]": 536,
    "Xu et al. [18]": 404,
    "Proposed (paper)": 104,
}


@dataclass
class PacketBreakdown:
    """Field-by-field accounting of one Step US3 request."""
    fields: dict[str, int]
    label: str

    @property
    def total(self) -> int:
        return sum(self.fields.values())

    def rows(self) -> list[dict]:
        return ([{"Field": k, "Bytes": v} for k, v in self.fields.items()]
                + [{"Field": "TOTAL", "Bytes": self.total}])


def request_as_paper_counts_it() -> PacketBreakdown:
    """104 bytes - Gamma_i counted as an element of G (40 B)."""
    s = config.SIZES_BYTES
    return PacketBreakdown(
        label="as Table V counts it (Gamma_i in G)",
        fields={
            "ts2 (timestamp)": s["timestamp"],
            "ID_i (hash)": s["hash"],
            "xi_i (scalar)": s["scalar"],
            "upsilon_i (scalar)": s["scalar"],
            "Gamma_i (G element)": s["G_element"],
        },
    )


def request_as_pairing_requires() -> PacketBreakdown:
    """192 bytes - Gamma_i in G1 (128 B), which Step GA2 requires."""
    s = config.SIZES_BYTES
    return PacketBreakdown(
        label="if Gamma_i must be a pairing argument (G1)",
        fields={
            "ts2 (timestamp)": s["timestamp"],
            "ID_i (hash)": s["hash"],
            "xi_i (scalar)": s["scalar"],
            "upsilon_i (scalar)": s["scalar"],
            "Gamma_i (G1 element)": s["G1_element"],
        },
    )


def group_overhead(scheme: str, n: int) -> int:
    """Table V, GA row: the per-UAV figure times n."""
    return TABLE_V[scheme] * n


def comparison_table(n: int) -> list[dict]:
    rows = []
    for scheme, per in TABLE_V.items():
        rows.append({
            "Scheme": scheme,
            "Per UAV (B)": per,
            f"GA at n={n} (B)": per * n,
            f"GA at n={n} (KB)": round(per * n / 1024, 1),
            "Source": SOURCE_PAPER,
        })
    rows.append({
        "Scheme": "Proposed (our accounting)",
        "Per UAV (B)": request_as_pairing_requires().total,
        f"GA at n={n} (B)": request_as_pairing_requires().total * n,
        f"GA at n={n} (KB)": round(request_as_pairing_requires().total * n / 1024, 1),
        "Source": SOURCE_MEASURED,
    })
    return rows


# ---------------------------------------------------------------------------
# What the paper does not count at all
# ---------------------------------------------------------------------------
def uncounted_costs(n: int, crt_broadcast_bytes: int = 0) -> list[dict]:
    """Three costs absent from Table V.

    None of these is a criticism of the scheme's design - they are simply
    outside the boundary the paper drew around its accounting.
    """
    s = config.SIZES_BYTES
    ga1_up = n * (s["timestamp"] + s["identity"] + 2 * s["scalar"])
    ga2_down = n * (s["G1_element"] + 3 * 12 * 32)
    return [
        {
            "Cost": "Step GA1 uplink to the TA",
            "Bytes": ga1_up,
            "Note": "<ts2, ID_i, xi_i, upsilon_i> per UAV, across the satellite link",
        },
        {
            "Cost": "Step GA2 downlink from the TA",
            "Bytes": ga2_down,
            "Note": "<sigma_i, psi_i, mu_i, delta_i> per UAV; the three target-group "
                    "elements dominate",
        },
        {
            "Cost": "Step GD4 key broadcast",
            "Bytes": crt_broadcast_bytes,
            "Note": "coefficients of Lambda(x); grows with the product of all moduli, "
                    "so O(n^2) bits overall",
        },
    ]


WHY_OURS_DIFFERS = (
    "Our measured per-request figure is 192 B rather than Table V's 104 B, "
    "because we place Gamma_i in the pairing group G1 (128 B) - the only group "
    "in which Step GA2's pairing is computable. See the module docstring."
)
