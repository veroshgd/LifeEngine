"""
Version marker for raw results — every CSV must carry it
========================================================

v2 → v3 differ by a single number (`COND_RECOVER_AT` 30 → 65), and **the file contents
give no hint of it**. Six months later you find a csv and, without a version column, you
are reduced to guessing from the file date.

So the convention is: **the first four columns of any raw result written to disk are**

    model_version   model version (v2 / v3 / …)
    experiment      which experiment (021-3 / 022-P1 / …)
    condition       which arm (full architecture / −all floors ①② / …)
    seed            seed (or the start of the seed block)

Usage:

    from resultmeta import META_FIELDS, meta
    FIELDS = META_FIELDS + ["ratio", "p", ...]
    w.writerow({**meta("021-3", "full architecture", seed), "ratio": r, ...})

⚠ `meta()` reads `sim.MODEL_VERSION` and `sim.COND_RECOVER_AT` **at call time**, so changing
   the sim globals inside a subprocess is still recorded faithfully — which is the point:
   it records not "which version I thought I ran" but "which version actually ran".
"""

META_FIELDS = ["model_version", "experiment", "condition", "seed",
               "cond_recover_at"]


def meta(experiment, condition, seed):
    import sim
    return {
        "model_version": getattr(sim, "MODEL_VERSION", "v2"),
        "experiment": experiment,
        "condition": condition,
        "seed": seed,
        # Redundant but worth it: this is the only difference between v2/v3, so no need to dig through the code when something goes wrong
        "cond_recover_at": sim.COND_RECOVER_AT,
    }
