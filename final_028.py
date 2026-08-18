"""
Experiment 028 runner — executed strictly according to NOVEL_TASK028_PREREGISTRATION.md
=======================================================================================

Rehearsal (burned seeds, run freely):
    python final_028.py --check
    python final_028.py --seed0 10000 --n 300
    python final_028.py --seed0 10000 --n 300 --workers 5     rule 55 self-check

Official run (**allowed exactly once**):
    python final_028.py --final

★ Four engineering protections (preregistration §8) ★
    ① Seed guard          --final accepts only seed0=70000, N=1500
    ② One-shot lock       final_028_result.txt already exists → refuse
    ③ Preflight ledger    print and persist the full seed ledger before starting
    ④ Frozen verification v3_frozen SHA + task fingerprint + interface028 sha256

★ Reading order ★ **validity gates before the task outcome** — even once the outcome is computed,
  validity is judged first, to avoid interpretive freedom after seeing the result.
"""

import argparse
import hashlib
import multiprocessing as mp
import os
import statistics as st
import sys
import time

import interface028 as IF
import novel_task as NT
import stats028 as S

HERE = os.path.dirname(os.path.abspath(__file__))
V3DIR = os.path.join(HERE, "v3_frozen")
WA, WB = "rich world", "barren world"
FINAL_SEED0, FINAL_N = 70000, 1500
CHUNK = 25
ARMS = ("A", "Bp", "Bm", "Cp", "Cm")
SESOI = 1.0
# ⚠ This is **not** a binding gate: neither the 028 preregistration nor amendment 01 defines <90% as a criterion for G,
#   and it is not folded into primary_ok. The five arms use **exactly the same** survivor intersection,
#   so G is still decided solely by the C± transport gates.
#   It is a **pre-task attrition diagnostic**; it must be reported alongside A when A serves as the
#   027 sampling replication.
ATTRITION_REPORT_REF = 0.90

LEDGER = [
    ("0–1499", "development"),
    ("10000–11499", "021 holdout set / 028 transport rehearsal"),
    ("20000–21499", "022 preregistration block / 027 + 028 group-blind calibration"),
    ("50000–51499", "v3 persistence FINAL"),
    ("60000–61499", "027 novel-task FINAL"),
    ("70000–71499", "★028 breadth FINAL★"),
]


def acquire_burn_lock(dirpath, result_name, lock_name, payload):
    """★crash-safe burn lock★ created atomically before **any** trajectory is generated.

    The result file alone is not enough: if `--final` crashes halfway the result has not been written,
    yet the trajectories of the 70000 block have been generated — which by the preregistration already counts as burned.
    So a STARTED lock is created exclusively with `open(..., "x")` and **never deleted, even on a crash**.

        no STARTED               → never burned
        STARTED without result   → started but not completed normally; the seeds are burned, re-running is forbidden
        STARTED with result      → completed normally; re-running is forbidden
    """
    res = os.path.join(dirpath, result_name)
    lock = os.path.join(dirpath, lock_name)
    if os.path.exists(res) or os.path.exists(lock):
        raise SystemExit(
            "✗ 028 FINAL has started or completed; 70000–71499 is considered burned, refusing to run again."
            f" (STARTED={os.path.exists(lock)}  result={os.path.exists(res)})")
    with open(lock, "x", encoding="utf-8") as f:      # exclusive creation, raises if it already exists
        f.write(payload)
    return lock


def _test_burn_lock():
    """Unit test that never touches the final seeds"""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        acquire_burn_lock(d, "r.txt", "s.lock", "x")          # the first call succeeds
        try:
            acquire_burn_lock(d, "r.txt", "s.lock", "x")
        except SystemExit:
            pass
        else:
            raise AssertionError("✗ the second creation somehow succeeded")
        # crash state: STARTED present, result absent → must refuse
        assert os.path.exists(os.path.join(d, "s.lock"))
        assert not os.path.exists(os.path.join(d, "r.txt"))
        try:
            acquire_burn_lock(d, "r.txt", "s.lock", "x")
        except SystemExit:
            pass
        else:
            raise AssertionError("✗ a re-run was somehow allowed in the crash state")
    with tempfile.TemporaryDirectory() as d:              # a result on its own must also refuse
        open(os.path.join(d, "r.txt"), "w").close()
        try:
            acquire_burn_lock(d, "r.txt", "s.lock", "x")
        except SystemExit:
            pass
        else:
            raise AssertionError("✗ a re-run was somehow allowed in the completed state")
    print("  ✓ burn lock: first call succeeds; repeat / crash state / completed state are all refused")


def preflight():
    bad = 0
    for line in open(os.path.join(V3DIR, "SHA256SUMS.txt"), encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        want, name = line.split(maxsplit=1)
        got = hashlib.sha256(
            open(os.path.join(V3DIR, name), "rb").read()).hexdigest()
        bad += 0 if got.startswith(want) else 1
    if bad:
        raise SystemExit(f"✗ v3_frozen verification failed ({bad} files)")
    fp = NT.assert_frozen()
    print("✓ v3_frozen verification passed")
    print(f"✓ task parameters frozen  α={NT.ALPHA} β={NT.BETA} τ={NT.TAU}  fingerprint {fp}")
    print(f"✓ interface frozen  sha256 {IF.F['sha256'][:16]}…  n_cal={IF.F['n_cal']}"
          f"  rank redundancy {IF.F['rho_spearman_A_Bperp']:+.4f}")
    print("\n  ── seed ledger (preregistration §7) ──")
    for seg, use in LEDGER:
        print(f"    {seg:<16}{use}")
    return fp


def task_sim(job):
    world, seed0, n = job
    import novel_situation as NS
    sim = NS.sim
    sim.COND_RECOVER_AT = 65.0                     # ★rule 55★
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
        out.append({"seed": s, "alive": True, "traits": dict(life.agent.traits)})
    return world, seed0, out


def _dispatch(j):
    return j[0](j[1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--final", action="store_true")
    ap.add_argument("--seed0", type=int, default=10000)
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--test-lock", action="store_true")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    a = ap.parse_args()

    if a.test_lock:
        _test_burn_lock()
        return
    preflight()
    if a.check:
        return

    out_path = os.path.join(HERE, "final_028_result.txt")

    if a.final:
        seed0, N = FINAL_SEED0, FINAL_N
        # ★① seed guard★
        if (a.seed0 not in (10000, FINAL_SEED0)) or \
                (a.n not in (300, FINAL_N)):
            raise SystemExit("✗ a non-default seed0/n may not be given together with --final")
        print("\n" + "!" * 76)
        print(f"!! 028 FINAL  seeds {seed0}–{seed0+N-1}  ——  may be run only once")
        print("!! No key design may be changed after seeing the result (preregistration §9)")
        print("!" * 76)
    else:
        seed0, N = a.seed0, a.n
        if seed0 == FINAL_SEED0:
            raise SystemExit("✗ the 70000 block must not be touched outside --final mode")
        print(f"\n[rehearsal] seeds {seed0}–{seed0+N-1}  N={N}"
              f"  —— verifies only the code path / n / gates / joint bootstrap / determinism")
        print("[rehearsal] ⛔ nothing is changed on the basis of the breadth effect\n")

    # ★② crash-safe burn lock — must come **before** any trajectory is generated★
    if a.final:
        nl = chr(10)
        payload = nl.join([
            "028 FINAL STARTED",
            f"seeds={FINAL_SEED0}-{FINAL_SEED0+FINAL_N-1}",
            f"interface_sha={IF.F['sha256']}",
            f"task_fp={NT.config_fingerprint()}",
            "ledger=" + " | ".join(f"{s2}:{u}" for s2, u in LEDGER),
        ]) + nl
        lock = acquire_burn_lock(
            HERE, "final_028_result.txt", "final_028_STARTED.lock", payload)
        print(nl + f"✓ burn lock created (seed ledger + fingerprints persisted): "
              f"{os.path.basename(lock)}")

    jobs = [(task_sim, (w, s0, min(CHUNK, seed0 + N - s0)))
            for w in (WA, WB) for s0 in range(seed0, seed0 + N, CHUNK)]
    assert sum(j[1][2] for j in jobs) == 2 * N, "✗ incomplete chunk coverage"
    store = {WA: [None] * N, WB: [None] * N}
    t0 = time.time()
    with mp.Pool(a.workers) as pool:
        for k, (w, s0, recs) in enumerate(pool.imap_unordered(_dispatch, jobs), 1):
            store[w][s0 - seed0:s0 - seed0 + len(recs)] = recs
            if k % 20 == 0 or k == len(jobs):
                print(f"  {k}/{len(jobs)}  elapsed {(time.time()-t0)/60:.1f}min",
                      flush=True)

    dead_a = sum(1 for r in store[WA] if not r["alive"]) / N
    dead_b = sum(1 for r in store[WB] if not r["alive"]) / N
    pairs = [i for i in range(N)
             if store[WA][i]["alive"] and store[WB][i]["alive"]]
    keep = len(pairs) / N
    print("\n" + "=" * 100)
    print(f" pre-task attrition diagnostic (★not a binding gate★):")
    print(f"   rich {dead_a:.2%} · poor {dead_b:.2%} · "
          f"valid twins {len(pairs)}/{N} = {keep:.2%}"
          f"   reference level {ATTRITION_REPORT_REF:.0%}"
          f"{'' if keep >= ATTRITION_REPORT_REF else '  ⚠ below the historical level, must be noted in the report'}")
    print(f"   the five arms share one survivor intersection; G is decided solely by the C± transport gates")

    # ---- per arm: beta / task / paired difference ----
    allt = [store[w][i]["traits"] for i in pairs for w in (WA, WB)]
    d, betas = {}, {}
    for arm in ARMS:
        betas[arm] = [IF.beta_for(arm, t) for t in allt]
        dv = []
        for i in pairs:
            ra = IF.run_arm(arm, store[WA][i]["traits"], seed0 + i)
            rb = IF.run_arm(arm, store[WB][i]["traits"], seed0 + i)
            dv.append(NT.switch_latency_restricted(ra)
                      - NT.switch_latency_restricted(rb))
        d[arm] = dv

    # ---- ★ gates judged and printed first ★ ----
    muA, sdA = st.mean(betas["A"]), st.stdev(betas["A"])
    diag = {}
    for arm, key in (("Bp", "B"), ("Bm", "B"), ("Cp", "Cp"), ("Cm", "Cm")):
        ref = IF.F["x_sorted"][key]
        raws = [IF.raw_readout(t)[key] for t in allt]
        oos = (sum(1 for x in raws if x < ref[0])
               + sum(1 for x in raws if x > ref[-1])) / len(raws)
        bmin, bmax = IF._BETA_A[0], IF._BETA_A[-1]
        bnd = sum(1 for v in betas[arm] if v == bmin or v == bmax) / len(betas[arm])
        diag[arm] = {"oos": oos, "boundary": bnd,
                     "mu": st.mean(betas[arm]), "sd": st.stdev(betas[arm])}
    gates, primary_ok, secondary_ok = S.check_gates(diag, muA, sdA)

    print("\n" + "=" * 100)
    print(" ★ VALIDITY GATES (read before the outcome, preregistration §4) ★")
    print("=" * 100)
    print(f"  contemporaneous A: μ={muA:.6f}  SD={sdA:.6f}")
    print(f"  {'arm':<5}{'out of range':>14}{'boundary mass':>15}{'|Δμ|/SD_A':>12}"
          f"{'|ΔSD|/SD_A':>12}{'support':>9}{'budget':>8}")
    print("  " + "-" * 88)
    for arm in ("Bp", "Bm", "Cp", "Cm"):
        g, dg = gates[arm], diag[arm]
        print(f"  {arm:<5}{dg['oos']:>9.2%}{dg['boundary']:>10.2%}"
              f"{g['dmu']:>12.1%}{g['dsd']:>12.1%}"
              f"{'✓' if g['support'] else '✗':>9}{'✓' if g['budget'] else '✗':>8}")
    print(f"\n  primary  (C±)  {'✓ valid' if primary_ok else '✗ INVALID'}"
          f"      secondary (B±)  {'✓ valid' if secondary_ok else '✗ INVALID'}")
    if N < FINAL_N:
        # ★Amendment 01 §A★ the validity gates are judged on the N=1500 confirmatory run
        se = (2.0 / (2 * len(pairs))) ** 0.5
        print(f"  ⚠ NON-BINDING: N={N} < {FINAL_N}, so this run's gate results **do not constitute** a verdict on"
              f" the frozen transform")
        print(f"    (the sampling SE of |Δμ|/SD_A ≈ {se:.1%}, so the 10% threshold is only about "
              f"{0.10/se:.1f} SEs) — it verifies only the code path and the order of magnitude")
    if not primary_ok:
        print(f"  ⚠ {S.CLOSURE_TEXT}")

    # ---- joint same-seed bootstrap ----
    boot = S.joint_bootstrap(d)
    G = S.point_G(d)
    glo, ghi = S.ci(boot["G"])
    rb = min(abs(st.mean(d["Bp"])), abs(st.mean(d["Bm"])))
    rlo, rhi = S.ci(boot["RB"])

    print("\n" + "=" * 100)
    tag = "FINAL" if a.final else "rehearsal (not final)"
    print(f" 028 {tag}   seeds {seed0}–{seed0+N-1}   n={len(pairs)}")
    print("=" * 100)
    print(f"  {'arm':<5}{'E (mean paired diff)':>24}{'95% CI':>28}")
    print("  " + "-" * 52)
    for arm in ARMS:
        e = st.mean(d[arm])
        lo, hi = S.ci(boot["E"][arm])
        print(f"  {arm:<5}{e:>+16.4f}   [{lo:>+8.4f}, {hi:>+8.4f}]")

    print(f"\n  ★PRIMARY G = min(|E_C+|,|E_C−|) − |E_A|★")
    if not primary_ok:
        print(f"    ✗ INVALID — the gates did not pass; neither a breadth gain nor a no-gain"
              f" may be claimed")
    else:
        if glo <= 0 <= ghi:
            v = "✗ no evidence that the broader readout beats A (the CI contains 0)"
        elif glo > SESOI:
            v = "★ functionally meaningful breadth gain established ★"
        elif glo > 0:
            v = "◐ a breadth gain is detected, but below the functional threshold (the CI overlaps [0,1])"
        else:
            v = "◐ the CI lies entirely < 0: the broader readout is in fact weaker (see the dilution reading in §6)"
        print(f"    {v}")
    print(f"    G = {G:+.4f} trial   95% CI [{glo:+.4f}, {ghi:+.4f}]"
          f"   SESOI = {SESOI} trial")

    print(f"\n  secondary R_B = min(|E_B+|,|E_B−|)"
          f"{'' if secondary_ok else '  ✗ INVALID'}")
    print(f"    R_B = {rb:.4f}   95% CI [{rlo:+.4f}, {rhi:+.4f}]"
          f"   (B+ {st.mean(d['Bp']):+.4f} · B− {st.mean(d['Bm']):+.4f})")

    print(f"\n  Each of C± against the ±{SESOI} equivalence region:")
    for arm in ("Cp", "Cm"):
        lo, hi = S.ci(boot["E"][arm])
        s2 = ("entirely beyond ±1" if lo > SESOI or hi < -SESOI
              else ("overlaps ±1" if lo > 0 or hi < 0 else "contains 0"))
        print(f"    {arm}  E={st.mean(d[arm]):+.4f}  [{lo:+.4f}, {hi:+.4f}]  {s2}")

    ea = st.mean(d["A"])
    alo, ahi = S.ci(boot["E"]["A"])
    print(f"\n  ★Arm A = the sampling-level replication of 027 (judged separately from G)★")
    print(f"    E_A = {ea:+.4f}  [{alo:+.4f}, {ahi:+.4f}]"
          f"   027 original −0.0798 [−0.1632, −0.0035]")
    print(f"    {'✓ reproduced a detectable effect in the same direction' if (alo>0 or ahi<0) and ea*(-0.0798)>0 else '⚠ did not reproduce the narrow-interface effect of 027 — the paper must say so plainly'}")

    txt = os.path.join(HERE, "final_028_result.txt" if a.final
                       else "final_028_rehearsal.txt")
    with open(txt, "w", encoding="utf-8") as f:
        f.write(f"028 {tag}  seeds {seed0}-{seed0+N-1}  n={len(pairs)}\n")
        f.write(f"interface_sha={IF.F['sha256']}  task_fp={NT.config_fingerprint()}\n")
        f.write(f"attrition rich={dead_a:.4f} poor={dead_b:.4f} keep={keep:.4f}\n")
        f.write(f"gates primary={primary_ok} secondary={secondary_ok}\n")
        for arm in ("Bp", "Bm", "Cp", "Cm"):
            g, dg = gates[arm], diag[arm]
            f.write(f"gate\t{arm}\t{dg['oos']:.5f}\t{dg['boundary']:.5f}"
                    f"\t{g['dmu']:.5f}\t{g['dsd']:.5f}\n")
        for arm in ARMS:
            lo, hi = S.ci(boot["E"][arm])
            f.write(f"E\t{arm}\t{st.mean(d[arm]):+.6f}\t{lo:+.6f}\t{hi:+.6f}\n")
        f.write(f"G\t{G:+.6f}\t{glo:+.6f}\t{ghi:+.6f}\n")
        f.write(f"RB\t{rb:.6f}\t{rlo:+.6f}\t{rhi:+.6f}\n")
        f.write("ledger " + " | ".join(f"{s}:{u}" for s, u in LEDGER) + "\n")
    print(f"\nWritten to {txt}")


if __name__ == "__main__":
    mp.freeze_support()
    sys.stdout.reconfigure(encoding="utf-8")
    main()
