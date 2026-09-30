"""
The live topology diagram - the four tiers of the paper's Figure 1.

    TA (cloud)
      |  satellite link          <- drawn RED, because it sits on the critical
    TUAV --- tether --- ECRV        path of every single verification
     /  |  \
  UAV  UAV  UAV ...
   |    |    |
  cars cars cars

Layout rules that keep it readable on a projector:

  * Tier labels live in a left-hand gutter, never on top of a node.
  * Each UAV owns a contiguous block of vehicles directly beneath it, so the
    links fan out locally instead of crossing the whole figure.
  * The ECRV sits to the SIDE of the tether, clear of the arrow fan.
  * Above ten UAVs the swarm is summarised rather than drawn one-by-one,
    because forty overlapping circles communicate nothing.
"""

from __future__ import annotations

import plotly.graph_objects as go

from ..protocol.entities import Status

# Colours chosen to survive a projector; they match the reports and the decks.
INK = "#131820"
INK2 = "#55606D"
INK3 = "#8A949F"
AMBER = "#A8580A"
TEAL = "#145D66"
RED = "#97302F"
GREEN = "#1C6B45"
GREY = "#B9C2CB"

STATUS_COLOUR = {
    Status.UNREGISTERED: GREY,
    Status.REGISTERED: INK3,
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

# Above this many UAVs, draw a summary instead of individual nodes.
MAX_DRAWN_UAVS = 10

Y_TA, Y_TUAV, Y_UAV, Y_VEH = 4.2, 2.6, 1.0, -0.5
X_MIN, X_MAX = -7.6, 8.6


def _spread(count: int, width: float) -> list[float]:
    if count <= 0:
        return []
    if count == 1:
        return [0.0]
    step = width / (count - 1)
    return [-width / 2 + i * step for i in range(count)]


def _empty(fig: go.Figure) -> go.Figure:
    fig.add_annotation(
        text="Nothing running yet.<br><b>Press Initialize in the sidebar.</b>",
        x=0.5, y=0.5, xref="paper", yref="paper",
        showarrow=False, font=dict(size=16, color=INK3), align="center")
    fig.update_layout(height=560, plot_bgcolor="rgba(0,0,0,0)",
                      paper_bgcolor="rgba(0,0,0,0)",
                      xaxis=dict(visible=False), yaxis=dict(visible=False))
    return fig


def render(state) -> go.Figure:
    """Build the topology figure. READ ONLY - never mutates state."""
    fig = go.Figure()

    if not state.initialized or state.tuav is None:
        return _empty(fig)

    link_up = state.link is not None and state.link.availability > 0
    link_colour = RED if not link_up else AMBER

    # =================================================== tier backgrounds ==
    for y0, y1 in ((Y_TA - 0.55, Y_TA + 0.62), (Y_UAV - 0.55, Y_UAV + 0.62)):
        fig.add_shape(type="rect", x0=X_MIN, x1=X_MAX, y0=y0, y1=y1,
                      line=dict(width=0), fillcolor="rgba(128,138,150,0.05)",
                      layer="below")

    # ======================================================= tier labels ==
    for y, label in ((Y_TA, "TIER 1<br>CLOUD"),
                     (Y_TUAV, "TIER 2<br>MOBILE EDGE"),
                     (Y_UAV, "TIER 3<br>AERIAL SWARM"),
                     (Y_VEH, "TIER 4<br>GROUND")):
        fig.add_annotation(x=X_MIN + 0.15, y=y, showarrow=False, xanchor="left",
                           text=f"<b>{label}</b>", align="left",
                           font=dict(size=9.5, color=INK3))

    # ===================================================== satellite link ==
    fig.add_trace(go.Scatter(
        x=[0, 0], y=[Y_TA - 0.40, Y_TUAV + 0.42], mode="lines",
        line=dict(color=link_colour, width=4,
                  dash="dot" if not link_up else "dash"),
        hoverinfo="text", showlegend=False,
        text=(f"TA link - {state.link.availability:.0%} available, "
              f"{state.link.rtt_ms:.0f} ms round trip<br>"
              "Steps GA1/GA2 cross this for EVERY verification")
        if state.link else "",
    ))
    if state.link is not None:
        status = ("LINK DOWN" if not link_up
                  else f"{state.link.availability:.0%} up · "
                       f"{state.link.rtt_ms:.0f} ms")
        fig.add_annotation(
            x=0.35, y=(Y_TA + Y_TUAV) / 2, xanchor="left", showarrow=False,
            align="left", font=dict(size=10, color=link_colour),
            text=f"<b>satellite link</b><br>{status}<br>"
                 f"<i>every check goes up here</i>")

    # =============================================================== TA ===
    fig.add_shape(type="rect", x0=-1.9, x1=1.9, y0=Y_TA - 0.40, y1=Y_TA + 0.40,
                  line=dict(color=INK2, width=2), fillcolor="white",
                  layer="below")
    fig.add_trace(go.Scatter(
        x=[0], y=[Y_TA + 0.11], mode="text", text=["<b>TA</b>"],
        textfont=dict(size=15, color=INK), hoverinfo="text", showlegend=False,
        hovertext=["Trusted Authority - performs EVERY pairing (Step GA2)"]))
    fig.add_annotation(x=0, y=Y_TA - 0.17, showarrow=False,
                       text="cloud · does all the heavy maths",
                       font=dict(size=9.5, color=INK2))

    # ============================================================= TUAV ===
    fig.add_shape(type="rect", x0=-2.1, x1=2.1, y0=Y_TUAV - 0.42,
                  y1=Y_TUAV + 0.42, line=dict(color=AMBER, width=2.5),
                  fillcolor="#FBF1E4", layer="below")
    fig.add_trace(go.Scatter(
        x=[0], y=[Y_TUAV + 0.13], mode="text", text=["<b>TUAV</b>"],
        textfont=dict(size=15, color=INK), hoverinfo="text", showlegend=False,
        hovertext=[f"Tethered UAV - the flying roadside unit<br>"
                   f"ID_tu = TEMP_{state.tuav.temp_id_hex()}<br>"
                   f"Computes ZERO pairings"]))
    fig.add_annotation(x=0, y=Y_TUAV - 0.18, showarrow=False,
                       text="flying base station · no pairings",
                       font=dict(size=9.5, color=INK2))

    # ==================================================== tether + ECRV ===
    # Drawn to the SIDE so the arrow fan below stays clear.
    # Placed BESIDE the TUAV rather than beneath it: anything below sits in
    # the fan of links to the swarm and gets crossed by them.
    fig.add_trace(go.Scatter(
        x=[2.1, 2.9], y=[Y_TUAV, Y_TUAV], mode="lines",
        line=dict(color=AMBER, width=6), hoverinfo="text", showlegend=False,
        text="Tether - continuous power from the ground vehicle"))
    fig.add_shape(type="rect", x0=2.9, x1=5.0, y0=Y_TUAV - 0.32,
                  y1=Y_TUAV + 0.32, line=dict(color=AMBER, width=1.6),
                  fillcolor="white", layer="below")
    fig.add_annotation(x=3.95, y=Y_TUAV + 0.09, showarrow=False,
                       text="<b>ECRV</b>", font=dict(size=11.5, color=INK))
    fig.add_annotation(x=3.95, y=Y_TUAV - 0.13, showarrow=False,
                       text="power truck", font=dict(size=9, color=INK2))
    fig.add_annotation(x=2.5, y=Y_TUAV + 0.26, showarrow=False,
                       text="tether", font=dict(size=9, color=AMBER))

    # ======================================================== dead RSU ====
    fig.add_shape(type="rect", x0=5.6, x1=8.4, y0=Y_TUAV - 0.42,
                  y1=Y_TUAV + 0.42, line=dict(color=RED, width=1.8, dash="dash"),
                  fillcolor="rgba(151,48,47,0.05)")
    fig.add_shape(type="line", x0=5.6, x1=8.4, y0=Y_TUAV - 0.42,
                  y1=Y_TUAV + 0.42, line=dict(color=RED, width=1.8))
    fig.add_shape(type="line", x0=5.6, x1=8.4, y0=Y_TUAV + 0.42,
                  y1=Y_TUAV - 0.42, line=dict(color=RED, width=1.8))
    fig.add_annotation(x=7.0, y=Y_TUAV + 0.63, showarrow=False,
                       text="<b>RSU - destroyed</b>",
                       font=dict(size=10.5, color=RED))
    fig.add_annotation(x=7.0, y=Y_TUAV - 0.63, showarrow=False,
                       text="what the TUAV replaces",
                       font=dict(size=9, color=RED))

    # ============================================================ swarm ===
    # Draw revoked members as well. Dropping them makes the numbering jump
    # (2, 4, 5 ...) and hides the very thing the revocation demo is showing.
    everyone = state.uavs
    drawn = everyone[:MAX_DRAWN_UAVS]
    hidden = len(everyone) - len(drawn)
    swarm_width = 9.4 if len(drawn) > 6 else 7.0
    xs = _spread(len(drawn), swarm_width)

    for x, u in zip(xs, drawn):
        revoked = u.status == Status.REVOKED
        col = STATUS_COLOUR.get(u.status, GREY)
        fig.add_trace(go.Scatter(
            x=[0, x], y=[Y_TUAV - 0.44, Y_UAV + 0.30], mode="lines",
            line=dict(color=col, width=1.6,
                      dash="dot" if revoked else "solid"),
            hoverinfo="skip", showlegend=False,
            opacity=0.22 if revoked else 0.6))

    fig.add_annotation(
        x=-swarm_width / 2 - 0.1, y=Y_UAV + 0.78, showarrow=False,
        xanchor="left", text="<b>batch authenticate + one group key</b>",
        font=dict(size=10.5, color=TEAL))

    if drawn:
        fig.add_trace(go.Scatter(
            x=xs, y=[Y_UAV] * len(xs), mode="markers+text",
            marker=dict(
                size=34,
                color=[STATUS_COLOUR.get(u.status, GREY) for u in drawn],
                line=dict(color="white", width=2.5),
                symbol=["x-thin-open" if u.status == Status.REVOKED
                        else "circle" for u in drawn]),
            text=[("" if u.status == Status.REVOKED else str(u.index))
                  for u in drawn],
            textposition="middle center",
            textfont=dict(size=11, color="white"),
            hovertext=[f"<b>{u.name}</b><br>"
                       f"{STATUS_SHORT.get(u.status, u.status)}<br>"
                       f"ID: TEMP_{u.temp_id_hex()}<br>"
                       f"key epoch: "
                       f"{u.key_epoch if u.key_epoch is not None else 'none'}"
                       for u in drawn],
            hoverinfo="text", showlegend=False))

    if hidden > 0:
        fig.add_annotation(
            x=swarm_width / 2 + 0.75, y=Y_UAV, showarrow=False, xanchor="left",
            align="left", text=f"<b>+{hidden} more</b><br>not drawn",
            font=dict(size=10, color=INK3))

    # ========================================================= vehicles ===
    # Each UAV owns a contiguous block directly beneath it, so nothing crosses.
    if state.vehicles and drawn:
        per_uav = max(1, min(3, len(state.vehicles) // max(1, len(drawn))))
        vx_all, vhover = [], []
        for x, u in zip(xs, drawn):
            if u.status == Status.REVOKED:
                continue
            offs = _spread(per_uav, 0.58 * (per_uav - 1)) if per_uav > 1 else [0.0]
            for o in offs:
                vx = x + o
                vx_all.append(vx)
                vhover.append(f"vehicle served by {u.name}")
                fig.add_trace(go.Scatter(
                    x=[x, vx], y=[Y_UAV - 0.30, Y_VEH + 0.18], mode="lines",
                    line=dict(color=INK3, width=0.9, dash="dot"),
                    hoverinfo="skip", showlegend=False, opacity=0.5))
        fig.add_trace(go.Scatter(
            x=vx_all, y=[Y_VEH] * len(vx_all), mode="markers",
            marker=dict(size=13, color="white", symbol="square",
                        line=dict(color=INK3, width=1.4)),
            hovertext=vhover, hoverinfo="text", showlegend=False))

        shown = len(vx_all)
        label = f"{shown} vehicles shown"
        if len(state.vehicles) > shown:
            label += f" of {len(state.vehicles)}"
        fig.add_annotation(
            x=swarm_width / 2 + 0.75, y=Y_VEH, showarrow=False, xanchor="left",
            align="left", font=dict(size=9.5, color=INK3),
            text=f"{label}<br><i>authentication out of<br>scope, as in the paper</i>")

    # =========================================================== layout ===
    fig.update_layout(
        height=580, margin=dict(l=6, r=6, t=6, b=6),
        # Transparent canvas: the figure inherits whichever Streamlit theme the
        # viewer has. Node fills stay opaque, so labels remain readable.
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False, range=[X_MIN, X_MAX], fixedrange=True),
        yaxis=dict(visible=False, range=[Y_VEH - 0.95, Y_TA + 0.95],
                   fixedrange=True),
        showlegend=False, hovermode="closest",
    )
    return fig


def legend_html() -> str:
    """Colour key, placed under the figure."""
    items = [
        (INK3, "registered"), (AMBER, "awaiting check"), (TEAL, "verified"),
        (GREEN, "has group key"), (RED, "rejected / revoked"),
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
            f'Hover any node for its status and temporary identity. The red '
            f'link to the TA sits on the critical path of every check.</div>')
