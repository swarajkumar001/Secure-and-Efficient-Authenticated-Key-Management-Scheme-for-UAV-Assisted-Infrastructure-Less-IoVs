"""
Animated protocol playback.

The static topology shows you the END STATE. This shows the protocol actually
running: you watch the signed requests leave the drones, land on the tethered
UAV, travel up the satellite link to the authority, come back, and then the
group key fan out again.

That matters for a demonstration, because the single most important fact about
this scheme - that the expensive work leaves the drone and crosses a satellite
link - is a thing that HAPPENS. A still picture cannot show it. Here you see the
packet go up and come back, and the caption tells you what it cost.

Built with Plotly animation frames rather than a Streamlit redraw loop, so the
browser runs the animation on its own and the server is not blocked.

Timeline
--------
  idle  ->  US1-US3 signing  ->  requests fly to the TUAV
        ->  GA1 offload up the satellite link
        ->  GA2 the authority computes every pairing
        ->  GA2 results return
        ->  GA3 one equation, all verified
        ->  GD4 group key broadcast
        ->  done
"""

from __future__ import annotations

import plotly.graph_objects as go

from ..protocol.entities import Status
from . import icons as I
from .network_graph import (
    AMBER, GREEN, GREY, INK, INK2, INK3, LINK_GREEN, RED, TEAL,
    Z_RSU, Z_SAT, Z_TA, Z_TUAV, Z_UAV, Z_VEH, MAX_DRAWN_UAVS,
)

FRAME_MS = 110          # per frame; ~4 s for the whole run
PACKET = "#E8873B"
KEY_PACKET = "#2FA36B"


# ---------------------------------------------------------------------------
def _lerp(a, b, t):
    return a + (b - a) * t


def _slots(n: int) -> list[tuple[float, float]]:
    base = [(1.15, 5.35), (2.85, 5.62), (4.55, 5.25),
            (0.95, 4.30), (2.55, 4.58), (4.25, 4.20), (3.30, 3.78)]
    return base[:n]


def _centre(z):
    return (z[0] + z[2]) / 2, (z[1] + z[3]) / 2


# ---------------------------------------------------------------------------
# The script: one entry per frame.
#   (caption, phase_label, uav_tone, packet_spec)
# packet_spec is ("none" | "uav->tuav" | "tuav->ta" | "ta->tuav" | "tuav->uav",
#                 progress 0..1)
# ---------------------------------------------------------------------------
def _script() -> list[dict]:
    f: list[dict] = []

    def add(n, caption, step, tone, mode, t0=0.0, t1=0.0, pulse=None):
        for i in range(n):
            p = t0 if n == 1 else _lerp(t0, t1, i / (n - 1))
            f.append(dict(caption=caption, step=step, tone=tone,
                          mode=mode, t=p, pulse=pulse))

    add(3, "Idle. Drones are registered but have proved nothing yet.",
        "", "registered", "none")
    add(4, "US1-US3 &mdash; each drone draws a fresh random value, builds a "
           "temporary name, and signs itself.",
        "US1&ndash;US3", "pending", "none")
    add(7, "The n signed requests travel to the tethered UAV.",
        "US3", "pending", "uav->tuav", 0.0, 1.0)
    add(2, "All requests received. The TUAV cannot verify them itself.",
        "GA1", "pending", "none")
    add(7, "GA1 &mdash; the TUAV forwards everything up the satellite link to "
           "the authority.",
        "GA1", "pending", "tuav->ta", 0.0, 1.0, pulse="link")
    add(4, "GA2 &mdash; the authority computes every bilinear pairing. "
           "This is the expensive step, and the paper does not report its cost.",
        "GA2", "pending", "none", pulse="ta")
    add(7, "GA2 &mdash; the precomputed pairings come back down.",
        "GA2", "pending", "ta->tuav", 0.0, 1.0, pulse="link")
    add(3, "GA3 &mdash; the TUAV checks ONE equation covering every drone.",
        "GA3", "pending", "none", pulse="tuav")
    add(3, "GA4 &mdash; it balances. Every requester is verified.",
        "GA4", "verified", "none")
    add(7, "GD4 &mdash; one broadcast carries the group key to all of them.",
        "GD4", "verified", "tuav->uav", 0.0, 1.0)
    add(4, "GD6 &mdash; every drone recovers the same key from its own private "
           "value. Secure group communication is established.",
        "GD6", "keyed", "none")
    return f


TONE_COLOUR = {
    "registered": "#6C7A89",
    "pending": AMBER,
    "verified": TEAL,
    "keyed": GREEN,
}


# ---------------------------------------------------------------------------
def build(state) -> go.Figure | None:
    """Return an animated figure, or None if the system is not initialised."""
    if not state.initialized or state.tuav is None or not state.uavs:
        return None

    drawn = state.uavs[:MAX_DRAWN_UAVS]
    pts = _slots(len(drawn))
    if not pts:
        return None

    tux, tuy = _centre(Z_TUAV)
    tuy_drone = tuy + 0.88
    sx, sy = _centre(Z_SAT)
    tax, tay = _centre(Z_TA)

    # ---------------------------------------------------- static scenery ---
    shapes: list[dict] = []
    I.zone(shapes, *Z_UAV)
    I.zone(shapes, *Z_TUAV, fill="rgba(252,246,236,0.9)", line="#D9B489")
    I.zone(shapes, *Z_SAT)
    I.zone(shapes, *Z_VEH)
    I.zone(shapes, *Z_RSU, fill="rgba(251,233,231,0.9)", line="#E0A9A4")
    I.zone(shapes, *Z_TA)

    I.tethered_drone(shapes, tux, tuy_drone, s=1.45, body=AMBER, rotor="#E8C79A")
    I.truck(shapes, tux, tuy - 0.55, s=1.05)
    I.cloud(shapes, sx, sy + 0.55, w=2.5, h=1.5)
    for dx, dy in ((-0.62, 0.95), (0.0, 1.20), (0.62, 0.95),
                   (-0.34, 0.42), (0.34, 0.42)):
        I.satellite(shapes, sx + dx, sy + dy, s=0.95)
    I.cloud(shapes, tax, tay + 0.28, w=2.6, h=1.7)
    I.buildings(shapes, tax, tay - 0.55, s=1.25)
    I.tower(shapes, *(_centre(Z_RSU)[0], _centre(Z_RSU)[1] - 0.55), s=1.5)
    rx, ry = _centre(Z_RSU)
    I._line(shapes, rx - 0.58, ry - 0.62, rx + 0.58, ry + 0.52, RED, 3.0)
    I._line(shapes, rx - 0.58, ry + 0.52, rx + 0.58, ry - 0.62, RED, 3.0)
    for i, (px, py) in enumerate(pts):
        I.drone(shapes, px, py, s=1.0, body="#AEB9C4", rotor="#CFD7DE")
    nveh = min(5, len(state.vehicles))
    for i in range(nveh):
        vx = 1.0 + i * 1.05
        (I.bus if i == 1 else I.car)(shapes, vx, 1.45, s=1.1)

    # ------------------------------------------------- static annotations --
    static = [
        dict(x=(Z_UAV[0] + Z_UAV[2]) / 2, y=Z_UAV[3] - 0.22, showarrow=False,
             text="<b>UAV Networks</b>", font=dict(size=13, color=INK2)),
        dict(x=tux, y=Z_TUAV[3] - 0.22, showarrow=False,
             text="<b>Tethered UAV</b>", font=dict(size=13, color=INK2)),
        dict(x=sx, y=Z_SAT[3] - 0.22, showarrow=False,
             text="<b>Satellite Networks</b>", font=dict(size=13, color=INK2)),
        dict(x=(Z_VEH[0] + Z_VEH[2]) / 2, y=Z_VEH[3] - 0.22, showarrow=False,
             text="<b>Vehicular Networks</b>", font=dict(size=13, color=INK2)),
        dict(x=rx, y=Z_RSU[3] - 0.22, showarrow=False,
             text="<b>RSU</b>", font=dict(size=13, color=RED)),
        dict(x=rx, y=ry - 0.95, showarrow=False, text="<b>DESTROYED</b>",
             font=dict(size=11, color=RED)),
        dict(x=tax, y=Z_TA[3] - 0.22, showarrow=False,
             text="<b>Trusted Authority</b>", font=dict(size=13, color=INK2)),
        dict(x=tax, y=tay + 1.02, showarrow=False, text="does every pairing",
             font=dict(size=9.5, color=INK2)),
        dict(x=tux, y=tuy - 1.02, showarrow=False, text="<b>ECRV</b>",
             font=dict(size=11, color=INK2)),
    ]
    for (px, py), u in zip(pts, drawn):
        static.append(dict(x=px, y=py - 0.32, showarrow=False,
                           text=f"<b>UAV{u.index}</b>",
                           font=dict(size=9.5, color=INK3)))

    # ------------------------------------------------------- packet paths --
    def path_points(mode: str, t: float) -> tuple[list[float], list[float]]:
        if mode == "uav->tuav":
            return ([_lerp(px, tux, t) for px, _ in pts],
                    [_lerp(py, tuy_drone, t) for _, py in pts])
        if mode == "tuav->uav":
            return ([_lerp(tux, px, t) for px, _ in pts],
                    [_lerp(tuy_drone, py, t) for _, py in pts])
        if mode == "tuav->ta":
            # up through the satellite zone, then down to the authority
            if t < 0.55:
                k = t / 0.55
                return ([_lerp(tux, sx, k)], [_lerp(tuy_drone, sy + 0.9, k)])
            k = (t - 0.55) / 0.45
            return ([_lerp(sx, tax, k)], [_lerp(sy + 0.9, tay + 0.5, k)])
        if mode == "ta->tuav":
            if t < 0.45:
                k = t / 0.45
                return ([_lerp(tax, sx, k)], [_lerp(tay + 0.5, sy + 0.9, k)])
            k = (t - 0.45) / 0.55
            return ([_lerp(sx, tux, k)], [_lerp(sy + 0.9, tuy_drone, k)])
        return ([], [])

    script = _script()

    def frame_traces(step: dict):
        tone = TONE_COLOUR[step["tone"]]
        ring = go.Scatter(
            x=[p[0] for p in pts], y=[p[1] for p in pts], mode="markers",
            marker=dict(size=30, color="rgba(0,0,0,0)",
                        line=dict(color=tone, width=3.5)),
            hoverinfo="skip", showlegend=False)
        px, py = path_points(step["mode"], step["t"])
        colour = KEY_PACKET if step["mode"] == "tuav->uav" else PACKET
        pkt = go.Scatter(
            x=px, y=py, mode="markers",
            marker=dict(size=13, color=colour, symbol="diamond",
                        line=dict(color="white", width=1.6)),
            hoverinfo="skip", showlegend=False)
        return [ring, pkt]

    def frame_annotations(step: dict):
        ann = list(static)
        ann.append(dict(
            x=(Z_UAV[0] + Z_TA[2]) / 2, y=0.02, xanchor="center",
            yanchor="bottom", showarrow=False, align="center",
            text=(f"<b style='color:{AMBER}'>{step['step']}</b> &nbsp; "
                  if step["step"] else "") + step["caption"],
            font=dict(size=13, color=INK),
            bgcolor="rgba(255,255,255,0.94)", bordercolor="#DCE2E8",
            borderwidth=1, borderpad=9))
        if step.get("pulse") == "ta":
            ann.append(dict(x=tax, y=tay + 1.45, showarrow=False,
                            text="<b>computing pairings…</b>",
                            font=dict(size=11, color=RED)))
        if step.get("pulse") == "tuav":
            ann.append(dict(x=tux, y=tuy_drone + 0.75, showarrow=False,
                            text="<b>one equation</b>",
                            font=dict(size=11, color=AMBER)))
        return ann

    # --------------------------------------------------- the link, always --
    base_shapes = list(shapes)
    link_shape = dict(type="line", x0=sx, y0=Z_SAT[1] - 0.05,
                      x1=tax, y1=Z_TA[3] + 0.05,
                      line=dict(color="#C97A1E", width=2.4, dash="dash"),
                      layer="below")
    base_shapes.append(link_shape)

    first = script[0]
    fig = go.Figure(
        data=frame_traces(first),
        frames=[go.Frame(data=frame_traces(s), name=str(i),
                         layout=dict(annotations=frame_annotations(s)))
                for i, s in enumerate(script)],
    )

    fig.update_layout(
        shapes=base_shapes,
        annotations=frame_annotations(first),
        height=620, margin=dict(l=6, r=6, t=48, b=6),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False, range=[0.0, 12.4], fixedrange=True),
        yaxis=dict(visible=False, range=[-0.55, 6.75], fixedrange=True,
                   scaleanchor="x", scaleratio=1),
        showlegend=False,
        updatemenus=[dict(
            type="buttons", direction="left", showactive=False,
            x=0.0, y=1.06, xanchor="left", yanchor="bottom",
            pad=dict(t=0, r=6),
            bgcolor="#FCF3E7", bordercolor="#E0B77E", borderwidth=1,
            font=dict(size=12, color=INK),
            buttons=[
                dict(label="  Play the protocol  ", method="animate",
                     args=[None, dict(
                         frame=dict(duration=FRAME_MS, redraw=True),
                         fromcurrent=True, mode="immediate",
                         transition=dict(duration=0))]),
                dict(label="  Pause  ", method="animate",
                     args=[[None], dict(
                         frame=dict(duration=0, redraw=False),
                         mode="immediate",
                         transition=dict(duration=0))]),
            ])],
        sliders=[dict(
            active=0, x=0.26, len=0.72, y=1.06, xanchor="left",
            yanchor="bottom", pad=dict(t=0, b=0),
            currentvalue=dict(visible=False),
            tickcolor="rgba(0,0,0,0)",
            font=dict(size=1, color="rgba(0,0,0,0)"),
            steps=[dict(method="animate", label="",
                        args=[[str(i)], dict(
                            frame=dict(duration=0, redraw=True),
                            mode="immediate",
                            transition=dict(duration=0))])
                   for i in range(len(script))])],
    )
    return fig


CAPTION = (
    "Press **Play the protocol** to watch one full authentication run: the "
    "drones sign, their requests reach the tethered UAV, the tethered UAV "
    "forwards everything up the satellite link to the authority, the pairings "
    "come back, one equation verifies the whole group, and the group key is "
    "broadcast. Drag the slider to step through it by hand."
)
