"""
Vector icons for the topology diagram.

Drawn as Plotly shapes rather than emoji or bitmaps, because:

  * emoji render differently on every machine and often fall back to
    black-and-white boxes on a projector;
  * vector shapes scale cleanly and their colours can be driven by live
    simulation state, which is the whole point of this diagram.

Every helper appends to a `shapes` list and returns it, so a caller can build
the whole figure and hand the list to `fig.update_layout(shapes=...)` once.

Coordinates are in data space. `s` is a size multiplier: 1.0 is roughly a
0.6-unit-wide icon.
"""

from __future__ import annotations

# ---------------------------------------------------------------- palette --
DRONE_BODY = "#4A5A6A"
DRONE_ROTOR = "#8A98A6"
TRUCK_RED = "#D6453D"
TRUCK_DARK = "#8E2B26"
SAT_BODY = "#6E89A8"
SAT_PANEL = "#3E5C7E"
TOWER = "#C0392B"
BUILDING = "#4A7FB5"
BUILDING_DARK = "#2F5B85"
WHEEL = "#2B3440"
GLASS = "#BFD8EE"

CAR_COLOURS = ["#F2B233", "#4A7FB5", "#D6453D", "#5FAE72", "#E8EDF2", "#9B7BC7"]


def _circle(shapes, cx, cy, r, fill, line=None, width=1.0, layer="above"):
    shapes.append(dict(
        type="circle", x0=cx - r, x1=cx + r, y0=cy - r, y1=cy + r,
        fillcolor=fill, line=dict(color=line or fill, width=width),
        layer=layer))
    return shapes


def _rect(shapes, x0, y0, x1, y1, fill, line=None, width=1.0, layer="above"):
    shapes.append(dict(
        type="rect", x0=x0, y0=y0, x1=x1, y1=y1, fillcolor=fill,
        line=dict(color=line or fill, width=width), layer=layer))
    return shapes


def _line(shapes, x0, y0, x1, y1, colour, width=1.5, dash=None, layer="above"):
    shapes.append(dict(
        type="line", x0=x0, y0=y0, x1=x1, y1=y1,
        line=dict(color=colour, width=width, dash=dash) if dash
        else dict(color=colour, width=width), layer=layer))
    return shapes


def _path(shapes, d, fill, line=None, width=1.0, layer="above"):
    shapes.append(dict(
        type="path", path=d, fillcolor=fill,
        line=dict(color=line or fill, width=width), layer=layer))
    return shapes


# ------------------------------------------------------------------ drone --
def drone(shapes, cx, cy, s=1.0, body=DRONE_BODY, rotor=DRONE_ROTOR):
    """A quadcopter seen from a three-quarter angle: four rotors and a body."""
    arm_x, arm_y = 0.30 * s, 0.17 * s
    for dx, dy in ((-1, 1), (1, 1), (-1, -1), (1, -1)):
        ex, ey = cx + dx * arm_x, cy + dy * arm_y
        _line(shapes, cx, cy, ex, ey, body, width=2.2 * s)
        # rotor disc
        shapes.append(dict(
            type="circle", x0=ex - 0.13 * s, x1=ex + 0.13 * s,
            y0=ey - 0.045 * s, y1=ey + 0.045 * s,
            fillcolor=rotor, line=dict(color=body, width=1.1), layer="above"))
    # fuselage
    shapes.append(dict(
        type="circle", x0=cx - 0.13 * s, x1=cx + 0.13 * s,
        y0=cy - 0.085 * s, y1=cy + 0.085 * s,
        fillcolor=body, line=dict(color=body, width=1), layer="above"))
    return shapes


def tethered_drone(shapes, cx, cy, s=1.0, body=DRONE_BODY, rotor=DRONE_ROTOR,
                   cable="#C97A1E"):
    """A larger quadcopter with a cable running down from it."""
    drone(shapes, cx, cy, s=s, body=body, rotor=rotor)
    _line(shapes, cx, cy - 0.09 * s, cx, cy - 0.85 * s, cable, width=3.2)
    return shapes


# ------------------------------------------------------------- fire truck --
def truck(shapes, cx, cy, s=1.0):
    """The ECRV, drawn as an emergency response vehicle."""
    w, h = 0.95 * s, 0.30 * s
    # body
    _rect(shapes, cx - w, cy - h * 0.2, cx + w * 0.30, cy + h,
          TRUCK_RED, TRUCK_DARK, 1.2)
    # cab
    _rect(shapes, cx + w * 0.30, cy - h * 0.2, cx + w, cy + h * 0.72,
          TRUCK_RED, TRUCK_DARK, 1.2)
    # windscreen
    _rect(shapes, cx + w * 0.46, cy + h * 0.16, cx + w * 0.88, cy + h * 0.62,
          GLASS, TRUCK_DARK, 0.8)
    # ladder
    _line(shapes, cx - w * 0.88, cy + h * 1.06, cx + w * 0.12, cy + h * 1.30,
          "#C9CFD6", width=2.6)
    # light bar
    _rect(shapes, cx + w * 0.44, cy + h * 0.74, cx + w * 0.80, cy + h * 0.92,
          "#3D7BD6", "#25518F", 0.7)
    # wheels
    _circle(shapes, cx - w * 0.60, cy - h * 0.26, 0.10 * s, WHEEL)
    _circle(shapes, cx + w * 0.62, cy - h * 0.26, 0.10 * s, WHEEL)
    return shapes


# --------------------------------------------------------------- vehicles --
def car(shapes, cx, cy, s=1.0, colour="#4A7FB5"):
    """A generic saloon."""
    w, h = 0.44 * s, 0.13 * s
    _path(shapes,
          f"M {cx-w},{cy} L {cx-w*0.82},{cy+h} L {cx+w*0.82},{cy+h} "
          f"L {cx+w},{cy} Z", colour, WHEEL, 0.9)
    _path(shapes,
          f"M {cx-w*0.50},{cy+h} L {cx-w*0.30},{cy+h*2.05} "
          f"L {cx+w*0.34},{cy+h*2.05} L {cx+w*0.52},{cy+h} Z",
          GLASS, WHEEL, 0.9)
    _circle(shapes, cx - w * 0.52, cy - 0.015 * s, 0.075 * s, WHEEL)
    _circle(shapes, cx + w * 0.52, cy - 0.015 * s, 0.075 * s, WHEEL)
    return shapes


def bus(shapes, cx, cy, s=1.0, colour="#F2B233"):
    """A school bus, for variety in the vehicular zone."""
    w, h = 0.56 * s, 0.22 * s
    _rect(shapes, cx - w, cy, cx + w, cy + h, colour, "#9A6F12", 1.0)
    for i in range(4):
        x0 = cx - w * 0.82 + i * (w * 0.42)
        _rect(shapes, x0, cy + h * 0.42, x0 + w * 0.26, cy + h * 0.84,
              GLASS, "#9A6F12", 0.6)
    _circle(shapes, cx - w * 0.56, cy - 0.012 * s, 0.078 * s, WHEEL)
    _circle(shapes, cx + w * 0.56, cy - 0.012 * s, 0.078 * s, WHEEL)
    return shapes


# -------------------------------------------------------------- satellite --
def satellite(shapes, cx, cy, s=1.0):
    """Body plus two solar panels."""
    bw, bh = 0.12 * s, 0.11 * s
    _rect(shapes, cx - bw, cy - bh, cx + bw, cy + bh, SAT_BODY, SAT_PANEL, 1.0)
    for sign in (-1, 1):
        _rect(shapes, cx + sign * bw, cy - bh * 0.62,
              cx + sign * (bw + 0.26 * s), cy + bh * 0.62,
              SAT_PANEL, SAT_PANEL, 0.8)
    _line(shapes, cx, cy + bh, cx, cy + bh + 0.10 * s, SAT_PANEL, width=1.4)
    return shapes


# ------------------------------------------------------------------ tower --
def tower(shapes, cx, cy, s=1.0, colour=TOWER):
    """A roadside unit mast."""
    h, w = 0.62 * s, 0.17 * s
    _path(shapes, f"M {cx-w},{cy} L {cx-w*0.34},{cy+h} "
                  f"L {cx+w*0.34},{cy+h} L {cx+w},{cy} Z",
          "rgba(0,0,0,0)", colour, 1.8)
    for yy in (0.22, 0.42, 0.62):
        half = w * (1 - yy * 0.9)
        _line(shapes, cx - half, cy + h * yy, cx + half, cy + h * yy,
              colour, width=1.1)
    _circle(shapes, cx, cy + h + 0.06 * s, 0.05 * s, colour)
    return shapes


# -------------------------------------------------------------- buildings --
def buildings(shapes, cx, cy, s=1.0):
    """The trusted authority, drawn as a small data-centre skyline."""
    specs = [(-0.52, 0.46, "#5C8FC4"), (-0.05, 0.72, BUILDING),
             (0.42, 0.55, BUILDING_DARK)]
    for dx, h, col in specs:
        x0, x1 = cx + (dx - 0.19) * s, cx + (dx + 0.19) * s
        _rect(shapes, x0, cy, x1, cy + h * s, col, "#24456A", 1.0)
        rows = 3 if h > 0.6 else 2
        for r in range(rows):
            for c in range(2):
                wx0 = x0 + (0.055 + c * 0.17) * s
                wy0 = cy + (0.10 + r * 0.19) * s
                _rect(shapes, wx0, wy0, wx0 + 0.10 * s, wy0 + 0.10 * s,
                      GLASS, GLASS, 0.4)
    return shapes


# ------------------------------------------------------------------ cloud --
def cloud(shapes, cx, cy, w=1.0, h=0.5, fill="#DCEAF6", line="#A9C6E2"):
    """A soft rounded backdrop, as in the paper's figure."""
    for dx, r in ((-0.34, 0.30), (0.0, 0.40), (0.34, 0.30)):
        shapes.append(dict(
            type="circle",
            x0=cx + (dx - r) * w, x1=cx + (dx + r) * w,
            y0=cy - r * h * 1.5, y1=cy + r * h * 1.5,
            fillcolor=fill, line=dict(color=line, width=1.2), layer="below"))
    _rect(shapes, cx - 0.42 * w, cy - 0.34 * h, cx + 0.42 * w, cy + 0.34 * h,
          fill, fill, 0, layer="below")
    return shapes


# ------------------------------------------------------------------- zone --
def zone(shapes, x0, y0, x1, y1, fill="rgba(246,248,250,0.85)",
         line="#B6C0CA", dash="dash"):
    """A dashed region box, as the paper uses for its four sub-networks."""
    shapes.append(dict(
        type="rect", x0=x0, y0=y0, x1=x1, y1=y1, fillcolor=fill,
        line=dict(color=line, width=1.4, dash=dash), layer="below"))
    return shapes


# ------------------------------------------------------------------ links --
def bolt(shapes, x0, y0, x1, y1, colour="#5FAE72", width=1.8):
    """A zig-zag wireless link, in the style of the paper's figure."""
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    dx, dy = x1 - x0, y1 - y0
    # perpendicular offset, scaled to the link length
    nx, ny = -dy, dx
    norm = max((nx * nx + ny * ny) ** 0.5, 1e-9)
    off = 0.055
    nx, ny = nx / norm * off, ny / norm * off
    _line(shapes, x0, y0, mx + nx, my + ny, colour, width)
    _line(shapes, mx + nx, my + ny, mx - nx, my - ny, colour, width)
    _line(shapes, mx - nx, my - ny, x1, y1, colour, width)
    return shapes
