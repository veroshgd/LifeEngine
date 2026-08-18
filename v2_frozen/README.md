# v2 / pre-condition-fix — frozen snapshot

Frozen on: 2026-08-15
Freeze point: `COND_RECOVER_AT = 30.0` (**before** the condition-recovery threshold correction)

> Experiments 011–022 were conducted under model v2 and are retained as
> development history rather than overwritten by subsequent model correction.

## What is in here

The **complete** source and raw results of `ai-sandbox/` as it stood before the change to v3 on
2026-08-15:

- every `.py` (including the experiment 022 diagnostic scripts `mortality_diagnose` /
  `fix_compare` / `cond_compare`, and the three scripts that settled v3: `cliff_probe` /
  `death_split` / `rule48_test`)
- `sweep_results.csv` (021 §4, 500 configs × 300 seeds)
- `holdout.csv` (the 021 holdout set, seeds 10000–10299)
- `SHA256SUMS.txt` (first 16 characters, for verifying that the snapshot has not been touched)

## What actually changed from v2 to v3

**One line only**: `COND_RECOVER_AT` in `sim.py`, `30.0 → 65.0`.
Every other parameter and every mechanism is bit-for-bit unchanged.

The reason is not "a parameter sweep found 65 gives the lowest mortality" but a complete
mechanistic account (see `SIMULATION_LOG.md` §3h, rule 49):

```
raise the recovery threshold → condition improves → survival urgency weakens → well-fed agents forage less
                             → hunger rises again → the **sloth valley** (mortality goes up, not down, at 55–60)
                             → by 65 the condition margin suffices to cross that negative-feedback stretch
                             → mortality falls again
```

## How to use it

To reproduce any historical number from 011–022:

```powershell
cd C:\Users\yinan\Desktop\ai-sandbox\v2_frozen
python <script name>.py
```

The snapshot is self-contained (every import resolves inside this directory), so it never
reaches the v3 `sim.py` one level up.

⚠ Do not change anything in this directory. If something needs changing, change the v3 copy
one level up.
