# Reproduction guide

```bash
pip install -r requirements.txt
pytest                       # < 1 minute; all green means the environment is sound
```

All it needs is **Python 3.10+ and the standard library**; `pytest` is used only for the
self-check. There are no third-party dependencies.

---

## Before you run anything: UTF-8 output is required

Several scripts print Unicode characters (`✓`, `★`) and Chinese labels. On Windows, Python
still defaults to the legacy `cp1252` console codec, which cannot encode them: the affected
scripts abort inside `print()` with `UnicodeEncodeError`, and the self-check suite then reports
failures that have nothing to do with model integrity.

Enable Python's UTF-8 mode first:

```powershell
$env:PYTHONUTF8 = "1"                                              # PowerShell, current session
[Environment]::SetEnvironmentVariable("PYTHONUTF8", "1", "User")   # or persist it, then reopen
```

```bash
export PYTHONUTF8=1          # Linux / macOS — usually already UTF-8, harmless to set
```

Verified environments:

| Environment | `tools/verify_provenance.py` | `pytest` |
|---|---|---|
| Linux, Python 3.12 (UTF-8 default) | 10/10 | 8/8 |
| Windows 11, Python 3.13, `PYTHONUTF8=1` | 10/10 | 8/8 |
| Windows 11, Python 3.13, **without** `PYTHONUTF8` | 10/10 | 6/8 |

In the last row both failures are `UnicodeEncodeError` raised by `print()` in
`novel_calibrate3.py` and `final_confirm.py`. No integrity check, hash comparison, or numerical
result is affected — `tools/verify_provenance.py` passes 10/10 in all three environments.

---

## Independent provenance verification

`final_029.py` is the historical one-shot confirmation runner and is left byte-unchanged,
including its absolute `PREREG_PATH`, which points at the machine used at confirmation time.
That path does not exist in a fresh clone, so the runner's own preflight prints "cannot find"
for the preregistration line. This is expected and is disclosed in Appendix B.9 of the paper.

To verify the chain without modifying the historical runner:

```bash
python tools/verify_provenance.py
```

It recomputes, from this repository alone, the SHA-256 of the preregistration document, the six
frozen runtime modules recorded in `final_029.py`, both frozen model directories, and the frozen
Experiment 028 interface, and compares each against the constants recorded before the
confirmatory runs. Exit code 0 means every artifact matches.

---

## Three levels of reproduction

| Level | Command | Time | What it proves |
|---|---|---|---|
| **① self-check / regression** | `pytest` | < 1 minute | frozen integrity, model provenance, mechanism layer, determinism |
| **② small-scale smoke test** | see below | ~15 minutes | the **direction** of the core results reproduces |
| **③ full reproduction** | see below | ~4 hours | the **specific numbers** in the paper |

### ① Self-check / regression

```bash
pytest
```

Verifies the SHA256 of `v2_frozen/` and `v3_frozen/`; asserts that the model really is imported
from `v3_frozen` with `MODEL_VERSION == "v3"` and `COND_RECOVER_AT == 65.0`; uses an **AST
comparison** to confirm that the only executable v2 → v3 difference is still that one constant;
runs the 6 mechanism-layer self-checks; verifies the rule 72 window regression; and verifies
that two runs of the same seed are bit-identical.

### ② Small-scale smoke test (direction, not numbers)

```bash
python novel_situation.py                        # the 8 mechanism-layer self-checks
python final_confirm.py --check                  # the frozen-verification gate
python final_confirm.py --seed0 20000 --n 200    # the main analysis pipeline (small N)
python rule71_ablation.py --seeds 50 --workers 4 # the causal direction of TRAIT_DRIFT
```

⚠ At small N the point estimate is biased upward (rule 34: the ratio estimator is inflated at
small N), so **read the direction only**.

### ③ Full reproduction (the paper's numbers)

```bash
# Final confirmation (preregistered, seeds 50000–51499, run once)  ~1.5 hours
python final_confirm.py --final

# v3 parameter robustness  500 configs × 300 seeds  ~45 minutes
python param_sweep.py --configs 500 --seeds 300 --out sweep_results_v3.csv
python sweep_report.py sweep_results_v3.csv

# v2→v3 same-seed revalidation (experiment 023 §7)  ~40 minutes
python v3_revalidate.py

# Rule 71 causal ablation  ~20 minutes
python rule71_ablation.py --seeds 300
```

---

## Which model each result came from — read this table

| Artefact | Model | Standing |
|---|---|---|
| `final_confirm_result.txt` | **v3_frozen** | ★the preregistered final confirmation★ (seeds 50000–51499, run once) |
| `sweep_results_v3.csv` | **v3_frozen** | v3 parameter robustness (the paper uses this one) |
| output of `rule71_ablation` | **v3_frozen** | TRAIT_DRIFT causal ablation (exploratory; the directional prediction was fixed beforehand) |
| `sweep_results.csv` / `holdout.csv` | **v2** | ⚠ **development history**, header carries no version column. The paper must not cite it as v3 robustness |
| `final_confirm_result.VOID_bug.txt` | — | ⚠ **void**: the empty run caused by the chunk-indexing bug, kept as a process record |
| every number from experiments 011–022 | **v2** | development history, **kept and not overwritten** |
| experiment 026 (novel-situation) | v3_frozen | **negative result**: all four probes retired |

> Experiments 011–022 were conducted under model v2 and are retained as
> development history rather than overwritten by subsequent model correction.

---

## Seed ledger (which blocks are burned)

| Block | Use | Still usable as a holdout |
|---|---|---|
| `0–1499` | development | ✗ |
| `10000–11499` | 021 holdout set (inspected many times) | ✗ |
| `20000–21499` | 022 preregistration block / all group-blind calibration | ✗ |
| `50000–51499` | **final confirmation, used once** | ✗ |
| `60000–61499` | once reserved for the 026 final — **026 was closed and it was never used** | ✓ clean |

---

## Layout

```
v2_frozen/     the v2 frozen snapshot (COND_RECOVER_AT = 30) + SHA256SUMS.txt
v3_frozen/     the v3 frozen snapshot (COND_RECOVER_AT = 65) + SHA256SUMS.txt  ★the paper's model★
tests/         the pytest self-check
tools/         path-independent provenance verifier (not part of any frozen manifest)
FINAL_PREREGISTRATION.md      the full preregistration (including amendment A)
NOVEL_SITUATION_DESIGN.md     the 026 design (closed)
```

The `*.py` files in the root are **experiment scripts**, not pytest tests — running them takes
tens of minutes of simulation. `pytest.ini` restricts collection to `testpaths = tests` and
excludes the two frozen directories (which hold modules of the same name and must not be edited).

**Deprecated** (kept for history, do not use): `sweep.py`, `food_sweep.py`.
**Retired** (the calibrations of 026's four probes, kept as evidence of a negative result):
`novel_calibrate.py`, `novel_calibrate2.py`, `novel_calibrate3.py`.
