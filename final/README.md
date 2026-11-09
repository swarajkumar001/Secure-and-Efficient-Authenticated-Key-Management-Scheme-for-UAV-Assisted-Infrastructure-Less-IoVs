# Cutting the Cord — final phase

Analysis, design, formal verification, implementation and measured evaluation of an
authority-independent authentication and key-management framework for TUAV-assisted
infrastructure-less IoV, building on Tan, Zheng & Vijayakumar (IEEE T-ITS 24(6), 2023).

| Folder | Content |
|---|---|
| `cutcord/` | Reference implementation: `base.py` (the base scheme as printed), `ours.py` (first design: C1 UAV tier, C2 vehicle tier, C3 handover, offline TA), `hardened.py` (fixes A1–A7, C4) |
| `tests/` | 57 tests — correctness of all designs, every attack, every defence |
| `experiments/` | `run_all.py` (E0–E7), `run_e8.py` (E8), `make_figures.py`, `make_macros.py` |
| `results/` | CSV outputs, `summary.json`, `macros.tex` (numbers quoted by the report and paper) |
| `figures/` | Generated figures (PDF and PNG) |
| `proverif/` | Eight ProVerif 2.05 models and `RESULTS.txt` (raw `*.out` files are not committed) |
| `report/` | Final report (LaTeX, chapters) |
| `paper/` | Research paper (IEEE conference format) |

## Hardened design and C4

`cutcord/ours.py` is the first design, kept unchanged so E0–E7 stay reproducible. `cutcord/hardened.py` fixes
seven flaws found in it (A1–A7) and adds C4, quorum eviction of a captured TUAV. `tests/test_hardened.py` runs each attack
against both designs. `experiments/run_e8.py` writes `results/e8_*`, `figures/f7_containment.*`.

Three ProVerif models give the attacker a captured TUAV (its link key, the member's pairwise key and
its own credential):

| Model | Design | Result |
|---|---|---|
| `c3_captured_ticket_only.pv` | first design (ticket alone) | attack: a member is accepted without starting anything, and the neighbour's group key leaks (A2) |
| `c3_captured_noreplysig.pv` | hardened, before A7 | new-TUAV side holds, but the member can complete a handover with the captured TUAV posing as the new one, and its data is not secret (A7) |
| `c3_captured_bound.pv` | hardened, with A7 | all five queries hold: authentication both ways, group-key secrecy, forward secrecy |

A7 was found this way. The fix: the new TUAV signs its handover reply under its own credential and the member
checks it (`HardenedTUAV.accept_handover`, `HardenedMember.handover_finish`). `run_e8.py --only=e8d` re-measures
the handover cost after the fix and keeps the other E8 numbers.

## Reproduce

Run everything from this folder.

```bash
python -m pip install py_ecc cryptography sympy matplotlib pytest
python -m pytest -q                                  # 57 passed
python experiments/run_all.py                        # E0–E7 (slow: pure-Python pairings)
python experiments/run_all.py --only=e2,e3,e5,e6     # re-run selected experiments
python experiments/make_figures.py
python experiments/make_macros.py
python experiments/run_e8.py                         # E8 (add --only=e8d for the handover cost only)
cd proverif && ../tools/proverif2.05/proverif.exe -lib common c1_typeI.pv
cd report && pdflatex final_report && pdflatex final_report
cd paper  && pdflatex paper && pdflatex paper
```

ProVerif is not vendored. Download the official Windows binary (`proverifbin2.05.tar.gz`)
from the ProVerif website and unpack it into `tools/`.

## Measurement notes

* Both schemes run on BN254 through `py_ecc` (pure Python) in the same process, back to back
  for each swarm size, so measured ratios are fair. Absolute times are far slower than an
  optimised C library.
* The laptop's speed drifted during the runs, so E2 also reports a load-independent ratio from
  exact operation counts multiplied by median primitive costs (E0).
* The E8 handover figures were re-measured after fix A7 on a slower machine than the rest of E8;
  compare them with each other only.
* Satellite round-trip time and link availability are model parameters, not measurements.
