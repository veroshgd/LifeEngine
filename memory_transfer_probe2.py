"""
Experiment 029 — memory_transfer_probe2.py (★ identifiability probe v2: stateful retrieval ★)
=============================================================================================

Run:  python memory_transfer_probe2.py

v1 (`memory_transfer_probe.py`) is **kept exactly as it was** and its results are not overwritten —
that failure is itself part of the methodological record. This file imports v1's memory stores, bodies and thresholds;
**the only thing changed is the retrieval mechanism**: one-shot → stateful.

--------------------------------------------------------------------------------
① Correction to criterion (c): the dominance criterion is ★ formally withdrawn ★
--------------------------------------------------------------------------------
    ⛔ withdrawn: |memory effect| > |body effect|

> Original SWAP dominance criterion failed at all tested λ, after which
> inspection showed that the criterion compared an event-triggered channel
> active on ~0.69/80 trials with an always-on trait channel. The dominance
> criterion was therefore **retired before any Stable/Volatile outcome was
> observed**.

**The reason for withdrawing it is not that it failed, but that it measures the wrong thing.**
It answers "is memory's endpoint effect larger than body's",
whereas SWAP should answer "**with the body completely fixed, does swapping only the memory change future
behaviour in the predicted direction**". Those are two entirely different estimands.

### The new SWAP (implemented in this file)

```
M_C = L(Body C, Memory V) − L(Body C, Memory S)
M_K = L(Body K, Memory V) − L(Body K, Memory S)
M   = (M_C + M_K) / 2
```

Of interest: ① whether M_C and M_K agree in direction  ② whether pooled M is in the preregistered direction
      ③ whether it exceeds a functional SESOI (**no SESOI is fixed today**)
      ④ whether the Body × Memory interaction is strong enough to mean memory only works on one kind of body

**The body effect is only a robustness diagnostic and is no longer a gate.**

--------------------------------------------------------------------------------
② Directional correction to rule 86 → the new rule 87
-----------------------------------------------------
❌ Old wording: "there must be equal exposure before comparing."

**Memory and personality should not have the same exposure in the first place.**
Personality is a prior that is always present; memory should be **invoked only when a relevant situation arises**.
Forcing memory to be online for 80/80 trials in the name of fairness would destroy the most important theoretical
feature of this design — **context-dependent retrieval**.

> ### ★ Rule 87 ★
> For an event-triggered mechanism, **an endpoint effect must not be compared in size directly against an
> always-on mechanism**; **exposure** and **per-opportunity influence** must be reported separately.

So the memory effect is split into two quantities:

```
A. Exposure   E_i = #{retrieval-eligible trials}      ← how many chances it gets to speak
B. Potency    Δp_t = p_switch(M_V) − p_switch(M_S)    ← how far it can push each time it speaks
              computed on **exactly the same decision state**
```

How potency is computed: **freeze the decision states from the memory-blind (λ=0) trajectory**
(same Q / same N / same current option / same surprise state),
then counterfactually swap in Memory S / Memory V only.
Only that distinguishes "memory is weak" from "memory is forceful whenever it speaks, but almost never gets the chance".

--------------------------------------------------------------------------------
③ (a) stateful retrieval — not "held for a fixed N trials"
----------------------------------------------------------
A fixed N would add an arbitrary parameter. Instead: **retrieval → active memory state → resolution**:

```
NORMAL
  ↓  a run of persistent surprises (≥ SURPRISE_RUN_MIN, with the strategy in hand having long been good)
RETRIEVE   ← record the suspect strategy at this moment ("this is the one I doubt")
  ↓  m enters the working decision state and continues to be used on each subsequent decision
ACTIVE
  ↓  ① the new strategy gathers enough evidence: Q[the other] > Q[suspect]   → "ah, it really did change"
  ↓  ② the surprise is explained: SURPRISE_RUN_MIN consecutive non-surprises on the suspect
  ↓                                                     → "that was just chance"
RESOLVED → clear the memory evidence and return to NORMAL (it can fire again later)
```

**Both resolution conditions use only existing quantities** (Q, pe, `PE_THRESH`, `SURPRISE_RUN_MIN`),
**adding no new parameter**. ② is symmetric with the entry condition: entry needs 3 consecutive surprises,
and exit needs 3 consecutive non-surprises.

### ★ Key: while ACTIVE, m acts on the suspect, not on the "switch" action ★

v1 added `+λm` to "switch" on every trial. Once that has pushed one switch through,
adding `+λm` again on the next trial means "switch back again" — semantically wrong, and it oscillates.

What the memory contains is "**in this situation, leaving that suspect strategy pays better**". So:

```
logit(switch) += λ · m · s        s = +1 if switching means **leaving the suspect**
                                  s = −1 if switching means **returning to the suspect**
```

That is what "I remember meeting this situation before, so I now **suspect the rule changed**" means —
and that suspicion persists until either "it really did change" or "that was just chance".

⚠ `suspect` is a **working variable** at decision time; it is **not** stored in an Episode.
Memory still holds only stay/switch and no option identity (rule 85 is unchanged).

--------------------------------------------------------------------------------
④ Locking down a hidden problem along the way: potential vs realized retrieval
------------------------------------------------------------------------------
`fired` is itself affected by the preceding choice sequence — a cautious body, for instance, stays three times in a row
more easily and so triggers retrieval more easily. **The firing count is itself a product of task dynamics.**

```
potential retrieval opportunity   defined on the memory-blind (λ=0) trajectory → measures mechanism exposure
realized retrieval                what actually happens on the memory-enabled trajectory → part of the outcome
```

⛔ It is **absolutely forbidden** to analyse only the agents that "successfully recalled a memory" — that is survivor conditioning.
Every summary in this file uses **all 400 seeds**, with no filtering by whether retrieval fired (asserted).

--------------------------------------------------------------------------------
⑤ What is deliberately left untouched this round
------------------------------------------------
```
GOOD_THRESH=.60   PE_THRESH=.30   SURPRISE_RUN_MIN=3   the task still has a single reversal
seeds 0–399       λ is still swept, not chosen
⛔ (b) relaxing SURPRISE_RUN_MIN      ⛔ (d) a multi-change-point task
⛔ final seeds  ⛔ preregistration  ⛔ SESOI  ⛔ Stable/Volatile outcome
```

**Why (a) before (b)**: v1 already showed the decision is **not saturated** when retrieval fires
(median base p(switch) 0.208), so it is not "remembered too late to have a choice".
Taking `SURPRISE_RUN_MIN` from 3 to 2 only makes memory appear earlier and
**does not fix "cleared as soon as it appears"** — that treats the quantity, not the mechanism.

**Why not (d) now**: turning one reversal into three naturally increases exposure, and if the result strengthens
we cannot tell "the mechanism was fixed" from "the same weak one-shot effect repeated three times".
(d) belongs after the mechanism is right on a single change point, at which time it becomes a
**dose-of-opportunity robustness test**.
"""

import math
import random
import statistics
import sys

import novel_task as NT
import memory_transfer_probe as P1
from memory_transfer_probe import (BODY_C, BODY_K, MEM_S, MEM_V,
                                   GOOD_THRESH, PE_THRESH, SURPRISE_RUN_MIN,
                                   LAMBDA_GRID, PROBE_SEEDS, query_from_state)

N_BOOT = 10000
ANALYSIS_SEED = 8181            # fixed, so the analysis layer is reproducible


# ================================================================== v2 main loop
def run_stateful(body, memory, seed, lam, *, trace=False):
    """stateful retrieval: RETRIEVE → ACTIVE → RESOLVED.

    Returns choices/rewards + the active flag of each trial; with trace=True it additionally returns
    the frozen decision state of each ACTIVE trial (for the counterfactual potency computation).
    """
    rows, us, a_good_first = NT.reward_table(seed)
    b = NT.BETA * NT.novelty_style(body)
    Q = [NT.Q_INIT, NT.Q_INIT]
    N = [0, 0]
    cur = None
    surprise_run = 0
    suspect = None                 # None = NORMAL; otherwise ACTIVE, holding the suspected strategy
    calm_run = 0
    choices, rewards, active, states = [], [], [], []

    for t in range(NT.TRIALS):
        val = [Q[i] + b / math.sqrt(1 + N[i]) for i in (0, 1)]

        if cur is None:
            d = max(-60.0, min(60.0, (val[0] - val[1]) / NT.TAU))
            c = 0 if us[t] < 1.0 / (1.0 + math.exp(-d)) else 1
            is_active = False
        else:
            # ---- NORMAL → RETRIEVE: the entry condition is word for word v1's ----
            if suspect is None and query_from_state(Q[cur], surprise_run):
                suspect = cur          # ★ record "this is the one I doubt" ★
                calm_run = 0

            oth = 1 - cur
            is_active = suspect is not None
            if is_active:
                m, _, _ = memory.evidence("previously_good_strategy")
                s = 1.0 if cur == suspect else -1.0   # is switching leaving or returning to the suspect
            else:
                m, s = 0.0, 0.0

            z_base = (val[oth] - val[cur]) / NT.TAU
            z = max(-60.0, min(60.0, z_base + lam * m * s))
            c = oth if us[t] < 1.0 / (1.0 + math.exp(-z)) else cur
            if trace and is_active:
                states.append((z_base, s))

        r = rows[t][c]
        pe = r - Q[c]

        # Exactly v1's surprise_run convention (the entry condition is untouched)
        if cur is not None and c == cur and pe < -PE_THRESH:
            surprise_run += 1
        else:
            surprise_run = 0

        # ---- ACTIVE → RESOLVED (both conditions use only existing quantities, no new parameter) ----
        if suspect is not None:
            if c == suspect:
                calm_run = calm_run + 1 if pe >= -PE_THRESH else 0
            if Q[1 - suspect] > Q[suspect]:        # ① the new strategy has gathered enough evidence
                suspect, calm_run = None, 0
            elif calm_run >= SURPRISE_RUN_MIN:     # ② the surprise has been explained
                suspect, calm_run = None, 0

        N[c] += 1
        Q[c] += NT.ALPHA * (r - Q[c])
        cur = c
        choices.append(c)
        rewards.append(r)
        active.append(1 if is_active else 0)

    out = {"seed": seed, "a_good_first": a_good_first, "choices": choices,
           "rewards": rewards, "fired": active, "explores": [0] * NT.TRIALS}
    if trace:
        out["states"] = states
    return out


RUNNERS = {"v1 one-shot": P1.run, "v2 stateful": run_stateful}


def latency(rec):
    return NT.switch_latency_restricted(rec)


def post_correct(rec):
    return NT.correct_rate(rec, NT.REVERSAL_AT, NT.TRIALS)


# ================================================================== self-checks
def _test_memory_blind(runner):
    d = sum(1 for sd in PROBE_SEEDS
            if runner(BODY_C, MEM_S, sd, 0.0)["choices"]
            != runner(BODY_C, MEM_V, sd, 0.0)["choices"])
    assert d == 0, f"✗ memory still affects the decision at λ=0 ({d} seeds)"
    return True


def _test_v1_unchanged():
    """★ v1 must still reproduce its original failure bit for bit — it must not be overwritten ★"""
    chg = sum(1 for sd in PROBE_SEEDS
              if P1.run(BODY_C, MEM_S, sd, 1.0)["choices"]
              != P1.run(BODY_C, MEM_V, sd, 1.0)["choices"])
    dl = statistics.fmean([latency(P1.run(BODY_C, MEM_V, sd, 1.0))
                           - latency(P1.run(BODY_C, MEM_S, sd, 1.0))
                           for sd in PROBE_SEEDS])
    assert chg == 71, f"v1's changed-trajectory count moved: {chg} ≠ 71 (the value in the log)"
    assert abs(dl - (-0.125)) < 1e-9, f"v1's Δlatency moved: {dl}"
    print(f"  ✓ v1 still reproduces the original result bit for bit (λ=1: 71/400 changed, Δlatency {dl:+.3f})"
          f" — the record of the failure has not been overwritten")


def _test_no_survivor_conditioning(cells):
    for k, v in cells.items():
        assert len(v) == len(PROBE_SEEDS), \
            f"✗ {k} summarised only {len(v)}/{len(PROBE_SEEDS)} seeds — survivor conditioning"
    print(f"  ✓ every summary uses all {len(PROBE_SEEDS)} seeds,"
          f" with no filtering by whether retrieval fired")


# ================================================================== ① ② exposure
def exposure_report():
    """potential (defined on the λ=0 trajectory) vs realized (what happens on the memory-enabled trajectory)"""
    print("\n" + "=" * 78)
    print("① ② EXPOSURE — potential (defined at λ=0) vs realized (actual at λ>0)")
    print("=" * 78)
    print(f"{'mechanism':<18}{'body':<10}{'eligible seeds':>16}"
          f"{'potential trial':>16}{'realized trial (λ=1)':>22}")
    print("-" * 78)
    out = {}
    for name, runner in RUNNERS.items():
        for body in (BODY_C, BODY_K):
            pot = [sum(runner(body, MEM_V, sd, 0.0)["fired"]) for sd in PROBE_SEEDS]
            rea = [sum(runner(body, MEM_V, sd, 1.0)["fired"]) for sd in PROBE_SEEDS]
            elig = sum(1 for x in pot if x > 0) / len(PROBE_SEEDS)
            print(f"{name:<14}{body.name[:8]:<10}{elig:>13.1%}"
                  f"{statistics.fmean(pot):>16.2f}{statistics.fmean(rea):>22.2f}")
            out[(name, body.name)] = (elig, statistics.fmean(pot),
                                      statistics.fmean(rea))
    print("\n⚠ potential is defined on the memory-blind trajectory — it is **mechanism exposure**;")
    print("  realized is affected by choice-sequence feedback — it is **part of the outcome**.")
    return out


# ================================================================== ③ potency
def potency_report():
    """On decision states frozen at λ=0, swap only Memory S/V → Δp_switch"""
    print("\n" + "=" * 78)
    print("③ POTENCY — with the decision state held fixed, how far does swapping the memory move p(switch)")
    print("=" * 78)
    mS = MEM_S.evidence("previously_good_strategy")[0]
    mV = MEM_V.evidence("previously_good_strategy")[0]

    for name, runner in RUNNERS.items():
        states = []
        for sd in PROBE_SEEDS:
            r = runner(BODY_C, MEM_V, sd, 0.0, trace=True) if name.startswith("v2") \
                else None
            if r is None:      # v1 has no trace interface → use the equivalent passive replay
                states += _v1_passive_states(BODY_C, sd)
            else:
                states += r["states"]
        if not states:
            print(f"{name:<18}  ⚠ no eligible opportunities")
            continue
        sig = lambda z: 1.0 / (1.0 + math.exp(-max(-60.0, min(60.0, z))))  # noqa: E731
        base = [sig(z) for z, _ in states]
        sat = sum(1 for p in base if p >= 0.9 or p <= 0.1) / len(base)
        print(f"\n{name}   eligible opportunities = {len(states)}"
              f"   ({len(states) / len(PROBE_SEEDS):.2f} per seed)")
        print(f"  base p(switch): median {statistics.median(base):.3f}"
              f"   saturated share (≤0.1 or ≥0.9) {sat:.1%}")
        print(f"  {'λ':>6}  {'mean|Δp|':>10}  {'median|Δp|':>12}  {'p90|Δp|':>10}")
        for lam in LAMBDA_GRID:
            if lam == 0:
                continue
            d = sorted(abs(sig(z + lam * mV * s) - sig(z + lam * mS * s))
                       for z, s in states)
            p90 = d[min(len(d) - 1, int(0.90 * len(d)))]
            print(f"  {lam:>6.2f}  {statistics.fmean(d):>10.4f}"
                  f"  {statistics.median(d):>12.4f}  {p90:>10.4f}")


def _v1_passive_states(body, seed):
    """v1's passive replay: mark the trials v1 would fire on, and their base logit, along the λ=0 trajectory"""
    rows, us, _ = NT.reward_table(seed)
    b = NT.BETA * NT.novelty_style(body)
    Q, N = [NT.Q_INIT, NT.Q_INIT], [0, 0]
    cur, run_, st = None, 0, []
    for t in range(NT.TRIALS):
        val = [Q[i] + b / math.sqrt(1 + N[i]) for i in (0, 1)]
        if cur is None:
            d = max(-60.0, min(60.0, (val[0] - val[1]) / NT.TAU))
            c = 0 if us[t] < 1.0 / (1.0 + math.exp(-d)) else 1
        else:
            oth = 1 - cur
            z = (val[oth] - val[cur]) / NT.TAU
            if query_from_state(Q[cur], run_):
                st.append((z, 1.0))          # v1 always adds it to "switch"
            c = oth if us[t] < 1.0 / (1.0 + math.exp(-max(-60., min(60., z)))) else cur
        r = rows[t][c]
        pe = r - Q[c]
        run_ = run_ + 1 if (cur is not None and c == cur and pe < -PE_THRESH) else 0
        N[c] += 1
        Q[c] += NT.ALPHA * (r - Q[c])
        cur = c
    return st


# ================================================================== ④ ⑤ SWAP
def new_swap(runner, lam, quiet=False):
    """★ The new SWAP ★ M_C / M_K / pooled M / interaction. **No dominance gate any more**"""
    L = {}
    for body in (BODY_C, BODY_K):
        for mem in (MEM_S, MEM_V):
            L[(body.name, mem.name)] = [latency(runner(body, mem, sd, lam))
                                        for sd in PROBE_SEEDS]
    _test_no_survivor_conditioning(L) if not quiet else None

    def per_seed(body):
        return [v - s for v, s in zip(L[(body.name, MEM_V.name)],
                                      L[(body.name, MEM_S.name)])]

    mc, mk = per_seed(BODY_C), per_seed(BODY_K)
    M_C, M_K = statistics.fmean(mc), statistics.fmean(mk)
    M = (M_C + M_K) / 2.0
    inter = M_C - M_K

    rng = random.Random(ANALYSIS_SEED)
    n = len(PROBE_SEEDS)
    boot = []
    for _ in range(N_BOOT):
        idx = [rng.randrange(n) for _ in range(n)]      # ★one shared set of seed indices★
        boot.append((statistics.fmean([mc[i] for i in idx])
                     + statistics.fmean([mk[i] for i in idx])) / 2.0)
    boot.sort()
    lo, hi = boot[int(0.025 * N_BOOT)], boot[int(0.975 * N_BOOT)]

    # body effect — a robustness diagnostic only, ★no longer a gate★
    beff = statistics.fmean([
        statistics.fmean(L[(BODY_K.name, m.name)])
        - statistics.fmean(L[(BODY_C.name, m.name)]) for m in (MEM_S, MEM_V)])
    return dict(M_C=M_C, M_K=M_K, M=M, ci=(lo, hi), inter=inter,
                same_sign=(M_C < 0) == (M_K < 0) and M_C != 0 and M_K != 0,
                body_diag=beff)


def swap_report():
    print("\n" + "=" * 78)
    print("④ NEW SWAP — M = (M_C + M_K)/2   ⛔ the dominance criterion is withdrawn ⛔")
    print("=" * 78)
    print(f"{'mechanism':<18}{'λ':>6}{'M_C':>9}{'M_K':>9}{'pooled M':>11}"
          f"{'95% CI (descriptive)':>26}{'same direction':>16}{'interaction':>13}")
    print("-" * 78)
    res = {}
    for name, runner in RUNNERS.items():
        for lam in LAMBDA_GRID:
            if lam == 0:
                continue
            r = new_swap(runner, lam, quiet=True)
            res[(name, lam)] = r
            print(f"{name:<14}{lam:>6.2f}{r['M_C']:>+9.3f}{r['M_K']:>+9.3f}"
                  f"{r['M']:>+11.3f}"
                  f"   [{r['ci'][0]:+.3f}, {r['ci'][1]:+.3f}]"
                  f"{'yes' if r['same_sign'] else 'no':>16}"
                  f"{r['inter']:>+13.3f}")
    print("\n⚠ The CI is **descriptive** (seed cluster bootstrap, n_boot=10000,"
          f" analysis seed {ANALYSIS_SEED}).")
    print("  No SESOI is fixed today, so no functional-significance reading is made.")
    return res


def downstream_report():
    """⑤ latency / correct rate are reported only as downstream consequences"""
    print("\n" + "=" * 78)
    print("⑤ DOWNSTREAM — trajectory change + latency / post-reversal accuracy")
    print("=" * 78)
    print(f"{'mechanism':<18}{'λ':>6}{'trajectory changed':>20}{'Δlatency(V−S)':>16}"
          f"{'Δpost-reversal accuracy':>25}")
    print("-" * 78)
    for name, runner in RUNNERS.items():
        for lam in LAMBDA_GRID:
            chg = dl = dp = 0.0
            n = len(PROBE_SEEDS)
            ch = 0
            for sd in PROBE_SEEDS:
                s = runner(BODY_C, MEM_S, sd, lam)
                v = runner(BODY_C, MEM_V, sd, lam)
                ch += (s["choices"] != v["choices"])
                dl += latency(v) - latency(s)
                dp += post_correct(v) - post_correct(s)
            print(f"{name:<14}{lam:>6.2f}{ch / n:>11.1%}"
                  f"{dl / n:>+16.3f}{dp / n:>+16.4f}")


# ================================================================== main
if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    fp = NT.assert_frozen()
    print("=" * 78)
    print("029 memory transfer probe v2 — stateful retrieval (★still a probe, not an experiment★)")
    print("=" * 78)
    print(f"task substrate: 027 novel_task fingerprint {fp} (unchanged)  "
          f"seeds {PROBE_SEEDS[0]}–{PROBE_SEEDS[-1]}  n={len(PROBE_SEEDS)}")
    print(f"thresholds untouched: GOOD_THRESH={GOOD_THRESH} PE_THRESH={PE_THRESH} "
          f"SURPRISE_RUN_MIN={SURPRISE_RUN_MIN}   single reversal   ★80000–81499 untouched★")
    print("Only change: one-shot retrieval → stateful retrieval (RETRIEVE→ACTIVE→RESOLVED)")

    print("\n[ engineering self-check ]")
    _test_v1_unchanged()
    for nm, rn in RUNNERS.items():
        _test_memory_blind(rn)
    print(f"  ✓ memory-blind (λ=0): each mechanism identical trial by trial on {len(PROBE_SEEDS)}/{len(PROBE_SEEDS)}"
          f" seeds")
    _ = new_swap(run_stateful, 1.0)          # triggers the survivor-conditioning assertion

    exposure_report()
    potency_report()
    sw = swap_report()
    downstream_report()

    print("\n" + "=" * 78)
    print("★ Reading ★")
    print("=" * 78)
    v1 = sw[("v1 one-shot", 1.0)]
    v2 = sw[("v2 stateful", 1.0)]
    print(f"  λ=1  v1 one-shot  pooled M = {v1['M']:+.3f}"
          f"  same direction {'yes' if v1['same_sign'] else 'no'}")
    print(f"  λ=1  v2 stateful  pooled M = {v2['M']:+.3f}"
          f"  same direction {'yes' if v2['same_sign'] else 'no'}")
    print("\n  Directional SWAP check — see whether M_C / M_K above share a sign")
    print("  Dominance criterion (|memory|>|body|) — ★ RETIRED, neither computed nor read ★")
    print("\n⚠ This is still not 029 scientific success:")
    print("   the memories are hand-built, λ is not frozen, and Stable/Volatile have not been run at all.")
