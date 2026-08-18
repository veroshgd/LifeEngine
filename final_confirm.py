"""
FINAL CONFIRMATION — executed strictly according to FINAL_PREREGISTRATION.md
============================================================================

Shake-down (development seeds, run freely):
    python final_confirm.py --check                    verify the hashes + frozen import only
    python final_confirm.py --n 200                    walk the whole pipeline on a small sample
    python final_confirm.py --n 200 --workers 5        rule 55 self-check: results must be bit-identical

Official run (**allowed exactly once**):
    python final_confirm.py --final

★ This script imports the model from `v3_frozen/` ★
not from the main directory. Files in the main directory may be changed by later experiments at any time;
what the preregistration locks is the frozen copy.
At startup `v3_frozen/SHA256SUMS.txt` is verified, and a mismatch refuses the run outright.

★ The five conditions (preregistration §6) ★
    H1    full architecture   022 ON    no deletion   main effect
    P1    −all floors ①②     022 ON    no deletion   does it still stand with the floors off
    P2②   −all floors ①②     022 ON    delete knowledge
    NC③   −all floors ①②     022 ON    delete memories     negative control: must be bit-identical to P1
    R52   −all floors ①②     022 OFF   no deletion   the verdict on rule 52 ★the one genuinely unknown item★

★ Statistics (preregistration §5) ★
    baseline  same-world cross-seed TV, random pairing repeated K=5 (rule 35)
    CI        cluster bootstrap resampling by agent 3000 times, 2.5/97.5 percentiles
    p         sign permutation of the per-seed δ 10000 times, p=(hits+1)/(n_perm+1)

★ Rule 55 ★ Every subtask sets all globals explicitly at its start, never relying on inheritance.
"""

import argparse
import hashlib
import multiprocessing as mp
import os
import random
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
V3DIR = os.path.join(HERE, "v3_frozen")

WA, WB, COMMON = "rich world", "barren world", "baseline"
SPLIT, TOTAL = 30, 60
BASE_K = 5
N_BOOT = 3000
N_PERM = 10000
CHUNK = 50

FINAL_SEED0, FINAL_N = 50000, 1500        # preregistration §3. Run once only.

# Preregistration amendment A (§5.5): the CI lower-bound criterion becomes three-valued.
# The threshold 0.01 ≈ 10 × the measured Monte Carlo SD (0.00097). Fixed before the run.
BOUNDARY = 0.01
DIAG_AT = 0.02          # if |lo−1| is below this, run the boundary diagnostic too (affects the report only)
DIAG_SEEDS = [777 + 1000 * r for r in range(8)]

# (label, all floors off, 022 on, what is deleted at transplant)
CONDITIONS = [
    ("H1  full architecture",   False, True,  frozenset()),
    ("P1  −all floors ①②",      True,  True,  frozenset()),
    ("P2② delete knowledge",    True,  True,  frozenset({"semantic"})),
    ("NC③ delete memories",     True,  True,  frozenset({"episodic"})),
    ("R52 −floors · 022 off",   True,  False, frozenset()),
]


# ---------------------------------------------------------------- frozen verification
def verify_frozen(verbose=True):
    sums = os.path.join(V3DIR, "SHA256SUMS.txt")
    if not os.path.exists(sums):
        raise SystemExit(f"✗ cannot find {sums}")
    bad, n = [], 0
    for line in open(sums, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        want, name = line.split(maxsplit=1)
        p = os.path.join(V3DIR, name)
        if not os.path.exists(p):
            bad.append(f"{name}: file does not exist")
            continue
        got = hashlib.sha256(open(p, "rb").read()).hexdigest()
        n += 1
        if got != want:
            bad.append(f"{name}: {got[:16]} ≠ {want[:16]}")
    if bad:
        print("✗ v3_frozen verification failed:")
        for b in bad:
            print("   ", b)
        raise SystemExit("Refusing to run. Preregistration §0: if it does not match, do not run.")
    if verbose:
        print(f"✓ v3_frozen verification passed ({n} files)")
    return n


def load_frozen():
    """Import the model from v3_frozen and assert that what we got really is the frozen copy"""
    if V3DIR not in sys.path:
        sys.path.insert(0, V3DIR)
    import sim, scenarios
    import persistence_ablation as PA
    for m in (sim, scenarios, PA):
        assert os.path.abspath(m.__file__).startswith(V3DIR), \
            f"✗ {m.__name__} comes from {m.__file__}, not v3_frozen"
    assert sim.MODEL_VERSION == "v3", f"✗ MODEL_VERSION={sim.MODEL_VERSION}"
    return sim, scenarios, PA


# ---------------------------------------------------------------- simulation
def wipe(agent, what):
    """★Non-nested★ each variant deletes one thing. Same semantics as p2_test.wipe_at_transplant.
    trait_floor / trait_identity are never deleted here — that is the business of the floor ablation."""
    if "semantic" in what:
        agent.knowledge = {}
        agent.knowledge_strength = {}
    if "episodic" in what:
        agent.memories = []
    if "flags" in what:
        agent.flags = set()


def task_sim(job):
    """One condition × one world × one seed block → the normalised window matrix per seed (None if it died)"""
    ci, world, seed0, n = job
    from collections import Counter

    sim, scenarios, PA = load_frozen()
    label, floor_off, k22, what = CONDITIONS[ci]

    # ★Rule 55★ set explicitly, never inherited
    sim.COND_RECOVER_AT = 65.0
    sim.COND_DEADZONE_RECOVER = 0.0
    sim.COND_SHELTER_RECOVER = 0.0
    sim.SLEEP_SUPPRESS = sim.HUNGER_URGENCY = 0.0
    sim.SLEEP_EFF_FLOOR = 0.35
    (sim.KNOWLEDGE_WEIGHT, sim.KNOWLEDGE_GOAL_WEIGHT, sim.KNOWLEDGE_FORGET) = \
        (12.0, 0.25, 0.02) if k22 else (0.0, 0.0, 0.0)

    def to_mat(w):
        out = []
        for h in w:
            tot = sum(h.values()) or 1
            out.append(tuple(h[x] / tot for x in sim.ACTIONS))
        return tuple(out)

    scenarios.make = PA.patched_make(False, floor_off)
    res = []
    try:
        for s in range(seed0, seed0 + n):
            life = scenarios.make(s, world)
            ag = life.agent

            def phase(d0, d1):
                for day in range(d0, d1):
                    for t in range(sim.TICKS_PER_DAY):
                        life.world.tick(day, t)
                        for inf in life.influences:
                            inf(life.world, ag, day, t, life.inf_rng)
                        ag.tick(day, t)
                        if not ag.alive:
                            return False
                    ag.daily(day)
                return True

            if not phase(0, SPLIT):
                res.append(None)
                continue
            snap = [Counter(c) for c in ag.action_by_hour]
            w = sim.World(s, **scenarios.WORLDS[COMMON])
            life.world, ag.world = w, w
            wipe(ag, what)                       # ★at exactly the moment of transplant★
            if not phase(SPLIT, TOTAL):
                res.append(None)
                continue
            res.append(to_mat([Counter(c) - snap[h]
                               for h, c in enumerate(ag.action_by_hour)]))
    finally:
        scenarios.make = PA._orig_make
    return ci, world, seed0, res


# ---------------------------------------------------------------- statistics
def mat_tv(a, b):
    """Equivalent to transplant.window_tv (the input is already normalised per hour)"""
    return sum(0.5 * sum(abs(x - y) for x, y in zip(ha, hb))
               for ha, hb in zip(a, b)) / len(a)


def shuffled_base(ws, k, rng):
    """Rule 35: random pairing repeated K times (same semantics as p1_test.shuffled_base)"""
    out, idx = [], list(range(len(ws)))
    for _ in range(k):
        rng.shuffle(idx)
        out += [mat_tv(ws[idx[j]], ws[idx[j + 1]])
                for j in range(0, len(idx) - 1, 2)]
    return out


def task_stats(job):
    """All the statistics for one condition. Run in a subprocess — the bootstrap is the bulk of it."""
    ci, wa, wb, dead_a, dead_b, n_seeds = job
    label = CONDITIONS[ci][0]
    n = len(wa)
    # Preregistration §4: an effective n < 1000 (= 2/3 of N=1500, i.e. mortality > 33%) is judged **invalid**.
    # Small-sample debug runs use the same proportion, otherwise every debug run would be judged invalid.
    floor_n = 1000 if n_seeds >= FINAL_N else max(30, (2 * n_seeds) // 3)
    if n < floor_n:
        return ci, dict(label=label, n=n, invalid=True,
                        dead_a=dead_a, dead_b=dead_b, n_seeds=n_seeds)

    rng = random.Random(777)
    treat = [mat_tv(wa[k], wb[k]) for k in range(n)]
    base = shuffled_base(wa, BASE_K, rng) + shuffled_base(wb, BASE_K, rng)
    ratio = statistics.mean(treat) / statistics.mean(base)

    boots = []                                   # cluster bootstrap, by agent
    for _ in range(N_BOOT):
        pick = [rng.randrange(n) for _ in range(n)]
        t = [treat[i] for i in pick]
        b = (shuffled_base([wa[i] for i in pick], BASE_K, rng) +
             shuffled_base([wb[i] for i in pick], BASE_K, rng))
        boots.append(statistics.mean(t) / statistics.mean(b))
    boots.sort()
    lo, hi = boots[int(.025 * N_BOOT)], boots[int(.975 * N_BOOT)]

    drng = random.Random(12345)                  # per-seed δ
    deltas = []
    for k in range(n):
        opp = []
        for _ in range(BASE_K):
            j = drng.randrange(n - 1); j = j if j < k else j + 1
            opp.append(mat_tv(wa[k], wa[j]))
            j = drng.randrange(n - 1); j = j if j < k else j + 1
            opp.append(mat_tv(wb[k], wb[j]))
        deltas.append(treat[k] - statistics.mean(opp))

    prng = random.Random(999)
    obs = statistics.mean(deltas)
    hits = sum(1 for _ in range(N_PERM)
               if abs(statistics.mean(d if prng.random() < .5 else -d
                                      for d in deltas)) >= abs(obs))
    p = (hits + 1) / (N_PERM + 1)
    sd = statistics.stdev(deltas)
    return ci, dict(label=label, n=n, invalid=False, ratio=ratio, lo=lo, hi=hi,
                    delta=obs, dz=obs / sd if sd else 0.0, p=p,
                    dead_a=dead_a, dead_b=dead_b, n_seeds=n_seeds,
                    fingerprint=round(statistics.mean(treat), 12))


def task_boundary(job):
    """Boundary diagnostic (preregistration amendment A): re-run the bootstrap with other analysis seeds; reported only, never used for the verdict."""
    ci, wa, wb, seed = job
    n = len(wa)
    rng = random.Random(seed)
    treat = [mat_tv(wa[k], wb[k]) for k in range(n)]
    boots = []
    for _ in range(N_BOOT):
        pick = [rng.randrange(n) for _ in range(n)]
        b = (shuffled_base([wa[i] for i in pick], BASE_K, rng) +
             shuffled_base([wb[i] for i in pick], BASE_K, rng))
        boots.append(statistics.mean(treat[i] for i in pick) / statistics.mean(b))
    boots.sort()
    return ci, seed, boots[int(.025 * N_BOOT)]


def _dispatch(job):
    fn, args = job
    return fn(args)


# ---------------------------------------------------------------- criteria
def verdicts(R, out):
    def ci_ok(k):
        """Preregistration amendment A: a three-valued verdict. Returns 'pass' / 'fail' / 'boundary' / 'invalid'"""
        r = R.get(k)
        if not r or r["invalid"]:
            return "invalid"
        d = r["lo"] - 1.0
        if d >= BOUNDARY:
            return "pass"
        if d <= -BOUNDARY:
            return "fail"
        return "boundary"

    def mark(k):
        v = ci_ok(k)
        return {"pass": "✓ pass", "fail": "✗ fail",
                "boundary": "◐ on the detection boundary; this criterion cannot decide",
                "invalid": "—— invalid ——"}[v]

    P = out.append
    bad = [R[k]["label"] for k in sorted(R) if R[k]["invalid"]]
    if bad:
        P("")
        P("=" * 100)
        P(f" ⚠ The following conditions have insufficient effective n and are judged **invalid** rather than \"not significant\": {', '.join(bad)}")
        P(" The criteria cannot decide; only the parts that remain valid are printed below.")
        P("=" * 100)

    def fmt(k):
        r = R.get(k)
        if not r or r["invalid"]:
            return "—— invalid ——"
        return f"{r['ratio']:.3f} [{r['lo']:.5f}, {r['hi']:.5f}]"
    P("")
    P("=" * 100)
    P(" Preregistered criteria (FINAL_PREREGISTRATION.md §6)")
    P("=" * 100)

    P(f"\n  H1  main effect: full architecture CI lower bound > 1.00")
    P(f"      → {mark(0)}   {fmt(0)}")

    P(f"\n  P1  still > 1 with all floors off")
    P(f"      → {mark(1)}   {fmt(1)}")
    P(f"      pass = there is a persistence channel that does not depend on the floor ratchet")

    ok12 = not (R[1]["invalid"] or R[2]["invalid"])
    drop = R[1]["ratio"] - R[2]["ratio"] if ok12 else float("nan")
    overlap = (not (R[2]["hi"] < R[1]["lo"] or R[1]["hi"] < R[2]["lo"])) if ok12 else True
    p2 = ok12 and drop >= 0.05 and not overlap
    P(f"\n  P2  delete knowledge only: drop ≥ 0.05 and CIs do not overlap")
    P(f"      → {'✓ pass' if p2 else '✗ fail'}"
      f"   {fmt(1)} → {fmt(2)}"
      f"   drop {drop:+.3f}   CI {'overlap' if overlap else 'no overlap'}")
    P(f"      fail = the knowledge channel cannot be claimed; the main line becomes \"discrete memory structures are not the long-term carrier\"")

    P(f"\n  R52 ★the one genuinely unknown★  022 off + all floors off, CI lower bound > 1.00")
    P(f"      → {mark(4)}   {fmt(4)}")
    P(f"      pass = the no-floor residual effect is real, and the withdrawal of rule 33 must be revisited")
    P(f"      fail = the withdrawal of rule 33 is settled: trait_identity is a **necessary mechanism**, not an amplifier")
    P(f"      boundary = the true value sits on the detection limit; no verdict this time (preregistration amendment A)")

    same = R[1].get("fingerprint") == R[3].get("fingerprint")
    P(f"\n  Negative control  deleting memories only must be bit-identical to P1")
    P(f"      → {'✓ passed' if same else '✗ failed —— the whole batch is void and must be re-checked'}"
      f"   {R[1].get('fingerprint')} vs {R[3].get('fingerprint')}")

    P("\n" + "-" * 100)
    P("  Comparison with the prior predictions (preregistration §7)")
    g = lambda k: ("—" if not R.get(k) or R[k]["invalid"] else f"{R[k]['ratio']:.3f}")
    P(f"    H1  predicted pass, 1.12–1.16      measured {ci_ok(0)}, {g(0)}")
    P(f"    P1  predicted pass, 1.07–1.10      measured {ci_ok(1)}, {g(1)}")
    P(f"    P2  predicted fail, drop≈0.03      measured {'pass' if p2 else 'fail'}, drop {drop:+.3f}")
    P(f"    R52 predicted fail, 1.03–1.06      measured {ci_ok(4)}, {g(4)}")
    P(f"    episodic memory predicted bit-identical   measured {'bit-identical' if same else 'different'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--final", action="store_true",
                    help=f"use the preregistered final seed block {FINAL_SEED0}–"
                         f"{FINAL_SEED0+FINAL_N-1} (allowed only once)")
    ap.add_argument("--seed0", type=int, default=0)
    ap.add_argument("--n", type=int, default=1500)
    ap.add_argument("--check", action="store_true", help="frozen verification only")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    a = ap.parse_args()

    verify_frozen()
    sim, _, _ = load_frozen()
    print(f"✓ model from {os.path.dirname(sim.__file__)}")
    print(f"✓ MODEL_VERSION={sim.MODEL_VERSION}  COND_RECOVER_AT={sim.COND_RECOVER_AT}")
    if a.check:
        return

    seed0, N = (FINAL_SEED0, FINAL_N) if a.final else (a.seed0, a.n)
    if a.final:
        print("\n" + "!" * 78)
        print(f"!! FINAL CONFIRMATION  seeds {seed0}–{seed0+N-1}  ——  this block may be run only once")
        print(f"!! Once run, the model is not changed again whatever the result (preregistration §3)")
        print("!" * 78)
    else:
        print(f"\n[debug run] seeds {seed0}–{seed0+N-1}, N={N}"
              f"   —— not the final run; re-run as often as you like")

    # ⚠ This was once written min(CHUNK, N - s0): correct by luck at seed0=0, negative at seed0=50000
    #   → every task ran 0 seeds → all n=0. The rehearsal used seed0=0 and slipped straight past it. See rule 57.
    jobs = [(task_sim, (ci, w, s0, min(CHUNK, seed0 + N - s0)))
            for ci in range(len(CONDITIONS))
            for w in (WA, WB)
            for s0 in range(seed0, seed0 + N, CHUNK)]
    print(f"\nSimulating {len(jobs)} tasks, processes {a.workers}", flush=True)

    store = {(ci, w): [None] * N for ci in range(len(CONDITIONS)) for w in (WA, WB)}
    t0 = time.time()
    with mp.Pool(a.workers) as pool:
        for k, (ci, w, s0, res) in enumerate(pool.imap_unordered(_dispatch, jobs), 1):
            store[(ci, w)][s0 - seed0:s0 - seed0 + len(res)] = res
            if k % 30 == 0 or k == len(jobs):
                el = time.time() - t0
                print(f"  {k}/{len(jobs)}  elapsed {el/60:.1f}min  "
                      f"remaining ~{el/k*(len(jobs)-k)/60:.1f}min", flush=True)

    # ★Post-launch self-check★ coverage must be 100%: any cell no task wrote to means the chunking arithmetic
    #   is wrong, not that "the balls all died". These two cases are handled completely differently and must never be conflated.
    planned = sum(j[1][3] for j in jobs)
    want = len(CONDITIONS) * 2 * N
    if planned != want:
        raise SystemExit(f"✗ incomplete chunk coverage: {planned} simulations planned, expected {want}."
                         f" (check the CHUNK/seed0 arithmetic) No result is produced this run.")

    sjobs, live_w = [], {}
    for ci in range(len(CONDITIONS)):
        ca, cb = store[(ci, WA)], store[(ci, WB)]
        live = [i for i in range(N) if ca[i] is not None and cb[i] is not None]
        if len(live) == 0:
            raise SystemExit(f"✗ {CONDITIONS[ci][0]} has effective n = 0."
                             f" n=0 is a **failure**, not a mortality rate; no result is produced this run.")
        live_w[ci] = ([ca[i] for i in live], [cb[i] for i in live])
        sjobs.append((task_stats, (ci, [ca[i] for i in live], [cb[i] for i in live],
                                   1 - sum(x is not None for x in ca) / N,
                                   1 - sum(x is not None for x in cb) / N, N)))
    print(f"\nComputing statistics for {len(sjobs)} conditions (bootstrap {N_BOOT} + permutation {N_PERM})…", flush=True)
    R = {}
    with mp.Pool(min(a.workers, len(sjobs))) as pool:
        for ci, r in pool.imap_unordered(_dispatch, sjobs):
            R[ci] = r
            print(f"  finished {r['label']}", flush=True)

    # ── Boundary diagnostic (preregistration amendment A): affects the report only, never the verdict ──
    need = [ci for ci in R if not R[ci]["invalid"]
            and abs(R[ci]["lo"] - 1.0) < DIAG_AT]
    diag = {}
    if need:
        print(f"\nBoundary diagnostic: {len(need)} conditions have |CI lower−1| < {DIAG_AT}, "
              f"re-running with {len(DIAG_SEEDS)} analysis seeds…", flush=True)
        bjobs = [(task_boundary, (ci, live_w[ci][0], live_w[ci][1], sd))
                 for ci in need for sd in DIAG_SEEDS]
        with mp.Pool(min(a.workers, len(bjobs))) as pool:
            for ci, sd, lo in pool.imap_unordered(_dispatch, bjobs):
                diag.setdefault(ci, []).append(lo)

    out = []
    out.append("\n" + "=" * 100)
    tag = "FINAL CONFIRMATION" if a.final else "debug run (not final)"
    out.append(f" {tag}   seeds {seed0}–{seed0+N-1}   N={N}   model v3 (frozen)")
    out.append("=" * 100)
    out.append(f"  {'condition':<24}{'n':>6}{'dead rich':>11}{'dead barren':>13}{'ratio':>8}"
               f"  {'95% CI':<18}{'mean δ':>9}{'dz':>7}{'p':>10}")
    out.append("  " + "-" * 96)
    for ci in range(len(CONDITIONS)):
        r = R[ci]
        if r["invalid"]:
            out.append(f"  {r['label']:<24}{r['n']:>6}  ⚠ effective n < 1000 → judged **invalid**"
                       f", not \"not significant\" (preregistration §4)")
            continue
        out.append(f"  {r['label']:<20}{r['n']:>6}{r['dead_a']:>8.1%}{r['dead_b']:>8.1%}"
                   f"{r['ratio']:>8.3f}  [{r['lo']:.3f}, {r['hi']:.3f}]"
                   f"{r['delta']:>+9.4f}{r['dz']:>7.2f}{r['p']:>10.4f}")
    if diag:
        out.append("")
        out.append("=" * 100)
        out.append(" Boundary diagnostic (preregistration amendment A · report only, not part of the verdict)")
        out.append("=" * 100)
        out.append(f"  {'condition':<24}{'lower-bound range':>26}{'MC SD':>10}{'pass/total':>12}")
        out.append("  " + "-" * 66)
        for ci in sorted(diag):
            v = diag[ci]
            sd = statistics.stdev(v) if len(v) > 1 else 0.0
            npass = sum(1 for x in v if x > 1.0)
            out.append(f"  {R[ci]['label']:<20}"
                       f"[{min(v):.5f}, {max(v):.5f}]".rjust(26) +
                       f"{sd:>10.5f}{f'{npass}/{len(v)}':>8}")
        out.append("  If \"pass/total\" is neither 0/8 nor 8/8 → the criterion is decided by the analysis seed,")
        out.append("   which is exactly the case amendment A requires to be judged \"◐ detection boundary\".")
    verdicts(R, out)
    out.append("\n  ⚠ Scope (preregistration §0.5): what is confirmed here is the **persistence architecture**,")
    out.append("     not generalized individuality. The latter belongs to novel-situation generalization.")
    text = "\n".join(out)
    print(text)

    fn = os.path.join(HERE, "final_confirm_result.txt" if a.final
                      else "final_confirm_debug.txt")
    with open(fn, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(f"\nWritten to {fn}")


if __name__ == "__main__":
    mp.freeze_support()
    main()
