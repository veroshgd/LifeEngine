"""
v3 mechanistic revalidation — same seeds against v2, only COND_RECOVER_AT changed
=================================================================================

Run:  python v3_revalidate.py                (full run, about 1 hour, 13 processes)
      python v3_revalidate.py --quick        (N=300/BOOT=500, about 5 minutes, direction first)
      python v3_revalidate.py --only 021     (021§3 only)

★ This is not a new confirmatory experiment ★
---------------------------------------------
We have already seen the data, changed the model, and 65 was itself picked by a diagnostic experiment.
So the correct name for this step is **v3 mechanistic revalidation / robustness reanalysis**; it answers
"what happens to the conclusions that depended on the survival confound once it is fixed", and
**it cannot carry the final confirmation**. Final confirmation waits until the model is fully frozen
and uses a block of seeds that has never been run.

★ Why old seeds — this is an advantage, not a problem ★
The only variable is `COND_RECOVER_AT: 30 → 65`. A same-seed comparison attributes "the conclusion
changed" cleanly to that one number, rather than to "a different batch of balls".

★ Where the v2 arm comes from ★
`v2_frozen/` was compared bit for bit with the main directory: **the only executable difference is
COND_RECOVER_AT** (everything else is comments and the new MODEL_VERSION). So the v2 arm = setting it
back to 30.0 in the v3 code, exactly equivalent to running `v2_frozen/` but without the bother of two import paths.

Which three are revalidated (011–020 are not re-run — they are development history and their job is done):

  021 §3   floor ablation       does `−all floors ①②` still stand at N=1500
  022 P1   no floors > 1 after wiring   preregistered criterion: bootstrap CI lower bound > 1.00
  022 P2   non-nested deletion   does deleting knowledge collapse the persistence

Plus a **hardship trigger diagnosis** (the direct to-do of rule 50):
`fears_hunger` trigger rate / day of first trigger / anchor presence rate / survival rate.
⚠ Main effects are always reported on **all predefined seeds**, not just the 86% that triggered —
   "whether it triggered" is itself a product of the simulation, and selecting triggerers afterwards
   re-creates a selection effect. Results within the triggerers are secondary descriptive analysis only.
"""

import argparse
import io
import multiprocessing as mp
import os
import time
from contextlib import redirect_stdout

WA, WB, COMMON = "rich world", "barren world", "baseline"
VERSIONS = [("v2", 30.0), ("v3", 65.0)]
K22 = (12.0, 0.25, 0.02)          # the KNOWLEDGE_* trio when 022 is on
CHUNK = 250


def _setup(rec_at):
    import sim
    sim.COND_RECOVER_AT = rec_at
    sim.COND_DEADZONE_RECOVER = 0.0
    sim.COND_SHELTER_RECOVER = 0.0
    return sim


# ---------------------------------------------------------------- 021 §3
def task_021(job):
    ver, rec_at, seed0, label, cfg, n_seeds, n_perm = job
    sim = _setup(rec_at)
    import significance_main as S
    S.N_PERM = n_perm
    sim.KNOWLEDGE_WEIGHT = sim.KNOWLEDGE_GOAL_WEIGHT = sim.KNOWLEDGE_FORGET = 0.0
    buf = io.StringIO()
    with redirect_stdout(buf):
        S.run(label, cfg, n_seeds, seed0)
    return ("021", ver, f"seeds {seed0}+", label, buf.getvalue().strip(), None)


# ---------------------------------------------------------------- 022 P1
def task_p1(job):
    ver, rec_at, tag, kw, label, cfg, n_seeds, n_boot, n_perm = job
    sim = _setup(rec_at)
    import p1_test as P
    P.N_SEEDS, P.N_BOOT, P.N_PERM = n_seeds, n_boot, n_perm
    sim.KNOWLEDGE_WEIGHT, sim.KNOWLEDGE_GOAL_WEIGHT, sim.KNOWLEDGE_FORGET = kw
    buf = io.StringIO()
    with redirect_stdout(buf):
        ret = P.analyse(label, cfg)
    return ("P1", ver, tag, label, buf.getvalue().strip(), ret)


# ---------------------------------------------------------------- 022 P2
def task_p2(job):
    ver, rec_at, label, wipe, n_seeds, n_boot = job
    sim = _setup(rec_at)
    import p2_test as P
    import p1_test as P1
    P.N_SEEDS, P1.N_BOOT = n_seeds, n_boot
    sim.KNOWLEDGE_WEIGHT, sim.KNOWLEDGE_GOAL_WEIGHT, sim.KNOWLEDGE_FORGET = K22
    buf = io.StringIO()
    with redirect_stdout(buf):
        ret = P.analyse(label, wipe)
    return ("P2", ver, "seeds 20000+", label, buf.getvalue().strip(), ret)


# ------------------------------------------------- hardship trigger diagnosis (rule 50)
def task_trigger(job):
    """Every seed is counted — the dead included, with no post-hoc filtering"""
    ver, rec_at, world, floor_off, seed0, n = job
    sim = _setup(rec_at)
    import scenarios
    import persistence_ablation as PA
    sim.KNOWLEDGE_WEIGHT, sim.KNOWLEDGE_GOAL_WEIGHT, sim.KNOWLEDGE_FORGET = K22

    alive = trig = anchor = 0
    first_days = []
    scenarios.make = PA.patched_make(False, floor_off)
    try:
        for s in range(seed0, seed0 + n):
            life = scenarios.make(s, world)
            ag = life.agent
            first = None
            dead = False
            for day in range(60):
                if day == 30:                       # transplanted to baseline on day 30
                    w = sim.World(s, **scenarios.WORLDS[COMMON])
                    life.world, ag.world = w, w
                for t in range(sim.TICKS_PER_DAY):
                    life.world.tick(day, t)
                    for inf in life.influences:
                        inf(life.world, ag, day, t, life.inf_rng)
                    ag.tick(day, t)
                    if first is None and "fears_hunger" in ag.flags:
                        first = day
                    if not ag.alive:
                        dead = True
                        break
                if dead:
                    break
                ag.daily(day)
            alive += not dead
            if first is not None:
                trig += 1
                first_days.append(first)
            if getattr(ag, "_hardship_anchor", None) is not None:
                anchor += 1
    finally:
        scenarios.make = PA._orig_make
    return ("TRIG", ver, world, "all floors off" if floor_off else "full architecture",
            (alive, trig, anchor, first_days, n))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--only", default="all",
                    help="all / 021 / p1 / p2 / trig (comma-separated)")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args()

    N = 300 if a.quick else 1500
    BOOT = 500 if a.quick else 3000
    PERM = 2000 if a.quick else 10000
    want = {w.strip() for w in a.only.split(",")} if a.only != "all" \
        else {"021", "p1", "p2", "trig"}

    jobs = []
    if "021" in want:
        for ver, rec in VERSIONS:
            for seed0 in (0, 10000):
                for label, cfg in [("full architecture", dict()), ("−all floors ①②", dict(floor=True))]:
                    jobs.append((task_021, (ver, rec, seed0, label, cfg, N, PERM)))
    if "p1" in want:
        for ver, rec in VERSIONS:
            for tag, kw in [("022 off", (0.0, 0.0, 0.0)), ("022 on", K22)]:
                for label, cfg in [("full architecture", dict()), ("−all floors ①②", dict(floor=True))]:
                    jobs.append((task_p1, (ver, rec, tag, kw, label, cfg, N, BOOT, PERM)))
    if "p2" in want:
        for ver, rec in VERSIONS:
            for label, wipe in [("① delete nothing (=P1)", set()),
                                ("② delete semantic knowledge only", {"semantic"}),
                                ("③ delete episodic memories only", {"episodic"}),
                                ("④ delete flags only", {"flags"}),
                                ("⑤ delete semantic+episodic+flags", {"semantic", "episodic", "flags"})]:
                jobs.append((task_p2, (ver, rec, label, wipe, N, BOOT)))
    if "trig" in want:
        for ver, rec in VERSIONS:
            for world in (WA, WB):
                for fo in (False, True):
                    for s0 in range(20000, 20000 + N, CHUNK):
                        jobs.append((task_trigger,
                                     (ver, rec, world, fo, s0, min(CHUNK, 20000 + N - s0))))

    print(f"v3 mechanistic revalidation   {len(jobs)} tasks   N={N} BOOT={BOOT} PERM={PERM}   "
          f"processes {a.workers}")
    print("Only variable: COND_RECOVER_AT  v2=30.0  vs  v3=65.0\n", flush=True)

    t0, out = time.time(), []
    with mp.Pool(a.workers) as pool:
        for k, r in enumerate(pool.imap_unordered(_dispatch, jobs), 1):
            out.append(r)
            el = time.time() - t0
            print(f"  [{k}/{len(jobs)}] {r[0]:<5}{r[1]:<4}{str(r[2]):<14}{r[3]:<22}"
                  f"elapsed {el/60:.1f}min remaining ~{el/k*(len(jobs)-k)/60:.1f}min", flush=True)

    report(out, N)


def _dispatch(job):
    fn, args = job
    return fn(args)


def report(out, N):
    for tag, title, hdr in [
            ("021", "021 §3 · floor ablation (022 off)",
             f"  {'condition':<20}{'numerator TV':>14}{'baseline TV':>13}{'ratio':>8}"
             f"{'mean δ':>10}{'dz':>7}{'δ>0':>8}{'p':>10}"),
            ("P1", "022 P1 · can the no-floor variant still exceed 1 after wiring", None),
            ("P2", "022 P2 · non-nested deletion", None)]:
        rows = [r for r in out if r[0] == tag]
        if not rows:
            continue
        print("\n" + "=" * 108)
        print(f" {title}   ★ v2 vs v3, same seeds ★")
        print("=" * 108)
        groups = sorted({(r[2], r[3]) for r in rows})
        for grp, label in groups:
            print(f"\n  ── {grp} · {label} ──")
            for ver, _ in VERSIONS:
                line = next((r[4] for r in rows
                             if r[1] == ver and r[2] == grp and r[3] == label), None)
                if line:
                    print(f"    {ver}  {line.strip()}")

    trig = [r for r in out if r[0] == "TRIG"]
    if trig:
        print("\n" + "=" * 108)
        print(" hardship trigger diagnosis (rule 50) ★ all predefined seeds, no post-hoc filtering ★")
        print("=" * 108)
        print(f"  {'version':<9}{'world':<14}{'architecture':<20}{'alive%':>8}"
              f"{'trigger%':>10}{'anchor%':>10}{'median first-trigger day':>26}")
        print("  " + "-" * 74)
        agg = {}
        for _, ver, world, arch, (al, tr, an, fd, n) in trig:
            a_, t_, an_, f_, n_ = agg.get((ver, world, arch), (0, 0, 0, [], 0))
            agg[(ver, world, arch)] = (a_ + al, t_ + tr, an_ + an, f_ + fd, n_ + n)
        for key in sorted(agg):
            al, tr, an, fd, n = agg[key]
            fd_sorted = sorted(fd)
            med = fd_sorted[len(fd_sorted) // 2] if fd_sorted else float("nan")
            print(f"  {key[0]:<5}{key[1]:<10}{key[2]:<10}{al/n:>7.1%}"
                  f"{tr/n:>9.1%}{an/n:>9.1%}{med:>15.0f}")
        print("\n  ⚠ The v2→v3 drop in trigger rate must go into the report of the 021§3 re-run — the denominator of the ablation changed.")
        print("  ⚠ The main causal test uses all seeds; the triggerer subset can only be secondary descriptive.")


if __name__ == "__main__":
    mp.freeze_support()
    main()
