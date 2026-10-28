"""Measured evaluation E0-E7 for the final report and paper.

Both schemes run on the same curve (BN254, py_ecc, pure Python) on the same machine, so
measured times are comparable *with each other*; absolute values are slower than an
optimised C library. Network delays (satellite RTT) are added as stated parameters.

    python experiments/run_all.py            # full run (~10-15 min)
    python experiments/run_all.py --quick    # small n, for a smoke test
Outputs: results/*.csv, results/summary.json
"""
import csv
import json
import os
import platform
import random
import statistics as stats
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from cutcord import base, ec, ours, sym                      # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "results")
os.makedirs(OUT, exist_ok=True)
QUICK = "--quick" in sys.argv
NOW = 10_000
RNG = random.Random(2026)
SUMMARY = {"machine": {"python": platform.python_version(), "cpu": platform.processor(), "os": platform.platform()}}


def write(name, header, rows):
    with open(os.path.join(OUT, name), "w", newline="") as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)


def timed(fn, *a):
    t = time.perf_counter(); r = fn(*a); return r, (time.perf_counter() - t) * 1000


def log(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------- E0 micro-benchmarks
def e0():
    import hashlib
    from py_ecc import optimized_bn128 as bn
    reps = 5 if QUICK else 60
    k = lambda: ec.rand_scalar()
    A = bn.multiply(bn.G1, k())
    g = bn.pairing(bn.G2, bn.G1)
    key = os.urandom(16)
    ops = {
        "G1 scalar multiplication": lambda: bn.multiply(bn.G1, k()),
        "G1 small (64-bit) multiplication": lambda: bn.multiply(A, random.getrandbits(64)),
        "G1 point addition": lambda: bn.add(A, bn.G1),
        "G2 scalar multiplication": lambda: bn.multiply(bn.G2, k()),
        "bilinear pairing": lambda: bn.pairing(bn.G2, A),
        "GT exponentiation": lambda: g ** k(),
        "SHA-256 hash": lambda: hashlib.sha256(b"x" * 64).digest(),
        "HKDF-SHA256": lambda: sym.kdf(b"x" * 64),
        "AES-128-GCM seal (20 B)": lambda: sym.seal(key, b"x" * 20),
    }
    rows = {}
    for name, fn in ops.items():
        n = max(2, reps // 6) if name in ("bilinear pairing", "GT exponentiation", "G2 scalar multiplication") else reps
        ts = [timed(fn)[1] for _ in range(n)]
        rows[name] = (stats.median(ts), n)
        log(f"E0 {name:34s} {rows[name][0]:9.4f} ms")
    write("e0_micro.csv", ["operation", "median_ms", "reps"], [[k, round(v[0], 4), v[1]] for k, v in rows.items()])
    SUMMARY["E0"] = {k: round(v[0], 4) for k, v in rows.items()}
    return rows


# ---------------------------------------------------------------- shared setups
def ours_world(n, epochs=2):
    ta = ours.TA()
    T = ours.TUAV("TUAV-A", ta.register_tuav("TUAV-A"), ta.Ppub)
    ms = [ours.Member(ta.register(os.urandom(16), epochs), ta.Ppub) for _ in range(n)]
    return ta, T, ms


def ours_round(T, ms, ep=1, now=NOW, corrupt=0):
    b = T.beacon(now)
    reqs = [m.request(b, ep, now) for m in ms]
    for r in reqs[:corrupt]:
        r.v = (r.v + 1) % ec.q
    ec.reset_counts()
    (acc, st), t_ver = timed(T.verify_window, reqs, now, ep)
    acks, t_key = timed(T.admit, acc, now)
    return acc, st, t_ver, t_key, acks, dict(ec.COUNT)


def base_world(n):
    ta = base.BaseTA()
    tu = base.BaseTUAV("tuav", ta.register_tuav("tuav"))
    ids = [f"uav-{i}" for i in range(n)]
    us = [base.BaseUAV(i, ta.register_uav(i)) for i in ids]
    return ta, tu, ids, us


def base_round(ta, tu, ids, us, now=NOW):
    beacon = tu.is4(now)
    reqs = [u.us(beacon, now) for u in us]
    ec.reset_counts()
    res, t_ta = timed(ta.ga2, reqs, ids)
    cnt_ta = dict(ec.COUNT); ec.reset_counts()
    ok, t_tu = timed(tu.ga3, res)
    (kappa, coeffs, acks, moduli), t_gd = timed(base.gd, tu, res, [r[1] for r in reqs], now)
    return ok, t_ta, t_tu, t_gd, coeffs, cnt_ta


# ---------------------------------------------------------------- E2 latency vs n (measured)
def e2():
    ns = [5, 10, 20] if QUICK else [10, 20, 40, 60, 80, 100, 120]
    rows = []
    for n in ns:
        ta, T, ms = ours_world(n, epochs=1)
        reps = 3
        tv, tk = [], []
        for _ in range(reps):
            acc, st, t_ver, t_key, acks, cnt = ours_round(T, ms)
            ours_cnt = cnt
            assert len(acc) == n and all(m.receive(acks["join"]) for m in ms)
            tv.append(t_ver); tk.append(t_key)
        bta, btu, bids, bus = base_world(n)
        ok, t_ta, t_tu, t_gd, coeffs, cnt_ta = base_round(bta, btu, bids, bus)
        assert ok
        M = MICRO
        est_ours = (ours_cnt["mul"] * M["G1 scalar multiplication"] + ours_cnt["small_mul"] * M["G1 small (64-bit) multiplication"]
                    + ours_cnt["add"] * M["G1 point addition"])
        est_base_ta = (cnt_ta["pairing"] * M["bilinear pairing"] + cnt_ta["mul"] * M["G1 scalar multiplication"]
                       + cnt_ta["add"] * M["G1 point addition"])
        row = [n, round(stats.median(tv), 1), round(stats.median(tk), 1), round(stats.median(tv) + stats.median(tk), 1),
               round(t_ta, 1), round(t_tu, 1), round(t_gd, 1), round(t_ta + t_tu + t_gd, 1), cnt_ta["pairing"],
               ours_cnt["mul"], ours_cnt["small_mul"], cnt_ta["mul"], round(est_ours, 1), round(est_base_ta, 1)]
        rows.append(row)
        log("E2", row)
    write("e2_latency.csv", ["n", "ours_verify_ms", "ours_keys_ms", "ours_total_ms", "base_TA_ms", "base_TUAV_ms",
                             "base_GD_ms", "base_total_ms", "base_pairings",
                             "ours_muls", "ours_small_muls", "base_TA_muls", "ours_est_ms", "base_TA_est_ms"], rows)
    last = rows[-1]
    SUMMARY["E2"] = {"n": last[0], "ours_total_ms": last[3], "base_total_ms": last[7], "base_TUAV_only_ms": last[5],
                     "speedup": round(last[7] / last[3], 1)}
    return rows


# ---------------------------------------------------------------- E1 availability (link model)
def e1(e2rows):
    n_ref = e2rows[-1]
    base_compute, ours_compute = n_ref[7], n_ref[3]
    rounds = 2000 if QUICK else 20000
    rows = []
    for A in [x / 10 for x in range(10, -1, -1)]:
        for model in ("iid", "bursty"):
            succ = {"base_1": 0, "base_3": 0, "ours": 0}
            state_up = True
            for _ in range(rounds):
                if model == "iid":
                    ups = [RNG.random() < A for _ in range(3)]
                else:   # Gilbert-Elliott: mean outage 10 rounds, steady-state availability A
                    ups = []
                    for _ in range(3):
                        if A in (0.0, 1.0):
                            state_up = A == 1.0
                        else:
                            p_rec = 0.1; p_fail = p_rec * (1 - A) / A
                            state_up = (RNG.random() >= p_fail) if state_up else (RNG.random() < p_rec)
                        ups.append(state_up)
                succ["base_1"] += ups[0]; succ["base_3"] += any(ups); succ["ours"] += 1
            rows.append([model, A, *(round(100 * succ[k] / rounds, 2) for k in ("base_1", "base_3", "ours"))])
    write("e1_availability.csv", ["model", "A", "base_one_attempt_pct", "base_three_attempts_pct", "ours_pct"], rows)
    SUMMARY["E1"] = {"rounds_per_point": rounds, "base_at_A0": 0.0, "ours_at_A0": 100.0}
    log("E1 done")


# ---------------------------------------------------------------- E3 batch poisoning
def split_retest(T, reqs, k0=4):
    stack, good, t0 = [reqs], [], time.perf_counter()
    while stack:
        b = stack.pop()
        if len(b) <= k0:
            good += [r for r in b if ours.verify(T.Ppub, *T._item(r))]; continue
        if ours.batch_verify(T.Ppub, [T._item(r) for r in b]):
            good += b
        else:
            h = len(b) // 2; stack += [b[:h], b[h:]]
    return good, (time.perf_counter() - t0) * 1000


def e3():
    n = 20 if QUICK else 60
    ta, T, ms = ours_world(n, epochs=1)
    rows = []
    for pct in [0, 2, 5, 10, 20]:
        d = round(n * pct / 100)
        fb, sp, ind, gp = [], [], [], []
        for _ in range(1 if QUICK else 3):
            T.mode, T.clean, T.evicted = "batch", 0, set()
            acc, st, t_fb, _, _, _ = ours_round(T, ms, corrupt=d)
            b = T.beacon(NOW); reqs = [m.request(b, 1, NOW) for m in ms]
            for r in reqs[:d]:
                r.v = (r.v + 1) % ec.q
            g2, t_split = split_retest(T, reqs)
            t_ind = timed(lambda: [ours.verify(T.Ppub, *T._item(r)) for r in reqs])[1]
            fb.append(t_fb); sp.append(t_split); ind.append(t_ind); gp.append(100 * len(acc) / n)
        md = stats.median
        rows.append([pct, d, round(md(fb), 1), round(md(sp), 1), round(md(ind), 1), round(md(gp), 1), 100.0 if d == 0 else 0.0])
        log("E3", rows[-1])
    # confirm the base behaviour on a small batch: one bad request -> whole batch rejected
    bta, btu, bids, bus = base_world(10)
    beacon = btu.is4(NOW); reqs = [u.us(beacon, NOW) for u in bus]
    r0 = list(reqs[0]); r0[4] = ec.add(r0[4], ec.P); reqs[0] = tuple(r0)
    base_ok = btu.ga3(bta.ga2(reqs, bids))
    write("e3_poisoning.csv", ["bad_pct", "bad", "ours_fallback_ms", "split_retest_ms", "individual_ms", "ours_goodput_pct", "base_goodput_pct"], rows)
    SUMMARY["E3"] = {"n": n, "clean_ms": rows[0][2], "worst_fallback_ms": max(r[2] for r in rows),
                     "base_batch_with_one_bad_accepted": bool(base_ok)}


# ---------------------------------------------------------------- E4 bytes
def e4():
    rows = []
    for n in ([10, 20] if QUICK else [10, 20, 40, 60, 80, 100, 120]):
        moduli = [base.sigma_int(ec.mul(ec.P, ec.rand_scalar())) for _ in range(n)]
        coeffs = base.crt_poly(moduli, random.getrandbits(base.SIGMA_BITS - 2) | 1)
        cb = base.coeff_bytes(coeffs)
        ack_base = ec.SIZE["ts"] + 2 * ec.SIZE["hash"] + cb
        rows.append([n, n * base.REQ_SIZE, n * (base.UP_SIZE + base.DOWN_SIZE), ack_base, n * ack_base,
                     n * ours.Request.size(), 0, ec.SIZE["id"] + ec.SIZE["ts"] + 4 + n * ours.ENTRY])
    write("e4_bytes.csv", ["n", "base_requests_B", "base_satellite_B", "base_ack_each_B", "base_acks_total_B",
                           "ours_requests_B", "ours_satellite_B", "ours_ack_B"], rows)
    r = rows[-1]
    SUMMARY["E4"] = {"n": r[0], "per_request_base_B": base.REQ_SIZE, "per_request_ours_B": ours.Request.size(),
                     "base_key_traffic_B": r[4], "ours_key_traffic_B": r[7], "base_satellite_B": r[2], "ratio": round(r[4] / r[7])}
    log("E4", r)


# ---------------------------------------------------------------- E5 vehicle tier
def e5():
    ta = ours.TA()
    T = ours.TUAV("TUAV-A", ta.register_tuav("TUAV-A"), ta.Ppub)
    relay = ours.Member(ta.register(os.urandom(16), 1), ta.Ppub)
    rows = []
    ms_list = [20, 50] if QUICK else [50, 100, 200, 300, 500]
    pool = [ours.Member(ta.register(os.urandom(16), 1), ta.Ppub, role="veh") for _ in range(max(ms_list))]
    for m in ms_list:
        T.members.clear(); T.evicted.clear(); T.mode = "batch"
        b = T.beacon(NOW)
        relay.request(b, 1, NOW); acc, _ = T.verify_window([relay.request(b, 1, NOW)], NOW, 1)
        relay.receive(T.admit(acc, NOW)["join"])
        vreqs = [v.request(b, 1, NOW) for v in pool[:m]]
        bundle = relay.relay(vreqs, NOW)
        tb, ti = [], []
        for rep in range(1 if QUICK else 3):
            if rep:
                T.members.clear(); T.evicted.clear(); T.mode = "batch"
                b = T.beacon(NOW); acc, _ = T.verify_window([relay.request(b, 1, NOW)], NOW, 1)
                relay.receive(T.admit(acc, NOW)["join"])
                vreqs = [v.request(b, 1, NOW) for v in pool[:m]]; bundle = relay.relay(vreqs, NOW)
            (ack, st), t_batch = timed(T.process_bundle, bundle, NOW, 1)
            ok = all(v.receive(ack) for v in pool[:m])
            tb.append(t_batch); ti.append(timed(lambda: [ours.verify(T.Ppub, *T._item(r)) for r in vreqs])[1])
        t_batch, t_ind = stats.median(tb), stats.median(ti)
        fake = {"relay": os.urandom(32), "ts": NOW, "reqs": vreqs, "tag": os.urandom(32)}
        (_, why), t_drop = timed(T.process_bundle, fake, NOW, 1)
        rows.append([m, round(t_batch, 1), round(t_ind, 1), round(t_drop, 3), ok, why.get("dropped")])
        log("E5", rows[-1])
    write("e5_vehicles.csv", ["vehicles", "batch_admit_ms", "individual_verify_ms", "outsider_bundle_drop_ms", "all_keyed", "drop_reason"], rows)
    SUMMARY["E5"] = {"vehicles": rows[-1][0], "batch_ms": rows[-1][1], "individual_ms": rows[-1][2], "drop_ms": rows[-1][3]}


# ---------------------------------------------------------------- E6 handover
def e6():
    ta = ours.TA()
    A = ours.TUAV("TUAV-A", ta.register_tuav("TUAV-A"), ta.Ppub)
    B = ours.TUAV("TUAV-B", ta.register_tuav("TUAV-B"), ta.Ppub)
    oa, ob = A.link_offer(NOW), B.link_offer(NOW); A.link_accept(ob, NOW); B.link_accept(oa, NOW)
    reps = 5 if QUICK else 25
    ho_t, ho_m, full_t, full_m = [], [], [], []
    for i in range(reps):
        m = ours.Member(ta.register(os.urandom(16), 1), ta.Ppub)
        b = A.beacon(NOW); acc, _ = A.verify_window([m.request(b, 1, NOW)], NOW, 1); m.receive(A.admit(acc, NOW)["join"])
        m.take_ticket(A.issue_ticket(m.cred(1).key, B.id, NOW), B.id)
        msg, t1 = timed(m.handover_request, A.id, NOW + 1)
        (resp, why), t2 = timed(B.accept_handover, msg, NOW + 1)
        ok, t3 = timed(m.handover_finish, resp, B.id)
        assert why == "ok" and ok
        ho_m.append(t1 + t3); ho_t.append(t2)
        # full re-admission at B: member verifies beacon + signs; B verifies + derives key
        bb = B.beacon(NOW + 1)
        req, t4 = timed(m.request, bb, 1, NOW + 1)
        (acc, _), t5 = timed(B.verify_window, [req], NOW + 1, 1)
        acks, t6 = timed(B.admit, acc, NOW + 1)
        _, t7 = timed(m.receive, acks["join"])
        full_m.append(t4 + t7); full_t.append(t5 + t6)
    med = lambda x: round(stats.median(x), 2)
    rows = [["new TUAV", med(full_t), med(ho_t)], ["member", med(full_m), med(ho_m)]]
    write("e6_handover.csv", ["side", "full_readmission_ms", "ticket_handover_ms"], rows)

    # mobility: 3 cells of 2 km on a line, 30 UAVs moving 10-20 m/s for one hour, beacon period 1 s
    cells, L, uavs, T_end = 3, 2000.0, 30, 3600
    pos = [RNG.uniform(0, cells * L) for _ in range(uavs)]
    vel = [RNG.choice([-1, 1]) * RNG.uniform(10, 20) for _ in range(uavs)]
    crossings = 0
    for _ in range(T_end):
        for i in range(uavs):
            old = int(pos[i] // L); pos[i] += vel[i]
            if pos[i] < 0 or pos[i] >= cells * L:
                vel[i] = -vel[i]; pos[i] = min(max(pos[i], 0), cells * L - 1e-6)
            if int(pos[i] // L) != old:
                crossings += 1
    beacon_wait_ms = 500.0                                     # mean wait for the next beacon (1 s period)
    gap_full = beacon_wait_ms + rows[1][1] + rows[0][1]
    gap_ho = rows[1][2] + rows[0][2]
    write("e6_mobility.csv", ["cells", "uavs", "seconds", "crossings", "gap_full_ms", "gap_ticket_ms",
                              "tuav_cpu_full_s", "tuav_cpu_ticket_s"],
          [[cells, uavs, T_end, crossings, round(gap_full, 1), round(gap_ho, 1),
            round(crossings * rows[0][1] / 1000, 2), round(crossings * rows[0][2] / 1000, 2)]])
    SUMMARY["E6"] = {"tuav_full_ms": rows[0][1], "tuav_ticket_ms": rows[0][2], "member_full_ms": rows[1][1],
                     "member_ticket_ms": rows[1][2], "crossings_per_hour": crossings, "gap_full_ms": round(gap_full, 1),
                     "gap_ticket_ms": round(gap_ho, 1)}
    log("E6", rows, crossings)


# ---------------------------------------------------------------- E7 attack outcomes
def e7():
    out = []
    # ---- base scheme
    bta, btu, bids, bus = base_world(4)
    beacon = btu.is4(NOW)
    forged = base.ta_forge(bta, beacon, bids[0], NOW)
    out.append(["base", "TA forges a UAV request (Finding 2)", btu.ga3(bta.ga2([forged], [bids[0]]))])
    reqs = [u.us(beacon, NOW) for u in bus]
    D = ec.mul(ec.P, 777)
    r0, r1 = list(reqs[0]), list(reqs[1]); r0[4] = ec.add(r0[4], D); r1[4] = ec.add(r1[4], ec.neg(D))
    out.append(["base", "cancelling errors pass the batch (Finding 5)", btu.ga3(bta.ga2([tuple(r0), tuple(r1)] + reqs[2:], bids))])
    moduli = [base.sigma_int(ec.mul(ec.P, ec.rand_scalar())) for _ in range(8)]
    old = base.crt_poly(moduli, 12345); stay = moduli[:3] + moduli[5:]; k2 = random.getrandbits(150)
    got, _ = base.revocation_attack(old, moduli[3], base.crt_poly(stay, k2))
    out.append(["base", "revoked UAV recovers the new group key (Finding 4)", got == k2])
    r0 = list(reqs[0]); r0[4] = ec.add(r0[4], ec.P)
    out.append(["base", "one bad request -> honest UAVs still admitted", btu.ga3(bta.ga2([tuple(r0)] + reqs[1:], bids))])
    # ---- ours
    ta, T, ms = ours_world(4, epochs=2)
    acc, st, *_ , acks, _ = ours_round(T, ms)
    for m in ms:
        m.receive(acks["join"])
    c = ms[0].cred(1)
    R, v = ours.sign(ours.Credential(c.ident, 1, c.X, c.Y, c.d, ec.rand_scalar()), b"m", NOW)
    out.append(["ours", "TA forges a member signature (knows d, not x)", ours.verify(ta.Ppub, c.ident, 1, c.X, c.Y, b"m", NOW, R, v)])
    b = T.beacon(NOW + 1); rq = [m.request(b, 2, NOW + 1) for m in ms[:2]]
    rq[0].v = (rq[0].v + 99) % ec.q; rq[1].v = (rq[1].v - 99) % ec.q
    out.append(["ours", "cancelling errors pass the batch", ours.batch_verify(ta.Ppub, [T._item(r) for r in rq])])
    oldK = ms[3].K
    rk = T.rekey([ms[3].cred(1).key], NOW + 2)
    leaked = any(sym.open_(oldK, blob, k + rk["nu"].to_bytes(4, "big") + rk["ts"].to_bytes(8, "big")) for k, blob in rk["entries"])
    out.append(["ours", "revoked UAV recovers the new group key", leaked or ms[3].receive_update(rk)])
    T.mode = "batch"; T.evicted.clear()
    acc, *_ = ours_round(T, ms[:3], ep=2, now=NOW + 3, corrupt=1)
    out.append(["ours", "one bad request -> honest UAVs still admitted", len(acc) == 2])
    b1 = T.beacon(NOW + 4); oldreq = ms[1].request(b1, 2, NOW + 4); T.beacon(NOW + 5)
    out.append(["ours", "replayed request accepted under a new beacon", bool(T.verify_window([oldreq], NOW + 5, 2)[0])])
    write("e7_attacks.csv", ["scheme", "attack", "succeeds"], out)
    SUMMARY["E7"] = [{"scheme": s, "attack": a, "succeeds": bool(x)} for s, a, x in out]
    for r in out:
        log("E7", r)


MICRO = {}

if __name__ == "__main__":
    t0 = time.time()
    MICRO.update({k: v[0] for k, v in e0().items()})
    only = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--only=")), None)
    if "--only-e2" in sys.argv:
        only = ["e2"]
    if only:                                 # quiet re-run of selected experiments
        fns = {"e2": e2, "e3": e3, "e4": e4, "e5": e5, "e6": e6, "e7": e7}
        for k in only:
            fns[k]()
        path = os.path.join(OUT, "summary.json")
        old = json.load(open(path)) if os.path.exists(path) else {}
        old.update({k: v for k, v in SUMMARY.items()})
        json.dump(old, open(path, "w"), indent=2)
        sys.exit(0)
    rows = e2()
    e1(rows)
    e3(); e4(); e5(); e6(); e7()
    SUMMARY["runtime_s"] = round(time.time() - t0, 1)
    with open(os.path.join(OUT, "summary.json"), "w") as f:
        json.dump(SUMMARY, f, indent=2)
    log("done in", SUMMARY["runtime_s"], "s")
