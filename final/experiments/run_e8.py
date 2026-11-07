"""E8: the first design against the hardened design with C4 containment.

    python experiments/run_e8.py            # full run
    python experiments/run_e8.py --quick    # small sizes, smoke test only; do not quote
Outputs: results/e8_*.csv, results/e8_macros.tex, figures/f7_containment.{pdf,png}

E8a  each flaw, executed against both designs
E8b  targeted lockout: can a victim get in while forged requests carry its pseudonym?
E8c  blast radius of captured TUAVs on a grid of cells, attacks executed on real objects
E8d  overhead of the fixes: handover, join with rekey, eviction certificates
"""
import csv
import math
import os
import random
import statistics as stats
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from cutcord import ec, hardened as hd, ours, sym       # noqa: E402
from cutcord.ec import P, mul, enc_point                # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT, FIG = os.path.join(ROOT, "results"), os.path.join(ROOT, "figures")
QUICK = "--quick" in sys.argv
NOW = 10_000
RNG = random.Random(2026)
MACROS = {}


class V1:
    TA, TUAV, Member = ours.TA, ours.TUAV, ours.Member
    hardened = False


class V2:
    TA, TUAV, Member = hd.HardenedTA, hd.HardenedTUAV, hd.HardenedMember
    hardened = True


def write(name, header, rows):
    with open(os.path.join(OUT, name), "w", newline="") as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)


def timed(fn, *a):
    t = time.perf_counter(); r = fn(*a); return r, (time.perf_counter() - t) * 1000


def log(*a):
    print(*a, flush=True)


def member(S, ta, role="join", epochs=1):
    if S.hardened:
        return S.Member(ta.register(os.urandom(16), epochs, role=role), ta.Ppub, role=role)
    return S.Member(ta.register(os.urandom(16), epochs), ta.Ppub, role=role)


def tuav(S, ta, name):
    return S.TUAV(name, ta.register_tuav(name), ta.Ppub)


def link(a, b):
    oa, ob = a.link_offer(NOW), b.link_offer(NOW)
    a.link_accept(ob, NOW); b.link_accept(oa, NOW)


def join(T, ms, now=NOW):
    b = T.beacon(now)
    acc, st = T.verify_window([m.request(b, 1, now) for m in ms], now, 1)
    acks = T.admit(acc, now)
    for m in ms:
        if "join" in acks:
            m.receive(acks["join"])
    return acc, st


def junk(c, i=0, now=NOW):
    return ours.Request(c.ident, c.ep, c.X, c.Y, mul(P, 7), now, mul(P, 9), 12345 + i)


def mint(A, B, ident, ep, X, Y, hk, now=NOW):
    body = (len(ident).to_bytes(2, "big") + ident + ep.to_bytes(4, "big") + enc_point(X) + enc_point(Y)
            + b"join" + hk + os.urandom(12) + (now + 30).to_bytes(8, "big"))
    return sym.seal(A.links[B.id], body, A.id + B.id)


def forged_handover(A, B, ident, ep, X, Y, e, hk, now=NOW):
    """the best a captured TUAV can send: it owns K_ab and hk, and it signs with its own key"""
    E = mul(P, e)
    tk = mint(A, B, ident, ep, X, Y, hk, now)
    msg = {"from": A.id, "ticket": tk, "E": E, "ts": now, "tau": sym.mac(hk, tk, enc_point(E), now.to_bytes(8, "big"))}
    msg["R"], msg["v"] = ours.sign(A.cred, hd.handover_msg(A.id, B.id, tk, E), now)
    return msg


# ---------------------------------------------------------------- E8a
def attack_a1(S):
    ta = S.TA(); T = tuav(S, ta, "A")
    m = member(S, ta); c = m.cred(1)
    T.beacon(NOW)
    T.verify_window([junk(c)], NOW, 1)                 # sent ahead of the victim, or in any earlier window
    b = T.beacon(NOW + 1)
    return T.verify_window([m.request(b, 1, NOW + 1)], NOW + 1, 1)[0] == []


def attack_a2(S):
    ta = S.TA(); A, B = tuav(S, ta, "A"), tuav(S, ta, "B"); link(A, B)
    e, hk, ident = ec.rand_scalar(), os.urandom(16), b"phantom" + b"U"
    resp, _ = B.accept_handover(forged_handover(A, B, ident, 1, mul(P, 3), mul(P, 5), e, hk), NOW)
    if resp is None:
        return False
    K2 = sym.kdf(enc_point(mul(resp["E"], e)), hk, ident, B.id)
    return sym.open_(K2, resp["blob"], enc_point(resp["E"]) + resp["ts"].to_bytes(8, "big"))[:16] == B.GK


def attack_a2b(S):
    ta = S.TA(); A, B = tuav(S, ta, "A"), tuav(S, ta, "B"); link(A, B)
    m = member(S, ta); join(B, [m]); c = m.cred(1)
    B.accept_handover(forged_handover(A, B, c.ident, 1, c.X, c.Y, ec.rand_scalar(), os.urandom(16)), NOW)
    return not m.receive_update(B.rekey([], NOW + 1))


def attack_a3(S):
    ta = S.TA(); A, B = tuav(S, ta, "A"), tuav(S, ta, "B"); link(A, B)
    m = member(S, ta); key = m.cred(1).key
    if S.hardened:
        b = A.beacon(NOW); r = m.request(b, 1, NOW)
        B.merge_evictions(A.id, [(A.id, A.E_a, r, junk(m.cred(1)))])
    else:
        B.merge_evictions(A.id, sym.seal(A.links[B.id], key, A.id))
    return key in B.evicted


def attack_a4(S):
    ta = S.TA(); T = tuav(S, ta, "A")
    creds = ta.register(os.urandom(16), 1, role="veh") if S.hardened else ta.register(os.urandom(16), 1)
    m = S.Member(creds, ta.Ppub, role="join")
    join(T, [m])
    return m.GK == T.GK


def attack_a5(S):
    ta = S.TA(); T = tuav(S, ta, "A")
    us = [member(S, ta) for _ in range(3)]; join(T, us)
    rk1 = T.rekey([], NOW + 1)
    for u in us:
        u.receive_update(rk1)
    us[0].receive_update(T.rekey([us[2].cred(1).key], NOW + 2))
    us[0].receive_update(rk1)
    return us[0].GK == us[2].GK


def attack_a6(S):
    ta = S.TA(); T = tuav(S, ta, "A")
    join(T, [member(S, ta)]); in_use = T.GK
    later = member(S, ta); join(T, [later], NOW + 1)
    return later.GK == in_use


def e8a():
    rows = []
    for name, fn in [("A1 one forged packet locks a UAV out", attack_a1),
                     ("A2 captured TUAV reads a neighbour's group key", attack_a2),
                     ("A2' captured TUAV displaces an honest member", attack_a2b),
                     ("A3 captured TUAV frames a member at a neighbour", attack_a3),
                     ("A4 vehicle credential obtains the UAV key", attack_a4),
                     ("A5 replayed rekey restores a key a removed member holds", attack_a5),
                     ("A6 joiner receives the key already in use", attack_a6)]:
        rows.append([name, fn(V1), fn(V2)])
        log("E8a", rows[-1])
    write("e8_attacks.csv", ["attack", "first_design_succeeds", "hardened_succeeds"], rows)
    MACROS["EAttacksVOne"] = sum(1 for r in rows if r[1])
    MACROS["EAttacksVTwo"] = sum(1 for r in rows if r[2])
    MACROS["EAttackTotal"] = len(rows)


# ---------------------------------------------------------------- E8b
def e8b():
    trials, windows = (20, 5) if QUICK else (200, 5)
    rows = []
    ta = V2.TA()
    T = tuav(V2, ta, "A")
    m = member(V2, ta); c = m.cred(1)
    for k in [0, 1, 2, 4, 8, 16, 32]:
        first, within = 0, 0
        for _ in range(trials):
            T.mode, T.clean = "batch", 0
            for w in range(windows):
                now = NOW + w
                b = T.beacon(now)
                m.pending = None; m._last_req = None
                reqs = [junk(c, i, now) for i in range(k)] + [m.request(b, 1, now)]
                RNG.shuffle(reqs)
                acc, _ = T.verify_window(reqs, now, 1)
                if acc:
                    first += w == 0
                    within += 1
                    break
        p = min(1.0, hd.PER_PID / (k + 1))
        rows.append([k, round(100 * first / trials, 1), round(100 * p, 1), round(100 * within / trials, 1),
                     round(100 * (1 - (1 - p) ** windows), 1), 0.0 if k else 100.0])
        log("E8b", rows[-1])
    write("e8_lockout.csv", ["junk_per_window", "hardened_first_window_pct", "predicted_first_pct",
                             "hardened_within5_pct", "predicted_within5_pct", "first_design_pct"], rows)
    MACROS["ELockTrials"] = trials
    by_k = {r[0]: r for r in rows}
    MACROS["ELockFourFirst"] = by_k[4][1]
    MACROS["ELockFourFive"] = by_k[4][3]
    MACROS["ELockThirtyTwoFive"] = by_k[32][3]

    # every pseudonym in a swarm spoofed once
    n = 20 if QUICK else 60
    swarm = []
    for S in (V1, V2):
        ta = S.TA(); T = tuav(S, ta, "A")
        ms = [member(S, ta) for _ in range(n)]
        ts, tc, got = [], [], 0
        for rep in range(1 if QUICK else 3):
            T.evicted.clear(); T.mode, T.clean = "batch", 0
            b = T.beacon(NOW)
            for mm in ms:
                mm.pending = None
                if S.hardened:
                    mm._last_req = None
            honest = [mm.request(b, 1, NOW) for mm in ms]
            tc.append(timed(T.verify_window, honest, NOW, 1)[1])
            T.mode, T.clean = "batch", 0
            reqs = [junk(mm.cred(1), 0) for mm in ms] + honest
            (acc, _), t = timed(T.verify_window, reqs, NOW, 1)
            ts.append(t); got = len(acc)
        swarm.append(["hardened" if S.hardened else "first", n, got, len(T.evicted), round(stats.median(tc), 1), round(stats.median(ts), 1)])
        log("E8b swarm", swarm[-1])
    write("e8_swarm.csv", ["design", "n", "admitted", "evicted", "clean_ms", "spoofed_ms"], swarm)
    MACROS["ESwarmN"] = n
    MACROS["ESwarmFirst"] = swarm[0][2]
    MACROS["ESwarmHard"] = swarm[1][2]
    MACROS["ESwarmEvictedFirst"] = swarm[0][3]
    MACROS["ESwarmCleanS"] = round(swarm[1][4] / 1000, 2)
    MACROS["ESwarmSpoofS"] = round(swarm[1][5] / 1000, 2)
    MACROS["ESwarmCostRatio"] = round(swarm[1][5] / swarm[1][4], 1)


# ---------------------------------------------------------------- E8c
def grid_world(S, g, per_cell):
    ta = S.TA()
    cells = {(i, j): tuav(S, ta, f"T{i}-{j}") for i in range(g) for j in range(g)}
    nbrs = {}
    for (i, j), a in cells.items():
        nbrs[(i, j)] = [(i + di, j + dj) for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)) if (i + di, j + dj) in cells]
        for p in nbrs[(i, j)]:
            if p > (i, j):
                link(a, cells[p])
    ms = {p: [member(S, ta) for _ in range(per_cell)] for p in cells}
    for p, T in cells.items():
        join(T, ms[p])
    return cells, nbrs, ms


def e8c():
    sizes, ks, trials = ([3], [1, 2], 5) if QUICK else ([3, 4, 5], [1, 2, 3], 30)
    per_cell = 3
    rows = []
    for g in sizes:
        for S in (V1, V2):
            cells, nbrs, ms = grid_world(S, g, per_cell)
            saved = {p: dict(T.members) for p, T in cells.items()}
            for k in ks:
                expo, disp, framed = [], [], []
                for _ in range(trials):
                    for p, T in cells.items():
                        T.members = dict(saved[p]); T.evicted.clear(); T.used_nonces.clear()
                        if S.hardened:
                            T.outbox.clear(); T._rekeyed.clear()
                    captured = RNG.sample(sorted(cells), k)
                    read = set(captured); d, f = set(), set()
                    for cp in captured:
                        A = cells[cp]
                        for np_ in nbrs[cp]:
                            if np_ in captured:
                                continue
                            B = cells[np_]
                            e, hk = ec.rand_scalar(), os.urandom(16)
                            resp, _ = B.accept_handover(forged_handover(A, B, os.urandom(80) + b"U", 1, mul(P, 3), mul(P, 5), e, hk), NOW)
                            if resp is not None:
                                read.add(np_)
                            victim = ms[np_][0].cred(1)
                            before = B.members[victim.key][0]
                            B.accept_handover(forged_handover(A, B, victim.ident, 1, victim.X, victim.Y, ec.rand_scalar(), os.urandom(16)), NOW)
                            if B.members[victim.key][0] != before:
                                d.add(victim.key)
                            target = ms[np_][1].cred(1).key
                            if S.hardened:
                                b = A.beacon(NOW); r = ms[np_][1].request(b, 1, NOW)
                                B.merge_evictions(A.id, [(A.id, A.E_a, r, junk(ms[np_][1].cred(1)))])
                                ms[np_][1].pending = None; ms[np_][1]._last_req = None
                            else:
                                B.merge_evictions(A.id, sym.seal(A.links[B.id], target, A.id))
                            if target in B.evicted:
                                f.add(target)
                    expo.append(100 * len(read) / len(cells)); disp.append(len(d)); framed.append(len(f))
                rows.append(["hardened" if S.hardened else "first", g * g, k, round(stats.mean(expo), 1),
                             round(stats.mean(disp), 2), round(stats.mean(framed), 2)])
                log("E8c", rows[-1])
    write("e8_blast.csv", ["design", "cells", "captured", "cells_exposed_pct", "members_displaced", "members_framed"], rows)
    largest = max(r[1] for r in rows)
    pick = {(r[0], r[2]): r for r in rows if r[1] == largest}
    MACROS["EBlastCells"] = largest
    MACROS["EBlastFirstOne"] = pick[("first", 1)][3]
    MACROS["EBlastHardOne"] = pick[("hardened", 1)][3]
    top = max(r[2] for r in rows)
    MACROS["EBlastCapMax"] = top
    MACROS["EBlastFirstMax"] = pick[("first", top)][3]
    MACROS["EBlastHardMax"] = pick[("hardened", top)][3]
    MACROS["EBlastDispFirst"] = pick[("first", top)][4]
    MACROS["EBlastFrameFirst"] = pick[("first", top)][5]
    MACROS["EBlastDispHard"] = pick[("hardened", top)][4]
    MACROS["EBlastFrameHard"] = pick[("hardened", top)][5]
    MACROS["EBlastTrials"] = trials


# ---------------------------------------------------------------- E8d
def e8d():
    reps = 5 if QUICK else 25
    cell = 10
    w1 = V1.TA(); a1, b1 = tuav(V1, w1, "A"), tuav(V1, w1, "B"); link(a1, b1)
    w2 = V2.TA(); a2, b2 = tuav(V2, w2, "A"), tuav(V2, w2, "B"); link(a2, b2)
    ms1 = [member(V1, w1) for _ in range(cell)]; join(b1, ms1)
    ms2 = [member(V2, w2) for _ in range(cell)]; join(b2, ms2)
    join(a2, [member(V2, w2) for _ in range(cell)])          # the old cell has members to rekey too
    base = {k: v for k, v in b2.members.items()}
    T1, M1, T2, M2, TF, MF, TD = [], [], [], [], [], [], []
    ops = {}
    for i in range(reps):
        now = NOW + 10 * (i + 1)
        # first design, ticket only
        m = member(V1, w1); b = a1.beacon(now); acc, _ = a1.verify_window([m.request(b, 1, now)], now, 1); m.receive(a1.admit(acc, now)["join"])
        m.take_ticket(a1.issue_ticket(m.cred(1).key, b1.id, now), b1.id)
        msg, t1 = timed(m.handover_request, a1.id, now + 1)
        ec.reset_counts(); (resp, why), t2 = timed(b1.accept_handover, msg, now + 1); ops["v1"] = dict(ec.COUNT)
        ok, t3 = timed(m.handover_finish, resp, b1.id); assert why == "ok" and ok
        T1.append(t2); M1.append(t1 + t3)
        b1.members.pop(m.cred(1).key)
        # hardened ticket
        m = member(V2, w2); b = a2.beacon(now); acc, _ = a2.verify_window([m.request(b, 1, now)], now, 1); m.receive(a2.admit(acc, now)["join"])
        k = m.cred(1).key
        m.take_ticket(a2.issue_ticket(k, b2.id, now), b2.id)
        msg, t1 = timed(m.handover_request, a2.id, b2.id, now + 1)
        ec.reset_counts(); (resp, why), t2 = timed(b2.accept_handover, msg, now + 1); ops["v2"] = dict(ec.COUNT)
        ok, t3 = timed(m.handover_finish, resp, b2.id); assert why == "ok" and ok
        T2.append(t2); M2.append(t1 + t3)
        _, t = timed(a2.depart, k, now + 1); TD.append(t)
        # hardened full re-admission at the same TUAV (beacon check, signature, verify, key, rekey)
        b2.members = dict(base); b2._rekeyed.clear()
        bb = b2.beacon(now + 2)
        m.pending = None; m._last_req = None
        req, t4 = timed(m.request, bb, 1, now + 2)
        (acc, _), t5 = timed(b2.verify_window, [req], now + 2, 1)
        acks, t6 = timed(b2.admit, acc, now + 2)
        _, t7 = timed(m.receive, acks["join"])
        TF.append(t5 + t6); MF.append(t4 + t7)
        b2.members = dict(base); b2._rekeyed.clear(); b2.mode, b2.clean = "batch", 0; b2.outbox.clear()
    med = lambda x: round(stats.median(x), 2)
    rows = [["new TUAV", med(T1), med(T2), med(TF)], ["member", med(M1), med(M2), med(MF)]]
    write("e8_handover.csv", ["side", "first_ticket_ms", "hardened_ticket_ms", "hardened_full_ms"], rows)
    log("E8d handover", rows, ops)
    entry, sig = ours.ENTRY, hd.HO_SIG_SIZE
    gap_first, gap_hard, gap_full = rows[0][1] + rows[1][1], rows[0][2] + rows[1][2], rows[0][3] + rows[1][3]
    MACROS.update(EHoCell=cell, EHoTuavFirst=rows[0][1], EHoTuavHard=rows[0][2], EHoTuavFull=rows[0][3],
                  EHoMemFirst=rows[1][1], EHoMemHard=rows[1][2], EHoMemFull=rows[1][3],
                  EHoGapFirst=round(gap_first), EHoGapHard=round(gap_hard), EHoGapFull=round(gap_full),
                  EHoGapFullWait=round(gap_full + 500), EHoSigBytes=sig, EHoRekeyBytes=entry * cell,
                  EHoDepart=med(TD), EHoOverhead=round(gap_hard / gap_first, 1))

    # join: half the cell present, half arriving, with and without the rekey
    n = 20 if QUICK else 60
    jr = []
    for S in (V1, V2):
        ta = S.TA(); T = tuav(S, ta, "A")
        old = [member(S, ta) for _ in range(n // 2)]; join(T, old)
        base_m = dict(T.members); nu0 = T.nu
        new = [member(S, ta) for _ in range(n // 2)]
        ts, bytes_ = [], 0
        for rep in range(1 if QUICK else 3):
            T.members = dict(base_m)
            if S.hardened:
                T.outbox.clear(); T._rekeyed.clear()
            now = NOW + 100 + rep
            b = T.beacon(now)
            for mm in new:
                mm.pending = None
                if S.hardened:
                    mm._last_req = None
            acc, _ = T.verify_window([mm.request(b, 1, now) for mm in new], now, 1)
            acks, t = timed(T.admit, acc, now)
            ts.append(t)
            bytes_ = len(acks["join"]["entries"]) * ours.ENTRY
            if S.hardened:
                bytes_ += sum(len(u["entries"]) for _, u in T.outbox) * ours.ENTRY
        jr.append(["hardened" if S.hardened else "first", n, round(stats.median(ts), 1), bytes_])
        log("E8d join", jr[-1])
    write("e8_join.csv", ["design", "n", "key_delivery_ms", "key_bytes"], jr)
    MACROS.update(EJoinN=n, EJoinFirstMs=jr[0][2], EJoinHardMs=jr[1][2], EJoinFirstB=jr[0][3], EJoinHardB=jr[1][3])

    # eviction certificates
    ta = V2.TA()
    voters = [tuav(V2, ta, f"T{i}") for i in range(9)]
    target = b"captured"
    cert = []
    for t in [2, 3, 5, 7, 9]:
        votes = [v.vote(target, NOW) for v in voters[:t]]
        ts = [timed(hd.cert_ok, ta.Ppub, target, votes, t)[1] for _ in range(3 if QUICK else 15)]
        ec.reset_counts(); assert hd.cert_ok(ta.Ppub, target, votes, t)
        cert.append([t, t * hd.VOTE_SIZE, med(ts), ec.COUNT["mul"], ec.COUNT["small_mul"]])
        log("E8d cert", cert[-1])
    write("e8_cert.csv", ["t", "bytes", "verify_ms", "mul", "small_mul"], cert)
    MACROS.update(ECertTwoB=cert[0][1], ECertTwoMs=cert[0][2], ECertFiveB=cert[2][1], ECertFiveMs=cert[2][2], EVoteB=hd.VOTE_SIZE)


# ---------------------------------------------------------------- figure and macros
def figure():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    OURS, BASE, CTX, INK, MUTED = "#00889E", "#C81D25", "#9AA3AA", "#1F2933", "#5B6770"
    plt.rcParams.update({"font.family": "serif", "font.size": 9, "axes.titlesize": 9, "axes.labelsize": 9, "legend.fontsize": 8,
                         "xtick.labelsize": 8, "ytick.labelsize": 8, "axes.edgecolor": "#B8C0C6", "axes.labelcolor": INK,
                         "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True, "grid.color": "#E6EAED", "grid.linewidth": 0.6,
                         "axes.spines.top": False, "axes.spines.right": False, "lines.linewidth": 2, "lines.markersize": 5,
                         "legend.frameon": False, "savefig.bbox": "tight", "savefig.dpi": 200})
    with open(os.path.join(OUT, "e8_blast.csv")) as f:
        blast = list(csv.DictReader(f))
    with open(os.path.join(OUT, "e8_lockout.csv")) as f:
        lock = list(csv.DictReader(f))
    largest = max(int(r["cells"]) for r in blast)
    fig, (ax, ay) = plt.subplots(1, 2, figsize=(7.0, 2.4))
    rows = [r for r in blast if int(r["cells"]) == largest]
    ks = sorted({int(r["captured"]) for r in rows})
    for name, col, label, off, hatch in (("first", BASE, "First design", -0.18, None), ("hardened", OURS, "Hardened", 0.18, "//")):
        ys = [next(float(r["cells_exposed_pct"]) for r in rows if r["design"] == name and int(r["captured"]) == k) for k in ks]
        bars = ax.bar([k + off for k in ks], ys, 0.32, color=col, label=label, hatch=hatch, edgecolor="white", linewidth=0.8)
        for b_, y in zip(bars, ys):
            ax.text(b_.get_x() + b_.get_width() / 2, y + 1, f"{y:.0f}%", ha="center", va="bottom", fontsize=7.5, color=INK)
    ax.set_xticks(ks); ax.set_xlabel("TUAVs captured"); ax.set_ylabel("Group keys exposed (% of cells)"); ax.set_axisbelow(True)
    ax.set_title(f"Blast radius, {largest}-cell grid", loc="left"); ax.grid(axis="x", visible=False); ax.legend(loc="upper left")
    ax.set_ylim(0, max(float(r["cells_exposed_pct"]) for r in rows) * 1.28)
    xs = [int(r["junk_per_window"]) for r in lock]
    pos = [max(x, 0.5) for x in xs]
    ay.plot(pos, [float(r["predicted_within5_pct"]) for r in lock], color=CTX, linewidth=1.2, linestyle="--", label="Hardened, predicted")
    ay.plot(pos, [float(r["hardened_within5_pct"]) for r in lock], color=OURS, marker="o", label="Hardened, measured")
    ay.plot(pos, [float(r["first_design_pct"]) for r in lock], color=BASE, marker="s", label="First design")
    ay.set_xscale("log", base=2); ay.set_xticks(pos); ay.set_xticklabels([str(x) for x in xs]); ay.minorticks_off()
    ay.set_xlabel("Forged requests per window naming the victim"); ay.set_ylabel("Admitted within 5 windows (%)")
    ay.set_title("Targeted lockout", loc="left"); ay.set_ylim(-4, 108); ay.legend(loc="center", bbox_to_anchor=(0.42, 0.3))
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(FIG, f"f7_containment.{ext}"))


def write_macros():
    with open(os.path.join(OUT, "e8_macros.tex"), "w") as f:
        f.write("% generated by experiments/run_e8.py -- do not edit\n")
        for k, v in MACROS.items():
            f.write(f"\\newcommand{{\\{k}}}{{{v}}}\n")


if __name__ == "__main__":
    t0 = time.time()
    e8a(); e8b(); e8c(); e8d()
    figure(); write_macros()
    log("done in", round(time.time() - t0), "s")
