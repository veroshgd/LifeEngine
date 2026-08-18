"""
anchor content causal probe — is the history slice stored in the anchor the carrier of persistence?
===================================================================================================

Run:  python anchor_probe.py --verify        (part A only, ~2 minutes)
      python anchor_probe.py                 (full run, 13 processes)

★ Freeze declaration ★
v3 is frozen (`v3_frozen/`). This script is an **experiment-level intervention**:
it changes only `_hardship_anchor` on the agent instance and **touches no default in `sim.py`**.

--------------------------------------------------------------------------
A. First falsify a wrong inference: v3 does not postpone the anchor
-------------------------------------------------------------------
023 §7.5 once inferred that "v3 pushes the consolidation moment later → it samples a more mature personality".
**That does not hold**, and from the code it could never have held:

    sim.py:965   if deficit > 0:  ...  if self._hardship_anchor is None: write
    deficit = (100 − condition)/100

condition can only be pulled below 100 by `COND_DRAIN` (hunger>70); while condition is still 100, the gain from
raising `COND_RECOVER_AT` is entirely eaten by `clamp`.
**So before the anchor is written, the v2 and v3 trajectories are bit-identical** — the anchor day must be the same.

Part A verifies this seed by seed (v2 vs v3, same seeds, reporting the "share exactly equal").

The quantity that was mistaken for the anchor is `fears_hunger`: it requires `hardship_norm ≥ 0.5`
(`HARDSHIP_STORY_AT`) to be recorded, making it a **narrative landmark**, not the moment personality sets.

--------------------------------------------------------------------------
B. The new experimental question: is the **content** of the anchor the causal carrier?
--------------------------------------------------------------------------------------
Not by doing "only start writing the anchor on day N" — that changes two things at once
(① what is in the snapshot ② when the floor starts to act), which is causally unclean.

Instead, do an **anchor-content transplant** (a miniature state transplant):

    1. Let the agent run the whole development phase normally (days 0–29),
       saving trait snapshots along the way: day 5 / 10 / 20 / 29
    2. At the fixed intervention point (day 30, the moment of transplant) deepcopy the exact same state
    3. **Change only `_hardship_anchor`**, swapping in a different history slice
    4. Every branch enters the common garden (the baseline world) from exactly the same current state

The only variable = the history slice stored in the anchor.

★ A natural negative control ★
The no-floor variant of `persistence_ablation` replaces `trait_floor` with `FrozenZero()`, and the only route
by which `_hardship_anchor` acts is anchor → trait_floor (sim.py:970).
**So with the floors off, what is put in the anchor should make no difference at all.**
If the no-floor arm moves too → there is a leak or a second anchor channel, which would be a strong negative-control failure.

★ Predictions (primary / secondary) ★
  primary   under the full architecture, the anchor-content intervention **produces a detectable difference in late behavioural persistence**
            (no monotone relation Day5 < Day10 < Day20 < Day29 is preregistered —
             the system has feedback, hardship boost, floors and saturation, so a later snapshot carrying
             more information does not imply a monotone final effect)
  secondary the trend in Day order
  negative  no-floor variant: Day5 ≈ Day10 ≈ Day20 ≈ Day29 ≈ No-anchor

★ Seeds ★ Uses the **already inspected development seeds (0+)**.
The fresh seed block for the final confirmation is left untouched.
"""

import argparse
import copy
import multiprocessing as mp
import os
import random
import statistics
import time

WA, WB, COMMON = "rich world", "barren world", "baseline"
SPLIT, TOTAL = 30, 60
SNAP_DAYS = (5, 10, 20, 29)
BRANCHES = ["natural anchor", "Day 5", "Day 10", "Day 20", "Day 29", "no anchor"]
BASE_K = 5
N_PERM = 10000
V3_RECOVER_AT = 65.0        # part B runs only on frozen v3; pinned explicitly, never inherited
CHUNK = 50


def _prep(floor_off, rec_at):
    """★ rec_at must be passed explicitly ★
    mp.Pool worker processes are **reused**: part A's task_verify sets `sim.COND_RECOVER_AT`
    to 30.0 or 65.0 and leaves it in that process.
    If part B does not set it back explicitly, it runs whatever version the previous task left behind —
    the result then depends on task scheduling order, and the same command gives different numbers twice.
    (That is exactly how the first version came off the rails: two N=100 runs disagreed completely.)"""
    import sim
    import scenarios
    import persistence_ablation as PA
    sim.COND_RECOVER_AT = rec_at
    sim.COND_DEADZONE_RECOVER = 0.0
    sim.COND_SHELTER_RECOVER = 0.0
    sim.KNOWLEDGE_WEIGHT, sim.KNOWLEDGE_GOAL_WEIGHT, sim.KNOWLEDGE_FORGET = 12.0, 0.25, 0.02
    scenarios.make = PA.patched_make(False, floor_off)
    return sim, scenarios, PA


# ------------------------------------------------------------------ part A
def task_verify(job):
    """Record per seed the first day the anchor is written + the first day fears_hunger appears, once for v2 and once for v3"""
    rec_at, world, floor_off, seed0, n = job
    sim, scenarios, PA = _prep(floor_off, rec_at)
    out = []
    try:
        for s in range(seed0, seed0 + n):
            life = scenarios.make(s, world)
            ag = life.agent
            a_day = f_day = None
            for day in range(SPLIT):
                for t in range(sim.TICKS_PER_DAY):
                    life.world.tick(day, t)
                    for inf in life.influences:
                        inf(life.world, ag, day, t, life.inf_rng)
                    ag.tick(day, t)
                    if a_day is None and ag._hardship_anchor is not None:
                        a_day = day
                    if f_day is None and "fears_hunger" in ag.flags:
                        f_day = day
                    if not ag.alive:
                        break
                if not ag.alive:
                    break
                ag.daily(day)
            out.append((s, a_day, f_day))
    finally:
        scenarios.make = PA._orig_make
    return ("V", rec_at, world, floor_off, out)


# ------------------------------------------------------------------ part B
def task_branch(job):
    """One seed block × one world × one architecture → the window matrix of each branch"""
    world, floor_off, seed0, n = job
    sim, scenarios, PA = _prep(floor_off, V3_RECOVER_AT)   # ★v3 pinned explicitly★
    from collections import Counter

    def to_mat(w):
        out = []
        for h in w:
            tot = sum(h.values()) or 1
            out.append(tuple(h[x] / tot for x in sim.ACTIONS))
        return tuple(out)

    res = {b: [None] * n for b in BRANCHES}
    try:
        for k, s in enumerate(range(seed0, seed0 + n)):
            life = scenarios.make(s, world)
            ag = life.agent
            snaps, dead = {}, False

            for day in range(SPLIT):                       # ── development
                for t in range(sim.TICKS_PER_DAY):
                    life.world.tick(day, t)
                    for inf in life.influences:
                        inf(life.world, ag, day, t, life.inf_rng)
                    ag.tick(day, t)
                    if not ag.alive:
                        dead = True
                        break
                if dead:
                    break
                ag.daily(day)
                if day in SNAP_DAYS:
                    snaps[day] = dict(ag.traits)
            if dead or len(snaps) < len(SNAP_DAYS):
                continue

            snap0 = [Counter(c) for c in ag.action_by_hour]   # day-30 snapshot

            for b in BRANCHES:                              # ── intervention + common garden
                life_b = copy.deepcopy(life)               # exactly the same state (including RNG)
                ag_b = life_b.agent
                # ⚠ Trap: FrozenZero is a dict subclass whose __setitem__ is a no-op, and deepcopy
                #   rebuilds it by feeding data through __setitem__ → it produces an **empty dict**
                #   → the next read of trait_floor['industry'] raises KeyError.
                #   v3 is frozen, so persistence_ablation.py is not changed; it is patched back here.
                #   FrozenZero carries no state (reads are always 0, writes always dropped), so rebuilding is equivalent.
                if floor_off:
                    ag_b.trait_floor = PA.FrozenZero()
                    ag_b.trait_identity = PA.FrozenZero()
                if b == "no anchor":
                    ag_b._hardship_anchor = None
                elif b != "natural anchor":
                    ag_b._hardship_anchor = dict(snaps[int(b.split()[1])])

                w = sim.World(s, **scenarios.WORLDS[COMMON])   # the same world for every branch
                life_b.world, ag_b.world = w, w
                ok = True
                for day in range(SPLIT, TOTAL):
                    for t in range(sim.TICKS_PER_DAY):
                        life_b.world.tick(day, t)
                        for inf in life_b.influences:
                            inf(life_b.world, ag_b, day, t, life_b.inf_rng)
                        ag_b.tick(day, t)
                        if not ag_b.alive:
                            ok = False
                            break
                    if not ok:
                        break
                    ag_b.daily(day)
                if ok:
                    res[b][k] = to_mat([Counter(c) - snap0[h]
                                        for h, c in enumerate(ag_b.action_by_hour)])
    finally:
        scenarios.make = PA._orig_make
    return ("B", world, floor_off, seed0, res)


def mat_tv(a, b):
    return sum(0.5 * sum(abs(x - y) for x, y in zip(ha, hb))
               for ha, hb in zip(a, b)) / len(a)


def build_opp(n, rng):
    out = []
    for k in range(n):
        pick = lambda: [(lambda j: j if j < k else j + 1)(rng.randrange(n - 1))
                        for _ in range(BASE_K)]
        out.append((pick(), pick()))
    return out


def deltas_on(idx, wa, wb, opp):
    ds, bs = [], []
    for k, i in enumerate(idx):
        ds.append(mat_tv(wa[i], wb[i]))
        bs.append(statistics.mean(
            [mat_tv(wa[i], wa[idx[j]]) for j in opp[k][0]] +
            [mat_tv(wb[i], wb[idx[j]]) for j in opp[k][1]]))
    return [d - b for d, b in zip(ds, bs)], statistics.mean(ds), statistics.mean(bs)


def sign_perm_p(vals, rng, n_perm=N_PERM):
    obs = statistics.mean(vals)
    hits = sum(1 for _ in range(n_perm)
               if abs(statistics.mean(v if rng.random() < .5 else -v
                                      for v in vals)) >= abs(obs))
    return obs, (hits + 1) / (n_perm + 1)


def _dispatch(job):
    fn, args = job
    return fn(args)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=600)
    ap.add_argument("--verify", action="store_true", help="run part A only")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args()
    N = a.seeds

    jobs = []
    for rec in (30.0, 65.0):                       # A: v2 / v3
        for world in (WA, WB):
            for fo in (False, True):
                for s0 in range(0, N, CHUNK):
                    jobs.append((task_verify, (rec, world, fo, s0, min(CHUNK, N - s0))))
    if not a.verify:
        for world in (WA, WB):                     # B: on v3 only (already frozen)
            for fo in (False, True):
                for s0 in range(0, N, CHUNK):
                    jobs.append((task_branch, (world, fo, s0, min(CHUNK, N - s0))))

    print(f"anchor probe   {len(jobs)} tasks   N={N} (development seeds 0+)   "
          f"processes {a.workers}")
    print("★ v3 is frozen: this script only changes the agent instance's _hardship_anchor, never a sim.py default\n",
          flush=True)

    t0, out = time.time(), []
    with mp.Pool(a.workers) as pool:
        for k, r in enumerate(pool.imap_unordered(_dispatch, jobs), 1):
            out.append(r)
            if k % 10 == 0 or k == len(jobs):
                el = time.time() - t0
                print(f"  {k}/{len(jobs)}  elapsed {el/60:.1f}min  "
                      f"remaining ~{el/k*(len(jobs)-k)/60:.1f}min", flush=True)

    report_verify([r for r in out if r[0] == "V"], N)
    if not a.verify:
        report_branch([r for r in out if r[0] == "B"], N)


def report_verify(rows, N):
    print("\n" + "=" * 96)
    print(" A · anchor write day vs fears_hunger day — v2/v3 checked seed by seed")
    print("=" * 96)
    acc = {}
    for _, rec, world, fo, lst in rows:
        acc.setdefault((world, fo, rec), {}).update({s: (ad, fd) for s, ad, fd in lst})

    print(f"  {'world':<14}{'architecture':<20}{'anchor day v2':>15}{'anchor day v3':>15}"
          f"{'equal per seed':>16}{'fears day v2':>14}{'fears day v3':>14}")
    print("  " + "-" * 92)
    for world in (WA, WB):
        for fo in (False, True):
            d2, d3 = acc[(world, fo, 30.0)], acc[(world, fo, 65.0)]
            common = sorted(set(d2) & set(d3))
            a2 = [d2[s][0] for s in common if d2[s][0] is not None]
            a3 = [d3[s][0] for s in common if d3[s][0] is not None]
            same = sum(1 for s in common if d2[s][0] == d3[s][0])
            f2 = [d2[s][1] for s in common if d2[s][1] is not None]
            f3 = [d3[s][1] for s in common if d3[s][1] is not None]
            m = lambda v: statistics.median(v) if v else float("nan")
            print(f"  {world:<14}{'all floors off' if fo else 'full architecture':<20}"
                  f"{m(a2):>13.1f}{m(a3):>13.1f}{f'{same}/{len(common)}':>12}"
                  f"{m(f2):>12.1f}{m(f3):>12.1f}")
    print("\n  ★ Reading ★ anchor day equal on 100% of seeds → v3 did not postpone consolidation;")
    print("           a later fears_hunger day → what moved later is the **narrative threshold**, not the moment personality sets.")


def report_branch(rows, N):
    store = {}
    for _, world, fo, s0, res in rows:
        for b, lst in res.items():
            store.setdefault((b, world, fo), [None] * N)[s0:s0 + len(lst)] = lst

    for fo in (False, True):
        arch = "−all floors ①② (★negative control★)" if fo else "full architecture"
        print("\n" + "=" * 100)
        print(f" B · anchor content intervention · {arch} · N={N} · development seeds 0+")
        print("=" * 100)

        own = {b: {i for i in range(N)
                   if store[(b, WA, fo)][i] is not None
                   and store[(b, WB, fo)][i] is not None} for b in BRANCHES}
        common = sorted(set.intersection(*own.values()))
        n_c = len(common)
        print(f"\n  Common seed set (all branches × both worlds alive): n={n_c} ({n_c/N:.1%})")
        if n_c < 50:
            print("  ⚠ not enough samples")
            continue

        opp = build_opp(n_c, random.Random(20260815))
        res = {}
        for b in BRANCHES:
            d, num, den = deltas_on(common, store[(b, WA, fo)], store[(b, WB, fo)], opp)
            res[b] = (d, num / den)

        base = res["natural anchor"][0]
        print(f"\n  {'branch':<18}{'ratio':>9}{'mean δ':>10}{'Δ vs natural':>15}{'dz':>7}{'p':>10}")
        print("  " + "-" * 64)
        prng = random.Random(777)
        for b in BRANCHES:
            d, r = res[b]
            dm = statistics.mean(d)
            if b == "natural anchor":
                print(f"  {b:<14}{r:>9.3f}{dm:>10.4f}{'—':>12}{'—':>7}{'—':>10}")
                continue
            diff = [x - y for x, y in zip(d, base)]
            obs, p = sign_perm_p(diff, prng)
            sd = statistics.stdev(diff)
            star = "***" if p < .001 else "**" if p < .01 else "*" if p < .05 else "n.s."
            print(f"  {b:<14}{r:>9.3f}{dm:>10.4f}{obs:>+12.4f}"
                  f"{obs/sd if sd else 0:>7.2f}{p:>10.4f} {star}")

        if fo:
            print("\n  ★ Negative-control reading ★ all n.s. = pass (the anchor acts only through trait_floor)")
            print("  Any significant row → there is a leak or a second anchor channel; investigate.")
        else:
            print("\n  ★ primary ★ any intervention arm significantly ≠ natural shows the anchor content is one of the causal carriers")
            print("  ★ secondary ★ the trend in Day order (monotonicity is not preregistered)")


if __name__ == "__main__":
    mp.freeze_support()
    main()
