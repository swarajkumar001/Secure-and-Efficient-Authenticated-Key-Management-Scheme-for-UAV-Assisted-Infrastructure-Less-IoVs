"""Every number used in the Phase-2 paper and slides comes from this file.

Cost model: the base paper's own MIRACL timings (80-bit level, Tan et al. Sec. VI-A),
so that our scheme and the base scheme are priced with identical constants.
Run:  python phase2/scripts/compute_results.py      (writes phase2/data/*.csv and prints a summary)
"""
import csv, math, os, random

OUT = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(OUT, exist_ok=True)

# ---- base-paper constants (ms) ----
T_P, T_SMP, T_SSMP, T_PAP, T_HMP = 7.2232, 2.6784, 0.1685, 0.0342, 8.1940
T_SME, T_SSME, T_PAE, T_ME, T_SH = 0.9018, 0.0475, 0.0107, 0.6256, 0.0012

# ---- base scheme, as reported (TUAV side only) ----
orig_US = 2*T_SME + T_PAE + 5*T_SH                  # 1.8203
orig_SA = T_SME + 2*T_ME + 4*T_SH                   # 2.1578
orig_GA = lambda n: T_SME + 2*n*T_ME + (n+3)*T_SH   # 1.2524n + 0.9054
# ---- base scheme, honest accounting ----
orig_US_G1 = 2*T_SMP + T_PAP + 5*T_SH               # Gamma_i must live in G1 to be paired
TA_per_uav = 3*T_P + 3*T_SMP + T_PAP + 2*T_SH       # GA2: sigma, psi, mu, delta
orig_GA_h = lambda n: orig_GA(n) + n*TA_per_uav
orig_SA_h = orig_SA + TA_per_uav
# ---- other schemes (GA formulas from the base paper) ----
mei  = lambda n: 5.4252*n + 45.2124
kum  = lambda n: 16.2292*n + 37.0868
ali  = lambda n: 2.7126*n + 7.2232
xu   = lambda n: 13.6534*n + 29.7952
# ---- proposed scheme ----
our_sign = 2*T_SME + T_SH                                   # R=rP, E=eP, c
our_SV   = 3*T_SME + 3*T_PAE + 2*T_SH                       # single verification
our_BV   = lambda n: (n+2)*T_SME + n*T_SSME + 3*n*T_PAE + 2*n*T_SH
our_KD   = lambda n: n*(T_SME + 2*T_SH)                     # ECDH + KDF + AEAD per member
our_total= lambda n: our_BV(n) + our_KD(n)
our_member_recv = our_SV + T_SME + 2*T_SH                   # verify beacon once, ECDH, KDF/AEAD
ho_target = 2*T_SME + 4*T_SH; ho_member = 2*T_SME + 3*T_SH
full_target = our_SV + T_SME + 2*T_SH; full_member = our_sign + our_SV + T_SME + 2*T_SH

def lin(f):  # slope, intercept
    return f(1)-f(0), f(0)

# ---- communication (bytes, base-paper sizes: |G|=40, |G1|=|G2|=128, hash 20, ts 4) ----
B = dict(orig_req_claimed=4+20+20+20+40, orig_req_honest=4+20+20+20+128,
         orig_sat_up=4+20+20+20+128, orig_sat_down=128+3*128,
         our_req=(40+20+4)+40+40+40+4+40+20,   # PID(60)+epoch(4), X, Y, E, ts, R, v
         our_entry=20+48, our_beacon=20+80+40+4+40+20,
         ho_req=20+(64+80+1+16+4+12+12+16)+40+4+32, ho_resp=40+4+48)

def crt_coeff_bytes(n, bits=160, seed=1):
    """exact size of the CRT coefficient set {a_i} (Step GD2) for n random 160-bit primes"""
    import sympy
    rnd = random.Random(seed)
    sig = [sympy.randprime(2**(bits-1), 2**bits) for _ in range(n)]
    M = math.prod(sig); S = sum((M//s)*pow(M//s, -1, s) for s in sig)
    kappa = rnd.randrange(2, 2**(bits-2))
    coeffs = [1]                                   # prod (x - s), highest degree first
    for s in sig:
        coeffs = [a - s*b for a, b in zip(coeffs+[0], [0]+coeffs)]
    coeffs[-1] += kappa*S
    return sum((abs(c).bit_length()+7)//8 for c in coeffs)

def isolate(flags, k0=4):
    """adaptive split-and-retest: returns cost (ms) to find every bad signature"""
    cost = 0.0
    stack = [flags]
    while stack:
        b = stack.pop()
        if len(b) <= k0:
            cost += len(b)*our_SV; continue
        cost += our_BV(len(b))
        if any(b):
            h = len(b)//2; stack += [b[:h], b[h:]]
    return cost

if __name__ == "__main__":
    ns = list(range(20, 121, 20))
    with open(os.path.join(OUT, "ga_cost.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["n","mei","kumar","ali","xu","orig","orig_honest","ours_bv","ours_total"])
        for n in ns: w.writerow([n]+[round(v,2) for v in (mei(n),kum(n),ali(n),xu(n),orig_GA(n),orig_GA_h(n),our_BV(n),our_total(n))])
    with open(os.path.join(OUT, "e2e.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["n","orig_reported","orig_leo","orig_geo","ours"])
        for n in ns: w.writerow([n, round(orig_GA(n),1), round(orig_GA_h(n)+50,1), round(orig_GA_h(n)+600,1), round(our_total(n),1)])
    rows = []
    for n in range(10, 121, 10):
        cb = crt_coeff_bytes(n)
        rows.append([n, cb, cb*n, B["our_entry"]*n+4, 104*n])
    with open(os.path.join(OUT, "keybytes.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["n","crt_per_ack","crt_total","ours_total","paper_claim"]); w.writerows(rows)
    n = 120; rng = random.Random(3); iso = []
    for pct in range(0, 21, 2):
        d = round(n*pct/100); runs = []
        for _ in range(200):
            fl = [1]*d + [0]*(n-d); rng.shuffle(fl); runs.append(isolate(fl))
        fallback = our_BV(n) + (n*our_SV if d else 0)          # batch, then individual on failure
        iso.append([pct, d, round(sum(runs)/len(runs),1), round(fallback,1), round(n*our_SV,1),
                    100-pct, 100 if d == 0 else 0])
    with open(os.path.join(OUT, "isolation.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["pct","d","split_ms","fallback_ms","individual_ms","ours_goodput","orig_goodput"]); w.writerows(iso)
    with open(os.path.join(OUT, "rekey.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["n","crt","flat","lkh"])
        for m in range(20, 121, 20):
            w.writerow([m, (m-1)*crt_coeff_bytes(m-1), (m-1)*B["our_entry"]+4, (2*math.ceil(math.log2(m))-1)*52+4])

    print("orig US/SA/GA(120) reported:", round(orig_US,4), round(orig_SA,4), round(orig_GA(120),2))
    print("orig US in G1:", round(orig_US_G1,4), " TA per UAV:", round(TA_per_uav,4))
    print("orig GA honest: %.4fn + %.4f ; n=120 -> %.2f" % (*lin(orig_GA_h), orig_GA_h(120)))
    print("orig SA honest:", round(orig_SA_h,4))
    print("ours sign/SV:", round(our_sign,4), round(our_SV,4))
    print("ours BV: %.4fn + %.4f ; n=120 -> %.2f" % (*lin(our_BV), our_BV(120)))
    print("ours KD: %.4fn ; total %.4fn + %.4f ; n=120 -> %.2f" % (lin(our_KD)[0], *lin(our_total), our_total(120)))
    print("member recv:", round(our_member_recv,4), " HO target/member:", round(ho_target,4), round(ho_member,4),
          " full target/member:", round(full_target,4), round(full_member,4))
    print("others n=120: mei %.1f kum %.1f ali %.1f xu %.1f" % (mei(120),kum(120),ali(120),xu(120)))
    print("bytes:", B)
    print("keybytes:", rows)
    print("isolation:", iso)
