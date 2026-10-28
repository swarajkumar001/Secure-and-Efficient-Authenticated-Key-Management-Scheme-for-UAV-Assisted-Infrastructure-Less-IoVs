"""Figures for the final report and paper, drawn from results/*.csv.

Palette validated with the dataviz checker (light surface): ours #00889E, base #C81D25,
third #6A4C93, fourth #C96A12; context series in grey with direct labels.
    python experiments/make_figures.py
"""
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                        # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
RES, FIG = os.path.join(ROOT, "results"), os.path.join(ROOT, "figures")
os.makedirs(FIG, exist_ok=True)
OURS, BASE, THIRD, FOURTH, CTX, INK, MUTED = "#00889E", "#C81D25", "#6A4C93", "#C96A12", "#9AA3AA", "#1F2933", "#5B6770"

plt.rcParams.update({
    "font.family": "serif", "font.size": 9, "axes.titlesize": 9, "axes.labelsize": 9, "legend.fontsize": 8,
    "xtick.labelsize": 8, "ytick.labelsize": 8, "axes.edgecolor": "#B8C0C6", "axes.labelcolor": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True, "grid.color": "#E6EAED", "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False, "lines.linewidth": 2, "lines.markersize": 5,
    "legend.frameon": False, "savefig.bbox": "tight", "savefig.dpi": 200})


def load(name):
    with open(os.path.join(RES, name)) as f:
        rows = list(csv.DictReader(f))
    def conv(v):
        try:
            return float(v)
        except ValueError:
            return v
    return [{k: conv(v) for k, v in r.items()} for r in rows]


def save(fig, name):
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(FIG, f"{name}.{ext}"))
    plt.close(fig)


def label_end(ax, x, y, text, color, dy=0):
    ax.annotate(text, (x, y), xytext=(4, dy), textcoords="offset points", color=color, fontsize=8, va="center")


# ---------------------------------------------------------------- F1 availability
def f1():
    rows = load("e1_availability.csv")
    fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.4), sharey=True)
    for ax, model, title in zip(axes, ("iid", "bursty"), ("independent link losses", "bursty outages (Gilbert-Elliott)")):
        r = sorted([x for x in rows if x["model"] == model], key=lambda x: x["A"])
        A = [100 * x["A"] for x in r]
        ax.plot(A, [x["ours_pct"] for x in r], color=OURS, marker="o", label="Ours")
        ax.plot(A, [x["base_three_attempts_pct"] for x in r], color=FOURTH, marker="s", ls="--", label="Base, up to 3 attempts")
        ax.plot(A, [x["base_one_attempt_pct"] for x in r], color=BASE, marker="^", label="Base, one attempt")
        ax.set_title(title, color=INK); ax.set_xlabel("TA-link availability A (%)"); ax.invert_xaxis()
        ax.set_ylim(-3, 105)
    axes[0].set_ylabel("rounds authenticated (%)")
    axes[0].legend(loc="lower left")
    save(fig, "f1_availability")


# ---------------------------------------------------------------- F2 measured latency
def f2():
    r = load("e2_latency.csv")
    n = [x["n"] for x in r]
    fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.5))
    ax = axes[0]
    ax.plot(n, [x["base_total_ms"] / 1000 for x in r], color=BASE, marker="^", label="Base: TA (pairings) + TUAV + GD")
    ax.plot(n, [x["base_TUAV_ms"] / 1000 for x in r], color=BASE, marker="^", ls=":", label="Base: TUAV side only (as reported)")
    ax.plot(n, [x["ours_total_ms"] / 1000 for x in r], color=OURS, marker="o", label="Ours: verification + key delivery")
    ax.set_yscale("log"); ax.set_xlabel("number of UAVs n"); ax.set_ylabel("measured time (s, log scale)")
    ax.set_title("measured", color=INK); ax.legend(loc="center right", fontsize=7)
    ax = axes[1]
    ax.plot(n, [x["base_TA_est_ms"] / 1000 for x in r], color=BASE, marker="^", label="Base TA (ops x median)")
    ax.plot(n, [x["ours_est_ms"] / 1000 for x in r], color=OURS, marker="o", label="Ours (ops x median)")
    ax.set_yscale("log"); ax.set_xlabel("number of UAVs n"); ax.set_title("operation counts x primitive cost", color=INK)
    ax.legend(loc="center right", fontsize=7)
    save(fig, "f2_latency")


# ---------------------------------------------------------------- F3 poisoning
def f3():
    r = load("e3_poisoning.csv")
    pct = [x["bad_pct"] for x in r]
    fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.4))
    ax = axes[0]
    ax.plot(pct, [x["ours_goodput_pct"] for x in r], color=OURS, marker="o", label="Ours")
    ax.plot(pct, [x["base_goodput_pct"] for x in r], color=BASE, marker="^", label="Base")
    ax.set_xlabel("invalid requests in the window (%)"); ax.set_ylabel("honest UAVs admitted (%)"); ax.set_ylim(-5, 105)
    ax.legend(loc="center right"); ax.set_title("goodput", color=INK)
    ax = axes[1]
    ax.plot(pct, [x["ours_fallback_ms"] / 1000 for x in r], color=OURS, marker="o", label="Ours: batch, then individual")
    ax.plot(pct, [x["split_retest_ms"] / 1000 for x in r], color=THIRD, marker="s", ls="--", label="Split-and-retest")
    ax.plot(pct, [x["individual_ms"] / 1000 for x in r], color=CTX, marker="d", ls=":", label="Individual only")
    ax.set_xlabel("invalid requests in the window (%)"); ax.set_ylabel("verification time (s)")
    ax.legend(loc="lower right", fontsize=7); ax.set_title("cost of handling a failed batch", color=INK)
    save(fig, "f3_poisoning")


# ---------------------------------------------------------------- F4 bytes
def f4():
    r = load("e4_bytes.csv")
    n = [x["n"] for x in r]
    fig, ax = plt.subplots(figsize=(3.3, 2.5))
    ax.plot(n, [x["base_acks_total_B"] for x in r], color=BASE, marker="^", label="Base: CRT ACKs to all n")
    ax.plot(n, [x["base_satellite_B"] for x in r], color=FOURTH, marker="s", ls="--", label="Base: satellite traffic")
    ax.plot(n, [x["ours_ack_B"] for x in r], color=OURS, marker="o", label="Ours: one ACK")
    ax.set_yscale("log"); ax.set_xlabel("number of UAVs n"); ax.set_ylabel("bytes (log scale)")
    ax.legend(loc="upper left", fontsize=7)
    save(fig, "f4_bytes")


# ---------------------------------------------------------------- F5 vehicles
def f5():
    r = load("e5_vehicles.csv")
    m = [x["vehicles"] for x in r]
    fig, ax = plt.subplots(figsize=(3.3, 2.5))
    ax.plot(m, [x["individual_verify_ms"] / 1000 for x in r], color=CTX, marker="d", ls=":", label="Verify each vehicle")
    ax.plot(m, [x["batch_admit_ms"] / 1000 for x in r], color=OURS, marker="o", label="C2 bundle: batch + keys")
    ax.set_xlabel("vehicles in one bundle"); ax.set_ylabel("TUAV time (s)"); ax.legend(loc="upper left")
    save(fig, "f5_vehicles")


# ---------------------------------------------------------------- F6 handover
def f6():
    r = load("e6_handover.csv")
    fig, ax = plt.subplots(figsize=(3.3, 2.3))
    labels = [x["side"] for x in r]
    y = range(len(r))
    ax.barh([i + 0.2 for i in y], [x["full_readmission_ms"] for x in r], height=0.36, color=CTX, label="Full re-admission")
    ax.barh([i - 0.2 for i in y], [x["ticket_handover_ms"] for x in r], height=0.36, color=OURS, label="C3 ticket")
    for i, x in enumerate(r):
        ax.annotate(f"{x['full_readmission_ms']:.0f} ms", (x["full_readmission_ms"], i + 0.2), xytext=(3, 0), textcoords="offset points", va="center", fontsize=7, color=INK)
        ax.annotate(f"{x['ticket_handover_ms']:.0f} ms", (x["ticket_handover_ms"], i - 0.2), xytext=(3, 0), textcoords="offset points", va="center", fontsize=7, color=INK)
    ax.set_yticks(list(y)); ax.set_yticklabels(labels); ax.set_xlabel("computation (ms, measured)")
    ax.grid(axis="y", visible=False); ax.legend(loc="lower right", fontsize=7)
    ax.set_xlim(0, max(x["full_readmission_ms"] for x in r) * 1.3)
    save(fig, "f6_handover")


if __name__ == "__main__":
    for f in (f1, f2, f3, f4, f5, f6):
        try:
            f(); print("ok", f.__name__)
        except FileNotFoundError as e:
            print("skip", f.__name__, e)
