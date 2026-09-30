# TUAV-Assisted Infrastructure-Less IoV — Protocol Simulator

An interactive simulation of the authentication and key-management mechanism
proposed in:

> H. Tan, W. Zheng and P. Vijayakumar,
> **"Secure and Efficient Authenticated Key Management Scheme for UAV-Assisted
> Infrastructure-Less IoVs"**,
> *IEEE Transactions on Intelligent Transportation Systems*, vol. 24, no. 6,
> pp. 6389–6400, June 2023. DOI [10.1109/TITS.2023.3252082](https://doi.org/10.1109/TITS.2023.3252082)

**This is a simplified educational and experimental implementation.** It is not
a reproduction of the paper's cryptographic benchmark environment, and it does
not prove the paper's security theorems. See *Honest boundaries* below — that
section matters more than the feature list.

---

## The problem

Conventional Internet-of-Vehicles security routes every trust decision through
roadside units (RSUs) — boxes on poles. A disaster destroys them first. At
exactly the moment coordinated vehicular communication matters most — rescue
convoys, evacuation routing — the security layer has nobody to verify anyone.

## The paper's solution

A **tethered UAV (TUAV)**, powered by a cable from an emergency response vehicle,
hovers indefinitely and takes over the RSU's role. Three cryptographic choices
make it cheap:

| Choice | What it buys |
|---|---|
| Certificateless keys | No certificates to carry, and no key escrow — the authority alone cannot impersonate a drone |
| Batch verification | One equation verifies *n* drones instead of *n* checks |
| CRT group key | One broadcast delivers the shared key; revocation disturbs nobody who remains |

---

## Installation

```bash
pip install -r uav_iov_simulator/requirements.txt
```

No GPU, no compiler, no external service. `py_ecc` is pure Python.

## Running

From the folder **above** `uav_iov_simulator/`:

```bash
streamlit run uav_iov_simulator/app.py
```

Run the tests first — they are the gate everything else depends on:

```bash
python -m pytest uav_iov_simulator/tests -v
```

---

## Architecture

```
app.py                  Streamlit shell — routing and rendering only
state.py                one state machine, one event log; all mutation lives here
config.py               every number the paper states, in one place

crypto/
  interface.py          the one architectural rule: all crypto goes through here
  backend_pairing.py    FAITHFUL    real BN128 pairings via py_ecc
  backend_abstract.py   ABSTRACTED  toy bilinear group, instant
  hash_utils.py         h1..h4 and H1 from Step IS3, domain-separated
  crt.py                Steps GD1–GD6, DU1–DU2  (see "Declared correction")

protocol/
  entities.py           TA, TUAV, UAV, Vehicle
  initialization.py     Steps IS1–IS5
  signing.py            Steps US1–US3
  authentication.py     Steps GA1–GA4
  key_management.py     Steps GD1–GD6, DU1–DU2
  link.py               the TA link — OUR ADDITION, not the paper's

visualization/
  network_graph.py      the live four-tier topology

tests/
  test_correctness.py   the gate: the paper's equation must balance
  test_crt.py           the key phase, including the declared correction
```

**The one rule:** the protocol layer imports `crypto.interface` and never a
crypto library directly. That is what makes the two backends interchangeable and
what stops a fast approximation from leaking into a "faithful" measurement.

---

## The two backends

| | Faithful | Abstracted |
|---|---|---|
| G1 | BN128 elliptic curve | integers mod *q* |
| Pairing | real Ate pairing | exponentiation in Z*_p |
| Bilinear? | yes | **yes** — genuinely |
| Secure? | yes | **no** — the discrete log is trivial |
| Speed | ~190 ms per pairing | instant |
| Practical *n* | ≤ 30 interactively | ≤ 1000 |

The abstracted backend is **not** a hash-based fake. `e(aP, bP) := g^(ab) mod p`
with `g` of order *q* is a real bilinear map, which is why the paper's
verification equation balances there for exactly the same algebraic reason it
balances on a curve — and fails for exactly the same reasons. The all-or-nothing
batch behaviour, the revocation behaviour and the replay behaviour are all
reproduced faithfully. What it does not provide is hardness.

---

## Two things this simulator measures that the paper does not

### 1. The TA-side cost

Every pairing in the protocol happens in Step GA2, on the trusted authority. The
TUAV performs only target-group multiplications and two exponentiations. Measured
on a typical laptop with the faithful backend:

| n | TUAV side | TA side | ratio |
|---|---|---|---|
| 20 | ~25 ms | ~11.5 s | ~470× |
| 60 | ~28 ms | ~34.6 s | ~1200× |
| 120 | ~33 ms | ~69 s | ~2100× |

The paper's Table III reports the TUAV side. That is what makes its
group-authentication figure small. The pairings did not disappear — they moved.

### 2. The TA link

Step GA1 forwards every request across a satellite channel and Step GA3 cannot
be evaluated until Step GA2 returns. Set **availability → 0** in the sidebar:
authentication does not degrade, it **stops**. `test_correctness.py` asserts
this.

Both are our additions, clearly labelled as such in the UI and in the code.

---

## Honest boundaries

### Faithful to the paper

- Entity model and message flow, with the paper's own step labels
- Certificateless key split: TA issues `s_i`, the UAV draws `r_i`, both required
- The credential `Γ_i` computed exactly as printed
- Pseudonym derivation `ID_i = h3(id_i, ts2, ξ_i)`
- Real bilinear pairings (faithful backend)
- The aggregate verification equation of Step GA3, with its correctness
  reduction as a unit test
- The pairing offload, enforced architecturally — the TUAV object has no access
  to a pairing function

### Simplified, abstracted, or interpreted

- **CRT phase** — see *Declared correction* below
- **Abstracted backend** — bilinear but not secure; labelled at all times
- **Security theorems 1–5** — not reproduced. We demonstrate the corresponding
  *behaviour*, which is a weaker and different claim
- **Absolute timings** — not comparable. The paper reports MIRACL (C) at 80-bit;
  this is pure Python at BN128. Compare shape and slope, never milliseconds
- **Vehicle tier** — out of scope, as in the paper itself
- **Radio, mobility, channel** — absent, as in the paper

### Declared correction to the paper

The paper overloads the symbol `σ_i`. Step GA2 defines it as a **point**:

```
σ_i = h1(s_i · ξ_i) · P
```

and `ψ_i = e(Γ_i + h1(s_i ξ_i)P, P)` uses it that way, consistently. But Step
GD1 then writes `ω_i = ∏_{j≠i} σ_j` and `φ_i ≡ ω_i⁻¹ mod σ_i`, and Step GD6
computes `κ_tu = Λ(σ_i) mod σ_i`. None of those is defined for an elliptic-curve
point: you cannot multiply points together, invert modulo a point, or reduce
modulo a point.

Our reading, stated openly rather than papered over:

```
σ_i^point = h1(s_i · ξ_i) · P          used in GA2   (unchanged)
σ_i^int   = a prime derived from h1(s_i · ξ_i)   used in GD1–GD6
```

Primes make the moduli pairwise coprime, which `φ_i = ω_i⁻¹ mod σ_i` silently
requires and the paper never states. **Under this reading the paper's
construction is correct and we implement it verbatim** — `test_crt.py` proves
every member recovers the same key, revoked members do not, and survivors need
no new key material.

One further observation the paper does not make: the coefficients of `Λ(x)` grow
with the product of all moduli, so the "one broadcast" is O(n²) bits overall.
Table V does not account for this. We measure it rather than assume it away.

---

## What can honestly be compared with the paper

| Paper reports | Comparable? |
|---|---|
| GA cost is linear in *n* with a small slope | **Yes** — structural |
| Signing cheaper than pairing-based baselines | **Yes** — operation counts |
| Communication overhead is lower | **Yes** — near-exact; sizes are stated |
| 1.82 ms / 2.16 ms / 151 ms at n=120 | **No** — different language, curve and machine |
| Security theorems 1–5 | **No** — a demonstration is not a proof |

---

## The adversaries

Four attacks are implemented. Three are blocked; **one is not**, and that is the
finding.

| Attack | Outcome | Stopped at |
|---|---|---|
| Replay (timestamp) | blocked | Step GA1 — outside the acceptance window |
| Replay (cryptographic) | blocked | Step GA3 — `R_tu` and `ID_tu` were regenerated |
| Impersonation | blocked | Step GA3 — the TA resolves `ID_i` to the real `s_i` |
| Revoked-key access | blocked | AES-GCM authentication tag |
| **Batch poisoning** | **SUCCEEDS** | nothing — Step GA4 has no else-branch |

Replay is defended **twice**, and the simulator shows both. Switch off the
timestamp check and a replayed credential still fails, because the TUAV draws a
fresh `r_tu` each session — that is the cryptographic half of Theorem 3, and it
needs no check at all.

`test_attacks.py` asserts each of these, including the one that succeeds:

```python
def test_batch_poisoning_succeeds_against_the_published_scheme():
    assert not res.blocked, "the published scheme has no defence here"
    assert res.detail["culprit identified"] == "NO"
```

## The security board does not overclaim

The paper's Table II ticks eleven properties. This simulator reports three
evidence levels instead of ticks:

- **DEMONSTRATED** — an adversary was run and failed
- **STRUCTURAL** — follows from the construction, asserted by a unit test
- **NOT SHOWN** — a proof, or outside scope

**Two of the eleven are marked NOT SHOWN.** Forward secrecy (F7) is claimed in
Table II but never analysed in Section V, so we do not claim it either.
Non-repudiation (F10) needs a signed audit record, which we do not keep.

A test enforces this: `test_security_board_never_claims_proof`.

## Measured results

Both headline figures come from the **published scheme's own behaviour** — no
modification is needed to produce either.

### The availability cliff (E7)

| TA link availability | Authentication success rate |
|---|---|
| 100% | 100% |
| 50% | ~38% |
| 10% | **0%** |
| 0% | **0%** |

Not "degraded" — zero. Step GA3 cannot be evaluated without the TA's response,
so there is nothing to fall back to.

### Batch poisoning (E8), n = 20

| Forged credentials | Published scheme | With individual fallback |
|---|---|---|
| 0% | 100% goodput | 100% |
| **5%** (one packet) | **0% goodput** | 95% |
| 20% | 0% goodput | 80% |

One forged packet in twenty denies authentication to all nineteen honest
members. The fallback column is **not** part of the published scheme — Step GA4
has no else-branch.

### Where the work happens

Run E1 on the faithful backend and the Performance tab reports the ratio
directly. The TUAV side stays in the tens of milliseconds while the TA side runs
into tens of seconds, because every pairing in the protocol is in Step GA2.

## Two observations about Table V

The paper's per-request figure of 104 bytes decomposes as
`4 + 20 + 20 + 20 + 40` — so `Γᵢ` is counted as a **40-byte element of G**. But
Step GA2 computes `ψᵢ = e(Γᵢ + h1(s_i ξ_i)P, P)`, and a pairing argument must
live in **G₁, which the same section sizes at 128 bytes**. `Γᵢ` cannot be both.

The same conflation appears in Table III, where the proposed scheme's signing
cost uses the plain-EC constants rather than the pairing-group ones.

We do not assert the paper is wrong — both groups are defined in Section VI-A
and the intent may be a construction we cannot recover from the text. The
simulator reports **both accountings side by side** (104 B and 192 B) and says
why they differ, because a reader comparing our byte counts against Table V
deserves to know.

Table V also counts none of: the Step GA1 uplink, the Step GA2 downlink, or the
Step GD4 key broadcast. All three are reported separately on the Performance tab.

## Presentation mode

A nine-step guided demo: one idea per screen, the single number that matters,
and a line telling you what to say. Each step declares its precondition, so it
tells you "run authentication first" rather than showing an empty panel in front
of an examiner.

Toggle it at the bottom of the sidebar.

## Status

**Complete — all three stages.** 71 passing tests, 33 modules, ~6,200 lines.

| Tab | What it shows |
|---|---|
| Network | Live four-tier topology, UAV table, event log |
| Protocol run | Steps US1–US3, GA1–GA4, the TUAV/TA cost split |
| Group key | CRT distribution, key holders, the declared correction |
| Attacks | Replay ×2, impersonation, revoked access, batch poisoning |
| Anonymity | Pseudonyms across sessions, TA-only identity retrieval |
| Secure exchange | AES-GCM under the group key |
| Security board | F1–F11 with three evidence levels |
| Performance | E1/E7/E8 sweeps, Table III, overhead, transcription check |
| Paper vs us | Fidelity table, what is and is not comparable |
| Results | Full status, adversary outcomes, event log |
| About | The research, in plain language |

---

## For the viva

> "We implemented a simplified simulation of the proposed scheme, using real
> bilinear pairings where the library permitted and a clearly-labelled
> abstraction where it did not. We used it to demonstrate authentication, group
> key management, dynamic UAV joining and revocation, and performance behaviour.
> We additionally measured the trusted-authority-side cost and the authority
> link, neither of which the paper reports. The simulator is an educational and
> experimental implementation, not a reproduction of the paper's cryptographic
> benchmark environment."
