"""
Experiment 029 — memory_acquisition_probe.py (★ upstream only; no novel task attached ★)
========================================================================================

Run:  python memory_acquisition_probe.py

--------------------------------------------------------------------------------
The one question to answer
--------------------------
    ┌────────────────────────────────────────────────────────────────┐
    │  Can the two kinds of experience, Stable and Volatile, **naturally generate**   │
    │  the kind of differing relational evidence that our hand-built MEM_S / MEM_V    │
    │  represent?                                                                     │
    └────────────────────────────────────────────────────────────────┘

**This file does not attach the novel task.** Only upstream quantities may be inspected:

```
✅ episode count / surprise episode count / stay-switch counts / reward marginals
✅ the distribution of memory evidence m / episode completeness
✅ the manipulation check and matching diagnostics of Stable / Volatile
⛔ novel-task latency        ⛔ post-change errors
⛔ Stable vs Volatile transfer effect
```

This way we keep the freedom to adjust the acquisition mechanism
**without starting to tune the design around the final outcome.**

--------------------------------------------------------------------------------
★ Key design: both sides experience surprise ★
----------------------------------------------
❌ Wrong approach: "Stable never has a surprise, Volatile has many".
   That is far too easy — the memory difference would degenerate into "one has data, the other does not".

✅ Right approach: **the same surface phenomenon means different things.**

```
Stable    a long-effective strategy → a run of anomalous failures → but the environment did not change → sticking with it eventually recovers
Volatile  a long-effective strategy → a run of anomalous failures → the environment really did hit a change point → recovery follows a switch
```

So what each side actually learns is the relation:

```
Stable memory     persistent surprise is sometimes just noise, and staying pays better
Volatile memory   persistent surprise usually means the rule changed, and switching pays better
```

### ★★ Inside the anomaly window the two worlds are **bit-identical** ★★

The time structure of each problem:

```
trial  0 .. E-1        the original strategy p_high, the other p_low   ← identical in both conditions
trial  E .. E+D-1      ★both drop to p_low★                            ← **identical** in both conditions:
                                                                          the anomaly alone cannot tell you which world you are in
trial  E+D .. T-1      Stable   : the original strategy returns to p_high
                       Volatile : the other one becomes p_high
```

- **reward opportunity is equal trial by trial** (every trial has exactly one p_high, or neither does)
- the reward draws inside the anomaly window **share one random stream** → the two conditions are
  **bit-identical** for `trial < E+D`. The difference appears only after E+D — i.e. in "what this anomaly meant".

--------------------------------------------------------------------------------
How episodes grow (reusing the probe's own query / resolution machinery)
------------------------------------------------------------------------
During acquisition **no memory is available** (memory is being built), so choices are driven solely by base
learning (Q-learning + softmax, with the same α/τ as 027).

The entry and exit conditions of the context window are **word for word the same** as `memory_transfer_probe3.py`:

```
entry: Q[cur] ≥ GOOD_THRESH and a run of surprises ≥ SURPRISE_RUN_MIN   → record the suspect
exit:  Q[the other] > Q[suspect]  or  a run of non-surprises on the suspect ≥ SURPRISE_RUN_MIN
       (★judged on Q **after** the update — the timing bug probe3 fixed★)
```

**Every decision inside the window writes one Episode**:

```
context               "previously_good_strategy"
previous_expectation  Q[suspect] at the start of the window (how much we had expected from the failing strategy)
observation           the mean return over the run of anomalies that triggered the window
prediction_error      observation − previous_expectation
action_relation       whether this decision was a stay (still on the suspect) or a switch (left it)
outcome               the return this decision obtained
```

★ Still **only relations are stored, never identities** (rule 85) — the probe's `Episode` is reused directly,
and its `__post_init__` rejects any option identity.

--------------------------------------------------------------------------------
Four matching diagnostics (Stable / Volatile must match as closely as possible)
-------------------------------------------------------------------------------
```
① total trials              ② total reward opportunity
③ episode count             ④ concrete option identity / first-good side
```
**The only thing allowed to differ** is the relational structure of `context × action × outcome`.
Only then can the SHUFFLE control later prove that what works is the **relation**, not the marginal statistics.

--------------------------------------------------------------------------------
Still not done at this stage
----------------------------
```
⛔ attaching the novel task    ⛔ calibrating λ    ⛔ SESOI    ⛔ preregistration    ⛔ final seeds
⛔ looking at any transfer outcome
```
λ must wait until the real m distribution is available, and then be frozen by **interface capacity** using
**frozen-state counterfactual potency** (probe3 already has that pipeline) —
not by "who ends up looking better, Stable or Volatile".
"""

import math
import random
import statistics
import sys

import novel_task as NT
from memory_transfer_probe import (Episode, MemoryStore, GOOD_THRESH,
                                   PE_THRESH, SURPRISE_RUN_MIN, PROBE_SEEDS)

# ---- acquisition parameters: ★ frozen 2026-08-18 as the 029 acquisition candidate ★ ----
#
# Only the learning length **before** the anomaly is increased; GOOD_THRESH / PE_THRESH / RUN_MIN are untouched,
# and the number of problems is not increased. A pure upstream sweep (0–399, no novel task attached):
#
#   pre-anomaly   Stable completeness   Volatile completeness   complete-only m separation
#      20              23.5%                  24.0%                  +0.904
#      28              49.2%                  52.0%                  +0.872
#      34              61.0%                  69.3%                  +0.902
#   ★ 36 ★            65.8%                  73.3%                  +0.894
#      40              69.5%                  76.8%                  +0.884
#
# → Increasing pre-anomaly experience **mainly fixes yield and barely changes the memory contrast**;
#   it is a clean engineering correction.
# → 36 was chosen as the elbow (20→36 buys +42pp / +49pp; 36→40 buys only another 3–4pp),
#   **not** as the point of maximum separation — separation is much the same at 34/35/36/38.
N_PROBLEMS = 3
ANOMALY_AT = 36          # ★frozen★ learning length before the anomaly (was 20)
ANOMALY_LEN = 8          # ★unchanged★
T_PROBLEM = 66           # ★frozen★ keeps the post-anomaly stretch at 66−36−8 = 22 (as before)
P_HIGH, P_LOW = NT.P_HIGH, NT.P_LOW
ALPHA, TAU, Q_INIT = NT.ALPHA, NT.TAU, NT.Q_INIT

_SALT_ACQ = 0x29A10
_SALT_U = 0x29B10

CONDITIONS = ("Stable", "Volatile")

# The only change is the pre-anomaly learning length; the anomaly itself and the post-anomaly relearning time are untouched
assert T_PROBLEM - ANOMALY_AT - ANOMALY_LEN == 22, "there must still be 22 trials after the anomaly"
assert ANOMALY_LEN == 8


class NeutralBody:
    """Acquisition uses a neutral body, to keep the trait channel out of the upstream diagnostics"""
    name = "Neutral (50/50)"
    traits = {"curiosity": 50.0, "caution": 50.0, "industry": 50.0}


# ================================================================== environment
def problem_schedule(condition, t):
    """Returns (p_option0_is_good, the p of both options). Identities such as good0 are counterbalanced outside.

    ★ For trial < ANOMALY_AT+ANOMALY_LEN the two conditions are completely identical ★
    """
    if t < ANOMALY_AT:
        return "orig"                       # the original strategy is good
    if t < ANOMALY_AT + ANOMALY_LEN:
        return "none"                       # ★anomaly window: neither is good★
    return "orig" if condition == "Stable" else "flip"


def acq_tables(seed, condition):
    """One table per problem. The reward draws **share one random stream** across the two conditions.

    → The part with `trial < ANOMALY_AT+ANOMALY_LEN` is bit-identical between the two conditions.
    """
    probs = []
    for pi in range(N_PROBLEMS):
        rng = random.Random(_SALT_ACQ ^ (seed * 131 + pi))
        orig_is_0 = rng.random() < 0.5        # ★ counterbalance: which index is good first ★
        rows, opp = [], 0.0
        for t in range(T_PROBLEM):
            who = problem_schedule(condition, t)
            if who == "none":
                p0 = p1 = P_LOW
            else:
                good0 = orig_is_0 if who == "orig" else (not orig_is_0)
                p0, p1 = (P_HIGH, P_LOW) if good0 else (P_LOW, P_HIGH)
            # ★shared random stream★: draw the two u first, then decide by p
            u0, u1 = rng.random(), rng.random()
            rows.append((1 if u0 < p0 else 0, 1 if u1 < p1 else 0))
            opp += max(p0, p1)
        urng = random.Random(_SALT_U ^ (seed * 131 + pi))
        us = [urng.random() for _ in range(T_PROBLEM)]
        probs.append({"rows": rows, "us": us, "orig_is_0": orig_is_0,
                      "opportunity": opp})
    return probs


# ================================================================== acquisition
def acquire(seed, condition, body=NeutralBody):
    """Run N_PROBLEMS developmental problems, producing an Episode list + upstream diagnostics. **No memory involved.**"""
    b = NT.BETA * NT.novelty_style(body)
    episodes, diag = [], {"trials": 0, "opportunity": 0.0, "reward": 0,
                          "windows": 0, "window_trials": 0, "orig_is_0": []}

    for prob in acq_tables(seed, condition):
        rows, us = prob["rows"], prob["us"]
        diag["opportunity"] += prob["opportunity"]
        diag["orig_is_0"].append(prob["orig_is_0"])
        Q, N = [Q_INIT, Q_INIT], [0, 0]
        cur, surprise_run = None, 0
        suspect, calm_run = None, 0
        onset_expect, onset_obs = 0.0, 0.0
        surprise_buf = []

        for t in range(T_PROBLEM):
            val = [Q[i] + b / math.sqrt(1 + N[i]) for i in (0, 1)]
            if cur is None:
                d = max(-60.0, min(60.0, (val[0] - val[1]) / TAU))
                c = 0 if us[t] < 1.0 / (1.0 + math.exp(-d)) else 1
                in_window = False
            else:
                if suspect is None and Q[cur] >= GOOD_THRESH \
                        and surprise_run >= SURPRISE_RUN_MIN:
                    suspect = cur
                    calm_run = 0
                    onset_expect = Q[cur]
                    onset_obs = statistics.fmean(surprise_buf[-surprise_run:]) \
                        if surprise_run else 0.0
                    diag["windows"] += 1
                oth = 1 - cur
                in_window = suspect is not None
                # ★ no memory is available during acquisition — pure base learning ★
                z = max(-60.0, min(60.0, (val[oth] - val[cur]) / TAU))
                c = oth if us[t] < 1.0 / (1.0 + math.exp(-z)) else cur

            r = rows[t][c]
            pe = r - Q[c]
            surprise_buf.append(r)

            if in_window:
                episodes.append(Episode(
                    context="previously_good_strategy",
                    previous_expectation=onset_expect,
                    observation=onset_obs,
                    prediction_error=onset_obs - onset_expect,
                    action_relation="stay" if c == suspect else "switch",
                    outcome=float(r)))
                diag["window_trials"] += 1

            if cur is not None and c == cur and pe < -PE_THRESH:
                surprise_run += 1
            else:
                surprise_run = 0
            if suspect is not None and c == suspect:
                calm_run = calm_run + 1 if pe >= -PE_THRESH else 0

            N[c] += 1
            Q[c] += ALPHA * (r - Q[c])           # ★update Q first★

            if suspect is not None:              # ★then judge resolution (probe3's ordering)★
                if Q[1 - suspect] > Q[suspect] or calm_run >= SURPRISE_RUN_MIN:
                    suspect, calm_run = None, 0

            cur = c
            diag["trials"] += 1
            diag["reward"] += r

    return episodes, diag


def evidence_of(episodes):
    """Load the grown episodes into a MemoryStore and read out m (the same read-out convention as the probe)"""
    mem = MemoryStore("acquired", episodes)
    m, n_sw, n_st = mem.evidence("previously_good_strategy")
    return m, n_sw, n_st


# ================================================================== diagnostics
def _q(xs, f):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(f * len(xs)))]


def run_all():
    out = {}
    for cond in CONDITIONS:
        rec = []
        for sd in PROBE_SEEDS:
            eps, diag = acquire(sd, cond)
            m, n_sw, n_st = evidence_of(eps)
            rec.append({"m": m, "n": len(eps), "n_sw": n_sw, "n_st": n_st,
                        "complete": n_sw > 0 and n_st > 0, **diag})
        out[cond] = rec
    return out


def matching_report(res):
    print("\n" + "=" * 78)
    print("★ MATCHING DIAGNOSTICS — four items that must match ★")
    print("=" * 78)
    print(f"{'':<34}{'Stable':>16}{'Volatile':>16}{'equal':>8}")
    print("-" * 78)
    rows = [
        ("① total trials", lambda r: statistics.fmean([x["trials"] for x in r])),
        ("② total reward opportunity", lambda r: statistics.fmean([x["opportunity"] for x in r])),
        ("③ episode count", lambda r: statistics.fmean([x["n"] for x in r])),
        ("④ share with first-good = index0",
         lambda r: statistics.fmean([sum(x["orig_is_0"]) / N_PROBLEMS for x in r])),
        ("   total reward actually obtained", lambda r: statistics.fmean([x["reward"] for x in r])),
        ("   number of context windows", lambda r: statistics.fmean([x["windows"] for x in r])),
    ]
    ok = True
    for label, fn in rows:
        a, b = fn(res["Stable"]), fn(res["Volatile"])
        same = abs(a - b) < 1e-9
        if label.startswith(("①", "②", "④")) and not same:
            ok = False
        print(f"{label:<26}{a:>16.4f}{b:>16.4f}{'✓' if same else '≠':>8}")
    print(f"\n  ★ constructive matching (①②④) {'all bit-equal' if ok else '⚠ some items unequal'} ★")
    print("  ③ episode count is a **behavioural product** and need not be bit-equal — but a large gap means"
          " the two sides had unequal opportunity to form memories, which must be reported.")


def manipulation_report(res):
    print("\n" + "=" * 78)
    print("★ MANIPULATION CHECK — the same surface phenomenon means different things ★")
    print("=" * 78)
    # Environment level: are the two conditions bit-identical inside the anomaly window
    same_prefix = True
    for sd in PROBE_SEEDS[:100]:
        a, b = acq_tables(sd, "Stable"), acq_tables(sd, "Volatile")
        for pa, pb in zip(a, b):
            k = ANOMALY_AT + ANOMALY_LEN
            if pa["rows"][:k] != pb["rows"][:k] or pa["us"] != pb["us"]:
                same_prefix = False
    print(f"  bit-identical before the anomaly window ends (trial < {ANOMALY_AT + ANOMALY_LEN}): "
          f"{'yes ✓' if same_prefix else 'no ✗'}")
    print(f"  → the anomaly alone **cannot tell** which world you are in; the difference is only in 'what this anomaly meant'.")
    # Environment level: who is good after the window
    a = acq_tables(0, "Stable")[0]
    print(f"  after the anomaly window: Stable = the original strategy returns / Volatile = the other one becomes good"
          f" (by construction, see problem_schedule)")
    # Behaviour level: the stay/switch ratio inside the window
    print(f"\n{'':<12}{'trials in window':>18}{'stay entries':>14}{'switch entries':>16}"
          f"{'switch share':>14}{'both sides present':>20}")
    print("-" * 78)
    for cond in CONDITIONS:
        r = res[cond]
        st = statistics.fmean([x["n_st"] for x in r])
        sw = statistics.fmean([x["n_sw"] for x in r])
        print(f"{cond:<12}{statistics.fmean([x['window_trials'] for x in r]):>14.2f}"
              f"{st:>12.2f}{sw:>13.2f}{sw / (st + sw) if st + sw else 0:>13.1%}"
              f"{statistics.fmean([x['complete'] for x in r]):>11.1%}")


def yield_diagnostic():
    """★ Why only 1/4 of agents grow a memory — which half of the entry condition blocks them? ★

    Entry requires both: (i) Q[the strategy in hand] ≥ GOOD_THRESH   (ii) a run of surprises ≥ 3.
    Here the attainment rate of each half is counted separately along the acquisition trajectory.
    """
    print("\n" + "=" * 78)
    print("★ YIELD DIAGNOSTIC — where each half of the entry condition gets stuck ★")
    print("=" * 78)
    print(f"{'':<12}{'Q≥0.6 at anomaly onset':>26}{'ever reached stay-run≥3':>27}"
          f"{'both at once':>14}{'longest stay-run':>18}")
    print("-" * 78)
    for cond in CONDITIONS:
        okq = okr = okb = 0
        best = []
        for sd in PROBE_SEEDS:
            b = NT.BETA * NT.novelty_style(NeutralBody)
            for prob in acq_tables(sd, cond):
                rows, us = prob["rows"], prob["us"]
                Q, N = [Q_INIT, Q_INIT], [0, 0]
                cur, run_ = None, 0
                q_at_onset, maxrun, both = 0.0, 0, False
                for t in range(T_PROBLEM):
                    val = [Q[i] + b / math.sqrt(1 + N[i]) for i in (0, 1)]
                    if cur is None:
                        d = max(-60.0, min(60.0, (val[0] - val[1]) / TAU))
                        c = 0 if us[t] < 1.0 / (1.0 + math.exp(-d)) else 1
                    else:
                        oth = 1 - cur
                        z = max(-60.0, min(60.0, (val[oth] - val[cur]) / TAU))
                        c = oth if us[t] < 1.0 / (1.0 + math.exp(-z)) else cur
                    if t == ANOMALY_AT:
                        q_at_onset = Q[c]
                    r = rows[t][c]
                    pe = r - Q[c]
                    if cur is not None and c == cur and pe < -PE_THRESH:
                        run_ += 1
                        maxrun = max(maxrun, run_)
                        if run_ >= SURPRISE_RUN_MIN and Q[c] >= GOOD_THRESH:
                            both = True
                    else:
                        run_ = 0
                    N[c] += 1
                    Q[c] += ALPHA * (r - Q[c])
                    cur = c
                okq += q_at_onset >= GOOD_THRESH
                okr += maxrun >= SURPRISE_RUN_MIN
                okb += both
                best.append(maxrun)
        n = len(PROBE_SEEDS) * N_PROBLEMS
        print(f"{cond:<12}{okq / n:>15.1%}{okr / n:>20.1%}{okb / n:>12.1%}"
              f"{statistics.fmean(best):>15.2f}")
    print("\n  ⚠ Which half is the tighter bottleneck decides which acquisition component to touch next"
          " (not today).")


def evidence_report(res):
    print("\n" + "=" * 78)
    print("★ Distribution of the memory evidence m (= the relational evidence grown from real experience) ★")
    print("=" * 78)
    print("  Hand-built reference: MEM_S has m = −0.667, MEM_V has m = +0.667 (maximum contrast)")
    print(f"\n{'':<12}{'n (m definable)':>17}{'mean m':>10}{'SD':>9}{'p10':>9}"
          f"{'median':>9}{'p90':>9}{'share m>0':>12}")
    print("-" * 78)
    ms = {}
    for cond in CONDITIONS:
        v = [x["m"] for x in res[cond] if x["complete"]]
        ms[cond] = v
        if not v:
            print(f"{cond:<12}{'0':>17}   ⚠ no agent grew a definable m")
            continue
        print(f"{cond:<12}{len(v):>13}{statistics.fmean(v):>10.4f}"
              f"{statistics.pstdev(v):>9.4f}{_q(v, .10):>9.4f}"
              f"{statistics.median(v):>9.4f}{_q(v, .90):>9.4f}"
              f"{sum(1 for x in v if x > 0) / len(v):>11.1%}")

    # ============================================================ rule 91
    print("\n" + "-" * 78)
    print("★ Two margins that must be reported separately — memory availability is itself a developmental outcome ★")
    print("-" * 78)
    print(f"{'':<12}{'extensive: P[m available]':>28}{'intensive: mean(m|available)':>31}"
          f"{'overall mean m':>17}{'overall median':>17}")
    print("-" * 78)
    full = {}
    for cond in CONDITIONS:
        allm = [x["m"] for x in res[cond]]         # ★either side missing → m=0, still counted★
        full[cond] = allm
        ext = statistics.fmean([x["complete"] for x in res[cond]])
        inten = statistics.fmean(ms[cond]) if ms[cond] else float("nan")
        print(f"{cond:<12}{ext:>21.1%}{inten:>26.4f}"
              f"{statistics.fmean(allm):>14.4f}{statistics.median(allm):>13.4f}")

    d_pop = statistics.fmean(full["Volatile"]) - statistics.fmean(full["Stable"])
    d_cmp = (statistics.fmean(ms["Volatile"]) - statistics.fmean(ms["Stable"])) \
        if ms["Stable"] and ms["Volatile"] else float("nan")
    print(f"\n  population-level separation (all agents, including m=0) = {d_pop:+.4f}   ★this is the true value★")
    print(f"  complete-only separation (only those that grew a memory)  = {d_cmp:+.4f}   ⚠ inflated")
    print(f"  hand-built separation = +1.3333  →  the real population reaches {abs(d_pop) / 1.3333:.1%}"
          f", while complete-only would appear to reach {abs(d_cmp) / 1.3333:.1%}")
    print("""
  ⛔ Calibrating λ must use **the real m of every agent, including those with m=0**.
     Filtering out the agents that "failed to form a usable memory" and calibrating on the most informative
     remainder would **systematically inflate the real input strength of the memory channel** —
     structurally the same mistake as survivor conditioning (rules 88 / 91).

  ⚠ The unequal yield of Stable and Volatile (above) **does not need fixing**:
     Volatile is naturally more likely to accumulate both stay and switch experience,
     which is part of history → memory availability → future behaviour.
     Forcing completeness to match = modifying a post-treatment mediator.""")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print("=" * 78)
    print("029 memory ACQUISITION probe — ★upstream only, no novel task attached★")
    print("=" * 78)
    print(f"development: {N_PROBLEMS} problems × {T_PROBLEM} trials"
          f" (anomaly at {ANOMALY_AT}–{ANOMALY_AT + ANOMALY_LEN - 1})"
          f"   seeds {PROBE_SEEDS[0]}–{PROBE_SEEDS[-1]}  n={len(PROBE_SEEDS)}")
    print(f"read-out convention identical to the probe: GOOD_THRESH={GOOD_THRESH} PE_THRESH={PE_THRESH} "
          f"SURPRISE_RUN_MIN={SURPRISE_RUN_MIN}")
    print("★ 80000–81499 untouched ★   ⛔ this file computes no transfer outcome ⛔")

    res = run_all()
    matching_report(res)
    manipulation_report(res)
    yield_diagnostic()
    evidence_report(res)

    print("\n" + "=" * 78)
    print("⛔ Forbidden to inspect at this stage: novel-task latency / post-change errors /")
    print("   the Stable vs Volatile transfer effect — the code does not compute them either.")
    print("=" * 78)
