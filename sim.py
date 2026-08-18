"""
AI SANDBOX — Life Engine (core model)
=====================================

Pure code, zero LLM, zero dependencies.

★ The core change in v2: **there is no concept of a "user" in this file.**

It used to be:
    User type → Feeding → Personality

Now it is:
    World → Experience → Memory → Personality → Behavior

The Agent only knows it lives in a world that has resources, weather and objects.
"Who is feeding it" and "how diligently" are the business of the **experiment
scripts** — see scenarios.py. The Life Engine itself does not know what a user is.

This is not fastidiousness. The core claim is not "how the user raises it → how the
NPC grows", but "the user changes the world like a god, and life grows into
different shapes on its own according to the environment". Keeping USER_ARCHETYPES

Three layers:

    Agent               World              Influence
    ├─ personality      ├─ resources       ├─ give_food
    ├─ needs            ├─ weather         ├─ add_book
    ├─ memory           ├─ objects         ├─ play_music
    ├─ goals            └─ events          └─ change_environment
    └─ history

⚠ Compatibility: v2 reordered random-number consumption (world and individual are
   now two independent streams), so numeric results are not directly comparable with

★ v3 (2026-08-15): condition-stability correction — one number changed ★
------------------------------------------------------------------------
    COND_RECOVER_AT   30.0 → 65.0

Every other parameter and mechanism is **bit-for-bit unchanged**. The full v2

> Experiments 011–022 were conducted under model v2 and are retained as
> development history rather than overwritten by subsequent model correction.

Why 65 (log §3h / rules 46, 47, 49):
  rules 46/47  v2's condition only ever leaked one way; after a transplant 90–98% of
               ticks sat in the dead zone, and after day 30 **no ball had a positive
               balance** — structurally there was no steady state. 120-day mortality
               40.7% (all floors off), which contaminated every long-horizon result.
  rule 49      But raising the threshold is not monotonically helpful. There is a
               **sloth valley**: raise threshold → condition↑ → survival urgency↓
               (see urgency in score()) → well-fed agents forage less → hunger rises
               again → mortality **goes up**. Measured in the rich world: 24.3%
               →(T=55) 36.3% →(T=60) 18.0% →(T=65) 2.0%. Balls raised in the barren
               world have the hardship ratchet propping up their industry floor, so
               they tolerate sloth; well-fed balls have no such brake.
"""

import math
import random
from collections import Counter

# ============================================================
# Version marker — every CSV / raw result must carry this
# ============================================================
MODEL_VERSION = "v3"       # v3 = condition-stability correction (2026-08-15)

# ============================================================
# Parameters
# ============================================================

PERSONALITY_WEIGHT = 30.0  # How strongly personality weighs on action scoring. ★core knob★
                           #   too small → all balls behave alike → convergence
                           #   too large → balls ignore hunger and starve → cartoon characters
TRAIT_DRIFT        = 1.20  # How far each action nudges personality (positive-feedback gain)
TRAIT_SATURATION   = 0.90  # The more extreme a trait, the harder to grow further (0 = off)
# ★Why this is needed★ Positive feedback has no brake of its own: explore → curiosity↑
# caution↓ → want to explore more. In v1 the permanent trait_floor happened to act as the
# brake; v2 lets floors decay (note ⑤), so the brake was gone, and by day 60 a batch of
# balls had drifted to caution 8 / curiosity 100, explored non-stop and starved.
# This also incidentally cured the ceiling problem of experiment 017 (at day 60, 78% of
# balls had caution pinned at 100).
LANDMARK_BONUS     = 25.0  # Bonus an action gets from a landmark experience
HUNGER_RATE        = 2.2   # Hunger growth per tick

FOOD_NUTRITION     = 20.0  # How much hunger one portion of food removes
                           # one gather ≠ one day's ration, else the ball is fully self-sufficient

# Yield of exploring. ★A behaviour not bounded by a resource cap becomes an infinite tap★ (lesson of experiment 013)
EXPLORE_FOOD_CHANCE = 0.28
EXPLORE_FOOD_YIELD  = 0.5

TICKS_PER_DAY = 24
SIM_DAYS      = 30

TRAITS = ["caution", "curiosity", "industry"]   # caution / curiosity / industry

INITIAL_TRAIT_SPREAD = 6.0   # Random offset of personality at birth (±)
# ★Rule 12★ Positive feedback amplifies whichever difference enters the loop first. The seed
# enters on day 0, environmental influence takes days to show → this number is a *competitor*

# --- continuous transmission: suffering → personality (experiment 013) ---
HARDSHIP_SCALE     = 1.5   # Saturation-curve time constant (day-equivalent of condition hitting zero)
HARDSHIP_MAX_BOOST = 22.0  # How high the personality floor can be raised at saturation
HARDSHIP_FLOOR_WEIGHT = {"industry": 1.0, "curiosity": 0.27}
HARDSHIP_STORY_AT  = 0.5   # Accumulate to here and a landmark experience is recorded (for narrative)

# --- ★the temporal structure of personality★ (note ⑤: forms fast, fades slow) --------
# Before: landmark experience → trait_floor → never comes back. Good enough as a first
#         experiment, but real personality is not like that; it is more "forms fast, fades
#         slow": a storm gives caution +15, then half a year of calm → +15→+13→+11→+9
#         Only a truly major landmark leaves a permanent bias.
#
#   short-term adaptation → medium-term habit → long-term personality
#                                                   → landmark identity
#
# Implementation: two floors. soft decays slowly, perm does not, and soft is never below perm.
FLOOR_DECAY_PER_DAY  = 0.35   # How much the soft floor fades per day
LANDMARK_PERMANENT   = 0.40   # What fraction of a landmark boost becomes permanent bias
HARDSHIP_FORGET      = 0.015  # How fast the memory of suffering fades on a full stomach


def clamp(v, lo=0.0, hi=100.0):
    return max(lo, min(hi, v))


# ============================================================
# World — the world. The Agent lives in it, but does not know what a "user" is
# ============================================================

WORLD_DEFAULTS = {
    "food_regen":       2.4,   # Portions of food regrown per day (demand ≈ 2.64 → natural deficit)
    "food_cap":         6.0,
    "material_yield":   1.0,   # Portions of material obtained per gather
    "storm_chance":     0.04,  # Daily storm probability
    "storm_damage":     (10.0, 40.0),
    "season_days":      12,    # Abundant/lean season period
    "season_amplitude": 0.55,  # ★What produces a gradient is the fluctuation, not the mean★ (rule 4)
    "objects":          (),    # What exists in the world: {"book", "music"}
}


class World:
    """Resources, weather, objects, events.

    Note `objects`: whether the world has books or music is an **environmental**
    property, not a property of the Agent. Put the same Agent into different worlds
    and it grows into a different shape — which is exactly what we want to verify.
    """

    def __init__(self, seed=0, **params):
        self.rng = random.Random(seed)
        self.p = dict(WORLD_DEFAULTS)
        unknown = set(params) - set(WORLD_DEFAULTS)
        if unknown:
            raise ValueError(f"unknown world parameter: {sorted(unknown)}")
        self.p.update(params)
        self.objects = set(self.p["objects"])
        self.food = self.p["food_cap"]
        self.events = []          # what happened at world level (not the agent's memory)
        self.weather = "clear"

    def season_multiplier(self, day):
        """Abundant season ~1.5×, lean season ~0.45×. Shared world-wide (it is the world, not personal luck)"""
        return 1.0 + self.p["season_amplitude"] * math.sin(
            2 * math.pi * day / self.p["season_days"])

    def has(self, obj):
        return obj in self.objects

    def tick(self, day, tick_of_day):
        """The world's own evolution: resource regrowth + weather"""
        self.food = min(self.p["food_cap"],
                        self.food + self.p["food_regen"]
                        * self.season_multiplier(day) / TICKS_PER_DAY)

        self.weather = "clear"
        if tick_of_day == 3 and self.rng.random() < self.p["storm_chance"]:
            lo, hi = self.p["storm_damage"]
            self.weather = "storm"
            self.storm_damage = self.rng.uniform(lo, hi)
            self.events.append((day, "storm"))

    def take_food(self, rng):
        """The Agent comes to gather. Once it is empty it is gone — this cap comes from the environment, not the individual"""
        if self.food >= 1 and rng.random() < 0.85:
            self.food -= 1
            return 1
        return 0


# ============================================================
# Influence — external intervention (user / god)
# ============================================================
#
# ★Key design★ The Agent does not know these things were done by a "user".
# From the Agent's point of view, "the world suddenly has more food / a book in it".
# Each influence is a function (world, agent, day, tick, rng) -> None.

def give_food(amount=2.0, every_days=3.0, at_tick=8):
    """Feed on a schedule. Larger every_days = visits it less often."""
    def apply(world, agent, day, tick, rng):
        if tick == at_tick and rng.random() < 1.0 / every_days:
            agent.receive("food", amount, day, "someone gave me food")
    return apply


def add_book(day=0, at_tick=9):
    """Put a book into the world on some day. Only then is the `read` action legal."""
    def apply(world, agent, day_now, tick, rng):
        if day_now == day and tick == at_tick and not world.has("book"):
            world.objects.add("book")
            world.events.append((day_now, "book_appeared"))
            agent.remember(day_now, "a book appeared in the world", tags=("book", "new"),
                           importance=0.5)
    return apply


def play_music(from_day=0):
    """From some day on there is always music in the world. A passive influence: resting works better, more settled."""
    def apply(world, agent, day_now, tick, rng):
        if day_now >= from_day and not world.has("music"):
            world.objects.add("music")
            world.events.append((day_now, "music_started"))
            agent.remember(day_now, "music started playing", tags=("music", "new"),
                           importance=0.4)
    return apply


def change_environment(day, **new_params):
    """Change the world's physical parameters on some day (less food, frequent rain…)"""
    def apply(world, agent, day_now, tick, rng):
        if day_now == day and tick == 0:
            world.p.update(new_params)
            world.events.append((day_now, f"environment_changed:{new_params}"))
    return apply


def give_object(obj, day=0, at_tick=9):
    """Add an arbitrary object to the world"""
    def apply(world, agent, day_now, tick, rng):
        if day_now == day and tick == at_tick:
            world.objects.add(obj)
            world.events.append((day_now, f"object:{obj}"))
    return apply


# ============================================================
# Action definitions
# ============================================================

# Which traits each action "fits" — used when scoring
ACTION_TRAIT_MATCH = {
    "eat":            {},
    "sleep":          {"caution":  0.5},
    "gather_food":    {"industry": 1.0, "caution":  0.4},
    # Experiments 016/017: hanging this on industry alone makes "caring for it actually harms
    # it" (industry only ratchets up through hunger → a well-fed ball never gathers material →
    # never gets a home). Adding caution fixes the direction, but weight 1.2 wipes out the
    # population by day 60 (material eats 30% of the action budget), so back down to 0.6.
    "gather_material":{"industry": 1.0, "caution": 0.6},
    "build":          {"caution":  1.0, "industry": 0.6},
    "explore":        {"curiosity": 1.2, "caution": -1.0},
    "read":           {"curiosity": 1.0, "caution": 0.2},   # requires a book in the world
}

# Doing this → reinforce the trait that made you do it. ★This is the positive-feedback loop★
ACTION_TRAIT_FEEDBACK = {
    "eat":            {},
    "sleep":          {"caution":  0.05},
    "gather_food":    {"industry": 0.10, "caution":   0.05},
    "gather_material":{"industry": 0.12},
    "build":          {"caution":  0.15, "industry":  0.08},
    "explore":        {"curiosity": 0.20, "caution": -0.10},
    "read":           {"curiosity": 0.16},
}

# Some actions require a matching object in the world to be legal — the environment decides
# "what can be done", not merely "what the same action pays". This is the hardest channel
# by which the environment shapes the individual.
ACTION_REQUIRES_OBJECT = {"read": "book"}

ACTIONS = list(ACTION_TRAIT_MATCH)


# ============================================================
# Goal — from "reactive agent" to "autonomous life"
# ============================================================
#
# The old loop was:
#     tick → score every action → pick the highest → execute
# That is a fine **Reactive Agent**, but not life. What the user sees is
#     "this tick, build happened to score highest"
# whereas what we want is
#     "it has been building its home these last few days".
#
# The difference is **continuity of intent across ticks**. A Goal is exactly such a
# cross-tick object: generated from state and memory, persistent, biasing action scores,
# with progress, and completable.
#
# ★The key is hysteresis (GOAL_SWITCH_MARGIN)★
# Without hysteresis the goal is displaced every day by the most urgent need of that day —
# then it is just another name for need and nothing has changed. With hysteresis, it can
# "stick with something until it is done".

GOAL_ACTIONS = {
    "improve_home":  {"gather_material": 1.0, "build": 1.4},
    "stock_food":    {"gather_food": 1.2, "explore": 0.3},
    "see_the_world": {"explore": 1.4},
    "learn":         {"read": 1.4},
    "recover":       {"sleep": 1.0, "eat": 0.6},
}

GOAL_LABEL = {
    "improve_home":  "make the home sturdier",
    "stock_food":    "stock up on food",
    "see_the_world": "go and see distant places",
    "learn":         "read a bit more",
    "recover":       "get back in shape",
}

GOAL_BONUS         = 32.0   # Maximum bonus a goal gives an action score
GOAL_OFF_TASK      = 14.0   # **discretionary** actions unrelated to the current intent are damped = focus
# ★Why OFF_TASK is mandatory★ Bonusing goal actions is not enough: a ball that has drifted
# to curiosity 90 / caution 25 already gets +44 of personality bonus on explore, which a mere
# +22 goal bonus cannot cover — measured, it spent 13 straight days "wanting to fix the house"
# while running around outside, and the house rotted to 0.
DISCRETIONARY = ("explore", "read")   # Discretionary. Survival actions are never damped
GOAL_SWITCH_MARGIN = 0.25   # A new goal must beat the old by this much to be worth switching — this is "focus"
GOAL_MIN_DAYS      = 2      # A goal is kept at least this many days (unless already done)
GOAL_REFRACTORY    = 6      # Having just finished something, do not immediately do it again for this many days
GOAL_STALL_DAYS    = 4      # This many days with no progress at all → give up
GOAL_SLACK_FOOD    = 4.0    # Slack (rule 27): only with this much stored food does it count as "fed"
GOAL_SLACK_COND    = 90.0   # Slack: only at this condition does the body count as "holding up"

# ---------------------------------------------------------------------------
# ★Experiment 022★ Semantic memory wired into decisions
# ---------------------------------------------------------------------------
# Rules 30/31: `knowledge` used to be write-only — `score()` never read it, so semantic
# memory was decoration. The consequence in experiment 021 §3: with trait floors off, the
# transplant ratio was only 1.044 (CI containing 1.0), and "you did not discover
# irreversibility, you wrote irreversibility in" had no answer.
#
# Preregistration: [[Experiment 022 preregistration — memory wired into decisions]].
# The three predictions were frozen before any code was changed.
#
# ⚠ With everything set to 0, behaviour must be bit-identical to experiment 021 (regression check test_022_regression.py).
KNOWLEDGE_WEIGHT      = 12.0   # Bonus one piece of knowledge gives an action score (cf. LANDMARK_BONUS = 25)
KNOWLEDGE_GOAL_WEIGHT = 0.25   # Bonus to goal priority (cf. the +0.35 from flags)
KNOWLEDGE_FORGET      = 0.02   # Daily decay; performing the matching action refills it (use it or lose it)

# knowledge key → affected actions / goals. All four keys are written by landmark(); the
# mapping is the semantics that already exist, not something invented here.
KNOWLEDGE_ACTIONS = {
    "far_places": ("explore",),                  # there are places with more food far away
    "books":      ("read",),                     # books hold worlds I have not seen
    "shelter":    ("build", "gather_material"),  # without solid shelter, rain is dangerous
    "food":       ("gather_food",),              # the days when the food store runs out are hard
}
KNOWLEDGE_GOALS = {
    "far_places": "see_the_world",
    "books":      "learn",
    "shelter":    "improve_home",
    "food":       "stock_food",
}
# Discretionary goals — their knowledge bonus must pass the slack gate (rule 27), otherwise
# the ball runs off into the distance on an empty stomach. The first version missed this, and
# transplant-arm mortality went 4.0% → 39.3%.
DISCRETIONARY_GOALS = ("see_the_world", "learn")

# ---------------------------------------------------------------------------
# ★Rule 43★ Three candidate fixes for the sleep death spiral (all off by default = status quo, bit-identical)
# ---------------------------------------------------------------------------
# Diagnosis (mortality_diagnose.py): the dead have condition 0, hunger 74–87, and spend 53–56%
# of their last 10 days asleep, while 62–79% die pursuing stock_food — "it is not that it never
# thought of finding food, it is that it had no waking time". condition↓ → sleep efficiency↓
# (floor 0.35) → sleeps longer → gathers nothing → hungrier → condition↓ further.
# ---------------------------------------------------------------------------
# ★Rule 47★ Condition balance — the recovery channel is completely shut after a transplant, the system has no steady state
# ---------------------------------------------------------------------------
# Measured (§3f): after a transplant 90–98% of ticks sit in the "hunger 30–70" dead zone where
# nothing happens; the "hunger<30" share collapses to 0–2% and the +0.16 recovery channel almost
# never fires. After day 30 no ball has a positive balance; even the healthiest survivor is −0.12/day.
# ★From v3 on COND_RECOVER_AT defaults to 65.0★ The other three still default to off (= v2 behaviour).
# To reproduce v2: set COND_RECOVER_AT = 30.0, or just run v2_frozen/.
COND_DRAIN_AT        = 70.0  # Above this hunger the body starts being drained
COND_DRAIN           = 0.40  # How much is deducted per tick
COND_RECOVER_AT      = 65.0  # v3: condition-stability correction (v2 was 30.0)
                             # Raising it = cutting away the dead zone. Why 65: see the v3 note
                             # in the file header + log §3h rule 49 (sloth valley). ★Lowering is risky, raising is safe★
COND_RECOVER         = 0.16  # How much is restored per tick
COND_DEADZONE_RECOVER = 0.0  # Fix ②: slow recovery inside the dead zone too
COND_SHELTER_RECOVER = 0.0   # Fix ③: shelter also contributes to condition (× shelter/100)

HUNGER_CRISIS        = 70.0  # Above this hunger counts as "hanging by a thread", shared by A/B
SLEEP_SUPPRESS       = 0.0   # Variant A: suppress the intent to sleep during a crisis (1.0 = down to 0 at hunger 100)
HUNGER_URGENCY       = 0.0   # Variant B: raise the urgency of eat / gather_food during a crisis
SLEEP_EFF_FLOOR      = 0.35  # Variant C: floor on sleep efficiency (status quo 0.35; raising it slows the spiral)


def hunger_crisis(hunger):
    """0 → not hungry; 1 → starving. Crisis intensity shared by A/B."""
    if hunger <= HUNGER_CRISIS:
        return 0.0
    return min(1.0, (hunger - HUNGER_CRISIS) / (100.0 - HUNGER_CRISIS))
# ★Why stall-abandonment is needed★ A ball that has drifted to curiosity 100 / caution 18 will
# never gather material by temperament. But the refractory period pushes "fix the house" back to
# the top, producing **8 straight days of "wanting to fix the house" without picking up a single
# stick** — intent decoupled from behaviour, which makes the whole goal layer pointless. People
# are the same: "I have been meaning to fix the roof but never did" — that thought eventually dies on its own.
# ★Why a refractory period is needed★ Without it, "go and see distant places" would be raised again
# the very day it completes (because curiosity is still highest), and the ball would do only that
# for 27 days running, with the house forever at 0. In real life "having just finished something
# leaves you satisfied for a while" — that is what this is. Also, exploring lowers caution → wants
# to explore more → the positive feedback locks in. The refractory period is the brake on that lock-in.


# ============================================================
# Agent
# ============================================================

class Agent:
    """One individual. All it knows is: its own state, its own memory, and the world it is in."""

    def __init__(self, seed, world):
        self.rng = random.Random(seed)
        self.world = world

        # Source of difference #1: the initial random seed. Its job is to "break symmetry", not to create the difference itself
        self.traits = {t: 50.0 + self.rng.uniform(-INITIAL_TRAIT_SPREAD,
                                                  INITIAL_TRAIT_SPREAD)
                       for t in TRAITS}

        # State (not memory — just a database row, do not feed it to an LLM)
        self.hunger  = 30.0    # 100 = on the edge of starving to death
        self.energy  = 80.0
        self.shelter = 0.0
        self.inventory = {"food": 2.0, "material": 0.0}

        # ★Condition★ gives "failure" a grade lighter than death (experiment 006)
        self.condition = 100.0

        # ★Hardship accumulator★ a continuous quantity replacing a binary switch (experiment 013)
        self.hardship = 0.0
        self._hardship_anchor = None

        # ★Two personality floors★ (note ⑤) soft fades slowly, perm does not
        self.trait_floor = {t: 0.0 for t in TRAITS}       # soft floor (fades)
        self.trait_identity = {t: 0.0 for t in TRAITS}    # landmark identity

        self.flags = set()
        self.memories = []        # see remember()
        self.knowledge = {}       # semantic memory: general understanding of the world
        # ★022★ Each piece of knowledge has strength ∈ (0,1], living and dying with `knowledge`.
        # Stored separately rather than turning knowledge into (text, strength) so as not to break
        # the existing readers in context_packet / environment.py / persistence.py.
        self.knowledge_strength = {}

        # ★Intent★ the thing that persists across ticks. See the note above GOAL_ACTIONS.
        self.goal = None            # {type, priority, created_from, created_day, progress}
        self.goal_history = []      # goals completed/abandoned, used to tell "what it has been doing lately"
        self.goal_by_day = []       # what it pursued each day (demo material)
        self.goal_satiation = {}    # goal type → day it was last completed (refractory period)

        self.action_log = Counter()
        self.action_by_hour = [Counter() for _ in range(TICKS_PER_DAY)]
        self.alive = True

    # ---------- Memory ----------

    def remember(self, day, text, *, event=None, tags=(), importance=0.5,
                 emotional_weight=0.0, consequence=None, related_traits=()):
        """★Episodic memory★ one concrete event, with a timestamp.

        It used to be `flags: set` + `landmarks: [(day, text)]`. Good enough as a first version,
        but that structure has no "how important was this", "what did it lead to", "which trait
        is it tied to", so it supports neither retrieval nor being fed to an LLM.
        """
        self.memories.append({
            "event": event or (tags[0] if tags else "episode"),
            "day": day, "text": text, "tags": tuple(tags),
            "importance": importance, "emotional_weight": emotional_weight,
            "consequence": consequence, "related_traits": tuple(related_traits),
        })

    def learn(self, key, text):
        """★Semantic memory★ general understanding distilled from experience, without a timestamp.

            episodic: on day 12 there was a storm and the roof broke
            semantic: without solid shelter, rain is dangerous

        Why store them apart: episodic memory grows without bound and needs a forgetting
        mechanism; semantic memory caps out at a few dozen entries and is what behaviour should
        actually depend on.
        """
        self.knowledge[key] = text
        self.knowledge_strength[key] = 1.0      # ★022★ learned/refreshed → back to full

    def know(self, key):
        """★022★ How strong this piece of knowledge is right now. Never learned or already forgotten → 0."""
        return self.knowledge_strength.get(key, 0.0)

    def forget_knowledge(self):
        """★022★ Use it or lose it: decays daily, and the whole entry is dropped at 0.

        This step is the point of experiment 022: it turns "is irreversibility hardcoded?" from a
        binary accusation into **a measurable parameter** — you can sweep the forgetting rate and
        plot the curve, which also closes off the rebuttal "your knowledge never forgets, it is hardcoded".
        """
        if not KNOWLEDGE_FORGET:
            return
        for key in list(self.knowledge_strength):
            self.knowledge_strength[key] -= KNOWLEDGE_FORGET
            if self.knowledge_strength[key] <= 0.0:
                del self.knowledge_strength[key]
                self.knowledge.pop(key, None)

    def recall(self, tags=(), k=5, day=None, recent_days=7):
        """Retrieval by **structured tags**, not vector similarity.

        Why not vectors ([[Design points and risks]] §3.4): there is no query here, only a
        continuous state; semantic similarity would dredge up every hunger episode in history
        rather than the one that *mattered*. The most common failure mode of Generative Agents
        is retrieval error (Tom remembers "talk about the election at the party" but not that the party exists).

        Rule: tag hit + importance + recency — cheap, fast, deterministic, debuggable.
        """
        want = set(tags)
        scored = []
        for m in self.memories:
            s = m["importance"]
            if want & set(m["tags"]):
                s += 1.0
            if day is not None and day - m["day"] <= recent_days:
                s += 0.4
            s += abs(m["emotional_weight"]) * 0.3
            scored.append((s, m))
        scored.sort(key=lambda x: (-x[0], x[1]["day"]))
        return [m for _, m in scored[:k]]

    def context_packet(self, day):
        """★The bundle handed to the LLM★

        The LLM does not need to read every tick of 30 days, only:
            current state + current goal + relevant memories + world knowledge + personality
        Only then can it naturally answer "why have you been fixing the house lately":
            "The roof broke in the rain a few days ago, and I would rather not go through that again."

        Note that traits are **not** handed to the LLM to modify — personality is a number held
        by the code, and the LLM only puts it into words (§4).
        """
        goal_tags = ()
        if self.goal:
            goal_tags = (self.goal["type"], self.goal["created_from"])
        return {
            "state": {"hunger": round(self.hunger), "energy": round(self.energy),
                      "shelter": round(self.shelter),
                      "condition": round(self.condition),
                      "food": round(self.inventory["food"], 1)},
            "personality": {t: round(v) for t, v in self.traits.items()},
            "goal": None if not self.goal else {
                "type": self.goal["type"],
                "label": GOAL_LABEL[self.goal["type"]],
                "created_from": self.goal["created_from"],
                "days_on_it": day - self.goal["created_day"],
                "progress": round(self.goal["progress"], 2)},
            "memories": self.recall(goal_tags, k=5, day=day),
            "knowledge": dict(self.knowledge),
            "world": {"objects": sorted(self.world.objects),
                      "weather": self.world.weather},
        }

    @property
    def landmarks(self):
        """Backwards compatibility for old scripts: the (day, text) list of important memories"""
        return [(m["day"], m["text"]) for m in self.memories
                if m["importance"] >= 0.7]

    def mark(self, day, text, flag, floors, *, emotional_weight=0.8,
             consequence=None, knowledge=None):
        """A landmark experience: record it + leave a mark on personality (partly permanent)"""
        if flag in self.flags:
            return
        self.flags.add(flag)
        self.remember(day, text, tags=(flag,), importance=0.9,
                      emotional_weight=emotional_weight,
                      consequence=consequence,
                      related_traits=tuple(floors))
        if knowledge:
            self.learn(*knowledge)
        for t, boost in floors.items():
            base = self.traits[t]
            self.trait_floor[t] = max(self.trait_floor[t],
                                      min(base + boost, 90.0))
            # Only part of it becomes permanent identity — the rest will fade
            self.trait_identity[t] = max(
                self.trait_identity[t],
                min(base + boost * LANDMARK_PERMANENT, 90.0))

    def receive(self, what, amount, day, text=None):
        """Receive something from outside. The Agent does not know who gave it."""
        self.inventory[what] = self.inventory.get(what, 0.0) + amount
        if text:
            self.remember(day, text, tags=("gift", what), importance=0.35,
                          emotional_weight=0.3)

    @property
    def hardship_norm(self):
        """Saturation curve normalising the degree of suffering to 0→1. Continuous in the middle, which is the point."""
        return 1.0 - math.exp(-self.hardship / HARDSHIP_SCALE)

    # ---------- Goals ----------

    # Counting goals: progress must be measured from **the moment the goal was set**.
    # ⚠ The first version used the cumulative count directly, so see_the_world was already
    #   "complete" the moment it was raised — completed daily, re-raised daily, and re-raising
    #   refreshes created_day → permanently inside the GOAL_MIN_DAYS protection window → the
    #   ball is locked onto that goal and starves. Counting metrics must store a baseline; this
    #   is the same class of mistake as experiment 009.
    GOAL_COUNT_TARGET = {"learn": ("read", 12), "see_the_world": ("explore", 20)}

    def goal_progress(self, goal):
        gtype = goal["type"] if isinstance(goal, dict) else goal
        if gtype == "improve_home":
            return clamp(self.shelter / 80.0, 0.0, 1.0)
        if gtype == "stock_food":
            return clamp(self.inventory["food"] / 6.0, 0.0, 1.0)
        if gtype == "recover":
            return clamp(self.condition / 95.0, 0.0, 1.0)
        if gtype in self.GOAL_COUNT_TARGET:
            act, target = self.GOAL_COUNT_TARGET[gtype]
            base = goal.get("start", 0) if isinstance(goal, dict) else 0
            return clamp((self.action_log[act] - base) / target, 0.0, 1.0)
        return 0.0

    def _new_goal(self, gtype, pri, src, day):
        g = {"type": gtype, "priority": pri, "created_from": src,
             "created_day": day, "progress": 0.0}
        if gtype in self.GOAL_COUNT_TARGET:
            g["start"] = self.action_log[self.GOAL_COUNT_TARGET[gtype][0]]
        g["progress"] = self.goal_progress(g)
        return g

    def _slack(self):
        """★Slack (rule 27)★ Only with food to eat and a body that holds up can a discretionary ambition be raised."""
        return clamp(self.inventory["food"] / GOAL_SLACK_FOOD, 0.0, 1.0) \
            * clamp(self.condition / GOAL_SLACK_COND, 0.0, 1.0)

    def propose_goals(self, day):
        """Goals grow out of **state + memory + personality**, not a hardcoded priority table.

        `created_from` records "where this thought came from" — later the LLM will rely on it to
        answer "why have you been fixing the house lately".
        """
        c = (self.traits["caution"] - 50) / 100
        q = (self.traits["curiosity"] - 50) / 100
        out = []

        def add(gtype, pri, src):
            # ★022★ Semantic memory raises the priority of the matching goal. §5 of 019 already
            # showed the goal layer is a stronger carrier than the routine layer (1.79 vs 0.72);
            # wiring only score would most likely be wasted.
            #
            # ⚠ Correction (see "implementation correction 1" in the preregistration): the first
            #   version added the bonus straight onto pri, **bypassing the slack gate** — so
            #   "knowing there is food far away" turned into running off into the distance on an
            #   empty stomach, and transplant-arm mortality went 4.0% → 39.3%. This is exactly what
            #   rule 27 means by "inhibition must act on intent formation". The knowledge bonus for
            #   discretionary goals must be multiplied by slack.
            if KNOWLEDGE_GOAL_WEIGHT:
                for key, g in KNOWLEDGE_GOALS.items():
                    if g == gtype:
                        bonus = KNOWLEDGE_GOAL_WEIGHT * self.know(key)
                        if gtype in DISCRETIONARY_GOALS:
                            bonus *= self._slack()
                        pri += bonus
            out.append((gtype, pri - self._satiation(gtype, day), src))

        if self.shelter < 75:
            pri = (75 - self.shelter) / 75 * 0.8 + c
            src = "storm_memory" if "fears_storm" in self.flags else "shelter_low"
            if "fears_storm" in self.flags:
                pri += 0.35                      # a ball whose roof was torn off wants to fix the house more
            add("improve_home", pri, src)

        if self.inventory["food"] < 6:
            pri = (6 - self.inventory["food"]) / 6 * 0.7
            pri += self.hardship_norm * 0.6      # a ball that has gone hungry wants to hoard more
            src = "hunger_memory" if self.hardship_norm > 0.3 else "food_low"
            add("stock_food", pri, src)

        # ★A discretionary goal can only be raised once there is slack★
        # The damping inside goal_bonus acts "at execution time", which is too late: by the time
        # condition has fallen below 85 the deficit is already done. The real problem is **raising
        # the ambition "go and see distant places" while there is nothing to eat**.
        # Measured (90 days): the balls that died spent 46% of their time exploring and 2% gathering;
        # turning the goal layer off dropped mortality from 28.5% to 7.0% — it is this thought that kills them.
        slack = self._slack()

        if self.world.has("book"):
            add("learn", (0.35 + q * 1.2) * slack, "book_in_world")

        add("see_the_world", (0.30 + q * 1.4 - c * 0.8) * slack, "curiosity")

        if self.condition < 85:
            add("recover", (85 - self.condition) / 85 * 1.1, "body_weak")

        return out

    def _satiation(self, gtype, day):
        """Having just done something, you want it a little less for a while. The penalty decays linearly with time."""
        done = self.goal_satiation.get(gtype)
        if done is None:
            return 0.0
        left = max(0, GOAL_REFRACTORY - (day - done))
        return 0.9 * left / GOAL_REFRACTORY

    def update_goal(self, day):
        """Think once every morning: keep doing yesterday's thing, or not?"""
        cands = self.propose_goals(day)
        if not cands:
            return
        cands.sort(key=lambda x: -x[1])
        best_type, best_pri, best_src = cands[0]

        if self.goal is not None:
            prog = self.goal_progress(self.goal)
            # Making any progress? Any increase at all refreshes the timer
            if prog > self.goal.get("best_progress", -1.0) + 1e-9:
                self.goal["best_progress"] = prog
                self.goal["last_gain_day"] = day
            self.goal["progress"] = prog

            age = day - self.goal["created_day"]
            stalled = day - self.goal.get("last_gain_day", day)
            if prog >= 1.0:
                self._close_goal(day, "done")
            elif stalled >= GOAL_STALL_DAYS:
                self._close_goal(day, "stalled")
            elif age < GOAL_MIN_DAYS:
                return                            # still inside the minimum-commitment window
            elif best_type != self.goal["type"]:
                # ★Hysteresis★ a new goal must be clearly more urgent to win, otherwise carry on with the old one
                cur = next((p for t, p, _ in cands if t == self.goal["type"]), 0.0)
                if best_pri < cur + GOAL_SWITCH_MARGIN:
                    return
                self._close_goal(day, "switched")
            else:
                self.goal["priority"] = best_pri
                return

        self.goal = self._new_goal(best_type, best_pri, best_src, day)

    def _close_goal(self, day, why):
        g = dict(self.goal, closed_day=day, outcome=why)
        self.goal_history.append(g)
        if why == "done":
            self.goal_satiation[g["type"]] = day
            self.remember(day, f"finally managed to {GOAL_LABEL[g['type']]}",
                          tags=("goal", g["type"], "done"),
                          importance=0.7, emotional_weight=0.6,
                          consequence=g["type"])
        elif why == "stalled":
            # Abandonment also gets a cooldown, otherwise the same thought is raised again a second later
            self.goal_satiation[g["type"]] = day
            self.remember(day, f"wanted to {GOAL_LABEL[g['type']]}, but never got it done",
                          tags=("goal", g["type"], "stalled"),
                          importance=0.45, emotional_weight=-0.3,
                          consequence="gave_up")
        self.goal = None

    def goal_bonus(self, action):
        """★Intent only gets a say when there is slack★

        Rule (experiment 003): "personality needs slack to express itself". The same holds for
        intent, and more strongly: nobody about to starve is still thinking about "going to see
        distant places". Without this damping term, goals override survival needs and starve the
        ball — which is exactly how the first version died.
        """
        if self.goal is None:
            return 0.0
        urgency = max((self.hunger - 60) / 40.0, (85 - self.condition) / 85.0, 0.0)
        damp = clamp(1.0 - urgency, 0.0, 1.0)
        pri = clamp(self.goal["priority"], 0.0, 1.5)
        w = GOAL_ACTIONS.get(self.goal["type"], {}).get(action, 0.0)
        if w:
            return w * GOAL_BONUS * pri * damp
        if action in DISCRETIONARY:
            return -GOAL_OFF_TASK * pri * damp      # the price of distraction
        return 0.0

    # ---------- Scoring ----------

    def legal(self, action):
        need = ACTION_REQUIRES_OBJECT.get(action)
        return need is None or self.world.has(need)

    def score(self, action, day):
        if not self.legal(action):
            return None
        s = 0.0

        # 1. Urgency of need
        if action == "eat":
            if self.inventory["food"] < 1:
                return None
            s += self.hunger * 1.0
            s += HUNGER_URGENCY * hunger_crisis(self.hunger)        # variant B
        elif action == "sleep":
            s += (100 - self.energy) * 0.9
            s += 10 if self.shelter > 30 else -5
            if self.world.has("music"):
                s += 4                       # music makes it easier to settle down
            # ★Variant A (rule 43)★ Sleeping while about to starve — the suppression acts on intent
            # formation, structurally the same as the slack gate of rule 27.
            if SLEEP_SUPPRESS:
                s *= max(0.0, 1.0 - SLEEP_SUPPRESS * hunger_crisis(self.hunger))
        elif action == "gather_food":
            # Urgent only when genuinely hungry (experiment 003: that constant +12 was the culprit behind convergence)
            s += max(0.0, self.hunger - 35) * 0.85
            s += HUNGER_URGENCY * hunger_crisis(self.hunger)        # variant B
            if self.inventory["food"] <= 1:
                s += 20
            if self.world.food < 1:
                return None                  # gathered out nearby
        elif action == "gather_material":
            s += (100 - self.shelter) * 0.30
        elif action == "build":
            if self.inventory["material"] < 3:
                return None
            s += (100 - self.shelter) * 0.55
        elif action == "explore":
            s += 18
        elif action == "read":
            s += 12

        # 2. Personality match ★the differentiation engine is here★
        for trait, w in ACTION_TRAIT_MATCH[action].items():
            s += (self.traits[trait] - 50) / 50 * w * PERSONALITY_WEIGHT

        # 3. Influence of landmark experiences
        if action == "gather_food":
            s += LANDMARK_BONUS * self.hardship_norm     # the more it has suffered, the more it fears hunger
        if "fears_storm" in self.flags and action in ("build", "gather_material"):
            s += LANDMARK_BONUS
        if "loves_exploring" in self.flags and action == "explore":
            s += LANDMARK_BONUS

        # 3b. ★Semantic memory★ (experiment 022), structurally parallel to the flags branch above.
        # Difference: flags are permanent 0/1 marks, knowledge carries strength and can be forgotten.
        if KNOWLEDGE_WEIGHT:
            for key, acts in KNOWLEDGE_ACTIONS.items():
                if action in acts:
                    bonus = KNOWLEDGE_WEIGHT * self.know(key)
                    if action in DISCRETIONARY:      # rule 27, same as propose_goals
                        bonus *= self._slack()
                    s += bonus

        # 4. ★Current intent★ this term is what makes behaviour coherent across ticks
        s += self.goal_bonus(action)

        # 5. Cost and risk
        if action in ("gather_food", "gather_material", "explore", "build"):
            s -= (100 - self.energy) * 0.35
        if action == "explore":
            s -= 8

        return s

    # ---------- Execution ----------

    def act(self, action, day, hour=0):
        self.action_log[action] += 1
        self.action_by_hour[hour][action] += 1

        # ★022★ Use it or lose it: doing the matching thing refreshes this knowledge (only refills existing entries, never creates)
        if KNOWLEDGE_FORGET:
            for key, acts in KNOWLEDGE_ACTIONS.items():
                if action in acts and key in self.knowledge_strength:
                    self.knowledge_strength[key] = 1.0

        if action == "eat":
            self.inventory["food"] -= 1
            self.hunger = clamp(self.hunger - FOOD_NUTRITION)
            self.energy = clamp(self.energy + 5)
        elif action == "sleep":
            # Poor condition → no amount of sleep restores it → fewer things can be done → behaviour is shaped
            # Variant C: raising the floor slows the spiral (status quo 0.35)
            eff = SLEEP_EFF_FLOOR + (1.0 - SLEEP_EFF_FLOOR) * self.condition / 100
            if self.world.has("music"):
                eff *= 1.10
            self.energy = clamp(self.energy + 14 * eff)
        elif action == "gather_food":
            self.inventory["food"] += self.world.take_food(self.rng)
            self.energy = clamp(self.energy - 6)
        elif action == "gather_material":
            self.inventory["material"] += self.world.p["material_yield"]
            self.energy = clamp(self.energy - 6)
        elif action == "build":
            self.inventory["material"] -= 3
            self.shelter = clamp(self.shelter + 22)
            self.energy = clamp(self.energy - 10)
        elif action == "explore":
            self.energy = clamp(self.energy - 9)
            if self.rng.random() < EXPLORE_FOOD_CHANCE:
                self.inventory["food"] += EXPLORE_FOOD_YIELD
                if "loves_exploring" not in self.flags and self.rng.random() < 0.30:
                    self.mark(day, "found a food-rich place far away",
                              "loves_exploring", {"curiosity": 10},
                              consequence="food_found",
                              knowledge=("far_places", "there are places with more food far away"))
        elif action == "read":
            self.energy = clamp(self.energy - 3)
            if "reads" not in self.flags and self.rng.random() < 0.25:
                self.mark(day, "read some things I did not know before", "reads",
                          {"curiosity": 8}, emotional_weight=0.5,
                          knowledge=("books", "books hold worlds I have not seen"))

        # Positive feedback: what you do → what you become (but never below the floor left by a landmark)
        # ★Diminishing returns★ the more extreme, the harder to grow further. Without this term,
        # explore's `caution -0.10` would push caution all the way to 8 and curiosity to 100, and
        # the ball would only ever run around outside (measured: balls that died by day 60 spent
        # 47.7% of their time in explore and only 1.9% gathering food). v1 was protected by the
        # permanent floor; v2's floor fades, so that brake is gone and must be replaced.
        for trait, delta in ACTION_TRAIT_FEEDBACK[action].items():
            extremity = abs(self.traits[trait] - 50.0) / 50.0
            pull = max(0.12, 1.0 - extremity * TRAIT_SATURATION)
            v = self.traits[trait] + delta * TRAIT_DRIFT * pull
            self.traits[trait] = clamp(v, self.trait_floor[trait], 100.0)

    # ---------- Once a day: the slow fading of personality ----------

    def daily(self, day):
        """★Forms fast, fades slow★ the soft floor retreats, but never below the landmark identity"""
        for t in TRAITS:
            self.trait_floor[t] = max(self.trait_identity[t],
                                      self.trait_floor[t] - FLOOR_DECAY_PER_DAY)
        # On days of a full stomach and a warm roof, the memory of suffering also fades
        if self.condition >= 99.5 and self.hardship > 0:
            self.hardship = max(0.0, self.hardship - HARDSHIP_FORGET)
        self.forget_knowledge()      # ★022★ semantic memory fades too

    # ---------- One tick ----------

    def tick(self, day, tick_of_day):
        if not self.alive:
            return

        # Think once every morning about what to do. Here rather than every tick, precisely for
        # continuity: within a day it will not change its mind over a single tick's score jitter.
        if tick_of_day == 0:
            self.update_goal(day)
            self.goal_by_day.append(self.goal["type"] if self.goal else None)

        self.hunger  = clamp(self.hunger + HUNGER_RATE)
        self.energy  = clamp(self.energy - 1.2)
        self.shelter = clamp(self.shelter - 0.35)      # the house ages

        # What happens in the world lands on the individual
        if self.world.weather == "storm":
            dmg = self.world.storm_damage
            self.shelter = clamp(self.shelter - dmg)
            if dmg > 28:
                self.mark(day, "a storm tore the roof off", "fears_storm",
                          {"caution": 10}, emotional_weight=0.82,
                          consequence="shelter_damage",
                          knowledge=("shelter", "without solid shelter, rain is dangerous"))

        # ★Condition★ chronically underfed → the body is drained; only once fed does it slowly recover
        # Rule 47: in v2, after a transplant the "hunger<30" share collapses to 0–2%, the recovery
        # channel almost never fires, and the system spends 90–98% of its time being drained in the
        # dead zone — structurally no steady state. v3 raises COND_RECOVER_AT to 65 (across the sloth
        # valley of rule 49), narrowing the dead zone to 5 points.
        if self.hunger > COND_DRAIN_AT:
            self.condition = clamp(self.condition - COND_DRAIN)
        else:
            gain = COND_RECOVER if self.hunger < COND_RECOVER_AT \
                else COND_DEADZONE_RECOVER               # fix ① raise threshold / ② fill the dead zone
            gain += COND_SHELTER_RECOVER * (self.shelter / 100.0)   # fix ③
            if gain:
                self.condition = clamp(self.condition + gain)

        # ★Suffering → personality★ continuous transmission
        deficit = (100.0 - self.condition) / 100.0
        if deficit > 0:
            self.hardship += deficit / TICKS_PER_DAY
            if self._hardship_anchor is None:
                self._hardship_anchor = dict(self.traits)

        if self._hardship_anchor is not None:
            boost = HARDSHIP_MAX_BOOST * self.hardship_norm
            for t, w in HARDSHIP_FLOOR_WEIGHT.items():
                self.trait_floor[t] = max(
                    self.trait_floor[t],
                    min(self._hardship_anchor[t] + w * boost, 90.0))
            if (self.hardship_norm >= HARDSHIP_STORY_AT
                    and "fears_hunger" not in self.flags):
                self.mark(day, "got through a stretch of never having enough to eat", "fears_hunger", {},
                          emotional_weight=0.9, consequence="condition_loss",
                          knowledge=("food", "the days when the food store runs out are hard"))

        if self.condition <= 0:
            self.alive = False
            return

        scored = [(self.score(a, day), a) for a in ACTIONS]
        scored = [(s, a) for s, a in scored if s is not None]
        self.act(max(scored)[1], day, tick_of_day)

    # ---------- Readable labels ----------

    def dominant_style(self):
        """Translate the personality vector into a readable label — the difference must be visible

        ⚠ This reads the personality **numbers**. The ablation experiment (014) proved the numbers
          can decouple from behaviour, and what the user sees is behaviour — for the main result see behavior.py.
        """
        c, q, i = (self.traits[t] for t in TRAITS)
        if q > 58 and c < 48:  return "adventurer"
        if c > 58 and q < 48:  return "nest-builder"
        dev = {"cautious": c - 50.0, "curious": q - 50.0, "workhorse": i - 50.0}
        top = max(dev, key=dev.get)
        return top if dev[top] >= 8.0 else "unremarkable"


# ============================================================
# Life — ties world, individual and interventions together and runs them
# ============================================================

class Life:
    """One complete life process.

    ★ Interventions (influences) hang off this, not off the Agent. ★
    The Agent does not know someone is caring for it, only that "there are two more portions of food in the world today".
    """

    def __init__(self, seed, world=None, influences=(), world_seed=None):
        # World and individual are two independent random streams:
        # only that makes the "same seed, same initial personality, only the world changes" experiment possible
        self.world = world if world is not None else World(
            seed if world_seed is None else world_seed)
        self.agent = Agent(seed, self.world)
        self.influences = list(influences)
        self.inf_rng = random.Random(seed ^ 0x5EED)

    def run(self, days=None):
        days = SIM_DAYS if days is None else days
        for day in range(days):
            for t in range(TICKS_PER_DAY):
                self.world.tick(day, t)
                for inf in self.influences:
                    inf(self.world, self.agent, day, t, self.inf_rng)
                self.agent.tick(day, t)
                if not self.agent.alive:
                    return self.agent
            self.agent.daily(day)
        return self.agent


if __name__ == "__main__":
    print(__doc__)
    print("This is the core model; it defines no experiments of its own.")
    print("To run experiments use:  python scenarios.py   /   python paired.py   etc.")
