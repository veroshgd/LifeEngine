"""
NOVEL-SITUATION mechanism layer — two probes + levelling + sibling forking + serialisation controls
===================================================================================================

Self-check:  python novel_situation.py            (runs every mechanism-layer test, ~1 minute)

★ Freeze declaration ★
This module imports the model from `v3_frozen/` and **modifies no line of v3**.
Probe A uses a `World` subclass (changing the **access rule**, not the stock);
Probe B uses an influence (an extension point v3 already provides).

Design basis: `NOVEL_SITUATION_DESIGN.md` v3. Relevant rules:

  rule 60  affordance gating must be non-destructive — change the access rule, not the stock
  rule 61  counterfactual sibling branches — fork from one snapshot, with no feedback between them
  rule 62  the decision window (behaviour/G1) is separate from the consequence window (outcome/G2)
  rule 55  globals inside a subprocess are set explicitly per task, never inherited
"""

import copy
import hashlib
import os
import pickle
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
V3DIR = os.path.join(HERE, "v3_frozen")
if V3DIR not in sys.path:
    sys.path.insert(0, V3DIR)

import sim                                      # noqa: E402
import scenarios                                # noqa: E402
import persistence_ablation as PA               # noqa: E402

for _m in (sim, scenarios, PA):
    assert os.path.abspath(_m.__file__).startswith(V3DIR), \
        f"✗ {_m.__name__} does not come from v3_frozen: {_m.__file__}"
assert sim.MODEL_VERSION == "v3"

WA, WB, COMMON = "rich world", "barren world", "baseline"

# Levelling point (following leveling.py / experiment 020). ★ shelter must be below gate S ★
LEVEL = {"hunger": 30.0, "energy": 80.0, "shelter": 50.0,
         "condition": 100.0, "food": 3.0, "material": 0.0}

# Natural units for Probe B (one-dimensional λ calibration, see design §2)
K_FOOD = 1.0        # yield of one gather_food                 (sim.py:185)
K_SHELTER = 22.0    # shelter increment of one build           (sim.py:882)


# ---------------------------------------------------------------- Probe A
class GatedWorld(sim.World):
    """Frozen ground: world.food is **accessible** only while agent.shelter ≥ gate_S.

    ★ Rule 60 ★ `self.food` (the stock) is never overwritten. The stock regenerates and persists as
    usual; what changes is the **access rule**. Writing `world.food = 0` would burn the world's food
    store every tick and regrow it from 0 the next — that is "destroying food", not "being unable to reach food".

    `agent` is bound when the world is swapped → shelter is read **at call time**, with no one-tick lag.
    When the gate is closed, one rng draw is consumed under the same condition as v3, so the gate
    **changes only affordance and adds no extra perturbation to the random stream**.
    """

    def __init__(self, seed=0, gate_S=60.0, **params):
        super().__init__(seed, **params)
        self.gate_S = gate_S
        self.agent = None

    def take_food(self, rng):
        if self.agent is not None and self.agent.shelter >= self.gate_S:
            return super().take_food(rng)
        if self.food >= 1:          # same sampling condition as sim.py:183
            rng.random()
        return 0


# ---------------------------------------------------------------- Probe B
def salt_flat(lam):
    """Saline soil: gathering material costs extra world.food; foraging costs extra shelter.

    ⚠ One-tick lag: the influence runs **before** `agent.tick()`, so it can only charge for the
      action of the **previous** tick. Stated as such in the paper; no pretence of same-tick effect.
    """
    c_f, c_s = lam * K_FOOD, lam * K_SHELTER
    prev = {}

    def apply(world, agent, day, tick, rng):
        key = id(agent)
        last = prev.get(key)
        now = (agent.action_log["gather_material"], agent.action_log["gather_food"])
        if last is not None:
            if now[0] > last[0]:
                world.food = max(0.0, world.food - c_f)
            if now[1] > last[1]:
                agent.shelter = sim.clamp(agent.shelter - c_s)
        prev[key] = now
    return apply


# ------------------------------------------------- Probe A2 "pathfinding" (candidate 1)
def discovery_gather(tau, alpha, base=None):
    """Exploration history → material accessibility (a new track under rules 65/66/67)

    ★ The precise form (not "more explore automatically yields material") ★
        `gather_material` must actually be executed to obtain material;
        **the yield of that gather depends on the share of explore within the last τ ticks.**

        explore → a transient "surveyed area" state → gather_material pays more

        pure explore   gets no material (nothing is gathered)
        pure gather    gets material only inefficiently
        what benefits   is the **temporal combination** explore → gather

    This is a **cross-action contingency** that exists in neither developmental world
    (there `material_yield` is a constant). And it **does not touch the food economy** (rule 65):
    `world.food` / `hunger` / `condition` are all left alone.

    ⚠ Scope: v3 has no online causal learning, so **the agent will not "realise it should scout before
      gathering"**. It merely enters this new dynamic carrying its existing policy, and different
      policies happen to interact differently with the new contingency. The write-up must not say "it learned to scout first".

    Implementation: each tick, rewrite `world.p["material_yield"]` from the explore count inside a
    sliding window — what changes is a **rate parameter**, not a stock (rule 60). At α=0 it is bit-equivalent to no intervention.
    """
    from collections import deque
    hist, prev = deque(maxlen=tau), {}

    def apply(world, agent, day, tick, rng):
        b = world.p["material_yield"] if base is None else base
        apply.base = getattr(apply, "base", b)
        key = id(agent)
        now = agent.action_log["explore"]
        last = prev.get(key)
        if last is not None:
            hist.append(1 if now > last else 0)
        prev[key] = now
        f = (sum(hist) / tau) if tau else 0.0          # explore share of the last τ ticks
        world.p["material_yield"] = apply.base * (1.0 + alpha * f)

    apply.hit = lambda: (sum(hist) > 0)
    return apply


# ------------------------------------------- Probe C "home falls into disrepair" (formally cleared)
SHELTER_FLOOR = 40.0        # hard floor: avoids the step in the sleep score at shelter=30 (sim.py:792)
STORM_OFF = {"storm_chance": 0.0}   # ★both the ON and OFF arms must use this★


def home_neglect(kappa, floor=SHELTER_FLOOR):
    """Home falls into disrepair: each explore causes a very small "unmaintained" loss of shelter.

    `build` still repairs shelter under the original v3 rule — no line of v3 is changed.

        explore --new relation--> slight drop in shelter
                              ↓
                    improve_home progress regresses / priority rises (sim.py:611/662)
                              ↓
                    goal stall / switch → action scores redistributed

    Previously `see_the_world` and `improve_home` merely **competed for time**;
    now, for the first time, "exploring actively destroys the progress made on fixing the home".
    So it is at once **N1** (a new causal relation explore → shelter loss)
    and **N2** (a new goal conflict).

    ★ Why shelter is a goal-progress variable here rather than a survival variable ★
      · the hard floor 40 > the step point 30 at sim.py:792 — sleep physiology is untouched
      · 40–75 lies entirely in the range where improve_home priority responds (sim.py:662)
      · food / hunger / condition are all left alone (rule 65)
      · both the ON and OFF arms use `storm_chance = 0` (otherwise two things change at once)

    ⚠ One-tick lag: the influence runs before `agent.tick()`, so it can only charge the explore of
      the **previous** tick. Stated as such in the paper.
    ⚠ Scope: the agent **will not "realise"** that exploring wrecks its home. It merely reacts through v3's existing mechanisms.
    """
    prev = {}
    ctr = {"explore": 0, "saturated": 0, "clipped": 0}

    def apply(world, agent, day, tick, rng):
        key = id(agent)
        now = agent.action_log["explore"]
        last = prev.get(key)
        if last is not None and now > last:
            ctr["explore"] += 1
            # ⚠ It must not be written as max(floor, shelter - kappa): if natural decay (0.35/tick)
            #   has already pushed shelter below the floor, that would **lift it back up** to the
            #   floor — turning the floor into a booster, i.e. a subsidy for a ball with a ruined home.
            #   Correct semantics: the loss may not push shelter below the floor, but must never raise it.
            if agent.shelter > floor:
                if agent.shelter - kappa < floor:
                    ctr["clipped"] += 1        # should have cost κ, clipped at the floor
                agent.shelter = max(floor, agent.shelter - kappa)
            else:
                # ★ True saturation ★ shelter is already ≤ floor (natural decay pushes it down too),
                #   and from here on explore can produce no further loss — Probe C has expired.
                #   Note this is not the same as shelter == floor, so the "share of time at the edge"
                #   **must not** be used to measure saturation (it would badly underestimate it).
                ctr["saturated"] += 1
        prev[key] = now

    apply.kappa = kappa
    apply.floor = floor
    apply.counters = ctr        # read-only counters, affecting no state and no random stream
    return apply


def novel_world(seed, kappa=0.0):
    """Probe C's world. ★The only ON/OFF difference is kappa★ — the background is fully isomorphic."""
    return sim.World(seed, **{**scenarios.WORLDS[COMMON], **STORM_OFF})


def enter_novel(life, clear_goal=True):
    """Common handling when entering the novel/familiar branch.

    ★ Only the intention currently being executed is cleared ★ — otherwise "the rich twin happens to be
    in the middle of see_the_world while the poor twin happens to be in improve_home" would degrade the
    result into "it simply carried on with whatever it was doing on entry".

    **Not** cleared: traits / trait_floor / knowledge / flags / goal_satiation / memories / hardship —
    those are precisely "the internal structure left by the past", which is what is being measured.
    """
    if clear_goal:
        life.agent.goal = None


# ---------------------------------------------------------------- levelling
def level_state(agent):
    """State levelling (the experiment 020 convention). Only resource state is touched, never what history carries."""
    agent.hunger = LEVEL["hunger"]
    agent.energy = LEVEL["energy"]
    agent.shelter = LEVEL["shelter"]
    agent.condition = LEVEL["condition"]
    agent.inventory = {"food": LEVEL["food"], "material": LEVEL["material"]}


# --------------------------------------- field audit (rule 63) + state serialisation
#
# ★ Rule 63 ★ "complete executable state" must be established by a **field-by-field audit**, not listed from memory.
#   Audit method: grep the read points of v3's Agent / World field by field,
#   **read back → EXEC (enters the hash, and must be levelled along with everything else); write-only → LOG.**
#
#   The mistake of the first version: `"memories": len(ag.memories)` —
#   **"has 5 memories" ≠ "the 5 memories have the same content"**, and memories are read back by
#   `recall()` (sim.py:517/554/563). goal_satiation slipped through the same way.
#
# ── Agent ────────────────────────────────────────────────────────────
#  EXEC  traits/trait_floor/trait_identity   read directly by action scoring
#  EXEC  hunger/energy/shelter/condition/inventory   state items
#  EXEC  hardship/_hardship_anchor           → the trait_floor ratchet
#  EXEC  flags/knowledge/knowledge_strength  read back by score()
#  EXEC  memories          ★ read back by recall() (sim.py:517/554/563) ★ must be complete
#  EXEC  goal                                the current goal affects scoring
#  EXEC  goal_satiation    ★ read back at sim.py:694 — the goal refractory period ★
#  EXEC  action_log        ★ read back at sim.py:619/626 — goal progress ★
#  EXEC  alive / rng(state)
#  LOG   action_by_hour    never read back inside sim.py, pure record (for analysis)
#  LOG   goal_by_day       never read back
#  LOG   goal_history      never read back
#  STRUCT world            a reference, not state
#
# ── World ────────────────────────────────────────────────────────────
#  EXEC  food / objects / p / weather / rng(state)
#  EXEC  storm_damage      ★ dynamic attribute, present only after a storm; read back at sim.py:942 ★
#  LOG   events            written only by influences, never read back
#
# ── Life ─────────────────────────────────────────────────────────────
#  EXEC  inf_rng(state)          STRUCT  agent / world / influences

_AG_EXEC = ("traits", "trait_floor", "trait_identity", "hunger", "energy",
            "shelter", "condition", "inventory", "hardship", "_hardship_anchor",
            "flags", "knowledge", "knowledge_strength", "memories", "goal",
            "goal_satiation", "action_log", "alive", "rng")
_AG_LOG = ("action_by_hour", "goal_by_day", "goal_history")
_AG_STRUCT = ("world",)

_W_EXEC = ("food", "objects", "p", "weather", "rng", "storm_damage",
           "gate_S", "agent")          # the last two come from GatedWorld (agent is a reference, handled separately)
_W_LOG = ("events",)

_L_EXEC = ("inf_rng",)
_L_STRUCT = ("agent", "world", "influences")


def audit_fields(life):
    """★ Completeness assertion ★ any unclassified field makes it fail.

    v3 is frozen, but **this assertion guards against "I overlooked a field"**, not merely against
    "v3 changes later". The first version overlooked both memories content and goal_satiation.
    """
    known = {
        "agent": set(_AG_EXEC) | set(_AG_LOG) | set(_AG_STRUCT),
        "world": set(_W_EXEC) | set(_W_LOG),
        "life": set(_L_EXEC) | set(_L_STRUCT),
    }
    for name, obj in (("agent", life.agent), ("world", life.world), ("life", life)):
        unknown = set(vars(obj)) - known[name]
        if unknown:
            raise AssertionError(
                f"✗ {name} has unclassified fields {sorted(unknown)} — "
                f"decide whether each is read back (EXEC) before deciding whether it enters the hash.")


def _norm(v):
    """Normalise a value into a deterministically picklable form"""
    import random as _r
    from collections import Counter
    if isinstance(v, _r.Random):
        return ("rngstate", v.getstate())
    if isinstance(v, (set, frozenset)):
        return ("set", sorted(map(repr, v)))
    if isinstance(v, Counter):
        return ("counter", sorted(v.items()))
    if isinstance(v, dict):
        return ("dict", sorted((k, _norm(x)) for k, x in v.items()))
    if isinstance(v, (list, tuple)):
        return ("seq", [_norm(x) for x in v])
    return v


def exec_state(life):
    """**Executable** state (EXEC) — used by the full-levelling negative control.
    Contains only fields that are read back and can therefore affect future behaviour."""
    audit_fields(life)
    ag, w = life.agent, life.world
    st = {f"ag.{k}": _norm(getattr(ag, k)) for k in _AG_EXEC if hasattr(ag, k)}
    st.update({f"w.{k}": _norm(getattr(w, k))
               for k in _W_EXEC if hasattr(w, k) and k != "agent"})
    st["life.inf_rng"] = _norm(life.inf_rng)
    return st


def full_state(life):
    """EXEC + LOG — used by fork isolation / determinism tests (stricter)."""
    st = exec_state(life)
    ag, w = life.agent, life.world
    st.update({f"ag.{k}": _norm(getattr(ag, k)) for k in _AG_LOG if hasattr(ag, k)})
    st.update({f"w.{k}": _norm(getattr(w, k)) for k in _W_LOG if hasattr(w, k)})
    return st


def _h(d):
    return hashlib.sha256(pickle.dumps(sorted(d.items()), protocol=4)).hexdigest()


def exec_hash(life):
    return _h(exec_state(life))


def full_hash(life):
    return _h(full_state(life))


# ------------------------------------------------- rule 61: sibling forking
def fork(life, floor_off):
    """Fork a **fully isolated** sibling branch from the same snapshot.

    ⚠ The deepcopy trap of 024: `FrozenZero` is a dict subclass whose `__setitem__` is a no-op, so
      deepcopy rebuilds it through `__setitem__` → an **empty dict** is produced → KeyError.
      It carries no state (reads are always 0, writes are always dropped), so rebuilding is equivalent.
    """
    clone = copy.deepcopy(life)
    if floor_off:
        clone.agent.trait_floor = PA.FrozenZero()
        clone.agent.trait_identity = PA.FrozenZero()
    return clone


def run_window(life, day0, days, world=None, extra_inf=()):
    """Run one window, returning (alive?, the [24 hours × action] counts within that window)"""
    from collections import Counter
    ag = life.agent
    if world is not None:
        life.world = world
        ag.world = world
        if isinstance(world, GatedWorld):
            world.agent = ag                    # binding: shelter is read at call time
    snap = [Counter(c) for c in ag.action_by_hour]
    infl = list(life.influences) + list(extra_inf)
    for day in range(day0, day0 + days):
        for t in range(sim.TICKS_PER_DAY):
            life.world.tick(day, t)
            for inf in infl:
                inf(life.world, ag, day, t, life.inf_rng)
            ag.tick(day, t)
            if not ag.alive:
                return False, [Counter(c) - snap[h]
                               for h, c in enumerate(ag.action_by_hour)]
        ag.daily(day)
    return True, [Counter(c) - snap[h] for h, c in enumerate(ag.action_by_hour)]


# ---------------------------------------------------------------- self-checks
def _test_gate_non_destructive():
    """Rule 60: while the gate is shut the stock must regenerate as usual and never be burned"""
    w = GatedWorld(1, gate_S=60.0, **scenarios.WORLDS[COMMON])

    class Stub:
        shelter = 0.0
    w.agent = Stub()
    import random
    rng = random.Random(0)
    before = w.food
    got = [w.take_food(rng) for _ in range(50)]
    assert all(g == 0 for g in got), "got food through a shut gate"
    assert w.food == before, f"stock changed while the gate was shut: {before} → {w.food}"
    for d in range(3):
        for t in range(sim.TICKS_PER_DAY):
            w.tick(d, t)
    assert w.food >= before, "the stock did not regenerate as usual"
    w.agent.shelter = 99.0
    assert sum(w.take_food(rng) for _ in range(10)) > 0, "gate open but no food obtainable"
    print("  ✓ rule 60: a shut gate burns no stock, regen is normal, an open gate yields food")


def _test_sibling_isolation():
    """Rule 61: mutation test — changing one branch must not affect the other (once in each direction)"""
    life = scenarios.make(20000, WB)
    run_window(life, 0, 3)
    level_state(life.agent)
    h0 = full_hash(life)

    f, n = fork(life, False), fork(life, False)
    assert full_hash(f) == h0 and full_hash(n) == h0, "state already inconsistent at the moment of forking"

    hn = full_hash(n)
    f.agent.inventory["food"] += 99
    f.agent.traits["caution"] = 3.0
    f.agent.memories.append({"day": 999, "text": "mutation"})     # ★content level★
    f.agent.goal_satiation["stock_food"] = 999
    f.agent.action_log["explore"] += 7
    f.world.food = 0.0
    f.world.p["food_regen"] = 99.0
    f.agent.rng.random()
    assert full_hash(n) == hn, "✗ changing clone F affected clone N — the branches are not isolated"

    hf = full_hash(f)
    n.agent.inventory["material"] += 42
    n.agent.trait_floor["industry"] = 88.0
    n.agent.memories.append({"day": 998, "text": "reverse mutation"})
    n.agent.rng.random()
    assert full_hash(f) == hf, "✗ changing clone N affected clone F — the branches are not isolated"
    print("  ✓ rule 61: the sibling mutation test passes in both directions (including memories content / goal_satiation / action_log / world.p)")


def _test_identical_branches():
    """Identical complete executable state → placed in the same world, the runs must be **bit-identical**"""
    life = scenarios.make(20001, WA)
    run_window(life, 0, 5)
    level_state(life.agent)
    a, b = fork(life, False), fork(life, False)
    wa_ = sim.World(20001, **scenarios.WORLDS[COMMON])
    wb_ = sim.World(20001, **scenarios.WORLDS[COMMON])
    ra = run_window(a, 5, 7, world=wa_)
    rb = run_window(b, 5, 7, world=wb_)
    assert ra[0] == rb[0] and ra[1] == rb[1], "✗ two identical branches are not bit-identical — there is a leak"
    assert full_hash(a) == full_hash(b), "✗ final-state hashes differ — there is a leak"
    print("  ✓ negative control: identical complete state → bit-identical")


def _test_floor_off_fork():
    """The FrozenZero deepcopy trap of 024 must not come back"""
    scenarios.make = PA.patched_make(False, True)
    try:
        life = scenarios.make(20002, WB)
        run_window(life, 0, 3)
        level_state(life.agent)
        c = fork(life, True)
        run_window(c, 3, 3, world=sim.World(20002, **scenarios.WORLDS[COMMON]))
    finally:
        scenarios.make = PA._orig_make
    print("  ✓ forking with all floors off does not hit the FrozenZero deepcopy trap")


def _test_field_audit():
    """Rule 63: the field-completeness assertion must really fail on a new field"""
    life = scenarios.make(20004, WA)
    run_window(life, 0, 2)
    audit_fields(life)                       # must pass under normal conditions
    life.agent.some_new_field = 1
    try:
        audit_fields(life)
    except AssertionError as e:
        assert "some_new_field" in str(e)
    else:
        raise AssertionError("✗ the completeness assertion did not catch a new field")
    del life.agent.some_new_field
    # A change in memories content must change the hash (the hole in the first version)
    h = exec_hash(life)
    life.agent.memories.append({"day": 1, "text": "x"})
    assert exec_hash(life) != h, "✗ a change in memories content did not change the hash"
    life.agent.memories.pop()
    assert exec_hash(life) == h
    # Same for goal_satiation
    life.agent.goal_satiation["learn"] = 12345
    assert exec_hash(life) != h, "✗ a change in goal_satiation did not change the hash"
    print("  ✓ rule 63: the field audit assertion works, and both memories content and goal_satiation enter the hash")


def _test_salt_flat():
    """Probe B: the coupling really takes effect, and at λ=0 it is bit-identical to no coupling"""
    def run(lam):
        life = scenarios.make(20003, WB)
        run_window(life, 0, 3)
        level_state(life.agent)
        c = fork(life, False)
        w = sim.World(20003, **scenarios.WORLDS[COMMON])
        inf = (salt_flat(lam),) if lam else ()
        return run_window(c, 3, 10, world=w, extra_inf=inf), c

    (a0, _), c0 = run(0.0)
    (a1, _), c1 = run(0.0)
    assert full_hash(c0) == full_hash(c1), "λ=0 inconsistent across two runs"
    (_, _), c2 = run(0.5)
    assert full_hash(c0) != full_hash(c2), "λ=0.5 identical to no coupling — the coupling had no effect"
    print("  ✓ Probe B: λ=0 equals no coupling, λ>0 really changes the trajectory")


def _test_discovery():
    """Probe A2: α=0 is bit-equivalent to no intervention; α>0 really changes the trajectory; and the food economy is untouched"""
    def run(tau, alpha):
        life = scenarios.make(20005, WB)
        run_window(life, 0, 5)
        level_state(life.agent)
        c = fork(life, False)
        w = sim.World(20005, **scenarios.WORLDS[COMMON])
        inf = (discovery_gather(tau, alpha),) if alpha else ()
        run_window(c, 5, 12, world=w, extra_inf=inf)
        return c

    a, b = run(12, 0.0), run(12, 0.0)
    assert full_hash(a) == full_hash(b), "α=0 inconsistent across two runs"
    c = run(12, 0.0)
    d = run(12, 2.0)
    assert full_hash(c) != full_hash(d), "α=2 identical to no intervention — the rule had no effect"
    # ★Rule 65★ the food economy must not be touched
    src = discovery_gather.__doc__ or ""
    import inspect
    body = inspect.getsource(discovery_gather)
    for banned in ("world.food", "hunger", "condition", "FOOD_"):
        assert banned not in body.split('"""')[-1], f"✗ touched the food economy: {banned}"
    print("  ✓ Probe A2: α=0 equals no intervention, α>0 changes the trajectory, and the food economy is untouched")


def _test_probe_c():
    """Probe C: κ=0 bit-equivalent; κ>0 changes the trajectory; ON/OFF backgrounds isomorphic; the floor works; goal is cleared"""
    from collections import Counter

    def run(seed, kappa, clear=True):
        life = scenarios.make(seed, WB)
        run_window(life, 0, 8)
        level_state(life.agent)
        c = fork(life, False)
        enter_novel(c, clear_goal=clear)
        w = novel_world(seed)                       # ★the same background for ON/OFF★
        inf = (home_neglect(kappa),) if kappa else ()
        _, win = run_window(c, 8, 15, world=w, extra_inf=inf)
        acc = Counter()
        for h in win:
            acc.update(h)
        return c, acc["explore"]

    # ⚠ Seeds that really do explore must be chosen — 20006 is a pure builder ball (explore=0), and
    #   testing "did κ take effect" with it can never show anything (that is how the first version misreported).
    diffs = 0
    for sd in range(20010, 20030):
        a, ne = run(sd, 0.0)
        if ne == 0:
            continue
        b, _ = run(sd, 0.0)
        assert full_hash(a) == full_hash(b), f"κ=0 inconsistent across two runs (seed {sd})"
        c2, _ = run(sd, 0.5)
        if full_hash(a) != full_hash(c2):
            diffs += 1
    assert diffs >= 3, f"✗ κ=0.5 barely changes the trajectory (only {diffs} seeds changed)"

    # Isomorphic background: both ON and OFF arms must have storm_chance=0
    assert novel_world(1).p["storm_chance"] == 0.0, "the background world did not switch storms off"
    assert SHELTER_FLOOR > 30.0, "the floor must be above the sleep step point 30 at sim.py:792"

    # ★ The hard floor may only "catch" a loss; it must never lift a shelter already below the floor ★
    class Stub:
        shelter = 12.0
        action_log = Counter({"explore": 5})
    st = Stub()
    inf = home_neglect(3.0)
    inf(None, st, 0, 0, None)
    st.action_log["explore"] += 1
    inf(None, st, 0, 1, None)
    assert st.shelter == 12.0, f"✗ the floor lifted shelter from 12 to {st.shelter}"

    # Clearing the goal clears only the intention, never the historical structure
    life = scenarios.make(20007, WA)
    run_window(life, 0, 8)
    level_state(life.agent)
    d = fork(life, False)
    before = (dict(d.agent.traits), dict(d.agent.goal_satiation),
              sorted(d.agent.flags), len(d.agent.memories))
    enter_novel(d)
    assert d.agent.goal is None, "the goal was not cleared"
    after = (dict(d.agent.traits), dict(d.agent.goal_satiation),
             sorted(d.agent.flags), len(d.agent.memories))
    assert before == after, "✗ clearing the goal damaged the historical structure"
    print("  ✓ Probe C: κ=0 equals OFF, κ>0 takes effect, backgrounds isomorphic, the floor catches, only the intention is cleared")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"Mechanism-layer self-check   model from {os.path.dirname(sim.__file__)}   "
          f"{sim.MODEL_VERSION}  COND_RECOVER_AT={sim.COND_RECOVER_AT}")
    _test_gate_non_destructive()
    _test_sibling_isolation()
    _test_identical_branches()
    _test_floor_off_fork()
    _test_field_audit()
    _test_salt_flat()
    _test_discovery()
    _test_probe_c()
    print("\nAll passed. The mechanism layer is ready for group-blind calibration.")
