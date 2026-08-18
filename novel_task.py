"""
Experiment 027 — Novel-Task Transfer + Reversal (the only new module in v4)
===========================================================================

Self-check:  python novel_task.py

★★ The definition of v4 ★★
    v4 = the core of v3_frozen (**byte-for-byte untouched**) + this module
This module **modifies no line of `v3_frozen/`** and does not touch agent state within the first 60 days.
So "with NovelTask off, v4 is tick-for-tick identical to v3" holds **by construction**,
but it is still written as a regression test (`_test_v3_equivalence`), in case someone later couples it in by accident.

--------------------------------------------------------------------------
The task: two buttons A / B that never existed before
-----------------------------------------------------
    30 days of development (rich/barren) → 30 days of common garden → level the body state
    → enter the new task: 80 trials, each choosing A or B and scoring 0/1 points

**This task has nothing whatsoever to do with food / house / material / death** — all four probes of 026
foundered on "manipulate a resource → it becomes a survival problem or a saturation problem" (rules 64/68/70/71),
and 027 sidesteps the resource economy entirely.

    Trials 1–40   good option 80% / bad option 20%
    Trial 41      ★the rule suddenly reverses★
    Trials 41–80  the other way round

Which one is good first is **randomised by seed** (half the seeds have A good first), so no history is naturally aligned with A.
**The twins of one seed share the same reward table**, down to the tie-break bits —
so "rich was merely lucky" cannot be said.

--------------------------------------------------------------------------
How the past enters the new task (★the most sensitive point★)
-------------------------------------------------------------
**The past is not allowed to decide whether A or B is good.** That would be writing the conclusion in.

The past may enter only through something very general: **how willing it is to try an option it is still unsure about.**

    novelty_style = (curiosity − caution + 100) / 200   ∈ [0,1]
    beta          = BETA * novelty_style
    value(x)      = Q_x + beta / sqrt(1 + N_x)          ← uncertainty bonus

So: a curious ball is more willing to try the option "I do not yet understand";
a cautious ball tends to stay with the option it already has evidence for.
**Which option actually pays more is decided entirely by the external task.**

★ The learning rate α is exactly the same for every agent ★ — it must never be designed so that "rich learns faster".

⚠ Wording discipline: in this task the agent **really is learning** (Q values update from feedback),
   which is a new capability of v4 relative to v3. But what it learns is **the value of a 2-armed bandit**,
   **not** "an understanding of the causal structure of the world". The write-up must not say the latter.
"""

import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
V3DIR = os.path.join(HERE, "v3_frozen")
if V3DIR not in sys.path:
    sys.path.insert(0, V3DIR)

import sim                                        # noqa: E402

assert os.path.abspath(sim.__file__).startswith(V3DIR), "the core must come from v3_frozen"
assert sim.MODEL_VERSION == "v3"

MODEL_VERSION = "v4"          # v4 = the v3 core + this module

# ---- Task parameters (placeholders before calibration; the official values are written into the preregistration after group-blind calibration) ----
TRIALS = 80
REVERSAL_AT = 40
P_HIGH, P_LOW = 0.80, 0.20
# ★★ Already frozen by group-blind calibration (2026-08-17) ★★
#   Lexicographic β↑ → α↑ → τ↑, taking the first passing cell; 12 of 80 cells passed.
#   Calibration looks only at pooled metrics; the script physically cannot compute a rich/poor difference.
ALPHA = 0.05                  # learning rate — ★identical for every agent★
BETA = 0.05                   # strength of the uncertainty bonus — ★the only knob through which history enters★
TAU = 0.20                    # softmax temperature — ★identical for every agent, not a history channel★
Q_INIT = 0.5

# ⚠ The defaults must match the frozen values: if the final runner forgets to pass them explicitly,
#   it must never quietly fall back to the placeholders. The assertion + fingerprint below are the hard stop.
_FROZEN = dict(ALPHA=0.05, BETA=0.05, TAU=0.20, TRIALS=80, REVERSAL_AT=40,
               P_HIGH=0.80, P_LOW=0.20, Q_INIT=0.5)

# ⚠ Why TAU is needed (the first version had none and every calibration cell failed):
#   under a purely deterministic argmax, as long as the **ordering** of Q is right the choice is 100% correct —
#   so accuracy on trials 31–40 sat at 94–100% regardless of α and β, and never entered the 65–90% pass band.
#   That is a **task design problem**, not badly tuned parameters.
#   Adding choice noise that is identical for every agent (softmax) gives accuracy an adjustable range.
#   ★ TAU is identical for every agent, so it does not constitute a second history channel. ★

_SALT_REWARD = 0x27A50        # fixed salt, so the reward table is determined by the seed alone
_SALT_TIE = 0x27B10


def config_fingerprint():
    """Task configuration fingerprint — printed/written on every official run, so a wrong version is obvious at a glance"""
    import hashlib
    payload = "|".join(f"{k}={v!r}" for k, v in sorted(dict(
        TRIALS=TRIALS, REVERSAL_AT=REVERSAL_AT, P_HIGH=P_HIGH, P_LOW=P_LOW,
        ALPHA=ALPHA, BETA=BETA, TAU=TAU, Q_INIT=Q_INIT,
        SALT_R=_SALT_REWARD, SALT_T=_SALT_TIE).items()))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def assert_frozen():
    """★Hard stop★ the parameters must be bit-identical to the calibration-frozen values"""
    cur = dict(ALPHA=ALPHA, BETA=BETA, TAU=TAU, TRIALS=TRIALS,
               REVERSAL_AT=REVERSAL_AT, P_HIGH=P_HIGH, P_LOW=P_LOW,
               Q_INIT=Q_INIT)
    bad = {k: (v, cur[k]) for k, v in _FROZEN.items() if cur[k] != v}
    if bad:
        raise AssertionError(f"✗ task parameters deviate from the frozen values: {bad}")
    return config_fingerprint()


# ------------------------------------------------------------------ reward table
def reward_table(seed):
    """★Shared by the twins★ determined by the seed alone: the reward sequence + tie-break bits + which option is good first.

    The tie-break bits are also **pre-generated** (one per trial) rather than drawn on the fly —
    otherwise two twins hitting ties on different trials would consume different random numbers,
    and the tie-break itself would become a source of divergence.
    """
    rng = random.Random(_SALT_REWARD ^ seed)
    a_good_first = rng.random() < 0.5
    rows = []
    for t in range(TRIALS):
        flipped = t >= REVERSAL_AT
        a_is_good = a_good_first != flipped          # XOR
        pa = P_HIGH if a_is_good else P_LOW
        pb = P_LOW if a_is_good else P_HIGH
        rows.append((1 if rng.random() < pa else 0,
                     1 if rng.random() < pb else 0))
    # One shared uniform draw per trial, used for the softmax decision.
    # ★Shared by the twins★ → "one arm was merely lucky with the dice" cannot be said.
    # It also replaces the former tie-break bits: when val is equal p0 = 0.5, decided by the same u.
    trng = random.Random(_SALT_TIE ^ seed)
    us = [trng.random() for _ in range(TRIALS)]
    return rows, us, a_good_first


def correct_option(a_good_first, t):
    """The "correct" option on trial t (0=A, 1=B)"""
    return (0 if a_good_first else 1) if t < REVERSAL_AT \
        else (1 if a_good_first else 0)


# ------------------------------------------------------------------ choice rule
def novelty_style(agent):
    """[0,1]. **Uses only curiosity and caution; reads no resource/survival/history label.**"""
    ns = (agent.traits["curiosity"] - agent.traits["caution"] + 100.0) / 200.0
    return min(1.0, max(0.0, ns))


def run_task(agent, seed, *, beta=BETA, alpha=ALPHA, tau=TAU,
             history_blind=False):
    """Run all 80 trials. Returns the per-trial record. **Touches none of the agent's existing state.**

    `history_blind=True` → beta is fixed at its median while learning proceeds as usual
      (control three: if history still causes a systematic difference, there is an undiscovered channel)
    """
    rows, us, a_good_first = reward_table(seed)
    b = beta * (0.5 if history_blind else novelty_style(agent))
    Q = [Q_INIT, Q_INIT]
    N = [0, 0]
    choices, rewards, explores = [], [], []

    for t in range(TRIALS):
        val = [Q[i] + b / math.sqrt(1 + N[i]) for i in (0, 1)]
        d = (val[0] - val[1]) / tau
        d = max(-60.0, min(60.0, d))          # guard against exp overflow
        p0 = 1.0 / (1.0 + math.exp(-d))
        c = 0 if us[t] < p0 else 1            # ★shared draw★
        # "exploration" = choosing the option with the lower current Q (not the greedy choice)
        explores.append(1 if (Q[c] < Q[1 - c]) else 0)
        r = rows[t][c]
        N[c] += 1
        Q[c] += alpha * (r - Q[c])
        choices.append(c)
        rewards.append(r)

    return {
        "seed": seed, "a_good_first": a_good_first,
        "choices": choices, "rewards": rewards, "explores": explores,
        "beta": b, "tau": tau, "Q_end": list(Q), "N_end": list(N),
    }


# ------------------------------------------------------------------ metrics
def switch_latency(rec, window=5, need=4):
    """★H2 primary★ how many trials after the reversal before the new correct option is chosen stably.

    Definition: the first trial t after the reversal such that within [t, t+window) the new correct option is chosen ≥ need times.
    Never reached → returns None (which must be treated as neither 0 nor dropped, see the reading section).
    """
    good = correct_option(rec["a_good_first"], REVERSAL_AT)
    ch = rec["choices"]
    for t in range(REVERSAL_AT, TRIALS - window + 1):
        if sum(1 for x in ch[t:t + window] if x == good) >= need:
            return t - REVERSAL_AT
    return None


# The largest detectable latency: t goes up to TRIALS-window, so latency ≤ 35
MAX_DETECTABLE_LATENCY = TRIALS - REVERSAL_AT - 5      # = 35
NEVER_SWITCHED = MAX_DETECTABLE_LATENCY + 1            # = 36


def switch_latency_restricted(rec):
    """★H2 primary endpoint★ censored switch latency: 0–35 is a real latency, **36 = never switched within the observation window**.

    ⚠ 36 does **not** mean "it switched on trial 36", it means "it never switched during the whole observation period".

    Why this must be fixed now (rather than decided after the final run):
      · dropping never-switchers → creates selection (if one arm has more never-switchers,
        the effect would be quietly erased)
      · treating them as 0 → mistakes "never switched" for "switched immediately", the exact opposite direction
      · switching to a survival model afterwards → that is choosing the statistical method after seeing the result
    Censoring is the simplest option that deletes no data and introduces no complex model.
    Calibration measured never-switch at only 2.0%, so it will not dominate the result — but it is fixed in advance anyway.
    """
    x = switch_latency(rec)
    return NEVER_SWITCHED if x is None else x


def correct_rate(rec, lo, hi):
    ch = rec["choices"]
    return sum(1 for t in range(lo, hi)
               if ch[t] == correct_option(rec["a_good_first"], t)) / (hi - lo)


def explore_rate(rec, lo, hi):
    return sum(rec["explores"][lo:hi]) / (hi - lo)


# ------------------------------------------------------------------ self-checks
def _dev_snapshot(seed, world, days=60):
    """Run the v3 core for `days` days (30 days of development + 30 days of common garden) and return the life"""
    import novel_situation as NS
    life = NS.scenarios.make(seed, world)
    ok, _ = NS.run_window(life, 0, 30)
    if not ok:
        return None
    w = sim.World(seed, **NS.scenarios.WORLDS["baseline"])
    ok, _ = NS.run_window(life, 30, 30, world=w)
    return life if ok else None


def _test_v3_equivalence():
    """★Control one★ with NovelTask off, the first 60 days must be bit-identical to v3"""
    import novel_situation as NS
    for sd in (20000, 20001, 20002):
        a = _dev_snapshot(sd, "barren world")
        b = _dev_snapshot(sd, "barren world")
        if a is None:
            continue
        assert NS.full_hash(a) == NS.full_hash(b), f"the v3 core is non-deterministic on its own (seed {sd})"
        # Take the hash **after** running the task: the task must not write back any existing agent state
        before = NS.full_hash(a)
        run_task(a.agent, sd)
        assert NS.full_hash(a) == before, \
            "✗ NovelTask wrote back existing agent state — v3 equivalence is broken"
    print("  ✓ control one: the task does not touch v3 state, and the first 60 days are bit-identical")


def _test_identical_agent():
    """★Control two★ two clones of one snapshot + the same reward table → must be identical trial by trial"""
    import copy
    import novel_situation as NS
    life = _dev_snapshot(20003, "rich world")
    assert life is not None
    x, y = copy.deepcopy(life), copy.deepcopy(life)
    for c in (x, y):
        c.agent.trait_floor = dict(c.agent.trait_floor)
    ra, rb = run_task(x.agent, 20003), run_task(y.agent, 20003)
    assert ra["choices"] == rb["choices"], "✗ the same agent with the same reward table diverged"
    assert ra["rewards"] == rb["rewards"]
    print("  ✓ control two: same agent + same reward table → identical trial by trial")


def _test_shared_reward_table():
    """The twins share the reward table and tie-break bits — so \"one arm was merely lucky\" cannot be said"""
    ra, ua, ga = reward_table(20004)
    rb, ub, gb = reward_table(20004)
    assert ra == rb and ua == ub and ga == gb, "the reward table is not determined by the seed alone"
    # Half the seeds have A good first
    good = [reward_table(s)[2] for s in range(20000, 20400)]
    frac = sum(good) / len(good)
    assert 0.40 < frac < 0.60, f"the share of seeds with A good first is off: {frac:.1%}"
    print(f"  ✓ the reward table depends on the seed alone; A is good first in {frac:.1%} of seeds")


def _test_history_only_via_novelty():
    """★Key★ history may enter only via curiosity/caution. Changing anything else must not affect the task."""
    import copy
    life = _dev_snapshot(20005, "barren world")
    assert life is not None
    base = run_task(copy.deepcopy(life).agent, 20005)
    for field, val in (("hunger", 90.0), ("condition", 20.0),
                       ("shelter", 5.0), ("energy", 10.0)):
        c = copy.deepcopy(life)
        setattr(c.agent, field, val)
        c.agent.inventory = {"food": 99, "material": 99}
        r = run_task(c.agent, 20005)
        assert r["choices"] == base["choices"], \
            f"✗ the task read {field} — violating 'unrelated to resources/survival'"
    # Changing curiosity must have an effect (otherwise the beta channel is dead)
    c = copy.deepcopy(life)
    c.agent.traits["curiosity"] = 100.0
    c.agent.traits["caution"] = 0.0
    r = run_task(c.agent, 20005)
    assert r["beta"] != base["beta"], "✗ curiosity/caution did not reach beta"
    print("  ✓ the task reads only curiosity/caution, and no resource/survival variable")


def _test_history_blind():
    """★Control three★ with history_blind, beta is independent of history"""
    import copy
    life = _dev_snapshot(20006, "rich world")
    assert life is not None
    a = copy.deepcopy(life)
    a.agent.traits["curiosity"], a.agent.traits["caution"] = 95.0, 5.0
    b = copy.deepcopy(life)
    b.agent.traits["curiosity"], b.agent.traits["caution"] = 5.0, 95.0
    ra = run_task(a.agent, 20006, history_blind=True)
    rb = run_task(b.agent, 20006, history_blind=True)
    assert ra["beta"] == rb["beta"] and ra["choices"] == rb["choices"], \
        "✗ still affected by history under history_blind — there is a second channel"
    print("  ✓ control three: under history-blind, the two extreme personality trajectories are identical")


def _test_frozen_config():
    """★Control four★ the defaults must equal the frozen values; the fingerprint is stable"""
    fp = assert_frozen()
    assert ALPHA == 0.05 and BETA == 0.05 and TAU == 0.20
    assert fp == config_fingerprint()
    # A default call and an explicit call with the frozen values must be identical trial by trial
    class S:
        traits = {"curiosity": 60.0, "caution": 40.0, "industry": 50.0}
    a = run_task(S(), 20100)
    b = run_task(S(), 20100, alpha=ALPHA, beta=BETA, tau=TAU)
    assert a["choices"] == b["choices"], "a default call differs from an explicit one"
    print(f"  ✓ control four: parameters frozen at α={ALPHA} β={BETA} τ={TAU}  fingerprint {fp}")


def _test_metrics():
    """The metrics themselves must behave correctly"""
    rec = {"a_good_first": True, "choices": [0] * REVERSAL_AT + [1] * 40,
           "rewards": [0] * TRIALS, "explores": [0] * TRIALS}
    assert switch_latency(rec) == 0, "choosing the new correct option immediately after the reversal should give 0"
    assert switch_latency_restricted(rec) == 0
    rec2 = dict(rec, choices=[0] * TRIALS)
    assert switch_latency(rec2) is None, "never switching should return None, not 0"
    assert switch_latency_restricted(rec2) == NEVER_SWITCHED == 36,         "never switching must be censored to 36, neither None nor 0"
    print(f"  ✓ switch_latency: immediate switch=0, never switching censored to {NEVER_SWITCHED}"
          f" (not deleted, not treated as 0)")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"027 NovelTask self-check   core from {os.path.dirname(sim.__file__)}"
          f"   {sim.MODEL_VERSION} → {MODEL_VERSION}")
    _test_v3_equivalence()
    _test_identical_agent()
    _test_shared_reward_table()
    _test_history_only_via_novelty()
    _test_history_blind()
    _test_frozen_config()
    _test_metrics()
    print("\nAll passed. Ready for group-blind calibration.")
