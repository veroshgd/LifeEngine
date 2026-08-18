"""
Experiment 029 — memory_transfer_probe3.py (★ resolution-timing fix ★)
======================================================================

Run:  python memory_transfer_probe3.py

v1 (`memory_transfer_probe.py`) and v2 (`memory_transfer_probe2.py`)
are **kept intact and their results are not overwritten**. This file changes one piece of timing and adds a primary-endpoint candidate.

--------------------------------------------------------------------------------
① ★ The bug fixed: RESOLVED was judged before the Q update ★
------------------------------------------------------------
v2's loop order was:

    choice → reward → compute PE → judge RESOLVED (using the **old** Q) → update Q

So if this trial's new evidence **happens** to push the new strategy's Q past the suspect's,
that evidence has not yet been written into Q when the judgement is made.

> **resolution test was originally evaluated before incorporating the current
> outcome into Q, allowing retrieved evidence to persist for one extra decision
> after the resolution criterion had effectively been met.**

After the fix:

    choice → reward → compute PE → **update Q** → judge RESOLVED with the **updated** Q

The `calm_run` exit logic is unchanged (it always used the pre-update PE —
a prediction error is by definition relative to the expectation held **at the time**);
only `Q[other] > Q[suspect]` moves to after the Q update.

⚠ Direction: this bug **inflates** the effect (ACTIVE lives one decision longer, so memory pushes once more).
Fixing it shrinks the effect a little — but the story is unchanged (see the results at the end).

--------------------------------------------------------------------------------
② ★ Endpoint reshuffle: latency is demoted to secondary mechanistic ★
---------------------------------------------------------------------
The exit condition of `ACTIVE` ≈ "Q proves the new strategy is better", while restricted switch latency
≈ "the new strategy begins to dominate stably" — **the two are naturally bound together**, a constructive overlap.
Latency can still be reported (it describes "how much faster memory makes the switch happen" well),
but it **cannot** be 029's strongest scientific endpoint.

### ★ Primary candidate: post-change cumulative errors ★

```
C_i = Σ_{t=40}^{79} 1( choice_t ≠ correct_option_t )      how many wrong choices after the rule changes
ΔC  = C(V-memory) − C(S-memory)          ΔC < 0 when the V-memory helps
```

It is identical to the existing `post_correct` (`C = 40 × (1 − post_correct)`),
but its **unit is trials directly**. Its advantages:

```
· trials 40–79 are a window fixed in advance by the task
· it does not read whether retrieval is ACTIVE, nor when it RESOLVED
· there is no never-switch censoring       · every agent has this quantity
· its unit is trials, making a SESOI easy to set later      · it measures the actual functional cost
```

### Secondary mechanistic

`restricted switch latency` / `retrieval exposure` / `per-opportunity potency`
/ `ACTIVE duration` / `realized retrieval`.
**The primary asks "how many fewer errors were actually made", the secondary explains "why".**

--------------------------------------------------------------------------------
③ Still untouched
-----------------
```
GOOD_THRESH=.60  PE_THRESH=.30  SURPRISE_RUN_MIN=3   single reversal   seeds 0–399
λ is still swept, not chosen   ⛔ (b) relaxing SURPRISE_RUN_MIN   ⛔ (d) multiple change points
⛔ final seeds   ⛔ preregistration   ⛔ SESOI   ⛔ Stable/Volatile outcome
```

⚠ **The next step is not calibrating λ.** The hand-built MEM_S/MEM_V = ±0.667 is the **maximum contrast**;
before we know whether real Stable/Volatile histories produce m = 0.03 or 0.30,
arguing over λ = .25 versus 1 is scientifically meaningless. The correct order is:

```
fix the resolution bug → lock an independent endpoint → build real Stable/Volatile histories
→ let history generate the Episodes itself → observe the real memory-evidence distribution → and only then calibrate λ
```
"""

import math
import random
import statistics
import sys

import novel_task as NT
import memory_transfer_probe as P1
import memory_transfer_probe2 as P2
from memory_transfer_probe import (BODY_C, BODY_K, MEM_S, MEM_V,
                                   GOOD_THRESH, PE_THRESH, SURPRISE_RUN_MIN,
                                   LAMBDA_GRID, PROBE_SEEDS, query_from_state)

N_BOOT = P2.N_BOOT
ANALYSIS_SEED = P2.ANALYSIS_SEED


# ================================================================== v3 main loop
def run_fixed(body, memory, seed, lam, *, trace=False):
    """Word for word v2's, **except that RESOLVED is judged after the Q update rather than before**."""
    rows, us, a_good_first = NT.reward_table(seed)
    b = NT.BETA * NT.novelty_style(body)
    Q = [NT.Q_INIT, NT.Q_INIT]
    N = [0, 0]
    cur = None
    surprise_run = 0
    suspect = None
    calm_run = 0
    choices, rewards, active, states, runs = [], [], [], [], []
    cur_run = 0

    for t in range(NT.TRIALS):
        val = [Q[i] + b / math.sqrt(1 + N[i]) for i in (0, 1)]

        if cur is None:
            d = max(-60.0, min(60.0, (val[0] - val[1]) / NT.TAU))
            c = 0 if us[t] < 1.0 / (1.0 + math.exp(-d)) else 1
            is_active = False
        else:
            if suspect is None and query_from_state(Q[cur], surprise_run):
                suspect = cur
                calm_run = 0
            oth = 1 - cur
            is_active = suspect is not None
            if is_active:
                m, _, _ = memory.evidence("previously_good_strategy")
                s = 1.0 if cur == suspect else -1.0
            else:
                m, s = 0.0, 0.0
            z_base = (val[oth] - val[cur]) / NT.TAU
            z = max(-60.0, min(60.0, z_base + lam * m * s))
            c = oth if us[t] < 1.0 / (1.0 + math.exp(-z)) else cur
            if trace and is_active:
                states.append((z_base, s))

        r = rows[t][c]
        pe = r - Q[c]

        if cur is not None and c == cur and pe < -PE_THRESH:
            surprise_run += 1
        else:
            surprise_run = 0

        # calm_run uses the pre-update PE (a prediction error is by definition relative to the expectation held at the time)
        if suspect is not None and c == suspect:
            calm_run = calm_run + 1 if pe >= -PE_THRESH else 0

        N[c] += 1
        Q[c] += NT.ALPHA * (r - Q[c])          # ★★ update Q first ★★

        # ★★ then judge RESOLVED — using the updated Q ★★
        if suspect is not None:
            if Q[1 - suspect] > Q[suspect] or calm_run >= SURPRISE_RUN_MIN:
                suspect, calm_run = None, 0

        cur = c
        choices.append(c)
        rewards.append(r)
        active.append(1 if is_active else 0)
        if is_active:
            cur_run += 1
        elif cur_run:
            runs.append(cur_run)
            cur_run = 0
    if cur_run:
        runs.append(cur_run)

    out = {"seed": seed, "a_good_first": a_good_first, "choices": choices,
           "rewards": rewards, "fired": active, "explores": [0] * NT.TRIALS,
           "active_runs": runs}
    if trace:
        out["states"] = states
    return out


RUNNERS = {"v1 one-shot": P1.run,
           "v2 pre-fix": P2.run_stateful,
           "v3 fixed": run_fixed}


# ================================================================== endpoints
def post_change_errors(rec):
    """★ Primary candidate ★ how many wrong choices in the 40 trials after the reversal (unit: trials)"""
    ch = rec["choices"]
    return sum(1 for t in range(NT.REVERSAL_AT, NT.TRIALS)
               if ch[t] != NT.correct_option(rec["a_good_first"], t))


def latency(rec):
    """secondary mechanistic (constructively overlapping with the ACTIVE window)"""
    return NT.switch_latency_restricted(rec)


ENDPOINTS = {"ΔC post-change errors ★primary candidate★": post_change_errors,
             "Δlatency (secondary)": latency}


# ================================================================== self-checks
def _test_prior_versions_unchanged():
    chg = sum(1 for sd in PROBE_SEEDS
              if P1.run(BODY_C, MEM_S, sd, 1.0)["choices"]
              != P1.run(BODY_C, MEM_V, sd, 1.0)["choices"])
    assert chg == 71, f"v1 moved: {chg} ≠ 71"
    m2 = P2.new_swap(P2.run_stateful, 1.0, quiet=True)
    assert abs(m2["M"] - (-3.989)) < 5e-4, f"v2 pre-fix moved: {m2['M']}"
    print(f"  ✓ v1 (71/400) and v2 pre-fix (pooled M {m2['M']:+.3f})"
          f" are bit-unchanged — the old results have not been overwritten")


def _test_only_timing_changed():
    """At λ=0 the two versions must be identical: the RESOLVED timing does not affect the memory-blind trajectory"""
    d = sum(1 for sd in PROBE_SEEDS
            if P2.run_stateful(BODY_C, MEM_V, sd, 0.0)["choices"]
            != run_fixed(BODY_C, MEM_V, sd, 0.0)["choices"])
    assert d == 0, f"✗ the two versions already differ at λ=0 ({d} seeds) — more than the timing changed"
    for runner in (run_fixed,):
        dd = sum(1 for sd in PROBE_SEEDS
                 if runner(BODY_C, MEM_S, sd, 0.0)["choices"]
                 != runner(BODY_C, MEM_V, sd, 0.0)["choices"])
        assert dd == 0, "✗ memory still affects the decision at λ=0"
    print("  ✓ v2/v3 identical trial by trial at λ=0 → only the RESOLVED timing really changed")
    print("  ✓ memory-blind (λ=0): v3's two memory stores identical on 400/400 seeds")


def _test_endpoint_identity():
    """C = 40 × (1 − post_correct) must hold identically"""
    for sd in PROBE_SEEDS[:50]:
        r = run_fixed(BODY_C, MEM_V, sd, 1.0)
        assert abs(post_change_errors(r)
                   - 40 * (1 - NT.correct_rate(r, 40, 80))) < 1e-9
    print("  ✓ post-change errors ≡ 40 × (1 − post-reversal accuracy)")


# ================================================================== analysis
def swap(runner, lam, endpoint):
    L = {}
    for body in (BODY_C, BODY_K):
        for mem in (MEM_S, MEM_V):
            L[(body.name, mem.name)] = [endpoint(runner(body, mem, sd, lam))
                                        for sd in PROBE_SEEDS]
            assert len(L[(body.name, mem.name)]) == len(PROBE_SEEDS)

    def per_seed(body):
        return [v - s for v, s in zip(L[(body.name, MEM_V.name)],
                                      L[(body.name, MEM_S.name)])]

    mc, mk = per_seed(BODY_C), per_seed(BODY_K)
    M_C, M_K = statistics.fmean(mc), statistics.fmean(mk)
    rng = random.Random(ANALYSIS_SEED)
    n = len(PROBE_SEEDS)
    boot = []
    for _ in range(N_BOOT):
        idx = [rng.randrange(n) for _ in range(n)]
        boot.append((statistics.fmean([mc[i] for i in idx])
                     + statistics.fmean([mk[i] for i in idx])) / 2.0)
    boot.sort()
    return dict(M_C=M_C, M_K=M_K, M=(M_C + M_K) / 2.0,
                ci=(boot[int(0.025 * N_BOOT)], boot[int(0.975 * N_BOOT)]),
                inter=M_C - M_K,
                same_sign=(M_C < 0) == (M_K < 0) and M_C != 0 and M_K != 0)


def bugfix_impact():
    print("\n" + "=" * 78)
    print("① Effect of the bug fix (pre-fix v2  →  fixed v3)")
    print("=" * 78)
    print(f"{'λ':>6}{'pooled M pre-fix':>20}{'pooled M fixed':>18}"
          f"{'Δ':>10}{'same direction':>16}")
    print("-" * 78)
    for lam in LAMBDA_GRID:
        if lam == 0:
            continue
        a = swap(P2.run_stateful, lam, latency)
        b = swap(run_fixed, lam, latency)
        print(f"{lam:>6.2f}{a['M']:>+20.3f}{b['M']:>+18.3f}"
              f"{b['M'] - a['M']:>+10.3f}"
              f"{'yes' if b['same_sign'] else 'no':>16}")
    # exposure & downstream
    for lam in (1.0,):
        for nm, rn in (("pre-fix v2", P2.run_stateful), ("fixed v3", run_fixed)):
            exp = statistics.fmean([sum(rn(BODY_C, MEM_V, sd, lam)["fired"])
                                    for sd in PROBE_SEEDS])
            pot = statistics.fmean([sum(rn(BODY_C, MEM_V, sd, 0.0)["fired"])
                                    for sd in PROBE_SEEDS])
            dpc = statistics.fmean(
                [NT.correct_rate(rn(BODY_C, MEM_V, sd, lam), 40, 80)
                 - NT.correct_rate(rn(BODY_C, MEM_S, sd, lam), 40, 80)
                 for sd in PROBE_SEEDS])
            print(f"  {nm:<12} λ=1  potential exposure {pot:>5.2f}"
                  f"   realized {exp:>5.2f}   Δpost-reversal accuracy {dpc:+.4f}")


def endpoint_report():
    print("\n" + "=" * 78)
    print("② ENDPOINT — ΔC (primary candidate) and Δlatency (secondary)")
    print("=" * 78)
    for ep_name, ep in ENDPOINTS.items():
        print(f"\n{ep_name}")
        print(f"{'mechanism':<18}{'λ':>6}{'M_C':>9}{'M_K':>9}{'pooled':>10}"
              f"{'95% CI (descriptive)':>26}{'same direction':>16}{'interaction':>13}")
        print("-" * 78)
        for name, runner in RUNNERS.items():
            for lam in LAMBDA_GRID:
                if lam == 0:
                    continue
                r = swap(runner, lam, ep)
                print(f"{name:<14}{lam:>6.2f}{r['M_C']:>+9.3f}{r['M_K']:>+9.3f}"
                      f"{r['M']:>+10.3f}"
                      f"   [{r['ci'][0]:+.3f}, {r['ci'][1]:+.3f}]"
                      f"{'yes' if r['same_sign'] else 'no':>16}"
                      f"{r['inter']:>+13.3f}")


def mechanism_report():
    print("\n" + "=" * 78)
    print("③ SECONDARY MECHANISTIC —— exposure / ACTIVE duration / potency")
    print("=" * 78)
    print(f"{'mechanism':<18}{'body':<8}{'eligible':>10}{'potential':>11}"
          f"{'realized(λ=1)':>15}{'ACTIVE length':>15}")
    print("-" * 78)
    for name, runner in RUNNERS.items():
        for body in (BODY_C, BODY_K):
            pot = [sum(runner(body, MEM_V, sd, 0.0)["fired"]) for sd in PROBE_SEEDS]
            rea = [sum(runner(body, MEM_V, sd, 1.0)["fired"]) for sd in PROBE_SEEDS]
            elig = sum(1 for x in pot if x > 0) / len(PROBE_SEEDS)
            if name == "v3 fixed":
                runs = [x for sd in PROBE_SEEDS
                        for x in runner(body, MEM_V, sd, 1.0)["active_runs"]]
                dur = f"{statistics.fmean(runs):.2f}" if runs else "—"
            else:
                dur = "—"
            print(f"{name:<14}{body.name[:6]:<8}{elig:>9.1%}"
                  f"{statistics.fmean(pot):>11.2f}{statistics.fmean(rea):>15.2f}"
                  f"{dur:>12}")

    mS = MEM_S.evidence("previously_good_strategy")[0]
    mV = MEM_V.evidence("previously_good_strategy")[0]
    states = []
    for sd in PROBE_SEEDS:
        states += run_fixed(BODY_C, MEM_V, sd, 0.0, trace=True)["states"]
    sig = lambda z: 1.0 / (1.0 + math.exp(-max(-60.0, min(60.0, z))))  # noqa: E731
    base = [sig(z) for z, _ in states]
    sat = sum(1 for p in base if p >= 0.9 or p <= 0.1) / len(base)
    print(f"\nv3 potency (decision states frozen at λ=0)"
          f"  opportunities {len(states)}   median base p {statistics.median(base):.3f}"
          f"   saturated {sat:.1%}")
    print(f"  {'λ':>6}{'mean|Δp|':>11}{'median|Δp|':>13}{'p90|Δp|':>11}")
    for lam in LAMBDA_GRID:
        if lam == 0:
            continue
        d = sorted(abs(sig(z + lam * mV * s) - sig(z + lam * mS * s))
                   for z, s in states)
        print(f"  {lam:>6.2f}{statistics.fmean(d):>11.4f}"
              f"{statistics.median(d):>13.4f}"
              f"{d[min(len(d) - 1, int(0.9 * len(d)))]:>11.4f}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    fp = NT.assert_frozen()
    print("=" * 78)
    print("029 probe v3 — resolution-timing fix + endpoint reshuffle (★still a probe★)")
    print("=" * 78)
    print(f"task substrate 027 fingerprint {fp} (unchanged)  seeds {PROBE_SEEDS[0]}–{PROBE_SEEDS[-1]}"
          f"  n={len(PROBE_SEEDS)}  ★80000–81499 untouched★")
    print(f"thresholds untouched: GOOD_THRESH={GOOD_THRESH} PE_THRESH={PE_THRESH} "
          f"SURPRISE_RUN_MIN={SURPRISE_RUN_MIN}   single reversal   λ swept, not chosen")
    print("Only change: RESOLVED is judged after the Q update instead of before")

    print("\n[ engineering self-check ]")
    _test_prior_versions_unchanged()
    _test_only_timing_changed()
    _test_endpoint_identity()

    bugfix_impact()
    endpoint_report()
    mechanism_report()

    print("\n" + "=" * 78)
    print("★ Reading ★")
    print("=" * 78)
    c = swap(run_fixed, 1.0, post_change_errors)
    l_ = swap(run_fixed, 1.0, latency)
    print(f"  λ=1  ΔC (primary candidate) = {c['M']:+.3f} trials"
          f"   CI [{c['ci'][0]:+.3f}, {c['ci'][1]:+.3f}]"
          f"   same direction {'yes' if c['same_sign'] else 'no'}")
    print(f"  λ=1  Δlatency (secondary) = {l_['M']:+.3f} trials"
          f"   same direction {'yes' if l_['same_sign'] else 'no'}")
    print("\n  Directional SWAP check (after the fix): see whether M_C / M_K share a sign")
    print("  ⛔ the dominance criterion was RETIRED long ago and is not computed")
    print("\n⚠ The hand-built MEM_S/MEM_V = ±0.667 is the **maximum contrast** — the above is an upper bound, not an expected effect size.")
    print("⚠ The next step is not calibrating λ, it is building real Stable/Volatile histories"
          " (memory_acquisition_probe.py).")
