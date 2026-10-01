"""
System architecture figure, in the style of a research-paper diagram.

Six dashed containers hold the sub-networks of the paper's Figure 1. Every
entity is a geometric node - rectangle, rounded rectangle or oval - with a thin
border and a pale fill. There are no pictorial objects: the connections and the
information hierarchy are what the reader should see.

    +-- UAV NETWORKS -----+  +-- TETHERED UAV --+  +-- SATELLITE ----+
    |  UAV1..UAVn, U2U    |<>|  TUAV -- ECRV    |<>|  SAT relays     |
    +---------------------+  +------------------+  +-----------------+
              ^                                             |
    +-- VEHICULAR --------+  +-- RSU -----------+  +-- TA -----------+
    |  V1..Vn, V2V        |<>|  crossed out     |  |  does pairings  |
    +---------------------+  +------------------+  +-----------------+

The figure stays LIVE. Node borders and fills follow authentication status,
revoked members are struck through and lose their U2U edges, and the
satellite-to-authority edge turns red when the link is down.
"""

from __future__ import annotations

import plotly.graph_objects as go

from ..protocol.entities import Status
from . import nodes as N

# --------------------------------------------------------------- palette --
INK = N.TEXT
INK2 = N.TEXT_SOFT
INK3 = "#8A949F"
AMBER = "#A8580A"
TEAL = "#145D66"
RED = "#97302F"
GREEN = "#1C6B45"
GREY = "#9AA5B1"
PURPLE = "#6B5CA8"
LINK_GREEN = "#3F8E57"

#: border colour per status; fills are a pale wash of the same hue
STATUS_COLOUR = {
    Status.UNREGISTERED: GREY,
    Status.REGISTERED: "#5A6672",
    Status.PENDING: AMBER,
    Status.AUTHENTICATED: TEAL,
    Status.KEYED: GREEN,
    Status.FAILED: RED,
    Status.REVOKED: RED,
    Status.FORGED: RED,
}
STATUS_FILL = {
    Status.UNREGISTERED: "#FFFFFF",
    Status.REGISTERED: "#FFFFFF",
    Status.PENDING: "#FBF2E6",
    Status.AUTHENTICATED: "#E8F1F2",
    Status.KEYED: "#E7F2EC",
    Status.FAILED: "#FBECEA",
    Status.REVOKED: "#FBECEA",
    Status.FORGED: "#FBECEA",
}
STATUS_SHORT = {
    Status.UNREGISTERED: "not registered",
    Status.REGISTERED: "registered",
    Status.PENDING: "awaiting check",
    Status.AUTHENTICATED: "verified",
    Status.KEYED: "has group key",
    Status.FAILED: "rejected",
    Status.REVOKED: "revoked",
    Status.FORGED: "forged credential",
}

MAX_DRAWN_UAVS = 7
MAX_DRAWN_VEHICLES = 6

# ------------------------------------------------------------ geometry ----
Z_UAV = (0.20, 3.35, 5.55, 6.55)
Z_TUAV = (5.80, 3.35, 8.90, 6.55)
Z_SAT = (9.15, 3.35, 12.20, 6.55)
Z_VEH = (0.20, 0.20, 5.55, 3.10)
Z_RSU = (5.80, 0.20, 8.90, 3.10)
Z_TA = (9.15, 0.20, 12.20, 3.10)

UAV_W, UAV_H = 0.96, 0.46
VEH_W, VEH_H = 0.86, 0.40

UAV_SLOTS = [(1.15, 5.45), (2.85, 5.45), (4.45, 5.45),
             (1.15, 4.45), (2.85, 4.45), (4.45, 4.45),
             (2.85, 3.72)]
UAV_EDGES = [(0, 1), (1, 2), (3, 4), (4, 5), (0, 3), (1, 4), (2, 5), (4, 6)]

VEH_SLOTS = [(1.10, 2.20), (2.65, 2.20), (4.25, 2.20),
             (1.10, 1.25), (2.65, 1.25), (4.25, 1.25)]
VEH_EDGES = [(0, 1), (1, 2), (3, 4), (4, 5), (1, 4)]


def _centre(z):
    return (z[0] + z[2]) / 2, (z[1] + z[3]) / 2


def _empty() -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text="Nothing running yet.<br><b>Press Initialize in the sidebar.</b>",
        x=0.5, y=0.5, xref="paper", yref="paper",
        showarrow=False, font=dict(size=16, color=INK3), align="center")
    fig.update_layout(height=560, plot_bgcolor="rgba(0,0,0,0)",
                      paper_bgcolor="rgba(0,0,0,0)",
                      xaxis=dict(visible=False), yaxis=dict(visible=False))
    return fig


def render(state) -> go.Figure:
    """Build the architecture figure. READ ONLY - never mutates state."""
    if not state.initialized or state.tuav is None:
        return _empty()

    fig = go.Figure()
    shapes: list[dict] = []
    ann: list[dict] = []
    hx, hy, ht = [], [], []

    link_up = state.link is not None and state.link.availability > 0

    # ============================================================ zones ====
    N.zone(shapes, *Z_UAV)
    N.zone(shapes, *Z_TUAV, tone="amber")
    N.zone(shapes, *Z_SAT, tone="blue")
    N.zone(shapes, *Z_VEH)
    N.zone(shapes, *Z_RSU, tone="red")
    N.zone(shapes, *Z_TA, tone="blue")

    for z, title, col in ((Z_UAV, "UAV Networks", INK),
                          (Z_TUAV, "Tethered UAV", INK),
                          (Z_SAT, "Satellite Networks", INK),
                          (Z_VEH, "Vehicular Networks", INK),
                          (Z_RSU, "RSU", RED),
                          (Z_TA, "Trusted Authority", INK)):
        ann.append(N.label((z[0] + z[2]) / 2, z[3] - 0.20, title,
                           size=12.5, colour=col, bold=True))

    # ====================================================== UAV networks ===
    drawn = state.uavs[:MAX_DRAWN_UAVS]
    hidden = len(state.uavs) - len(drawn)
    pos = UAV_SLOTS[:len(drawn)]

    # U2U edges first, so the nodes sit on top of them
    for a, b in UAV_EDGES:
        if a >= len(drawn) or b >= len(drawn):
            continue
        ua, ub = drawn[a], drawn[b]
        dead = Status.REVOKED in (ua.status, ub.status)
        N.connector(shapes, pos[a][0], pos[a][1], pos[b][0], pos[b][1],
                    colour="#C6CDD4" if dead else LINK_GREEN,
                    width=1.0, dash="dot" if dead else None)
    if len(drawn) >= 2:
        ann.append(N.label((pos[0][0] + pos[1][0]) / 2,
                           pos[0][1] + 0.30, "U2U",
                           size=10.5, colour=LINK_GREEN, bold=True))

    for (px, py), u in zip(pos, drawn):
        col = STATUS_COLOUR.get(u.status, GREY)
        N.rounded(shapes, px, py, UAV_W, UAV_H,
                  fill=STATUS_FILL.get(u.status, "#FFFFFF"),
                  line=col, width=1.4,
                  dash="dot" if u.status == Status.REVOKED else None)
        if u.status == Status.REVOKED:
            N.cross_out(shapes, px, py, UAV_W * 0.74, UAV_H * 0.62, colour=RED)
        ann.append(N.label(px, py, f"UAV{u.index}", size=10.5,
                           colour=col, bold=True))
        hx.append(px)
        hy.append(py)
        ht.append(f"<b>{u.name}</b><br>{STATUS_SHORT.get(u.status, u.status)}"
                  f"<br>ID: TEMP_{u.temp_id_hex()}<br>key epoch: "
                  f"{u.key_epoch if u.key_epoch is not None else 'none'}")

    if hidden > 0:
        ann.append(N.label(Z_UAV[0] + 0.18, Z_UAV[1] + 0.20,
                           f"+{hidden} more not drawn", size=9.5,
                           colour=INK3, anchor="left"))

    # ======================================================= tethered UAV ==
    tux, tuy = _centre(Z_TUAV)
    tuav_col = AMBER if link_up else RED
    N.rounded(shapes, tux, tuy + 0.70, 2.30, 0.64,
              fill="#FBF2E6", line=tuav_col, width=1.6)
    ann.append(N.label(tux, tuy + 0.82, "TUAV", size=12, colour=tuav_col,
                       bold=True))
    ann.append(N.label(tux, tuy + 0.56, "flying base station",
                       size=9, colour=INK2))

    N.connector(shapes, tux, tuy + 0.38, tux, tuy - 0.43,
                colour=tuav_col, width=2.6, layer="above")
    ann.append(N.label(tux + 0.16, tuy, "tether", size=9.5, colour=tuav_col,
                       anchor="left"))

    N.rect(shapes, tux, tuy - 0.72, 2.00, 0.58, fill="#FFFFFF",
           line=N.LINE_SOFT, width=1.3)
    ann.append(N.label(tux, tuy - 0.62, "ECRV", size=11.5, colour=INK,
                       bold=True))
    ann.append(N.label(tux, tuy - 0.86, "power supply", size=9, colour=INK2))

    hx.append(tux)
    hy.append(tuy + 0.70)
    ht.append(f"<b>Tethered UAV</b><br>the flying roadside unit<br>"
              f"ID_tu = TEMP_{state.tuav.temp_id_hex()}<br>"
              f"computes ZERO pairings")

    # ========================================================= satellites ==
    sx, sy = _centre(Z_SAT)
    for i, dx in enumerate((-0.86, 0.0, 0.86)):
        N.rect(shapes, sx + dx, sy + 0.72, 0.74, 0.44,
               fill="#F0F6FC", line="#6F8CAB", width=1.2)
        ann.append(N.label(sx + dx, sy + 0.72, f"SAT{i+1}", size=9.5,
                           colour="#3E5C7E", bold=True))
    N.ellipse(shapes, sx, sy - 0.26, 2.50, 0.66, fill="#F0F6FC",
              line="#6F8CAB", width=1.2)
    ann.append(N.label(sx, sy - 0.26, "relay constellation", size=9.5,
                       colour="#3E5C7E"))
    for dx in (-0.86, 0.0, 0.86):
        N.connector(shapes, sx + dx, sy + 0.50, sx + dx * 0.45, sy + 0.07,
                    colour="#A9BFD6", width=1.0)

    # ================================================= trusted authority ===
    tax, tay = _centre(Z_TA)
    N.rect(shapes, tax, tay + 0.16, 2.40, 0.76, fill="#F0F6FC",
           line="#3E5C7E", width=1.5)
    ann.append(N.label(tax, tay + 0.30, "TA", size=13, colour=INK, bold=True))
    ann.append(N.label(tax, tay + 0.04, "does every pairing", size=9.5,
                       colour=INK2))
    N.rect(shapes, tax, tay - 0.70, 2.40, 0.46, fill="#FFFFFF",
           line=N.LINE_SOFT, width=1.1, dash="dot")
    ann.append(N.label(tax, tay - 0.70, "identity registry", size=9.5,
                       colour=INK2))
    N.connector(shapes, tax, tay - 0.22, tax, tay - 0.47,
                colour=N.LINE_SOFT, width=1.0)
    hx.append(tax)
    hy.append(tay + 0.16)
    ht.append("<b>Trusted Authority</b><br>performs EVERY pairing (Step GA2)"
              "<br>the paper does not report its cost")

    # ================================================================ RSU ==
    rx, ry = _centre(Z_RSU)
    ann.append(N.label(rx, ry + 0.62, "RSU / edge node", size=11.5,
                       colour=RED, bold=True))
    N.rect(shapes, rx, ry + 0.10, 2.20, 0.74, fill="#FFFFFF",
           line=RED, width=1.4, dash="dash")
    N.cross_out(shapes, rx, ry + 0.10, 2.20, 0.74, colour=RED, width=1.6)
    ann.append(N.label(rx, ry - 0.48, "DESTROYED", size=11.5, colour=RED,
                       bold=True))
    ann.append(N.label(rx, ry - 0.76, "the TUAV replaces it", size=9.5,
                       colour=RED))

    # ================================================ vehicular networks ===
    nveh = min(len(state.vehicles), MAX_DRAWN_VEHICLES)
    vpos = VEH_SLOTS[:nveh]
    for a, b in VEH_EDGES:
        if a >= nveh or b >= nveh:
            continue
        N.connector(shapes, vpos[a][0], vpos[a][1], vpos[b][0], vpos[b][1],
                    colour=PURPLE, width=1.0)
    for i, (px, py) in enumerate(vpos):
        N.rect(shapes, px, py, VEH_W, VEH_H, fill="#FFFFFF",
               line=N.LINE_SOFT, width=1.2)
        ann.append(N.label(px, py, f"V{i+1}", size=10, colour=INK2))
    if nveh >= 5:
        ann.append(N.label(vpos[1][0] + 0.26,
                           (vpos[1][1] + vpos[4][1]) / 2, "V2V",
                           size=10.5, colour=PURPLE, bold=True, anchor="left"))
    extra = len(state.vehicles) - nveh
    if extra > 0:
        ann.append(N.label(Z_VEH[0] + 0.18, Z_VEH[1] + 0.20,
                           f"+{extra} more · authentication out of scope",
                           size=9.5, colour=INK3, anchor="left"))

    # ====================================================== inter-zone =====
    ann += N.arrow(Z_UAV[2] + 0.02, 4.95, Z_TUAV[0] - 0.02, 4.95,
                   colour=LINK_GREEN, width=1.6, both=True)
    ann += N.arrow(Z_TUAV[2] + 0.02, 4.95, Z_SAT[0] - 0.02, 4.95,
                   colour=LINK_GREEN, width=1.6, both=True)
    ann += N.arrow(2.85, Z_UAV[1] - 0.02, 2.85, Z_VEH[3] + 0.02,
                   colour=LINK_GREEN, width=1.6, both=True)
    ann += N.arrow(Z_VEH[2] + 0.02, 1.65, Z_RSU[0] - 0.02, 1.65,
                   colour="#D8B4B0", width=1.3, both=True, dash="dot")

    # the critical edge: satellites -> authority
    link_col = RED if not link_up else "#C97A1E"
    ann += N.arrow(sx, Z_SAT[1] - 0.02, tax, Z_TA[3] + 0.02,
                   colour=link_col, width=2.0, both=True)
    if state.link is not None:
        status = ("LINK DOWN" if not link_up
                  else f"{state.link.availability:.0%} up · "
                       f"{state.link.rtt_ms:.0f} ms")
        ann.append(N.label(Z_SAT[2] - 0.18, Z_SAT[1] + 0.42, status,
                           size=10, colour=link_col, bold=True, anchor="right"))
        ann.append(N.label(Z_SAT[2] - 0.18, Z_SAT[1] + 0.20,
                           "every check goes up here",
                           size=9.5, colour=link_col, anchor="right"))

    # =============================================== invisible hover layer =
    fig.add_trace(go.Scatter(
        x=hx, y=hy, mode="markers",
        marker=dict(size=36, color="rgba(0,0,0,0)"),
        hovertext=ht, hoverinfo="text", showlegend=False))

    fig.update_layout(
        shapes=shapes, annotations=ann,
        height=580, margin=dict(l=6, r=6, t=6, b=6),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False, range=[0.0, 12.4], fixedrange=True),
        yaxis=dict(visible=False, range=[0.0, 6.75], fixedrange=True,
                   scaleanchor="x", scaleratio=1),
        showlegend=False, hovermode="closest",
    )
    return fig


def legend_html() -> str:
    items = [
        ("#5A6672", "registered"), (AMBER, "awaiting check"),
        (TEAL, "verified"), (GREEN, "has group key"),
        (RED, "rejected / revoked"),
    ]
    spans = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:6px;'
        f'margin-right:18px;font-size:12px;color:{INK2}">'
        f'<span style="width:13px;height:9px;border:1.4px solid {c};'
        f'border-radius:2px;display:inline-block"></span>{t}</span>'
        for c, t in items
    )
    return (f'<div style="margin-top:8px;line-height:1.9">{spans}</div>'
            f'<div style="font-size:11.5px;color:{INK3};margin-top:2px">'
            f'Green edges are drone-to-drone (U2U); purple are vehicle-to-'
            f'vehicle (V2V). Hover any node for its status and temporary '
            f'identity.</div>')
