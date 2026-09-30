# TUAV-Assisted Infrastructure-Less IoV — Protocol Simulator

An interactive simulation of the authentication and key-management mechanism
proposed in:

> H. Tan, W. Zheng and P. Vijayakumar,
> **"Secure and Efficient Authenticated Key Management Scheme for UAV-Assisted
> Infrastructure-Less IoVs"**,
> *IEEE Transactions on Intelligent Transportation Systems*, vol. 24, no. 6,
> pp. 6389–6400, June 2023.
> DOI [10.1109/TITS.2023.3252082](https://doi.org/10.1109/TITS.2023.3252082)

**This is a simplified educational and experimental implementation.** It is not
a reproduction of the paper's cryptographic benchmark environment, and it does
not prove the paper's security theorems. The [Honest boundaries](#honest-boundaries)
section matters more than the feature list.

> The paper itself is IEEE copyright and is **not** included in this repository.
> Obtain it from IEEE Xplore via the DOI above.

---

## The problem

Conventional Internet-of-Vehicles security routes every trust decision through
roadside units — boxes on poles. A disaster destroys them first. At exactly the
moment coordinated vehicular communication matters most — rescue convoys,
evacuation routing — the security layer has nobody left to verify anyone.

The paper's answer: a **tethered UAV**, powered by a cable from an emergency
response vehicle, hovers indefinitely and takes over the roadside unit's role.

---

## Quick start

```bash
pip install -r uav_iov_simulator/requirements.txt
streamlit run uav_iov_simulator/app.py
```

If `streamlit` is not on your PATH, use `python -m streamlit run ...` instead.

Run the tests — they are the gate everything else depends on:

```bash
python -m pytest uav_iov_simulator/tests -q     # 71 passed
```

No GPU, no compiler, no external service. `py_ecc` is pure Python.

---

## What it does

| Tab | Contents |
|---|---|
| **Network** | Live four-tier topology, UAV table, event log |
| **Protocol run** | Steps US1–US3 and GA1–GA4, with the TUAV / TA cost split |
| **Group key** | CRT distribution, key holders, the declared correction |
| **Attacks** | Replay (×2), impersonation, revoked access, batch poisoning |
| **Anonymity** | Pseudonyms across sessions, TA-only identity retrieval |
| **Secure exchange** | AES-GCM under the group key |
| **Security board** | F1–F11 with three evidence levels |
| **Performance** | E1/E7/E8 sweeps, Table III, overhead, transcription check |
| **Paper vs us** | Fidelity table; what is and is not comparable |
| **Results** | Full status, adversary outcomes, event log |

Every simulator action is labelled with the paper's own step label, so you can
follow along in the PDF.

---

## The two backends

| | Faithful | Abstracted |
|---|---|---|
| G₁ | BN128 elliptic curve | integers mod *q* |
| Pairing | real Ate pairing (`py_ecc`) | exponentiation in ℤ*ₚ |
| Bilinear? | yes | **yes** — genuinely |
| Secure? | yes | **no** — the discrete log is trivial |
| Speed | ~190 ms per pairing | instant |
| Practical *n* | ≤ 30 interactively | ≤ 1000 |

The abstracted backend is **not** a hash-based fake. `e(aP, bP) := g^(ab) mod p`
with `g` of order *q* is a real bilinear map, so the paper's verification
equation balances there for exactly the same algebraic reason it balances on a
curve — and fails for exactly the same reasons. What it does not provide is
hardness.

---

## Two things this measures that the paper does not

### 1. The trusted authority's side of the cost

Every pairing in the protocol happens in Step GA2, on the TA. The TUAV performs
only target-group multiplications and two exponentiations. Measured with the
faithful backend:

| n | TUAV side | TA side | ratio |
|---|---|---|---|
| 20 | ~25 ms | ~11.5 s | ~470× |
| 60 | ~28 ms | ~34.6 s | ~1200× |
| 120 | ~33 ms | ~69 s | ~2100× |

Table III of the paper reports the TUAV side. That is what makes its
group-authentication figure small. The pairings did not disappear — they moved.

The operation counts make the point independently of language or hardware:

```
TA   (Step GA2):  9 pairings      <- for 8 UAVs
TUAV (Step GA3):  0 pairings      <- by construction
```

### 2. The authority link

Step GA1 crosses a satellite channel for every verification, and Step GA3 cannot
be evaluated until Step GA2 returns. Set **availability → 0** in the sidebar and
authentication does not degrade — it **stops**.

| TA link availability | Authentication success rate |
|---|---|
| 100% | 100% |
| 50% | ~38% |
| 10% | **0%** |
| 0% | **0%** |

`tests/test_correctness.py` asserts this.

---

## The adversaries

Three are blocked. **One is not**, and that is the finding.

| Attack | Outcome | Stopped at |
|---|---|---|
| Replay (timestamp) | blocked | Step GA1 — outside the acceptance window |
| Replay (cryptographic) | blocked | Step GA3 — `R_tu` and `ID_tu` were regenerated |
| Impersonation | blocked | Step GA3 — the TA resolves `ID_i` to the real `s_i` |
| Revoked-key access | blocked | AES-GCM authentication tag |
| **Batch poisoning** | **SUCCEEDS** | nothing — Step GA4 has no else-branch |

Replay is defended **twice**. Switch off the timestamp check and a replayed
credential still fails, because the TUAV draws a fresh `r_tu` each session —
that is the cryptographic half of Theorem 3, and it needs no check at all.

Measured goodput under batch poisoning, n = 20:

| Forged credentials | Published scheme | With individual fallback |
|---|---|---|
| 0% | 100% | 100% |
| **5%** (one packet) | **0%** | 95% |
| 20% | 0% | 80% |

One forged packet denies authentication to all nineteen honest members. The
fallback column is **not** part of the published scheme.

---

## Honest boundaries

### Faithful to the paper

- Entity model and message flow, using the paper's own step labels
- Certificateless key split: TA issues `s_i`, the UAV draws `r_i`, both required
- The credential `Γ_i` computed exactly as printed in Step US2
- Pseudonym derivation `ID_i = h3(id_i, ts2, ξ_i)`
- Real bilinear pairings (faithful backend)
- The aggregate verification equation of Step GA3, with its correctness
  reduction asserted as a unit test
- The pairing offload, enforced architecturally — the TUAV object has no access
  to a pairing function

### Simplified, abstracted, or interpreted

- **CRT phase** — see the declared correction below
- **Abstracted backend** — bilinear but not secure; labelled at all times
- **Security theorems 1–5** — *not reproduced*. We demonstrate the corresponding
  behaviour, which is weaker and different
- **Absolute timings** — *not comparable*. The paper reports MIRACL (C) at
  80-bit; this is pure Python on BN128. Compare shape and slope, never
  milliseconds
- **Vehicle tier** — out of scope, as in the paper itself
- **Radio, mobility, channel** — absent, as in the paper

### Declared correction

The paper overloads `σ_i`. Step GA2 defines it as a **point**:

```
σ_i = h1(s_i · ξ_i) · P
```

and `ψ_i = e(Γ_i + h1(s_i ξ_i)P, P)` uses it that way, consistently. But Step
GD1 then writes `ω_i = ∏_{j≠i} σ_j` and `φ_i ≡ ω_i⁻¹ mod σ_i`, and Step GD6
computes `κ_tu = Λ(σ_i) mod σ_i`. None of those is defined for an
elliptic-curve point.

Our reading, stated openly:

```
σ_i^point = h1(s_i · ξ_i) · P              used in GA2   (unchanged)
σ_i^int   = a prime derived from h1(s_i · ξ_i)   used in GD1–GD6
```

Primes make the moduli pairwise coprime, which `φ_i = ω_i⁻¹ mod σ_i` silently
requires and the paper never states. **Under this reading the paper's
construction is correct and we implement it verbatim** — `tests/test_crt.py`
proves every member recovers the same key, revoked members do not, and survivors
need no new key material.

A similar conflation appears in Table V: the per-request figure of 104 bytes
counts `Γ_i` as a 40-byte element of G, yet Step GA2 feeds it into a pairing,
which requires the 128-byte group G₁. The simulator reports both accountings.

---

## Architecture

```
app.py                  Streamlit shell — routing and rendering only
state.py                one state machine, one event log; all mutation here
config.py               every number the paper states, in one place

crypto/
  interface.py          the one architectural rule: all crypto goes through here
  backend_pairing.py    FAITHFUL    real BN128 pairings via py_ecc
  backend_abstract.py   ABSTRACTED  toy bilinear group, instant
  hash_utils.py         h1..h4 and H1 from Step IS3, domain-separated
  crt.py                Steps GD1–GD6, DU1–DU2

protocol/
  entities.py           TA, TUAV, UAV, Vehicle
  initialization.py     Steps IS1–IS5
  signing.py            Steps US1–US3
  authentication.py     Steps GA1–GA4
  key_management.py     Steps GD1–GD6, DU1–DU2
  link.py               the TA link — OUR ADDITION, not the paper's

simulation/
  attacks.py            replay, impersonation, revoked access, batch poisoning
  datalink.py           AES-GCM secure data exchange
  experiments.py        E1–E8 runners

paper_model/
  cost.py               Table III formulas — a calculator, not a simulation
  overhead.py           Table V byte accounting

visualization/          topology, performance charts, security board, demo mode
tests/                  71 tests
```

**The one rule:** the protocol layer imports `crypto.interface` and never a
crypto library directly. That is what makes the two backends interchangeable and
what stops a fast approximation from leaking into a "faithful" measurement.

---

## Status

Complete. 71 passing tests on both backends, 33 modules, ~6,200 lines.

## Licence

Code: MIT (see `LICENSE`). The base paper is IEEE copyright and is not
distributed here.
