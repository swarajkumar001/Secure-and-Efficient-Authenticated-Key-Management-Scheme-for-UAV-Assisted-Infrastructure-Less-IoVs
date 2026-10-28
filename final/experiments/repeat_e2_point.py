"""Re-measure one E2 point (both schemes, back to back) and replace that row of
results/e2_latency.csv, keeping the previous measurement in results/e2_replaced_rows.csv.
    python experiments/repeat_e2_point.py 120
"""
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import run_all as R                                            # noqa: E402

n = int(sys.argv[1])
R.MICRO.update({k: v[0] for k, v in R.e0().items()})
rows = None
saved = R.write
R.write = lambda name, header, rs: None                        # capture instead of writing
orig_ns = None


def one_point():
    import statistics as stats
    from cutcord import ec
    ta, T, ms = R.ours_world(n, epochs=1)
    tv, tk = [], []
    for _ in range(3):
        acc, st, t_ver, t_key, acks, cnt = R.ours_round(T, ms)
        tv.append(t_ver); tk.append(t_key); ours_cnt = cnt
    bta, btu, bids, bus = R.base_world(n)
    ok, t_ta, t_tu, t_gd, coeffs, cnt_ta = R.base_round(bta, btu, bids, bus)
    M = R.MICRO
    est_o = ours_cnt["mul"] * M["G1 scalar multiplication"] + ours_cnt["small_mul"] * M["G1 small (64-bit) multiplication"] + ours_cnt["add"] * M["G1 point addition"]
    est_b = cnt_ta["pairing"] * M["bilinear pairing"] + cnt_ta["mul"] * M["G1 scalar multiplication"] + cnt_ta["add"] * M["G1 point addition"]
    return [n, round(stats.median(tv), 1), round(stats.median(tk), 1), round(stats.median(tv) + stats.median(tk), 1),
            round(t_ta, 1), round(t_tu, 1), round(t_gd, 1), round(t_ta + t_tu + t_gd, 1), cnt_ta["pairing"],
            ours_cnt["mul"], ours_cnt["small_mul"], cnt_ta["mul"], round(est_o, 1), round(est_b, 1)]


new = one_point()
R.write = saved
path = os.path.join(R.OUT, "e2_latency.csv")
with open(path) as f:
    table = list(csv.reader(f))
header, body = table[0], table[1:]
old = [r for r in body if int(float(r[0])) == n]
body = [r if int(float(r[0])) != n else [str(x) for x in new] for r in body]
with open(path, "w", newline="") as f:
    csv.writer(f).writerows([header] + body)
with open(os.path.join(R.OUT, "e2_replaced_rows.csv"), "a", newline="") as f:
    w = csv.writer(f)
    for r in old:
        w.writerow(["replaced"] + r)
    w.writerow(["new"] + new)
print("old", old, "\nnew", new)
