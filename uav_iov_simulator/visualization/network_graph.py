"""
The live topology diagram, laid out like Figure 1 of the paper.

    +-- UAV NETWORKS -----+  +-- TETHERED UAV --+  +-- SATELLITE ----+
    |  drones, U2U links  |<>|  TUAV + ECRV     |<>|  satellites     |
    +---------------------+  +------------------+  +-----------------+
              ^                       ^                     ^
    +-- VEHICULAR --------+  +-- RSU -----------+  +-- TA -----------+
    |  cars, V2V links    |<>|  tower, crossed  |  |  data centre    |
    +---------------------+  +------------------+  +-----------------+

The paper's figure is a static architecture drawing. This one is live: drone
colours follow authentication status, revoked members are struck through, the
satellite link turns red when the TA is unreachable, and the counts update.
So it reads like the paper's diagram while actually showing the simulation.

Icons are vector shapes from `icons.py` rather than emoji, which render
inconsistently and often lose their colour on a projector.
"""

from __future__ import annotations

import plotly.graph_objects as go

from ..protocol.entities import Status
from . import icons as I

# ------------------------------------------------------------- text colours
INK = "#131820"
INK2 = "#55606D"
INK3 = "#8A949F"
AMBER = "#A8580A"
TEAL = "#145D66"
RED = "#97302F"
GREEN = "#1C6B45"
GREY = "#B9C2CB"
PURPLE = "#7B6BB5"
LINK_GREEN = "#5FAE72"

STATUS_COLOUR = {
    Status.UNREGISTERED: GREY,
    Status.REGISTERED: "#6C7A89",
    Status.PENDING: AMBER,
    Status.AUTHENTICATED: TEAL,
    Status.KEYED: GREEN,
    Status.FAILED: RED,
    Status.REVOKED: RED,
    Status.FORGED: RED,
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

# ------------------------------------------------------------ zone geometry
#            x0     y0     x1     y1
Z_UAV = (0.20, 3.35, 5.55, 6.55)
Z_TUAV = (5.80, 3.35, 8.90, 6.55)
Z_SAT = (9.15, 3.35, 12.20, 6.55)
Z_VEH = (0.20, 0.20, 5.55, 3.10)
Z_RSU = (5.80, 0.20, 8.90, 3.10)
Z_TA = (9.15, 0.20, 12.20, 3.10)


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


def _zone_title(fig, z, text, colour=INK2):
    fig.add_annotation(x=(z[0] + z[2]) / 2, y=z[3] - 0.22, showarrow=False,
                       text=f"<b>{text}</b>",
                       font=dict(size=13, color=colour))


def _arrow(fig, x0, y0, x1, y1, colour=LINK_GREEN, width=9, label=""):
    """A thick two-headed arrow between zones, as in the paper."""
    fig.add_annotation(x=x1, y=y1, ax=x0, ay=y0, xref="x", yref="y",
                       axref="x", ayref="y", showarrow=True, text="",
                       arrowhead=2, arrowsize=1.1, arrowwidth=width / 4.5,
                       arrowcolor=colour, opacity=0.9)
    fig.add_annotation(x=x0, y=y0, ax=x1, ay=y1, xref="x", yref="y",
                       axref="x", ayref="y", showarrow=True, text="",
                       arrowhead=2, arrowsize=1.1, arrowwidth=width / 4.5,
                       arrowcolor=colour, opacity=0.9)
    if label:
        fig.add_annotation(x=(x0 + x1) / 2, y=(y0 + y1) / 2 + 0.16,
                           showarrow=False, text=label,
                           font=dict(size=10, color=colour))


def render(state) -> go.Figure:
    """Build the topology figure. READ ONLY - never mutates state."""
    if not state.initialized or state.tuav is None:
        return _empty()

    fig = go.Figure()
    shapes: list[dict] = []
    hover_x, hover_y, hover_t = [], [], []

    link_up = state.link is not None and state.link.availability > 0

    # =========================================================== the zones ==
    I.zone(shapes, *Z_UAV)
    I.zone(shapes, *Z_TUAV, fill="rgba(252,246,236,0.9)", line="#D9B489")
    I.zone(shapes, *Z_SAT)
    I.zone(shapes, *Z_VEH)
    I.zone(shapes, *Z_RSU, fill="rgba(251,233,231,0.9)", line="#E0A9A4")
    I.zone(shapes, *Z_TA)

    # ===================================================== UAV NETWORKS ====
    everyone = state.uavs
    drawn = everyone[:MAX_DRAWN_UAVS]
    hidden = len(everyone) - len(drawn)

    slots = [(1.15, 5.35), (2.85, 5.62), (4.55, 5.25),
             (0.95, 4.30), (2.55, 4.58), (4.25, 4.20), (3.30, 3.78)]
    placed = []
    for u, (px, py) in zip(drawn, slots):
        col = STATUS_COLOUR.get(u.status, GREY)
        revoked = u.status == Status.REVOKED
        I.drone(shapes, px, py, s=1.0, body=col,
                rotor=("#E3B9B6" if revoked else "#9AA8B4"))
        if revoked:
            I._line(shapes, px - 0.30, py - 0.20, px + 0.30, py + 0.20, RED, 2.6)
            I._line(shapes, px - 0.30, py + 0.20, px + 0.30, py - 0.20, RED, 2.6)
        placed.append((u, px, py, col))
        fig.add_annotation(x=px, y=py - 0.30, showarrow=False,
                           text=f"<b>UAV{u.index}</b>",
                           font=dict(size=9.5, color=col))
        hover_x.append(px)
        hover_y.append(py)
        hover_t.append(f"<b>{u.name}</b><br>{STATUS_SHORT.get(u.status, u.status)}"
                       f"<br>ID: TEMP_{u.temp_id_hex()}<br>"
                       f"key epoch: "
                       f"{u.key_epoch if u.key_epoch is not None else 'none'}")

    # U2U links between neighbouring drones
    for a in range(len(placed) - 1):
        u1, x1, y1, _ = placed[a]
        u2, x2, y2, _ = placed[a + 1]
        if Status.REVOKED in (u1.status, u2.status):
            continue
        I.bolt(shapes, x1, y1, x2, y2, LINK_GREEN, 1.5)
    if len(placed) >= 3:
        a, b = placed[0], placed[1]
        fig.add_annotation(x=(a[1] + b[1]) / 2, y=(a[2] + b[2]) / 2 + 0.22,
                           showarrow=False, text="<b>U2U</b>",
                           font=dict(size=10.5, color=LINK_GREEN))

    _zone_title(fig, Z_UAV, "UAV Networks")
    if hidden > 0:
        fig.add_annotation(x=Z_UAV[0] + 0.35, y=Z_UAV[1] + 0.25,
                           showarrow=False, xanchor="left",
                           text=f"+{hidden} more not drawn",
                           font=dict(size=9.5, color=INK3))

    # ====================================================== TETHERED UAV ====
    tx, ty = _centre(Z_TUAV)
    tuav_colour = AMBER if link_up else RED
    I.tethered_drone(shapes, tx, ty + 0.88, s=1.45, body=tuav_colour,
                     rotor="#E8C79A")
    I.truck(shapes, tx, ty - 0.55, s=1.05)
    _zone_title(fig, Z_TUAV, "Tethered UAV")
    fig.add_annotation(x=tx + 0.72, y=ty + 0.88, showarrow=False,
                       xanchor="left", text="<b>TUAV</b>",
                       font=dict(size=11.5, color=tuav_colour))
    fig.add_annotation(x=tx, y=ty - 1.02, showarrow=False, text="<b>ECRV</b>",
                       font=dict(size=11, color=INK2))
    fig.add_annotation(x=tx + 0.14, y=ty + 0.18, showarrow=False,
                       xanchor="left", text="tether",
                       font=dict(size=9, color="#C97A1E"))
    hover_x.append(tx)
    hover_y.append(ty + 0.88)
    hover_t.append(f"<b>Tethered UAV</b><br>the flying roadside unit<br>"
                   f"ID_tu = TEMP_{state.tuav.temp_id_hex()}<br>"
                   f"computes ZERO pairings")

    # ======================================================== SATELLITES ====
    sx, sy = _centre(Z_SAT)
    I.cloud(shapes, sx, sy + 0.55, w=2.5, h=1.5)
    for dx, dy in ((-0.62, 0.95), (0.0, 1.20), (0.62, 0.95),
                   (-0.34, 0.42), (0.34, 0.42)):
        I.satellite(shapes, sx + dx, sy + dy, s=0.95)
    _zone_title(fig, Z_SAT, "Satellite Networks")

    # ============================================================== TA =====
    ax, ay = _centre(Z_TA)
    I.cloud(shapes, ax, ay + 0.28, w=2.6, h=1.7)
    I.buildings(shapes, ax, ay - 0.55, s=1.25)
    _zone_title(fig, Z_TA, "Trusted Authority")
    fig.add_annotation(x=ax, y=ay - 0.86, showarrow=False, text="<b>TA</b>",
                       font=dict(size=12, color=INK))
    fig.add_annotation(x=ax, y=ay + 1.00, showarrow=False,
                       text="does every pairing",
                       font=dict(size=9.5, color=INK2))
    hover_x.append(ax)
    hover_y.append(ay - 0.3)
    hover_t.append("<b>Trusted Authority</b><br>"
                   "performs EVERY pairing (Step GA2)<br>"
                   "the paper does not report its cost")

    # ============================================================= RSU =====
    rx, ry = _centre(Z_RSU)
    I.tower(shapes, rx, ry - 0.55, s=1.5)
    I._line(shapes, rx - 0.58, ry - 0.62, rx + 0.58, ry + 0.52, RED, 3.0)
    I._line(shapes, rx - 0.58, ry + 0.52, rx + 0.58, ry - 0.62, RED, 3.0)
    _zone_title(fig, Z_RSU, "RSU", colour=RED)
    fig.add_annotation(x=rx, y=ry - 0.95, showarrow=False,
                       text="<b>DESTROYED</b>", font=dict(size=11, color=RED))
    fig.add_annotation(x=rx, y=ry - 1.28, showarrow=False,
                       text="what the TUAV replaces",
                       font=dict(size=9, color=RED))

    # ================================================ VEHICULAR NETWORKS ====
    vx, vy = _centre(Z_VEH)
    n_veh = min(len(state.vehicles), MAX_DRAWN_VEHICLES)
    vslots = [(1.10, 2.12), (2.70, 2.28), (4.35, 2.06),
              (0.95, 1.00), (2.60, 1.18), (4.30, 0.96)]
    vpos = []
    for i in range(n_veh):
        px, py = vslots[i]
        if i == 1:
            I.bus(shapes, px, py, s=1.15)
        else:
            I.car(shapes, px, py, s=1.15,
                  colour=I.CAR_COLOURS[i % len(I.CAR_COLOURS)])
        vpos.append((px, py))
    # Link within each row, plus a single cross-row link. Chaining every
    # vehicle in sequence produced long diagonals across the whole zone.
    pairs = [(0, 1), (1, 2), (3, 4), (4, 5), (1, 4)]
    for a, b in pairs:
        if a < len(vpos) and b < len(vpos):
            I.bolt(shapes, vpos[a][0], vpos[a][1] + 0.12,
                   vpos[b][0], vpos[b][1] + 0.12, PURPLE, 1.5)
    if len(vpos) >= 5:
        fig.add_annotation(x=vpos[1][0] + 0.30, y=(vpos[1][1] + vpos[4][1]) / 2,
                           showarrow=False, xanchor="left", text="<b>V2V</b>",
                           font=dict(size=10.5, color=PURPLE))
    _zone_title(fig, Z_VEH, "Vehicular Networks")
    extra = len(state.vehicles) - n_veh
    if extra > 0:
        fig.add_annotation(x=Z_VEH[0] + 0.35, y=Z_VEH[1] + 0.25,
                           showarrow=False, xanchor="left",
                           text=f"+{extra} more · authentication out of scope",
                           font=dict(size=9.5, color=INK3))

    # ====================================================== inter-zone ======
    # UAV network  <->  TUAV
    _arrow(fig, Z_UAV[2] + 0.02, 4.95, Z_TUAV[0] - 0.02, 4.95)
    # TUAV  <->  satellites
    _arrow(fig, Z_TUAV[2] + 0.02, 4.95, Z_SAT[0] - 0.02, 4.95)
    # UAV network  <->  vehicles
    _arrow(fig, 2.87, Z_UAV[1] - 0.02, 2.87, Z_VEH[3] + 0.02)
    # vehicles  <->  RSU (dead: drawn pale)
    _arrow(fig, Z_VEH[2] + 0.02, 1.65, Z_RSU[0] - 0.02, 1.65,
           colour="#D8B4B0", width=7)

    # satellites  <->  TA : THE critical link
    link_colour = RED if not link_up else "#C97A1E"
    fig.add_annotation(x=(Z_SAT[0] + Z_SAT[2]) / 2, y=Z_TA[3] + 0.02,
                       ax=(Z_SAT[0] + Z_SAT[2]) / 2, ay=Z_SAT[1] - 0.02,
                       xref="x", yref="y", axref="x", ayref="y",
                       showarrow=True, text="", arrowhead=2, arrowsize=1.1,
                       arrowwidth=2.6, arrowcolor=link_colour)
    if state.link is not None:
        status = ("LINK DOWN" if not link_up
                  else f"{state.link.availability:.0%} up · "
                       f"{state.link.rtt_ms:.0f} ms")
        fig.add_annotation(x=Z_SAT[2] - 0.22, y=Z_SAT[1] + 0.38,
                           showarrow=False, xanchor="right", align="right",
                           text=f"<b>{status}</b><br>"
                                f"<i>every check goes up here</i>",
                           font=dict(size=9.5, color=link_colour))

    # ============================================== invisible hover layer ==
    fig.add_trace(go.Scatter(
        x=hover_x, y=hover_y, mode="markers",
        marker=dict(size=34, color="rgba(0,0,0,0)"),
        hovertext=hover_t, hoverinfo="text", showlegend=False))

    # =========================================================== layout ====
    fig.update_layout(
        shapes=shapes,
        height=580, margin=dict(l=6, r=6, t=6, b=6),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False, range=[0.0, 12.4], fixedrange=True,
                   constrain="domain"),
        yaxis=dict(visible=False, range=[0.0, 6.75], fixedrange=True,
                   scaleanchor="x", scaleratio=1, constrain="domain"),
        showlegend=False, hovermode="closest",
    )
    return fig


def legend_html() -> str:
    """Colour key, placed under the figure."""
    items = [
        ("#6C7A89", "registered"), (AMBER, "awaiting check"),
        (TEAL, "verified"), (GREEN, "has group key"),
        (RED, "rejected / revoked"),
    ]
    spans = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:6px;'
        f'margin-right:18px;font-size:12px;color:{INK2}">'
        f'<span style="width:11px;height:11px;border-radius:50%;'
        f'background:{c};display:inline-block"></span>{t}</span>'
        for c, t in items
    )
    return (f'<div style="margin-top:8px;line-height:1.9">{spans}</div>'
            f'<div style="font-size:11.5px;color:{INK3};margin-top:2px">'
            f'Green links are drone-to-drone (U2U); purple are vehicle-to-vehicle '
            f'(V2V). Hover any drone for its status and temporary identity.</div>')
