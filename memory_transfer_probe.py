"""
Experiment 029 — memory_transfer_probe.py (★ an identifiability probe, not an experiment ★)
===========================================================================================

Run:  python memory_transfer_probe.py

--------------------------------------------------------------------------------
★★ This file is deliberately not called experiment029.py ★★
-----------------------------------------------------------
We have been burned repeatedly by **running a group comparison when the mechanism has no capacity to
affect the outcome at all**. All four probes of 026 foundered on exactly this.

So the first program of 029 asks one question only:

    ┌──────────────────────────────────────────────────────────┐
    │  Does this memory → retrieval → evidence → choice path,     │
    │  with everything else held completely equal,                │
    │  have any capacity to change a future choice sequence?      │
    └──────────────────────────────────────────────────────────┘

This is an **identifiability check**, not a hypothesis test.
As in 026: first prove that "the experiment is able to measure what it claims to measure".

**This file explicitly does not do** (none of it today):
    ⛔ the formal Stable vs Volatile comparison      ⛔ the 029 final seeds
    ⛔ preregistration                    ⛔ SESOI
    ⛔ the final value of λ (this file **sweeps** λ, it does not choose λ)
    ⛔ writing memory into sim.py              ⛔ LLM / embeddings
    ⛔ turning on episodic + semantic + abstraction all at once

Seeds: only the development block `0–1499` (long since burned).
      **80000–81499 is not touched.**

--------------------------------------------------------------------------------
① What memory is (029's own experiment-layer structure, not reusing autobiographical memory)
--------------------------------------------------------------------------------------------
The existing `{event, day, importance, text}` suits autobiographical memory but is
**not enough for causal transfer** — it stores "what happened", not "which relation mattered".

029 builds its own:

    Episode:
        context               a relational context label (not a scene description)
        previous_expectation  what was expected of the strategy in hand at the time
        observation           the return actually observed
        prediction_error      observation − previous_expectation
        action_relation       ★ "stay" / "switch" ★
        outcome               the return obtained after taking that action_relation

    ★★ The single most important rule: store stay/switch, never A/B ★★
    Storing A/B leaves nothing transferable once the task changes —
    the new task has no A or B at all. Only storing the "relation" can transfer.

    This file turns that into a **hard constraint** via `_assert_relational_only()`:
    any option identity appearing in an Episode field raises immediately.

--------------------------------------------------------------------------------
② Retrieval (first version: one relational query, deliberately minimal)
-----------------------------------------------------------------------
    current state:  the strategy in hand has long been good  +  a recent run of prediction errors
                        ↓
    retrieval:      has "previously-good strategy + persistent surprise" ever occurred before
                        ↓
    memory returns: what the return was after staying, and after switching, in that situation
                        ↓
    evidence:       m = E[R | switch, similar past] − E[R | stay, similar past]
                        ↓
    decision:       logit(switch) = base_learning + λ·m

**The essential difference from 027:**

    027    trait_i → β_i                                    (we read one scalar on its behalf)
    029    current situation → retrieval → past outcomes → evidence → choice
           ("I am in this situation now, so I recall similar situations from before")

When the query does not hold, `m = 0` and **memory does not enter the decision** — retrieval is context-triggered, which is the whole point.

--------------------------------------------------------------------------------
③ Today's two blades
--------------------
    ★ POSITIVE CONTROL ★
        same current state / same Q / same reward table / same random uniforms /
        same body — **only the memory is swapped**. Does the choice sequence change?
        If it cannot, there is no point running Stable / Volatile later.

    ★ SWAP TEST ★
        Body A + Memory S   vs   Body A + Memory V
        Body B + Memory S   vs   Body B + Memory V
        Requirement: **the outcome follows the memory**,
        not "the memory was swapped but the result still tracks the body/traits".

--------------------------------------------------------------------------------
④ The task substrate
--------------------
027's `novel_task.py` is reused directly: the same reward table, the same α/β/τ, the same 80 trials with a
reversal at trial 41, the same restricted switch latency. **Not one number is changed**,
so that the "memory path" and "027's trait path" are comparable.

⚠ The decision rule is rewritten in stay/switch form (equivalent to 027's value difference at λ=0,
   but consuming u under a different convention — this file does not claim trial-by-trial identity with 027, only the same substrate).

⚠ The following thresholds are **probe knobs and are not calibrated**; today they serve only to look at identifiability:
   `GOOD_THRESH` / `PE_THRESH` / `SURPRISE_RUN_MIN`.
   They are **not** 029 design parameters; their official values must go through group-blind calibration.
"""

import math
import os
import statistics
import sys
from dataclasses import dataclass, fields

import novel_task as NT

# ------------------------------------------------------------------ probe knobs
GOOD_THRESH = 0.60        # "this strategy has long been good": the Q of the strategy in hand ≥ this
PE_THRESH = 0.30          # threshold at which a single prediction error counts as a "surprise" (negative direction)
SURPRISE_RUN_MIN = 3      # "persistent surprise": how many consecutive negative PEs trigger retrieval

LAMBDA_GRID = (0.0, 0.25, 0.5, 1.0, 2.0, 4.0)
PROBE_SEEDS = tuple(range(0, 400))        # ★ the development block, long since burned ★

ALLOWED_CONTEXTS = ("previously_good_strategy",)
ALLOWED_RELATIONS = ("stay", "switch")


# ================================================================== memory structure
@dataclass(frozen=True)
class Episode:
    """029's experiment-layer memory entry. ★ Contains no option identity ★"""
    context: str
    previous_expectation: float
    observation: float
    prediction_error: float
    action_relation: str      # "stay" / "switch" — never "A" / "B"
    outcome: float

    def __post_init__(self):
        if self.context not in ALLOWED_CONTEXTS:
            raise ValueError(f"unknown context: {self.context!r}")
        if self.action_relation not in ALLOWED_RELATIONS:
            raise ValueError(
                f"action_relation must be stay/switch, got {self.action_relation!r}"
                " — storing an option identity would make the memory untransferable to a new task")


class MemoryStore:
    """A minimal memory store: one relational query returning the stay/switch return contrast."""

    def __init__(self, name, episodes):
        self.name = name
        self.episodes = list(episodes)

    def evidence(self, context):
        """m = E[R | switch, similar past] − E[R | stay, similar past]

        Either side lacking a comparable entry → m = 0 (**no evidence, not evidence of zero difference**).
        """
        if context is None:
            return 0.0, 0, 0
        sw = [e.outcome for e in self.episodes
              if e.context == context and e.action_relation == "switch"]
        st = [e.outcome for e in self.episodes
              if e.context == context and e.action_relation == "stay"]
        if not sw or not st:
            return 0.0, len(sw), len(st)
        return statistics.fmean(sw) - statistics.fmean(st), len(sw), len(st)


def _episode(relation, outcome, *, expect=0.80, obs=0.0):
    """Construct one experience under 'previously-good strategy + persistent surprise'"""
    return Episode(context="previously_good_strategy",
                   previous_expectation=expect,
                   observation=obs,
                   prediction_error=obs - expect,
                   action_relation=relation,
                   outcome=outcome)


# ★ Two hand-built memory stores ★
#
# ⚠ The user's original wording covered only the switch side (S: switch→bad; V: switch→good).
#    But m is a **difference**, and with only one side evidence() returns 0 by definition (no evidence).
#    So a complementary stay side is added to each, keeping the two stores **perfectly symmetric**:
#    the only difference is "in this situation in the past, did staying or switching pay better".
MEM_S = MemoryStore("Memory S (under persistent surprise: switching loses, staying pays)", [
    _episode("switch", 0.2), _episode("switch", 0.2), _episode("switch", 0.1),
    _episode("stay",   0.8), _episode("stay",   0.8), _episode("stay",   0.9),
])
MEM_V = MemoryStore("Memory V (under persistent surprise: switching pays, staying loses)", [
    _episode("switch", 0.8), _episode("switch", 0.8), _episode("switch", 0.9),
    _episode("stay",   0.2), _episode("stay",   0.2), _episode("stay",   0.1),
])
MEM_EMPTY = MemoryStore("Memory ∅ (empty store)", [])


# ================================================================== body
class Body:
    """The carrier of 027's path: only curiosity / caution enter β."""

    def __init__(self, name, curiosity, caution):
        self.name = name
        self.traits = {"curiosity": float(curiosity),
                       "caution": float(caution),
                       "industry": 50.0}


# Take the two extremes — giving the body path the widest range it could have
BODY_C = Body("Body C (curious 90/10)", 90.0, 10.0)     # novelty_style = 0.90
BODY_K = Body("Body K (cautious 10/90)", 10.0, 90.0)    # novelty_style = 0.05


# ================================================================== retrieval trigger
def query_from_state(q_cur, surprise_run):
    """current situation → relational query (returns the context if it holds, None otherwise)"""
    if q_cur >= GOOD_THRESH and surprise_run >= SURPRISE_RUN_MIN:
        return "previously_good_strategy"
    return None


# ================================================================== task
def run(body, memory, seed, lam):
    """Run 027's 80-trial reversal task with the decision rule written in stay/switch form.

    logit(switch) = (val_switch − val_stay)/τ  +  λ · m
                     └── base_learning ──┘      └ memory evidence ┘
    """
    rows, us, a_good_first = NT.reward_table(seed)
    b = NT.BETA * NT.novelty_style(body)
    Q = [NT.Q_INIT, NT.Q_INIT]
    N = [0, 0]
    cur = None
    surprise_run = 0
    choices, rewards, fired, m_trace = [], [], [], []

    for t in range(NT.TRIALS):
        val = [Q[i] + b / math.sqrt(1 + N[i]) for i in (0, 1)]

        if cur is None:
            # On the first trial there is no "strategy in hand", so stay/switch is meaningless.
            # Q and N are equal on both sides here → p = 0.5, decided by the shared u, and the two options are symmetric.
            d = max(-60.0, min(60.0, (val[0] - val[1]) / NT.TAU))
            c = 0 if us[t] < 1.0 / (1.0 + math.exp(-d)) else 1
            ctx, m = None, 0.0
        else:
            oth = 1 - cur
            ctx = query_from_state(Q[cur], surprise_run)
            m, _, _ = memory.evidence(ctx)
            z = (val[oth] - val[cur]) / NT.TAU + lam * m
            z = max(-60.0, min(60.0, z))
            c = oth if us[t] < 1.0 / (1.0 + math.exp(-z)) else cur

        r = rows[t][c]
        pe = r - Q[c]

        # Only "kept using the same strategy and kept being disappointed" accumulates; any switch resets it
        if cur is not None and c == cur and pe < -PE_THRESH:
            surprise_run += 1
        else:
            surprise_run = 0

        N[c] += 1
        Q[c] += NT.ALPHA * (r - Q[c])
        cur = c
        choices.append(c)
        rewards.append(r)
        fired.append(1 if ctx is not None else 0)
        m_trace.append(m)

    return {"seed": seed, "a_good_first": a_good_first, "choices": choices,
            "rewards": rewards, "fired": fired, "m": m_trace, "beta": b,
            "explores": [0] * NT.TRIALS}


def latency(rec):
    return NT.switch_latency_restricted(rec)


def post_correct(rec):
    return NT.correct_rate(rec, NT.REVERSAL_AT, NT.TRIALS)


# ================================================================== self-checks
def _assert_relational_only():
    """★Hard constraint★ no option identity may appear in an Episode"""
    names = {f.name for f in fields(Episode)}
    banned = {"option", "arm", "choice", "a", "b", "stimulus", "label"}
    assert not (names & banned), f"Episode has an option-identity field: {names & banned}"
    for mem in (MEM_S, MEM_V):
        for e in mem.episodes:
            assert e.action_relation in ALLOWED_RELATIONS
            assert e.context in ALLOWED_CONTEXTS
            for f in fields(Episode):
                v = getattr(e, f.name)
                assert not (isinstance(v, str) and v in ("A", "B", "0", "1")), \
                    f"field {f.name} stores the option identity {v!r}"
    # The evidence read from memory is independent of "which physical option is in hand" (structurally impossible to depend on it)
    assert MEM_S.evidence("previously_good_strategy")[0] < 0
    assert MEM_V.evidence("previously_good_strategy")[0] > 0
    assert MEM_EMPTY.evidence("previously_good_strategy")[0] == 0.0
    assert MEM_S.evidence(None)[0] == 0.0
    ms = MEM_S.evidence("previously_good_strategy")[0]
    mv = MEM_V.evidence("previously_good_strategy")[0]
    print(f"  ✓ relational constraint: an Episode stores only stay/switch, never A/B")
    print(f"      m(Memory S) = {ms:+.4f}     m(Memory V) = {mv:+.4f}"
          f"     m(empty store) = 0 (no evidence)")
    return ms, mv


def _test_determinism():
    for sd in (7, 42, 301):
        a = run(BODY_C, MEM_V, sd, 1.0)
        b = run(BODY_C, MEM_V, sd, 1.0)
        assert a["choices"] == b["choices"] and a["rewards"] == b["rewards"]
    print("  ✓ determinism: same body + same memory + same seed → identical trial by trial")


def _test_memory_blind():
    """★ λ=0 = memory-blind ★ the two memory stores must be completely identical trial by trial"""
    diff = 0
    for sd in PROBE_SEEDS:
        if run(BODY_C, MEM_S, sd, 0.0)["choices"] != \
           run(BODY_C, MEM_V, sd, 0.0)["choices"]:
            diff += 1
    assert diff == 0, f"✗ memory still affects the decision at λ=0 ({diff} seeds) — there is a second path"
    print(f"  ✓ memory-blind (λ=0): all {len(PROBE_SEEDS)} seeds completely identical trial by trial")


def _retrieval_diagnostics():
    """Does retrieval fire at all, and when — if it never fires, everything downstream is idling"""
    ever, first, rate = 0, [], []
    for sd in PROBE_SEEDS:
        r = run(BODY_C, MEM_V, sd, 1.0)
        f = r["fired"]
        rate.append(sum(f) / NT.TRIALS)
        if any(f):
            ever += 1
            first.append(f.index(1))
    pre = statistics.fmean(
        [sum(run(BODY_C, MEM_V, sd, 1.0)["fired"][:NT.REVERSAL_AT])
         for sd in PROBE_SEEDS])
    n_fire = statistics.fmean(
        [sum(run(BODY_C, MEM_V, sd, 1.0)["fired"]) for sd in PROBE_SEEDS])
    print(f"  ✓ retrieval firing: {ever}/{len(PROBE_SEEDS)} seeds fire at least once"
          f" ({ever / len(PROBE_SEEDS):.1%})")
    print(f"      on average {n_fire:.2f} trials fire per seed (out of {NT.TRIALS})"
          f"   median first-firing trial {statistics.median(first):.0f}"
          f"   average firings before the reversal {pre:.2f}")
    return ever, n_fire


def _base_pressure_diagnostic():
    """★ Key diagnostic ★ at the moment retrieval fires, does base_learning already want to switch anyway?

    If p(switch) from base is already near 1 when it fires, then λ·m cannot change anything however large it is —
    **the memory is not useless, it simply arrives too late**. This decides what to fix next.
    """
    ps = []
    for sd in PROBE_SEEDS:
        rows, us, _ = NT.reward_table(sd)
        b = NT.BETA * NT.novelty_style(BODY_C)
        Q = [NT.Q_INIT, NT.Q_INIT]
        N = [0, 0]
        cur, run_ = None, 0
        for t in range(NT.TRIALS):
            val = [Q[i] + b / math.sqrt(1 + N[i]) for i in (0, 1)]
            if cur is None:
                d = max(-60.0, min(60.0, (val[0] - val[1]) / NT.TAU))
                c = 0 if us[t] < 1.0 / (1.0 + math.exp(-d)) else 1
            else:
                oth = 1 - cur
                z = max(-60.0, min(60.0, (val[oth] - val[cur]) / NT.TAU))
                p = 1.0 / (1.0 + math.exp(-z))
                if query_from_state(Q[cur], run_) is not None:
                    ps.append(p)                 # ★ recorded only at the moment of firing ★
                c = oth if us[t] < p else cur
            r = rows[t][c]
            pe = r - Q[c]
            run_ = run_ + 1 if (cur is not None and c == cur
                                and pe < -PE_THRESH) else 0
            N[c] += 1
            Q[c] += NT.ALPHA * (r - Q[c])
            cur = c
    if not ps:
        print("  ⚠ retrieval never fired — everything downstream is idling")
        return None
    ps.sort()
    q = lambda f: ps[min(len(ps) - 1, int(f * len(ps)))]      # noqa: E731
    print(f"  ⚑ base_learning's own p(switch) at the moment of firing: "
          f"median {statistics.median(ps):.3f}"
          f"   quartiles [{q(.25):.3f}, {q(.75):.3f}]"
          f"   share ≥0.9 {sum(1 for x in ps if x >= 0.9) / len(ps):.1%}")
    return statistics.median(ps)


# ================================================================== positive control
def positive_control():
    """★ Swap only the memory, everything else identical — does the choice sequence change? ★"""
    print("\n" + "=" * 78)
    print("★ POSITIVE CONTROL ★  same body / same Q / same reward table / same u — only the memory changes")
    print("=" * 78)
    print(f"{'λ':>6}  {'seeds whose trajectory changed':>32}  {'first divergent trial':>23}"
          f"  {'Δlatency (V−S)':>16}  {'Δpost-reversal accuracy':>25}")
    print("-" * 78)
    out = []
    for lam in LAMBDA_GRID:
        changed, firstdiv, dlat, dpc = 0, [], [], []
        for sd in PROBE_SEEDS:
            s = run(BODY_C, MEM_S, sd, lam)
            v = run(BODY_C, MEM_V, sd, lam)
            if s["choices"] != v["choices"]:
                changed += 1
                firstdiv.append(next(i for i in range(NT.TRIALS)
                                     if s["choices"][i] != v["choices"][i]))
            dlat.append(latency(v) - latency(s))
            dpc.append(post_correct(v) - post_correct(s))
        frac = changed / len(PROBE_SEEDS)
        med = statistics.median(firstdiv) if firstdiv else float("nan")
        print(f"{lam:>6.2f}  {changed:>6}/{len(PROBE_SEEDS)} = {frac:>5.1%}"
              f"  {med:>14.0f}  {statistics.fmean(dlat):>+16.3f}"
              f"  {statistics.fmean(dpc):>+14.4f}")
        out.append((lam, frac, statistics.fmean(dlat), statistics.fmean(dpc)))
    return out


# ================================================================== SWAP
def swap_test(lam):
    """★ SWAP TEST ★ the outcome must follow the memory, not the body"""
    print("\n" + "=" * 78)
    print(f"★ SWAP TEST ★  Body × Memory 2×2      λ = {lam}")
    print("=" * 78)
    cell, seqs = {}, {}
    for body in (BODY_C, BODY_K):
        for mem in (MEM_S, MEM_V):
            recs = [run(body, mem, sd, lam) for sd in PROBE_SEEDS]
            cell[(body.name, mem.name)] = (
                statistics.fmean([latency(r) for r in recs]),
                statistics.fmean([post_correct(r) for r in recs]))
            seqs[(body.name, mem.name)] = [r["choices"] for r in recs]

    print(f"{'':<26}{'Memory S':>22}{'Memory V':>22}")
    print(f"{'':<26}{'latency  accuracy':>24}{'latency  accuracy':>24}")
    print("-" * 78)
    for body in (BODY_C, BODY_K):
        row = f"{body.name:<26}"
        for mem in (MEM_S, MEM_V):
            L, P = cell[(body.name, mem.name)]
            row += f"{L:>13.3f}{P:>9.4f}"
        print(row)

    # Swapping memory (body fixed) vs swapping body (memory fixed)
    mem_eff = [cell[(b.name, MEM_V.name)][0] - cell[(b.name, MEM_S.name)][0]
               for b in (BODY_C, BODY_K)]
    body_eff = [cell[(BODY_K.name, m.name)][0] - cell[(BODY_C.name, m.name)][0]
                for m in (MEM_S, MEM_V)]

    def frac_changed(k1, k2):
        return sum(1 for a, b in zip(seqs[k1], seqs[k2]) if a != b) / len(PROBE_SEEDS)

    mem_chg = [frac_changed((b.name, MEM_S.name), (b.name, MEM_V.name))
               for b in (BODY_C, BODY_K)]
    body_chg = [frac_changed((BODY_C.name, m.name), (BODY_K.name, m.name))
                for m in (MEM_S, MEM_V)]

    print("-" * 78)
    print(f"  swap memory (body fixed)  Δlatency = "
          f"{mem_eff[0]:+.3f} / {mem_eff[1]:+.3f}"
          f"   trajectory changed {mem_chg[0]:.1%} / {mem_chg[1]:.1%}")
    print(f"  swap body (memory fixed)  Δlatency = "
          f"{body_eff[0]:+.3f} / {body_eff[1]:+.3f}"
          f"   trajectory changed {body_chg[0]:.1%} / {body_chg[1]:.1%}")

    mm = statistics.fmean([abs(x) for x in mem_eff])
    bb = statistics.fmean([abs(x) for x in body_eff])
    ratio = mm / bb if bb > 0 else float("inf")
    print(f"\n  |memory effect| = {mm:.3f} trials      "
          f"|body effect| = {bb:.3f} trials      ratio = {ratio:.2f}×")
    # Reading: does the effect follow the memory, and is the direction consistent across both bodies
    same_sign = (mem_eff[0] < 0) == (mem_eff[1] < 0) and mem_eff[0] != 0
    verdict = mm > bb and same_sign
    print(f"  memory-effect direction consistent across both bodies: {'yes' if same_sign else 'no'}")
    print(f"  ★ SWAP verdict: {'the outcome follows the memory' if verdict else '⚠ not passed'}")
    return mm, bb, ratio, verdict


# ================================================================== main
if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    fp = NT.assert_frozen()
    print("=" * 78)
    print("029 memory transfer — ★an identifiability probe, not an experiment★")
    print("=" * 78)
    print(f"task substrate: 027 novel_task  fingerprint {fp}  "
          f"TRIALS={NT.TRIALS} REVERSAL_AT={NT.REVERSAL_AT} "
          f"α={NT.ALPHA} β={NT.BETA} τ={NT.TAU}")
    print(f"seeds: development block {PROBE_SEEDS[0]}–{PROBE_SEEDS[-1]}"
          f" (n={len(PROBE_SEEDS)}) ★ 80000–81499 untouched ★")
    print(f"probe knobs (uncalibrated): GOOD_THRESH={GOOD_THRESH} "
          f"PE_THRESH={PE_THRESH} SURPRISE_RUN_MIN={SURPRISE_RUN_MIN}")
    print("\n[ engineering self-check ]")
    _assert_relational_only()
    _test_determinism()
    _test_memory_blind()
    _retrieval_diagnostics()
    _base_pressure_diagnostic()

    pc = positive_control()
    print("\n" + "=" * 78)
    print("★ SWAP TEST swept along λ (λ is not chosen today; only whether it can pass at some λ) ★")
    print("=" * 78)
    sw = [(lam,) + swap_test(lam) for lam in LAMBDA_GRID if lam > 0]

    print("\n" + "=" * 78)
    print("★ Today answers one question only: is this path identifiable ★")
    print("=" * 78)
    ok = any(f > 0 for lam, f, _, _ in pc if lam > 0)
    passed = [lam for lam, _, _, _, v in sw if v]
    print(f"  positive control passed (at λ>0, swapping only the memory changes the trajectory): "
          f"{'yes' if ok else 'no'}")
    print(f"  λ values where SWAP passes: {passed if passed else '★ none ★ (no λ passed)'}")
    print("\n  λ      |memory effect|   |body effect|      ratio   SWAP")
    for lam, mm, bb, ratio, v in sw:
        print(f"  {lam:<5.2f}  {mm:>12.3f}  {bb:>11.3f}  {ratio:>8.2f}×"
              f"   {'passed' if v else 'not passed'}")
    print("\n⚠ Passing ≠ Stable/Volatile may be run."
          " λ is not fixed, the thresholds are not calibrated, and the preregistration is not written.")
