# v3 — frozen (the paper's candidate architecture)

Frozen on: 2026-08-15
`MODEL_VERSION = "v3"` · `COND_RECOVER_AT = 65.0`
Verification: `SHA256SUMS.txt` (full 64-character sha256, 32 files)

## ★ What freezing means ★

**From this moment on, the default mechanisms of `sim.py` are not changed again.**

Any later experiment (anchor probe, state transplant, novel-situation generalization…) may exist
only as an **experiment-level intervention**: temporarily change the state of an agent instance
inside the experiment script, or temporarily set a switch on `sim.`, and restore it afterwards.
Changing a v3 default to make some experiment easier is **not allowed**.

If an experiment exposes a structural problem that forces a model change — then **fork v4 and go
through the whole freezing procedure again**, recording explicitly which v3 conclusions are
invalidated as a result. Do not edit v3 in place.

## Differences from v2

The only executable difference: `COND_RECOVER_AT` in `sim.py`, `30.0 → 65.0`
(plus the newly added `MODEL_VERSION` constant). The v2 snapshot is in `../v2_frozen/`.

The reasoning is in §3h of `SIMULATION_LOG.md` (rule 49: the sloth valley) and experiment 023.

## The revalidation v3 has already passed (experiment 023 §7, N=1500, same seeds against v2)

```
                          v2                    v3
60-day mortality          7.5–8.1%              4.1–4.3%
022 P1                    1.058 [1.029,1.102]   1.090 [1.047,1.128]   ✓ pass
022 P2                    ✗ fail                 ✗ fail                 the preregistered conclusion is unchanged
021§3 no floors           1.032 / 1.034 n.s.    1.036 n.s. / 1.057 **  ⚠ inconsistent across blocks (rule 52)
episodic-memory deletion  bit-identical no-op    bit-identical no-op    rule 41 strengthened
```

## ⚠ Seeds not yet used

**The seed block of the final confirmation must be one that has never been run.**
Blocks already used: `0–1499` (development), `10000–11499` (reserved for 021, inspected many
times), `20000–21499` (reserved for the 022 preregistration, used for P1/P2 and the 023
revalidation).

⚠ **None** of those three may serve as the final holdout. The final block is named in
`FINAL_PREREGISTRATION.md`; **do not run it** before the preregistration is fixed in writing.
