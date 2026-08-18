"""
Experiment 029 — memory_transfer_rehearsal.py (★ OWN / DELETE / SWAP / SHUFFLE ★)
=================================================================================

Run:  python memory_transfer_rehearsal.py

**The first time natural Stable/Volatile memory is attached to the novel task.**
Still **only the burned development seeds 0–399**. ⛔ 80000–81499 untouched, ⛔ no preregistration, ⛔ no SESOI.

--------------------------------------------------------------------------------
Frozen inputs (all frozen before this file runs; it may change none of them)
----------------------------------------------------------------------------
```
acquisition   ANOMALY_AT=36  ANOMALY_LEN=8  T_PROBLEM=66 (22 after the anomaly)
retrieval     stateful, RESOLVED judged after the Q update (probe3)
interface     MEMORY_LAMBDA = 1.00   ← frozen by the group-blind capacity calibration
gates         saturation ≤5% / median|Δp| ≥.02 / flip ≤25% / max exposure ≤20/80
primary       ΔC = post-change cumulative errors (wrong choices on trials 40–79)
secondary     restricted switch latency + exposure / ACTIVE duration
population    ★all 400 seeds, including agents with m=0★ (rule 91)
```

--------------------------------------------------------------------------------
The four arms
-------------
```
OWN       each agent uses the memory grown from its own developmental history
DELETE    memory removed entirely (empty store, m≡0)
SWAP      the memories of the two conditions are exchanged
SHUFFLE   action_relation shuffled within an agent's entries — marginals preserved, relations destroyed
```

### ⚠⚠ To be clear first: under this architecture DELETE and SWAP are **algebraic identities** ⚠⚠

In this rehearsal the body is a **constant** (`NeutralBody`), and the developmental history carries
**nothing** into the task except memory. So the two conditions of one seed
**differ only in memory**, and therefore:

```
DELETE   both sides empty → identical trial by trial → ΔC ≡ 0        (an identity)
SWAP     the memories exchanged → OWN with a relabelled arm → ΔC ≡ −ΔC(OWN)   (an identity)
```

**They are not evidence, they are assertions** — used to prove "the developmental history has no second leakage path besides memory".
This file runs them **as assertions** (raising on mismatch), not interpreting them as results.

> ★ Rule 93 (final form) ★
> When memory is the sole developmental pathway into the test task, DELETE and
> within-seed SWAP are **algebraic integrity checks rather than independent
> causal evidence**. A second developmental pathway should **not** be introduced
> merely to make these controls non-trivial; causal support should instead come
> from **interventions on memory structure** such as relational shuffling and
> cross-seed donor tests.
>
> ⛔ The trait path must not be added back just to make SWAP "non-trivial" —
> that would turn the clean `history → relational memory → novel adaptation`
> back into `history → memory + traits → …`,
> bringing back memory/trait competition, interaction and budget, i.e. the whole 027/028 apparatus.

So: **the confirmatory scientific control is SHUFFLE** (an intervention on the memory structure itself),
plus one arm that answers the seed-coupling question:

```
XSEED-DONOR   seed s uses the opposite-condition memory of **another seed s'=(s+200)%400**
              → answers "the effect is not caused by development and test sharing a seed"
```

★ Naming discipline ★ **It is not called SWAP-XS** — it asks a different question from SWAP:
SWAP asks "does the result follow the memory identity" (an identity under this architecture);
XSEED-DONOR asks "does the effect depend on development and test sharing a seed" (non-trivial).

--------------------------------------------------------------------------------
Three questions to check (decided by the user)
----------------------------------------------
```
① can natural Stable/Volatile memory produce a downstream difference through the frozen λ=1 interface
② does DELETE collapse that difference
③ does SWAP make the result follow the memory identity, and does SHUFFLE destroy that effect
```
⚠ As stated above, the DELETE/SWAP parts of ②③ are identities;
**what really tests ③ are SHUFFLE and XSEED-DONOR.**

--------------------------------------------------------------------------------
Still not done
--------------
```
⛔ final seeds  ⛔ preregistration  ⛔ SESOI  ⛔ changing λ  ⛔ changing any acquisition parameter
```
Every CI in this file is **descriptive**: with no SESOI there is no functional-significance reading.
"""

import random
import statistics
import sys

import novel_task as NT
import memory_transfer_probe3 as P3
import memory_acquisition_probe as ACQ
from memory_transfer_probe import Episode, MemoryStore, PROBE_SEEDS
from memory_lambda_calibration import MEMORY_LAMBDA

BODY = ACQ.NeutralBody
LAM = MEMORY_LAMBDA
N_BOOT = 10000
ANALYSIS_SEED = 8181
SHUFFLE_SALT = 0x29C10
XS_OFFSET = len(PROBE_SEEDS) // 2          # the offset of XSEED-DONOR


# ================================================================== memory
def build_memories():
    """The natural memory of each seed × condition (including those that grew none → an empty store, m=0)"""
    mem = {}
    for cond in ACQ.CONDITIONS:
        for sd in PROBE_SEEDS:
            eps, _ = ACQ.acquire(sd, cond)
            mem[(cond, sd)] = MemoryStore(f"{cond}-{sd}", eps)
    return mem


def shuffled(store, sd):
    """★ SHUFFLE ★ shuffle action_relation within the agent's own entries.

    Preserved: the episode count, the counts of stay and switch, the marginal distribution of outcome.
    Destroyed: the **relation** between action and outcome.
    → If the effect comes from marginal statistics, it should survive SHUFFLE;
      if it comes from relational structure, it should collapse.
    """
    eps = store.episodes
    rel = [e.action_relation for e in eps]
    random.Random(SHUFFLE_SALT ^ sd ^ (len(eps) << 8)).shuffle(rel)
    return MemoryStore(store.name + "-shuf", [
        Episode(context=e.context,
                previous_expectation=e.previous_expectation,
                observation=e.observation,
                prediction_error=e.prediction_error,
                action_relation=r,
                outcome=e.outcome)
        for e, r in zip(eps, rel)])


EMPTY = MemoryStore("empty", [])


# ================================================================== endpoints
def endpoints(rec):
    return (P3.post_change_errors(rec),          # ★ primary candidate ★
            P3.latency(rec),                     # secondary mechanistic
            sum(rec["fired"]),                   # realized exposure
            statistics.fmean(rec["active_runs"]) if rec["active_runs"] else 0.0)


def arm(mem, memory_of):
    """Run one arm: memory_of(cond, seed) → the memory store this agent actually uses in this arm"""
    out = {}
    for cond in ACQ.CONDITIONS:
        rows = [endpoints(P3.run_fixed(BODY, memory_of(cond, sd), sd, LAM))
                for sd in PROBE_SEEDS]
        out[cond] = rows
        assert len(rows) == len(PROBE_SEEDS)      # rules 88/91: the whole population
    return out


def paired_delta(res, idx):
    """Same-seed paired difference, Volatile − Stable"""
    return [v[idx] - s[idx]
            for s, v in zip(res[ACQ.CONDITIONS[0]], res[ACQ.CONDITIONS[1]])]


def boot_ci(d):
    rng = random.Random(ANALYSIS_SEED)
    n = len(d)
    b = sorted(statistics.fmean([d[rng.randrange(n)] for _ in range(n)])
               for _ in range(N_BOOT))
    return b[int(0.025 * N_BOOT)], b[int(0.975 * N_BOOT)]


# ================================================================== main
if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print("=" * 78)
    print("029 REHEARSAL — natural memory × novel task (★development seeds, not FINAL★)")
    print("=" * 78)
    print(f"acquisition ANOMALY_AT={ACQ.ANOMALY_AT} LEN={ACQ.ANOMALY_LEN} "
          f"T={ACQ.T_PROBLEM}   interface ★λ={LAM:.2f} frozen★")
    print(f"task substrate 027 fingerprint {NT.assert_frozen()}   seeds "
          f"{PROBE_SEEDS[0]}–{PROBE_SEEDS[-1]}  n={len(PROBE_SEEDS)}"
          f"   ★80000–81499 untouched★")
    print("primary = ΔC post-change errors (trials 40–79)  "
          "secondary = latency / exposure")

    mem = build_memories()
    # ★ Convention frozen ★ primary extensive margin = P(relational memory COMPLETE)
    #   complete := at least one stay entry and at least one switch entry
    #   ⚠ It is **not** "m ≠ 0": an agent with entries on both sides whose two means happen to be equal
    #     has formed a **complete** relational memory that merely says "switching and staying make no difference" —
    #     that is **meaningful zero evidence**, not "no memory".
    comp, nz = {}, {}
    for c in ACQ.CONDITIONS:
        ev = [mem[(c, sd)].evidence("previously_good_strategy")
              for sd in PROBE_SEEDS]
        comp[c] = statistics.fmean([1.0 if (a > 0 and b > 0) else 0.0
                                    for _, a, b in ev])
        nz[c] = statistics.fmean([1.0 if m != 0 else 0.0 for m, _, _ in ev])
    print("\n★ memory completeness (primary extensive margin) ★  "
          + "   ".join(f"{c} {comp[c]:.2%}" for c in ACQ.CONDITIONS))
    print("  non-zero evidence rate (reportable, but not called extensive / availability)  "
          + "   ".join(f"{c} {nz[c]:.2%}" for c in ACQ.CONDITIONS))
    print("  ★ every primary transfer analysis still uses all predefined agents,"
          " including incomplete ones and m=0 ★")

    ARMS = {
        "OWN": lambda c, sd: mem[(c, sd)],
        "DELETE": lambda c, sd: EMPTY,
        "SWAP": lambda c, sd: mem[(ACQ.CONDITIONS[1 - ACQ.CONDITIONS.index(c)], sd)],
        "SHUFFLE": lambda c, sd: shuffled(mem[(c, sd)], sd),
        "XSEED-DONOR": lambda c, sd: mem[(c, PROBE_SEEDS[
            (PROBE_SEEDS.index(sd) + XS_OFFSET) % len(PROBE_SEEDS)])],
    }

    res = {name: arm(mem, fn) for name, fn in ARMS.items()}

    print("\n" + "=" * 78)
    print("★ PRIMARY: ΔC = C(Volatile) − C(Stable), same-seed paired, whole population ★")
    print("=" * 78)
    print(f"{'arm':<14}{'C Stable':>11}{'C Volatile':>12}{'ΔC':>10}"
          f"{'95% CI (descriptive)':>26}{'relative to OWN':>18}")
    print("-" * 78)
    dc = {}
    for name in ARMS:
        d = paired_delta(res[name], 0)
        dc[name] = statistics.fmean(d)
        cs = statistics.fmean([x[0] for x in res[name][ACQ.CONDITIONS[0]]])
        cv = statistics.fmean([x[0] for x in res[name][ACQ.CONDITIONS[1]]])
        lo, hi = boot_ci(d)
        rel = dc[name] / dc["OWN"] if dc["OWN"] else float("nan")
        print(f"{name:<10}{cs:>11.3f}{cv:>12.3f}{dc[name]:>+10.3f}"
              f"   [{lo:+.3f}, {hi:+.3f}]{rel:>11.2f}")

    print("\n" + "=" * 78)
    print("★ Identity assertions (not results) ★")
    print("=" * 78)
    d_del = paired_delta(res["DELETE"], 0)
    assert all(x == 0 for x in d_del), "✗ DELETE is non-zero → the developmental history has a leakage path besides memory"
    print("  ✓ DELETE: identical trial by trial on 400/400 seeds, ΔC ≡ 0")
    print("     → the developmental history has no second path into the task besides memory (an assertion, not a finding)")
    d_own, d_swap = paired_delta(res["OWN"], 0), paired_delta(res["SWAP"], 0)
    assert all(a == -b for a, b in zip(d_own, d_swap)), "✗ SWAP ≠ −OWN"
    print("  ✓ SWAP: exactly −OWN seed by seed (an algebraic identity when the body is constant)")
    print("     → the outcome follows the memory identity completely, but **that is construction, not evidence**")

    print("\n" + "=" * 78)
    print("★ The real controls: SHUFFLE (destroys the relation, preserves the marginals) and XSEED-DONOR ★")
    print("=" * 78)
    print(f"  OWN      ΔC = {dc['OWN']:+.3f}")
    print(f"  SHUFFLE  ΔC = {dc['SHUFFLE']:+.3f}"
          f"   retains {dc['SHUFFLE'] / dc['OWN']:.1%} of OWN"
          if dc["OWN"] else "")
    print(f"  XSEED    ΔC = {dc['XSEED-DONOR']:+.3f}"
          f"   retains {dc['XSEED-DONOR'] / dc['OWN']:.1%} of OWN")
    # ---- SHUFFLE's preregistered mechanistic control: the retention ratio ----
    d_own, d_shf = paired_delta(res["OWN"], 0), paired_delta(res["SHUFFLE"], 0)
    rng = random.Random(ANALYSIS_SEED)
    n = len(PROBE_SEEDS)
    ratios = []
    for _ in range(N_BOOT):
        idx = [rng.randrange(n) for _ in range(n)]        # ★one shared set of seed indices★
        a = abs(statistics.fmean([d_own[i] for i in idx]))
        b = abs(statistics.fmean([d_shf[i] for i in idx]))
        ratios.append(b / a if a > 0 else float("inf"))   # ★applied per replicate★
    ratios.sort()
    r_lo, r_hi = ratios[int(0.025 * N_BOOT)], ratios[int(0.975 * N_BOOT)]
    r_pt = abs(dc["SHUFFLE"]) / abs(dc["OWN"])
    print(f"\n  ★ retention ratio |ΔC_shuffle| / |ΔC_own| = {r_pt:.3f}"
          f"   95% CI [{r_lo:.3f}, {r_hi:.3f}]")
    print("     joint same-seed bootstrap; abs and division applied **per replicate** (the lesson of 028)")
    print(f"     preregistered criterion: CI upper bound < 0.25 → "
          f"{'met' if r_hi < 0.25 else 'not met'}"
          f" (≥75% of the transfer disappears once the relation is destroyed)")
    print("     ⚠ the ratio is always ≥ 0, so 'the CI excludes 0' carries no information (rule 84) — look only at the **upper bound** vs 0.25.")
    print("\n  Expected: SHUFFLE should collapse (the effect comes from the relation, not from marginal statistics);")
    print("        XSEED-DONOR should largely survive (the effect is carried by memory content, not by development and test sharing a seed).")

    print("\n" + "=" * 78)
    print("★ SECONDARY mechanistic ★")
    print("=" * 78)
    print(f"{'arm':<14}{'Δlatency':>11}{'exposure S':>13}{'exposure V':>13}"
          f"{'ACTIVE length S':>18}{'ACTIVE length V':>18}")
    print("-" * 78)
    for name in ARMS:
        dl = statistics.fmean(paired_delta(res[name], 1))
        es = statistics.fmean([x[2] for x in res[name][ACQ.CONDITIONS[0]]])
        ev = statistics.fmean([x[2] for x in res[name][ACQ.CONDITIONS[1]]])
        rs = statistics.fmean([x[3] for x in res[name][ACQ.CONDITIONS[0]]])
        rv = statistics.fmean([x[3] for x in res[name][ACQ.CONDITIONS[1]]])
        print(f"{name:<10}{dl:>+11.3f}{es:>13.2f}{ev:>13.2f}"
              f"{rs:>15.2f}{rv:>15.2f}")

    print("\n" + "=" * 78)
    print("⚠ Every CI is descriptive (seed cluster bootstrap, n_boot=10000,"
          f" analysis seed {ANALYSIS_SEED}).")
    print("⚠ No SESOI → no functional-significance reading. ⛔ λ and the acquisition parameters must not be changed on this basis.")
    print("⚠ This is a **rehearsal on development seeds**, not a confirmatory result of 029.")
    print("=" * 78)
