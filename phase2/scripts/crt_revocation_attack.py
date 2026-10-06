# Verifies, on the paper's own GD1-GD6 / DU1-DU2 construction (sigma_i read as integers, the only
# reading under which "mod sigma_i" is defined), two claims:
#  (A) any member who knows one sigma_j can recover EVERY member's sigma_i from the public {a_i}
#  (B) hence a REVOKED member recovers the post-revocation key kappa*
# and measures the true size of the broadcast coefficient set.
import random, sympy
from math import prod
random.seed(7)
BITS = 160                                   # |sigma_i| ~ |q| = 160 bits

def build(sigmas, kappa):
    M = prod(sigmas)
    S = 0
    for s in sigmas:
        w = M // s; S += w * pow(w, -1, s)       # omega_i * phi_i
    x = sympy.symbols('x')
    poly = sympy.Poly(sympy.prod([x - s for s in sigmas]), x) + sympy.Poly(kappa * S, x)
    return poly, x

n = 12
sig = [sympy.randprime(2**(BITS-1), 2**BITS) for _ in range(n)]
kappa = random.randrange(2, 2**(BITS-2))
L, x = build(sig, kappa)
assert all(L.eval(s) % s == kappa for s in sig), "paper's correctness"
print("correctness holds for all", n, "members")

# (A) member 0 knows only sig[0] and the public coefficients
C = L.eval(sig[0])                           # = kappa * S, constant
g = L - sympy.Poly(C, x)                     # = prod (x - sigma_i)
roots = sorted(r for r in sympy.Poly(g, x).ground_roots())
print("(A) insider recovered all sigma_i:", roots == sorted(sig))

# (B) revoke members 3 and 7, add two new members; rebuild per DU1
stay = [s for k, s in enumerate(sig) if k not in (3, 7)]
new = stay + [sympy.randprime(2**(BITS-1), 2**BITS) for _ in range(2)]
kappa2 = random.randrange(2, 2**(BITS-2))
L2, _ = build(new, kappa2)
revoked_sigma = sig[3]
print("    revoked member's own sigma gives kappa*?", L2.eval(revoked_sigma) % revoked_sigma == kappa2)
stolen = roots[0] if roots[0] in stay else [r for r in roots if r in stay][0]
print("(B) revoked member, using a stolen sigma, gets kappa*:", L2.eval(stolen) % stolen == kappa2)

# size of the coefficient set actually broadcast
for m in (20, 60, 120):
    s_ = [sympy.randprime(2**(BITS-1), 2**BITS) for _ in range(m)]
    P, _ = build(s_, random.randrange(2, 2**(BITS-2)))
    bits = sum(int(abs(c)).bit_length() for c in P.all_coeffs())
    per_ack = bits // 8
    print(f"n={m:4d}: coefficient set = {per_ack/1024:8.1f} KiB per ACK; "
          f"x n unicast ACKs = {per_ack*m/1024/1024:7.2f} MiB   (paper Table V GA: {104*m/1024:.1f} KiB)")
