"""
Performance charts.

ONE RULE, ENFORCED THROUGHOUT
-----------------------------
A number the paper reported and a number we measured must never look alike.
Paper series are DASHED and greyed in the legend; measured series are SOLID.
Every axis title says which. If a viewer cannot tell at a glance, the chart is
wrong and should not ship.

Absolute milliseconds are not comparable between the two - the paper reports
MIRACL (C) at 80-bit, we run pure Python on BN128. What IS comparable is the
shape: linear in n, and the relative ordering of the slopes.
"""

from __future__ import annotations

import math

import pandas as pd
import plotly.graph_objects as go

from ..paper_model import cost as paper_cost
from ..paper_model import overhead as paper_overhead

# Validated categorical palette, assigned in fixed order and never cycled.
S1, S2, S3, S4, S5 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"
INK, INK2, INK3 = "#131820", "#55606D", "#8A949F"
# Mid-tone with alpha: legible as a grid line on a white page and on a
# dark one, which a fixed light grey is not.
RULE = "rgba(128,138,150,0.30)"
RED, GREEN, AMBER = "#97302F", "#1C6B45", "#A8580A"

SCHEME_COLOUR = {
    "Proposed (paper)": S1,
    "Ali et al. [14]": S2,
    "Mei et al. [7]": S3,
    "Xu et al. [18]": S4,
    "Kumar et al. [10]": S5,
}

ACTOR_COLOUR = {
    "tuav": S1,
    "ta": RED,
    "link": S4,
    "drone": S3,
    "total": INK2,
}


def _base(fig: go.Figure, *, height: int = 430, ytitle: str = "",
          xtitle: str = "", logy: bool = False) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=14, r=14, t=42, b=14),
        # Transparent so the chart sits correctly in light OR dark theme.
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=INK2, size=12,
                  family="Segoe UI, Helvetica Neue, Arial, sans-serif"),
        legend=dict(orientation="h", yanchor="bottom", y=1.04,
                    xanchor="left", x=0, font=dict(size=11.5),
                    bgcolor="rgba(0,0,0,0)"),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="white", bordercolor=RULE,
                        font=dict(size=12, color=INK)),
    )
    fig.update_xaxes(
        title=dict(text=xtitle, font=dict(size=11.5, color=INK3)),
        showgrid=False, zeroline=False, showline=True,
        linecolor="rgba(128,138,150,0.45)", linewidth=1.2,
        ticks="outside", ticklen=4, tickcolor="rgba(128,138,150,0.45)",
        color=INK3, tickfont=dict(size=11))
    fig.update_yaxes(
        title=dict(text=ytitle, font=dict(size=11.5, color=INK3)),
        gridcolor=RULE, griddash="dot", zeroline=False, showline=False,
        color=INK3, tickfont=dict(size=11),
        type="log" if logy else "linear")
    return fig


# ---------------------------------------------------------------------------
# 1. The headline: where the work actually happens
# ---------------------------------------------------------------------------
def chart_where_the_work_happens(measured: pd.DataFrame) -> go.Figure:
    """Our measured TUAV / TA / link split, against the paper's reported curve.

    Log scale on the y axis, because the TA side is three orders of magnitude
    above the TUAV side. That gap is the finding, not a plotting artefact.
    """
    fig = go.Figure()
    if measured.empty:
        return _base(fig, ytitle="ms")

    n_values = sorted(measured["n"].unique())

    # --- the paper's reported curve, DASHED ---------------------------
    fig.add_trace(go.Scatter(
        x=n_values,
        y=[paper_cost.cost("Proposed (paper)", "GA", n) for n in n_values],
        name="Paper, reported (Table III)",
        mode="lines", line=dict(color=INK3, width=2, dash="dash"),
        hovertemplate="paper: %{y:.1f} ms<extra></extra>",
    ))

    # --- what we measured, SOLID --------------------------------------
    # NOTE: no area fills on this chart. The y axis is logarithmic, where
    # "fill to zero" means fill to negative infinity - Plotly then expands the
    # range to absurd values and every series collapses onto one line.
    wanted = [
        ("GA (TA side)", "Ours: TA side (paper reports none)",
         ACTOR_COLOUR["ta"], 3.4),
        ("GA (link)", "Ours: TA link", ACTOR_COLOUR["link"], 2.2),
        ("GA (TUAV side)", "Ours: TUAV side", ACTOR_COLOUR["tuav"], 3.4),
    ]
    seen: list[float] = []
    for phase, label, colour, width in wanted:
        sub = measured[measured["phase"] == phase].sort_values("n")
        if sub.empty:
            continue
        seen.extend(v for v in sub["ms"] if v > 0)
        fig.add_trace(go.Scatter(
            x=sub["n"], y=sub["ms"], name=label, mode="lines+markers",
            line=dict(color=colour, width=width),
            marker=dict(size=8, line=dict(color="white", width=1.8)),
            hovertemplate=label + ": %{y:.3g} ms<extra></extra>",
        ))
        # Direct label at the right end, so the legend is a backup not a lookup.
        #
        # On a LOG axis Plotly positions annotations by the log10 of the value,
        # not the value itself. Passing the raw number puts "200 ms" at 10^200,
        # i.e. off the chart entirely.
        last = sub.iloc[-1]
        val = float(last["ms"])
        if val <= 0:
            continue
        txt = f"{val:,.0f}" if val >= 10 else f"{val:.2g}"
        fig.add_annotation(
            x=last["n"], y=math.log10(val), xanchor="left", xshift=9,
            showarrow=False, text=f"<b>{txt} ms</b>",
            font=dict(size=10.5, color=colour))

    f = _base(fig, height=470, logy=True,
              xtitle="number of UAVs authenticated together (n)",
              ytitle="milliseconds (log scale)")
    # Pin the log range to the data. Left to itself a log axis with very small
    # values produces decades of empty space.
    if seen:
        lo = math.floor(math.log10(min(seen))) - 0.15
        hi = math.ceil(math.log10(max(seen))) + 0.35
        f.update_yaxes(range=[lo, hi])
    # Room for the end-of-line labels, which are otherwise clipped.
    f.update_layout(margin=dict(l=14, r=86, t=42, b=14))
    return f


# ---------------------------------------------------------------------------
# 2. The paper's own Table III comparison
# ---------------------------------------------------------------------------
def chart_paper_table_iii(n_max: int = 120) -> go.Figure:
    """All five schemes from Table III. Entirely analytical - nothing is run."""
    fig = go.Figure()
    n_values = list(range(0, n_max + 1, 5))
    order = ["Kumar et al. [10]", "Xu et al. [18]", "Mei et al. [7]",
             "Ali et al. [14]", "Proposed (paper)"]
    for scheme in order:
        ys = [paper_cost.cost(scheme, "GA", n) for n in n_values]
        is_proposed = scheme == "Proposed (paper)"
        fig.add_trace(go.Scatter(
            x=n_values, y=ys, name=scheme, mode="lines",
            line=dict(color=SCHEME_COLOUR[scheme],
                      width=4 if is_proposed else 2, dash="dash"),
            hovertemplate=scheme + ": %{y:.0f} ms<extra></extra>",
        ))
        fig.add_annotation(
            x=n_values[-1], y=ys[-1], text=f"  {ys[-1]:.0f} ms",
            showarrow=False, xanchor="left",
            font=dict(size=10, color=SCHEME_COLOUR[scheme]))

    fig.update_layout(title=dict(
        text="All series DASHED: every value here is reported, none measured.",
        font=dict(size=11, color=INK3), x=0))
    return _base(fig, height=450,
                 xtitle="number of UAVs (n)",
                 ytitle="group authentication, ms  ·  paper (analytical)")


# ---------------------------------------------------------------------------
# 3. The availability cliff
# ---------------------------------------------------------------------------
def chart_availability_cliff(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if df.empty:
        return _base(fig)

    d = df.sort_values("availability")
    fig.add_trace(go.Scatter(
        x=d["availability"] * 100, y=d["success rate"] * 100,
        mode="lines+markers", name="Authentication success rate",
        line=dict(color=RED, width=3),
        marker=dict(size=9, line=dict(color="white", width=1.5)),
        fill="tozeroy", fillcolor="rgba(151,48,47,0.10)",
        hovertemplate="%{x:.0f}% link → %{y:.0f}% success<extra></extra>",
    ))
    fig.add_annotation(
        x=5, y=4, text="<b>zero</b> &mdash; not degraded", showarrow=True,
        arrowhead=2, ax=72, ay=-52, font=dict(size=12.5, color=RED),
        arrowcolor=RED, arrowwidth=1.4,
        bgcolor="rgba(255,255,255,0.92)", borderpad=4)
    fig.add_hline(y=50, line=dict(color="rgba(128,138,150,0.35)", width=1,
                                  dash="dot"))

    fig.update_layout(title=dict(
        text="Measured on the PUBLISHED scheme - no modification needed.",
        font=dict(size=11, color=INK3), x=0))
    return _base(fig, height=420,
                 xtitle="TA link availability (%)",
                 ytitle="authentication success rate (%)  ·  measured")


# ---------------------------------------------------------------------------
# 4. Goodput under batch poisoning
# ---------------------------------------------------------------------------
def chart_goodput(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if df.empty:
        return _base(fig)

    for mode, colour, dash in (("published scheme", RED, "solid"),
                               ("with individual fallback", GREEN, "solid")):
        sub = df[df["mode"] == mode].sort_values("forged fraction")
        if sub.empty:
            continue
        fig.add_trace(go.Scatter(
            x=sub["forged fraction"] * 100, y=sub["goodput"] * 100,
            mode="lines+markers", name=mode,
            line=dict(color=colour, width=3, dash=dash),
            marker=dict(size=9, line=dict(color="white", width=1.5)),
            hovertemplate=mode + ": %{y:.0f}%<extra></extra>",
        ))

    fig.add_vrect(x0=0, x1=5, fillcolor="rgba(151,48,47,0.06)",
                  line_width=0, layer="below")
    fig.add_annotation(
        x=5.4, y=10, text="one forged packet in twenty<br>denies the whole swarm",
        showarrow=True, arrowhead=2, ax=96, ay=-54, arrowwidth=1.4,
        font=dict(size=11.5, color=RED), arrowcolor=RED, align="left",
        bgcolor="rgba(255,255,255,0.92)", borderpad=4)

    fig.update_layout(title=dict(
        text="The fallback is NOT part of the published scheme - "
             "Step GA4 has no else-branch.",
        font=dict(size=11, color=INK3), x=0))
    return _base(fig, height=420,
                 xtitle="forged credentials in the batch (%)",
                 ytitle="goodput: honest members authenticated (%)  ·  measured")


# ---------------------------------------------------------------------------
# 5. Communication overhead
# ---------------------------------------------------------------------------
def chart_overhead(n: int = 120) -> go.Figure:
    rows = paper_overhead.comparison_table(n)
    fig = go.Figure()

    labels = [r["Scheme"] for r in rows]
    values = [r[f"GA at n={n} (KB)"] for r in rows]
    colours = [
        S1 if "Proposed (paper)" == r["Scheme"]
        else (AMBER if r["Source"] == paper_overhead.SOURCE_MEASURED else INK3)
        for r in rows
    ]
    patterns = [
        "" if r["Source"] == paper_overhead.SOURCE_MEASURED else "/"
        for r in rows
    ]

    fig.add_trace(go.Bar(
        y=labels, x=values, orientation="h",
        marker=dict(color=colours, pattern=dict(shape=patterns, solidity=0.25)),
        text=[f" {v:.0f} KB" for v in values], textposition="outside",
        hovertemplate="%{y}: %{x:.1f} KB<extra></extra>",
        showlegend=False,
    ))
    fig.update_layout(title=dict(
        text="Hatched = reported in Table V.  Solid = our accounting.",
        font=dict(size=11, color=INK3), x=0))
    f = _base(fig, height=380, xtitle=f"bytes transmitted for n={n} (KB)")
    f.update_xaxes(range=[0, max(values) * 1.18])
    return f


# ---------------------------------------------------------------------------
# 6. Cost of autonomy - what leaving the TA in costs at realistic latency
# ---------------------------------------------------------------------------
def chart_end_to_end_vs_rtt(measured: pd.DataFrame, n: int = 60) -> go.Figure:
    """End-to-end authentication time against link RTT.

    The TUAV-side compute is flat; everything that rises is the link. That is
    the component the paper's Table III omits entirely.
    """
    fig = go.Figure()
    sub = measured[measured["n"] == n]
    if sub.empty:
        return _base(fig)

    tuav = float(sub[sub["phase"] == "GA (TUAV side)"]["ms"].iloc[0])
    ta = float(sub[sub["phase"] == "GA (TA side)"]["ms"].iloc[0])
    rtts = [0, 40, 100, 200, 300, 500, 700]

    fig.add_trace(go.Scatter(
        x=rtts, y=[tuav] * len(rtts), name="TUAV compute (flat)",
        mode="lines", line=dict(color=S1, width=3)))
    fig.add_trace(go.Scatter(
        x=rtts, y=[tuav + ta + r for r in rtts],
        name="End-to-end, as deployed", mode="lines+markers",
        line=dict(color=RED, width=3),
        marker=dict(size=8, line=dict(color="white", width=1.5))))
    fig.add_trace(go.Scatter(
        x=rtts, y=[paper_cost.cost("Proposed (paper)", "GA", n)] * len(rtts),
        name="Paper, reported", mode="lines",
        line=dict(color=INK3, width=2, dash="dash")))

    return _base(fig, height=400, logy=True,
                 xtitle=f"TA link round-trip time (ms), n={n}",
                 ytitle="milliseconds (log scale)")
