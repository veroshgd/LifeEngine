"""
Experiment 027 runner — executed strictly according to NOVEL_TASK_PREREGISTRATION.md
====================================================================================

Rehearsal (burned seeds, run freely):
    python final_027.py --check                      frozen verification only
    python final_027.py --seed0 20000 --n 300        full-pipeline rehearsal
    python final_027.py --seed0 20000 --n 300 --workers 5   rule 55 self-check

Official run (**allowed exactly once**):
    python final_027.py --final

★ v4 = the v3_frozen core (byte-for-byte untouched) + novel_task.py ★
At startup `v3_frozen/SHA256SUMS.txt` and the task configuration fingerprint are verified; either mismatch refuses the run.

★ The four arms ★
    main            beta_i = β × novelty_style_i        main analysis
    hist_blind      beta_i = β × 0.5 (identical for everyone)   control three
    trait_level     curiosity/caution levelled at the task entrance   control four
    (controls one/two live in the self-checks of `novel_task.py`, which pytest also runs)

⚠ **Controls three/four = pathway-isolation / leakage controls (downgraded in amendment 01)**:
  the task's input surface is **only** `novelty_style = f(curiosity, caution)`,
  so both "fix beta" and "level curiosity/caution" make the twins identical within the task.
  They are therefore **two leakage detectors at two implementation layers** (one inside NovelTask,
  one on the agent-state side); they **cannot** count as two independent negative controls,
  and still less can they be used to "discover another carrier of history" — the task leaves no input port for one.
"""

import argparse
import hashlib
import os
import random
import statistics
import multiprocessing as mp
import sys
import time

import novel_task as NT

HERE = os.path.dirname(os.path.abspath(__file__))
V3DIR = os.path.join(HERE, "v3_frozen")
WA, WB = "rich world", "barren world"
FINAL_SEED0, FINAL_N = 60000, 1500
CHUNK = 25
N_BOOT, N_PERM = 10000, 10000
BOOT_SEED, PERM_SEED = 20260817, 777
DIAG_SEEDS = [BOOT_SEED + 1000 * r for r in range(8)]   # decidability rehearsal
ATTRITION_GATE = 0.90
SESOI = 1.0          # amendment 01: a ±1 trial practical-equivalence region
ARMS = ("main", "hist_blind", "trait_level")


def preflight(verbose=True):
    sums = os.path.join(V3DIR, "SHA256SUMS.txt")
    bad = 0
    for line in open(sums, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        want, name = line.split(maxsplit=1)
        got = hashlib.sha256(open(os.path.join(V3DIR, name), "rb").read()).hexdigest()
        bad += 0 if got.startswith(want) else 1
    if bad:
        raise SystemExit(f"✗ v3_frozen verification failed ({bad} files) — refusing to run")
    fp = NT.assert_frozen()
    if verbose:
        print(f"✓ v3_frozen verification passed")
        print(f"✓ task parameters frozen  α={NT.ALPHA} β={NT.BETA} τ={NT.TAU}"
              f"  fingerprint {fp}")
        print(f"✓ model {NT.sim.MODEL_VERSION} → {NT.MODEL_VERSION}"
              f"  COND_RECOVER_AT={NT.sim.COND_RECOVER_AT}")
    return fp


def task_sim(job):
    """Run the 60-day v3 core → level → return the minimal state the task needs"""
    world, seed0, n = job
    import novel_situation as NS
    sim = NS.sim
    sim.COND_RECOVER_AT = 65.0                      # ★rule 55★ set explicitly
    sim.COND_DEADZONE_RECOVER = sim.COND_SHELTER_RECOVER = 0.0
    sim.SLEEP_SUPPRESS = sim.HUNGER_URGENCY = 0.0
    sim.SLEEP_EFF_FLOOR = 0.35
    sim.KNOWLEDGE_WEIGHT, sim.KNOWLEDGE_GOAL_WEIGHT, sim.KNOWLEDGE_FORGET = 12.0, 0.25, 0.02

    out = []
    for s in range(seed0, seed0 + n):
        life = NS.scenarios.make(s, world)
        ok, _ = NS.run_window(life, 0, 30)
        if ok:
            w = sim.World(s, **NS.scenarios.WORLDS["baseline"])
            ok, _ = NS.run_window(life, 30, 30, world=w)
        if not ok:
            out.append({"seed": s, "alive": False})
            continue
        NS.level_state(life.agent)
        t = life.agent.traits
        out.append({"seed": s, "alive": True,
                    "cur": t["curiosity"], "cau": t["caution"]})
    return world, seed0, out


def _dispatch(j):
    return j[0](j[1])


class _Agent:
    def __init__(self, cur, cau):
        self.traits = {"curiosity": cur, "caution": cau, "industry": 50.0}


def endpoints(rec):
    """primary = restricted switch latency; secondary = exploration rate on trials 1–10"""
    return NT.switch_latency_restricted(rec), NT.explore_rate(rec, 0, 10)


def run_arm(arm, ra, rb, seed):
    """Returns (rich's (L, E), poor's (L, E))"""
    if arm == "trait_level":
        m_cur = (ra["cur"] + rb["cur"]) / 2.0
        m_cau = (ra["cau"] + rb["cau"]) / 2.0
        agents = (_Agent(m_cur, m_cau), _Agent(m_cur, m_cau))
    else:
        agents = (_Agent(ra["cur"], ra["cau"]), _Agent(rb["cur"], rb["cau"]))
    blind = (arm == "hist_blind")
    x = NT.run_task(agents[0], seed, history_blind=blind)
    y = NT.run_task(agents[1], seed, history_blind=blind)
    return endpoints(x), endpoints(y)


def boot_ci(d, seed, n_boot=N_BOOT):
    rng = random.Random(seed)
    n = len(d)
    vals = sorted(statistics.mean(d[rng.randrange(n)] for _ in range(n))
                  for _ in range(n_boot))
    return vals[int(.025 * n_boot)], vals[int(.975 * n_boot)]


def perm_p(d, seed, n_perm=N_PERM):
    rng = random.Random(seed)
    obs = statistics.mean(d)
    hits = sum(1 for _ in range(n_perm)
               if abs(statistics.mean(x if rng.random() < .5 else -x
                                      for x in d)) >= abs(obs))
    return obs, (hits + 1) / (n_perm + 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--final", action="store_true")
    ap.add_argument("--seed0", type=int, default=20000)
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    a = ap.parse_args()

    fp = preflight()
    if a.check:
        return

    # ★★ machine enforcement of the closure rule ★★
    # Preregistration §8 says "allowed exactly once", but printing alone constrains nothing —
    # running it again would overwrite the same result file. This is made a hard stop.
    final_out = os.path.join(HERE, "final_027_result.txt")
    if a.final and os.path.exists(final_out):
        raise SystemExit(
            "✗ final_027_result.txt already exists: 027 FINAL has been run; refusing to run again."
            " (Preregistration §8: seeds 60000–61499 may be burned only once.)")

    seed0, N = (FINAL_SEED0, FINAL_N) if a.final else (a.seed0, a.n)
    if a.final:
        print("\n" + "!" * 76)
        print(f"!! 027 FINAL  seeds {seed0}–{seed0+N-1}  ——  this block may be run only once")
        print("!! No key design may be changed after seeing the result (preregistration §8)")
        print("!" * 76)
    else:
        print(f"\n[rehearsal] seeds {seed0}–{seed0+N-1}  N={N} —— not the final run, re-run freely")
        print("[rehearsal] only checks the code path / n / metrics / controls / determinism / statistical procedure")
        print("[rehearsal] ⛔ nothing is changed on the basis of the rich/poor effect\n")

    jobs = [(task_sim, (w, s0, min(CHUNK, seed0 + N - s0)))
            for w in (WA, WB) for s0 in range(seed0, seed0 + N, CHUNK)]
    planned = sum(j[1][2] for j in jobs)
    assert planned == 2 * N, f"✗ incomplete chunk coverage {planned} ≠ {2*N}"

    store = {WA: [None] * N, WB: [None] * N}
    t0 = time.time()
    with mp.Pool(a.workers) as pool:
        for k, (w, s0, recs) in enumerate(pool.imap_unordered(_dispatch, jobs), 1):
            store[w][s0 - seed0:s0 - seed0 + len(recs)] = recs
            if k % 20 == 0 or k == len(jobs):
                el = time.time() - t0
                print(f"  {k}/{len(jobs)}  elapsed {el/60:.1f}min", flush=True)

    # ---- validity gate (preregistration §6) ----
    dead_a = sum(1 for r in store[WA] if not r["alive"]) / N
    dead_b = sum(1 for r in store[WB] if not r["alive"]) / N
    pairs = [i for i in range(N) if store[WA][i]["alive"] and store[WB][i]["alive"]]
    keep = len(pairs) / N
    print("\n" + "=" * 96)
    print(f" Validity gate: rich pre-task mortality {dead_a:.2%} · "
          f"poor {dead_b:.2%} · valid twins {len(pairs)}/{N} = {keep:.2%}")
    if keep < ATTRITION_GATE:
        print(f" ✗ valid twins < {ATTRITION_GATE:.0%} → **validity compromised;"
              f" no strong conclusion is drawn** (preregistration §6)")
    else:
        print(f" ✓ passed (threshold {ATTRITION_GATE:.0%})")
    if not pairs:
        raise SystemExit("✗ no valid pairs — this is a failure, not a result")

    # ---- the three arms ----
    res = {}
    for arm in ARMS:
        dL, dE = [], []
        for i in pairs:
            (la, ea), (lb, eb) = run_arm(arm, store[WA][i], store[WB][i],
                                         seed0 + i)
            dL.append(la - lb)
            dE.append(ea - eb)
        res[arm] = {"dL": dL, "dE": dE}

    print("\n" + "=" * 96)
    tag = "FINAL" if a.final else "rehearsal (not final)"
    print(f" 027 {tag}   seeds {seed0}–{seed0+N-1}   n={len(pairs)}   fingerprint {fp}")
    print("=" * 96)
    print(f"  {'arm':<14}{'metric':<34}{'mean paired diff':>18}{'95% CI':>26}{'p':>10}")
    print("  " + "-" * 92)
    verdict = {}
    for arm in ARMS:
        for key, name in (("dL", "H2 restricted switch latency"),
                          ("dE", "H1 trial 1–10 exploration")):
            d = res[arm][key]
            lo, hi = boot_ci(d, BOOT_SEED)
            obs, p = perm_p(d, PERM_SEED)
            sig = (lo > 0) or (hi < 0)
            verdict[(arm, key)] = (obs, lo, hi, p, sig)
            print(f"  {arm:<12}{name:<28}{obs:>+12.4f}"
                  f"   [{lo:>+8.4f}, {hi:>+8.4f}]{p:>10.4f}"
                  + ("  *" if sig else ""))

    # ---- decidability rehearsal (rule 56) ----
    print("\n  Decidability diagnostic: re-run the main arm's CI with 8 analysis seeds")
    for key, name in (("dL", "H2"), ("dE", "H1")):
        los = [boot_ci(res["main"][key], sd)[0] for sd in DIAG_SEEDS]
        his = [boot_ci(res["main"][key], sd)[1] for sd in DIAG_SEEDS]
        npass = sum(1 for lo, hi in zip(los, his) if lo > 0 or hi < 0)
        sd_lo = statistics.stdev(los)
        print(f"    {name}  lower-bound range [{min(los):+.4f}, {max(los):+.4f}]"
              f"  MC SD {sd_lo:.4f}  judged significant {npass}/8"
              + ("   ⚠ decided by the analysis seed" if 0 < npass < 8 else ""))

    print("\n" + "=" * 96)
    print(" Reading (preregistration §2/§3)")
    print("=" * 96)
    o, lo, hi, p, sig = verdict[("main", "dL")]
    # ★Amendment 01★ three-valued reading: CI contains 0 / excludes 0 but overlaps ±1 / lies entirely beyond ±1
    if not sig:
        h2 = "✗ H2 unsupported (the 95% CI contains 0)"
    elif lo > SESOI or hi < -SESOI:
        h2 = "★ functionally meaningful reversal-transfer established ★"
    else:
        h2 = "◐ a history effect exists statistically, but **functional significance is not established** (the CI overlaps ±1)"
    print(f"  ★PRIMARY H2★  {h2}")
    print(f"     Δ={o:+.4f} trial  95% CI [{lo:+.4f}, {hi:+.4f}]  p={p:.4f}"
          f"   SESOI = ±{SESOI} trial")
    print(f"     positive = rich switches more slowly; negative = poor switches more slowly. **Two-sided, no direction assumed.**")
    print(f"     ⚠ A \"point estimate crosses the line\" reading is not used: with Δ=1.05 and CI=[0.20,1.90],")
    print(f"       the true value could be only 0.2 trials, so there is no confidence it exceeds the functional threshold.")
    o2, lo2, hi2, p2, sig2 = verdict[("main", "dE")]
    print(f"  secondary H1  {'✓' if sig2 else '✗'}   Δ={o2:+.4f}"
          f"  [{lo2:+.4f}, {hi2:+.4f}]  p={p2:.4f}")
    print(f"     ⛔ H1 must not substitute for the primary: H2 not significant → H1 significant ≠ 027 succeeded")

    print("\n  Controls three/four (leakage detectors):")
    for arm in ("hist_blind", "trait_level"):
        z = all(abs(x) < 1e-12 for x in res[arm]["dL"] + res[arm]["dE"])
        print(f"    {arm:<14}{'✓ exactly zero (no leakage)' if z else '✗ non-zero — there is leakage, the whole batch is void'}")
    print("    ⚠ The only path by which history enters the task is history→curiosity/caution→novelty_style→β_i,")
    print("      so these two controls are **equivalent by construction** and must both be zero.")
    print("      They check two different implementation layers (inside NovelTask / on the agent-state side),")
    print("      which is not redundant as engineering, but **does not count as two independent negative controls scientifically**.")
    print("      ✅ May be said: the history effect enters the new task via novelty style, as designed")
    print("      ⛔ May not be said: all carriers of history were searched and only traits were found")

    out = os.path.join(HERE, "final_027_result.txt" if a.final
                       else "final_027_rehearsal.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"027 {tag}  seeds {seed0}-{seed0+N-1}  n={len(pairs)}  fp={fp}\n")
        f.write(f"attrition rich={dead_a:.4f} poor={dead_b:.4f} keep={keep:.4f}\n")
        for (arm, key), v in verdict.items():
            f.write(f"{arm}\t{key}\t{v[0]:+.6f}\t{v[1]:+.6f}\t{v[2]:+.6f}\t{v[3]:.6f}\n")
    print(f"\nWritten to {out}")


if __name__ == "__main__":
    mp.freeze_support()
    main()
