"""
Geometric node vocabulary for the system-architecture figure.

Academic figure style: rectangles, rounded rectangles, circles and ovals with
thin borders and pale fills. No pictorial objects, no decoration. The
connections and the information hierarchy are what the reader should see.

Every helper appends to a `shapes` list and returns it, so the caller builds
the whole figure and hands the list to `fig.update_layout(shapes=...)` once.
Text is added separately as annotations, because Plotly shapes carry no label.
"""

from __future__ import annotations

# ----------------------------------------------------------------- palette --
LINE = "#2B3440"          # node borders
LINE_SOFT = "#7D8894"     # secondary borders, connectors
ZONE_LINE = "#9AA5B1"     # dashed container borders
TEXT = "#15191F"
TEXT_SOFT = "#5A6672"
WHITE = "#FFFFFF"

ZONE_FILLS = {
    "neutral": "rgba(246,248,250,0.9)",
    "amber": "rgba(252,246,236,0.9)",
    "red": "rgba(252,238,236,0.9)",
    "blue": "rgba(240,246,252,0.9)",
}
ZONE_LINES = {
    "neutral": ZONE_LINE,
    "amber": "#D3AC7C",
    "red": "#D8A49F",
    "blue": "#A9BFD6",
}


def rect(shapes, cx, cy, w, h, *, fill=WHITE, line=LINE, width=1.2,
         dash=None, layer="above"):
    """A plain rectangle, centred on (cx, cy)."""
    d = dict(type="rect", x0=cx - w / 2, x1=cx + w / 2,
             y0=cy - h / 2, y1=cy + h / 2, fillcolor=fill, layer=layer,
             line=dict(color=line, width=width))
    if dash:
        d["line"]["dash"] = dash
    shapes.append(d)
    return shapes


def rounded(shapes, cx, cy, w, h, *, r=None, fill=WHITE, line=LINE,
            width=1.2, dash=None, layer="above"):
    """A rounded rectangle, drawn as an SVG path.

    Plotly has no rounded-rect shape type, so the corners are quarter arcs.
    """
    r = r if r is not None else min(w, h) * 0.26
    x0, x1 = cx - w / 2, cx + w / 2
    y0, y1 = cy - h / 2, cy + h / 2
    p = (f"M {x0 + r},{y0} "
         f"L {x1 - r},{y0} Q {x1},{y0} {x1},{y0 + r} "
         f"L {x1},{y1 - r} Q {x1},{y1} {x1 - r},{y1} "
         f"L {x0 + r},{y1} Q {x0},{y1} {x0},{y1 - r} "
         f"L {x0},{y0 + r} Q {x0},{y0} {x0 + r},{y0} Z")
    d = dict(type="path", path=p, fillcolor=fill, layer=layer,
             line=dict(color=line, width=width))
    if dash:
        d["line"]["dash"] = dash
    shapes.append(d)
    return shapes


def ellipse(shapes, cx, cy, w, h, *, fill=WHITE, line=LINE, width=1.2,
            dash=None, layer="above"):
    d = dict(type="circle", x0=cx - w / 2, x1=cx + w / 2,
             y0=cy - h / 2, y1=cy + h / 2, fillcolor=fill, layer=layer,
             line=dict(color=line, width=width))
    if dash:
        d["line"]["dash"] = dash
    shapes.append(d)
    return shapes


def connector(shapes, x0, y0, x1, y1, *, colour=LINE_SOFT, width=1.1,
              dash=None, layer="below"):
    """A plain connecting line. Use `arrow()` for directed edges."""
    d = dict(type="line", x0=x0, y0=y0, x1=x1, y1=y1, layer=layer,
             line=dict(color=colour, width=width))
    if dash:
        d["line"]["dash"] = dash
    shapes.append(d)
    return shapes


def cross_out(shapes, cx, cy, w, h, *, colour="#97302F", width=1.6):
    """Two diagonals through a node, for a dysfunctional component."""
    connector(shapes, cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2,
              colour=colour, width=width, layer="above")
    connector(shapes, cx - w / 2, cy + h / 2, cx + w / 2, cy - h / 2,
              colour=colour, width=width, layer="above")
    return shapes


def zone(shapes, x0, y0, x1, y1, *, tone="neutral"):
    """A dashed container for one sub-network."""
    shapes.append(dict(
        type="rect", x0=x0, y0=y0, x1=x1, y1=y1,
        fillcolor=ZONE_FILLS.get(tone, ZONE_FILLS["neutral"]),
        line=dict(color=ZONE_LINES.get(tone, ZONE_LINE), width=1.3,
                  dash="dash"),
        layer="below"))
    return shapes


# ------------------------------------------------------------- annotations --
def label(cx, cy, text, *, size=10.5, colour=TEXT, bold=False,
          anchor="center", yanchor="middle"):
    """Build an annotation dict for a node label."""
    return dict(x=cx, y=cy, showarrow=False, xanchor=anchor,
                yanchor=yanchor, align="center",
                text=f"<b>{text}</b>" if bold else text,
                font=dict(size=size, color=colour))


def arrow(x0, y0, x1, y1, *, colour=LINE_SOFT, width=1.4, head=2,
          both=False, dash=None):
    """Build annotation dict(s) for a directed edge.

    Returns a list, because a two-headed arrow needs two annotations.
    """
    out = [dict(x=x1, y=y1, ax=x0, ay=y0, xref="x", yref="y",
                axref="x", ayref="y", showarrow=True, text="",
                arrowhead=head, arrowsize=1.1, arrowwidth=width,
                arrowcolor=colour)]
    if both:
        out.append(dict(x=x0, y=y0, ax=x1, ay=y1, xref="x", yref="y",
                        axref="x", ayref="y", showarrow=True, text="",
                        arrowhead=head, arrowsize=1.1, arrowwidth=width,
                        arrowcolor=colour))
    return out
