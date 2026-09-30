"""
Global constants for the TUAV-assisted infrastructure-less IoV simulator.

Everything the paper states numerically lives here, so that no magic number is
buried inside the simulation code.

Base paper
----------
H. Tan, W. Zheng and P. Vijayakumar,
"Secure and Efficient Authenticated Key Management Scheme for UAV-Assisted
Infrastructure-Less IoVs", IEEE Trans. Intelligent Transportation Systems,
vol. 24, no. 6, pp. 6389-6400, June 2023.  DOI 10.1109/TITS.2023.3252082
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# Paper metadata
# --------------------------------------------------------------------------
PAPER = {
    "title": "Secure and Efficient Authenticated Key Management Scheme "
             "for UAV-Assisted Infrastructure-Less IoVs",
    "authors": "Haowen Tan, Wenying Zheng, Pandi Vijayakumar",
    "venue": "IEEE Trans. Intelligent Transportation Systems, 24(6), 6389-6400",
    "year": 2023,
    "doi": "10.1109/TITS.2023.3252082",
}

# --------------------------------------------------------------------------
# Table III / Section VI-A : primitive costs the paper borrows from ref. [47]
# MIRACL, 80-bit security level.  Milliseconds.
# These describe the PAPER's benchmark machine, not ours.
# --------------------------------------------------------------------------
MIRACL_MS = {
    "T_P":       7.2232,   # bilinear pairing
    "T_SM_P":    2.6784,   # scalar multiplication in the pairing group
    "T_SSM_P":   0.1685,   # small-scalar multiplication, pairing group
    "T_PA_P":    0.0342,   # point addition, pairing group
    "T_H_MP_P":  8.1940,   # MapToPoint hash related to bilinear pairing
    "T_SM_E":    0.9018,   # scalar multiplication, plain elliptic curve
    "T_SSM_E":   0.0475,   # small-scalar multiplication, plain EC
    "T_PA_E":    0.0107,   # point addition, plain EC
    "T_ME":      0.6256,   # modular exponentiation
    "T_SH":      0.0012,   # general secure hash
}

# --------------------------------------------------------------------------
# Table III : closed-form cost expressions, exactly as printed in the paper.
# Each entry is (constant_ms, per_uav_ms) so that cost(n) = c + m * n.
# US = UAV signing, SA = single verification, GA = group authentication.
# --------------------------------------------------------------------------
PAPER_COSTS = {
    "Mei et al. [7]":   {"US": (27.1700, 0.0), "SA": (50.6376, 0.0), "GA": (45.2124, 5.4252)},
    "Kumar et al. [10]": {"US": (18.9760, 0.0), "SA": (45.1220, 0.0), "GA": (37.0868, 16.2292)},
    "Ali et al. [14]":  {"US": (2.6784, 0.0),  "SA": (9.9358, 0.0),  "GA": (7.2232, 2.7126)},
    "Xu et al. [18]":   {"US": (16.2634, 0.0), "SA": (43.4486, 0.0), "GA": (29.7952, 13.6534)},
    "Proposed (paper)": {"US": (1.8203, 0.0),  "SA": (2.1578, 0.0),  "GA": (0.9054, 1.2524)},
}

# Headline figures the paper reports in Section VI-A.
PAPER_HEADLINE = {"US_ms": 1.8203, "SA_ms": 2.1578, "GA_ms_at_120": 151.1934, "n": 120}

# --------------------------------------------------------------------------
# Section VI-B : element sizes used for the communication-overhead comparison.
# Bytes.
# --------------------------------------------------------------------------
SIZES_BYTES = {
    "G1_element": 128,   # 64 * 2, from the 512-bit field p'
    "G_element": 40,     # 20 * 2, from the 160-bit field p
    "hash": 20,          # general secure hash output
    "timestamp": 4,
    "identity": 20,      # temporary session identity
    "scalar": 20,        # element of Z_q
}

# --------------------------------------------------------------------------
# Simulator defaults
# --------------------------------------------------------------------------
DEFAULTS = {
    "n_uav": 8,
    "n_vehicle": 16,
    "session": 1,
    "ta_rtt_ms": 40.0,        # our addition; the paper reports no link latency
    "ta_availability": 1.0,   # our addition; 1.0 = link always up
    "poison_fraction": 0.0,   # fraction of requests carrying a forged credential
    "replay_window_s": 30.0,  # timestamp acceptance window
    "backend": "abstract",
}

LIMITS = {
    "n_uav_min": 2,
    "n_uav_max": 100,
    "n_vehicle_min": 5,
    "n_vehicle_max": 100,
    "faithful_interactive_max": 30,   # above this the faithful backend is slow
}

# --------------------------------------------------------------------------
# Toy bilinear group used by the ABSTRACTED backend.
#
# q is a 256-bit prime; p = k*q + 1 is prime; g has order q in Z*_p.
# The map e(aP, bP) := g^(ab mod q) mod p is GENUINELY BILINEAR, which is what
# lets the abstracted backend reproduce the paper's algebra and its failure
# modes exactly.  It is NOT cryptographically secure: the discrete logarithm is
# trivial because the simulator tracks scalars directly.
# --------------------------------------------------------------------------
TOY_Q = 57896044618658097711785492504343953926634992332820282019728792003956564832381
TOY_K = 528
TOY_P = 30569111558651475591822740042293607673263275951729108906416802178089066231497169
TOY_G = 14094948971085873960849812935361446242918470069778830307332123276188345787369407

# Bit length of the integer CRT moduli.  See crypto/crt.py for why the paper's
# own definition cannot be used verbatim.
CRT_MODULUS_BITS = 64

# --------------------------------------------------------------------------
# Honesty strings.  Rendered verbatim in the UI so a viewer can never mistake a
# reported number for a measured one.
# --------------------------------------------------------------------------
DISCLAIMER_SHORT = (
    "Simplified educational implementation of the proposed scheme. "
    "Not a reproduction of the paper's cryptographic benchmark environment."
)

DISCLAIMER_TIMING = (
    "Absolute timings are NOT comparable with the paper. The paper reports "
    "MIRACL (C) at 80-bit security; this simulator is pure Python. Compare "
    "shape and slope, never milliseconds."
)
