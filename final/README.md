# Cutting the Cord — final phase

Analysis, design, formal verification, implementation and measured evaluation of an
authority-independent authentication and key-management framework for TUAV-assisted
infrastructure-less IoV, building on Tan, Zheng & Vijayakumar (IEEE T-ITS 24(6), 2023).

| Folder | Content |
|---|---|
| `cutcord/` | Reference implementation: `base.py` (the base scheme as printed), `ours.py` (C1 UAV tier, C2 vehicle tier, C3 handover, offline TA) |
| `tests/` | 20 tests — correctness of both schemes, every attack, every defence |
| `experiments/` | `run_all.py` (E0–E7), `make_figures.py`, `make_macros.py` |
| `results/` | CSV outputs, `summary.json`, `macros.tex` (numbers quoted by the report and paper) |
| `figures/` | Generated figures (PDF and PNG) |
| `proverif/` | Five ProVerif 2.05 models, their outputs (`*.out`) and `RESULTS.txt` |
| `report/` | Final report (LaTeX, chapters) |
| `paper/` | Research paper (IEEE conference format) |

## Reproduce

Run everything from this folder.

```bash
python -m pip install py_ecc cryptography sympy matplotlib pytest
python -m pytest -q                                  # 20 passed
python experiments/run_all.py                        # E0–E7 (slow: pure-Python pairings)
python experiments/run_all.py --only=e2,e3,e5,e6     # re-run selected experiments
python experiments/make_figures.py
python experiments/make_macros.py
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
* Timings are cross-checked against exact operation counts multiplied by median primitive
  costs (E0). The two agree closely, so the results do not depend on machine noise.
* Satellite round-trip time and link availability are model parameters, not measurements.
