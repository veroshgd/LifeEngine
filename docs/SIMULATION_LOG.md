# Simulation experiment log

> The experiment log of a pure-code simulator. The code lives in `C:\Users\yinan\Desktop\ai-sandbox\`
> Related: [[Design points and risks]] · [[Vida artificial]]
> Date: 2026-08-06

---

## Experiment 001 — initial parameters: **convergence**

```
PERSONALITY_WEIGHT=8  TRAIT_DRIFT=0.55  HUNGER_RATE=2.2
999 balls × 30 days
```

| Metric | Result | Verdict |
|---|---|---|
| personality gap between user types | **1.1 points** | ❌ essentially zero |
| caution distribution | unimodal, concentrated in 55–80 | ❌ |
| σ | 11.3 | ❌ too small |
| mortality | 0% | ✓ |
| personality types | 559/999 are all "workhorses" | ❌ |

**Conclusion: the core selling point does not hold.** Three completely different users raise balls that are almost identical.

---

## Experiment 002 — parameter sweep: **not a tuning problem**

Swept 24 parameter sets (PW ∈ {8,18,30,45} × drift ∈ {0.55,1.2} × hunger ∈ {2.2,1.2,0.7}).

**Not one set satisfies** spread>8 + peaks≥3 + death<10% simultaneously.

The key observation: the only combination that pushes spread to 10+ (PW=45, drift=1.2) has a mortality of **38%–62%**.

> In other words: to give the balls a personality, you have to let them starve to death.
> **This is a structural problem, not a parameter problem.**

---

## Experiment 003 — a structural fix: one line of code

### Diagnosis

The original food-gathering score:

```python
s += self.hunger * 0.55 + 12      # ← that constant +12 is the culprit
```

That `+12` means **it wants to gather whether it is hungry or not**. The consequence:

```
the user feeds it → hunger falls → but the ball keeps gathering → the time saved is eaten by gathering again
        → the user's actions leave no trace at all → convergence
```

### The fix

```python
s += max(0.0, self.hunger - 35) * 0.85
if self.inventory["food"] <= 1:
    s += 20                        # anxiety only once the food store runs out
```

### Result

| Metric | Before | After |
|---|---|---|
| usable parameter sets | **0 / 24** | **6 / 24** |
| best spread | 13.1 (but mortality 55%) | 10.4 (mortality 0.3%) |
| σ | 11.3 | 36.2 |
| distribution shape | unimodal | **bimodal** |

---

## ★ The design rule obtained

This rule deserves a place in the formal design document:

> ### Personality needs slack in order to express itself
>
> If survival pressure permanently fills the action budget, every individual's behaviour is driven by need,
> and no amount of personality weight can squeeze into the decision → convergence is inevitable.
>
> **Corollary: the user's actions must change **what choices the ball has**, not merely change its numbers.**
>
> Feeding that only fills a number which climbs back by itself is the same as nothing happening.
> Feeding must free up time, and that time must flow into personality-determined behaviour (exploring / building)
> before differentiation can occur.

This rule holds for **any** need-driven agent, not just this project.

---

## Current configuration (already written into sim.py)

```python
PERSONALITY_WEIGHT = 30.0   # 45 also works, but sits far too close to the mortality cliff
TRAIT_DRIFT        = 1.20
LANDMARK_BONUS     = 25.0
HUNGER_RATE        = 2.2
```

The result of 999 balls × 30 days:

```
mortality 0%        σ = 36.2        bimodal distribution

adventurer  362  ▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇
nest-builder 356  ▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇
workhorse   234  ▇▇▇▇▇▇▇▇▇▇
cautious     47  ▇▇
```

---

## ⚠ Two problems still unsolved

### 1. The user's influence is still too weak

```
overall difference between balls        σ = 36.2
difference caused by user type          6.0 points
```

**Differentiation does hold, but it comes mainly from the internal positive feedback loop (difference source #4)
and the initial seed (#1), not from the user (#3).**

Whether a ball ends up an adventurer or a nest-builder is currently decided mainly by the random seed, not by the user.

That is a problem for the product — the user cannot feel "I raised it", so no emotional bond forms.

**Directions to try next:**
- let the user's actions directly trigger irreversible events (a ratchet) rather than merely changing numbers
- widen the gap between feeding intervals (currently 1 / 3 / 8 days, which may not be extreme enough)
- add more inputs that **only the user can provide** (conversation, giving specific objects, taking it somewhere)

### 2. The "nearly starved to death" ratchet has never fired (0%)

The balls are far too good at finding food themselves and never get hungrier than 92.

This irreversible event was meant to be the best story material ("my ball nearly starved, and hoarded food ever after"),
but it is currently dead code. Balls under a hands-off user need to face a genuine crisis.

---

---

# Round two: solving the "user influence" problem

The starting point: **a storm is an act of god, the user cannot prevent it, so it is useless for attribution.**
Hunger is the opposite — it is the one channel the user actually operates (feeding), which makes it the best carrier for attribution.

So why did it not work before? The numbers make it obvious:

```
hunger rises per day   2.2 × 24 = 52.8
one portion of food removes        55
```

**One gather = a whole day's ration. The ball is fully self-sufficient → whatever the user gives is redundant.**

> ### The user's influence exists only in the part the ball cannot solve by itself
> If the ball can feed itself, the user is an ornament.

---

## Experiment 004 — manufacturing a deficit: spread 6 → 37, but 26% died

Changes: food nutrition 55 → 20, and local food is finite and regrows slowly (2.0/day against a demand of 2.64/day).

| | Result |
|---|---|
| spread | **6.0 → 37.3** |
| doting | caution 62 / curiosity 65, house integrity 98 |
| hands-off | caution 25 / curiosity 95, house integrity 0 |
| mortality | **26.1%** ❌ |

The doted-on ball becomes a stay-at-home architect and the hands-off ball a wandering adventurer — **because it has to go out to find food**.
The story is beautiful, but 66% of the hands-off balls died.

## Experiment 005 — sweeping the food supply: it is a cliff, not a slope

```
regen 2.0 → spread 34.7   hands-off mortality 66%
regen 2.2 → spread 11.2   hands-off mortality 45%
regen 2.4 → spread  6.2   hands-off mortality  5%    ← once life is comfortable there is no difference
```

**Survival and differentiation have become the same variable**: the balls can only show a difference by nearly dying.

## Experiment 006 — adding a "condition" layer: giving failure a grade milder than death

Hunger used to have only two states: **fine** or **dead**. There was no chronic state in between,
and personality is formed precisely in that middle stretch.

Added `condition`: chronically underfed → condition falls → sleep recovery efficiency drops → fewer things become possible.
Death is redefined as "condition reaching zero" rather than "one missed meal kills".

Result: mortality fell (hands-off 45% → 17%), but spread also fell back to around 6.

## Experiment 007 — adding seasons: turning the cliff into a slope

Diagnosis: local regrowth and user feeding are **both flat rates**; added together they are either enough or not enough, with no middle state.

> **What produces a gradient is fluctuation, not the mean.**
> The user's food is not filling a constant deficit; it is **helping the ball through the lean season**.
> That is also closer to what a carer really does.

After adding a 12-day cycle of plenty and lean (amplitude 0.55): hands-off mortality 33% → 6.7%,
and the ratchet trigger rate rose to 11%. But spread is still 6.6.

## Experiment 008 — a one-way valve for personality

Diagnosis: **personality drifts back.** Forced to explore in the lean season → curiosity spikes → the season of plenty arrives and it drifts back to the middle.
Irreversible events only gave a bonus to behaviour and left no trace on **personality**.

Added `trait_floor`: a landmark experience raises the floor of some trait, which can never fall back below it again.

```python
def mark(self, day, text, flag, floors):
    self.flags.add(flag)
    self.landmarks.append((day, text))
    for t, boost in floors.items():
        self.trait_floor[t] = max(self.trait_floor[t],
                                  min(self.traits[t] + boost, 90.0))
```

What makes formative experience formative is precisely that it is irreversible.

---

## ⚠ Experiment 009 — a methodological correction: I have been tuning against noise

The sweep said spread=9.4 at regen=2.2 (450 balls), but 999 balls gave only 4.7.
That gap looked wrong, so a **permutation test** was run (shuffle the user-type labels 400 times and see what pure chance produces).

```
observed spread          :  4.66
null median (pure noise)  :  3.10
null 95th percentile      :  6.41
p value                  :  0.188   ← not significant
```

**The spread metric takes the maximum over 9 combinations of 3 user types × 3 dimensions,
and taking a maximum inflates noise by itself.** The "✓" threshold I had set at 5 points was below the noise floor.

> Conclusion: every spread of 6–9 in experiments 006–008 was **an illusion**.
> The only real signal is the 37.3 of experiment 004, and that configuration kills 26% of the balls.
>
> **Lesson: any metric that takes a maximum must have its noise floor measured first.**

## Experiment 010 — locating it: the mechanism is right, the transmission is too weak

The key diagnosis (`diagnose.py`):

```
              hunger-scarred  storm-fearing  exploration-loving  industry  condition
doting              0.0%          37.8%            35.4%           66.3      100.0
balanced            2.7%          33.9%            38.1%           66.4       97.9
hands-off          25.6%          42.0%            35.9%           71.0       79.3
```

- **"hunger-scarred" 0% / 2.7% / 25.6%** — perfect separation, the mechanism is entirely correct
- **"storm-fearing" is almost identical across the three rows** — the control arm, unrelated to the user as expected ✓ (which in turn validates the design logic)
- **"condition" 100 / 97.9 / 79.3** — strong separation

**The user's actions really do produce a clear, measurable difference — it just shows up in "state" and "events"
and never reaches "personality".** Because only 25.6% of hands-off balls fired the ratchet, the other 74% are
indistinguishable from the doted-on ones and the group mean is diluted away.

## Experiment 011 — strengthening the transmission: ✓ passes

Raised the condition threshold from 55 to 72 (so more balls fire it) and the ratchet floor from +10 to +22.

```
              hunger-scarred   industry
doting              0.0%          66.3
balanced            4.8%          67.1
hands-off          36.2%          75.3

permutation test:  spread = 8.96   p = 0.000   ✓ significant
          industry diff/SE = 7.2
mortality:    total 2.1%   doting 0%   balanced 0%   hands-off 6.3%
```

**For the first time both are satisfied at once: statistically significant user attribution + acceptable mortality.**

---

## Current configuration

```python
PERSONALITY_WEIGHT = 30.0
TRAIT_DRIFT        = 1.20
LANDMARK_BONUS     = 25.0
HUNGER_RATE        = 2.2
FOOD_NUTRITION     = 20.0    # one gather ≠ one day's ration
LOCAL_FOOD_REGEN   = 2.2     # demand is 2.64, a natural deficit
SEASON_DAYS        = 12      # the lean season is what the user is for
SEASON_AMPLITUDE   = 0.55
condition threshold = 72     # the trigger rate must be high enough or the group mean is diluted
```

---

## ★ The four design rules from this round

1. **The user's influence = the part the ball cannot solve by itself.**
   With a self-sufficient pet, the user is an ornament.

2. **Acts of god are useless for attribution.** Nobody can stop a storm, so the user feels no responsibility for it.
   Attribution must hang on a channel the user operates (feeding).

3. **Give failure a grade milder than death.** With only "fine / dead",
   survival and differentiation are the same variable, and tuning is necessarily zero-sum between them.

4. **What produces a gradient is fluctuation, not the mean.**
   A flat supply only produces a cliff. The user's value is helping through the lean season, not filling a constant deficit.

Plus one methodological rule:

5. **Any metric that takes a maximum must have its noise floor measured first.**
   Otherwise you spend hours tuning parameters against random numbers (as I did).

---

## ⚠ Still unsolved

**The effect size is small.** Industry differs by 9 points with σ≈19, an effect size ≈ 0.47 SD.
Statistically real, but **a user comparing two balls side by side may not see it**.

An investor demo needs a difference visible within 30 seconds, and we are not there yet.

There is a more practical finding, though: **attribution does not have to run through personality.**

| Carrier | Current state | Can the user perceive it immediately |
|---|---|---|
| state (condition 100 vs 79) | ✓ already strong | **immediately, visibly** |
| events (0% vs 36% went hungry) | ✓ already strong | **there is a story to tell** |
| personality (industry 66 vs 75) | weak | needs long observation |

"Your ball looks thin" is **immediately perceivable** attribution, far more direct than a personality number.
Perhaps the first demo should lead with the first two carriers and keep personality as a long-term reward.

---

---

---

# Round three: from "group means" to "pairing"

> Date: 2026-08-09

The last round ended on "the effect size is small". This round first explored everything outside the 30-day
configuration, found problems far worse than "small", and then changed the measurement method.

## ⚠ Stocktake: four blind spots in the experiment 011 configuration

### 1. The user explains only 4% of the variance

`spread=8.96, p=0.000` is real, but the variance explained (eta²) is:

```
industry    3.82%
caution     0.24%
curiosity   0.07%
```

**96% of the personality difference comes from the random seed and random world events.**
At a sample size of 999 balls, even a 4% effect can produce p=0.000.
**A large sample makes a tiny effect "statistically significant", but the product experience has nothing to do with a p value.**

### 2. 30 days is a time window; the configuration collapses at 60 days

```
 days   mortality   gap   gap/SE   σ(caution)  caution pinned at 100   hands-off hunger-scarred
   15    0.0%    6.41     7.3      21.2         0.0%          21.3%
   30    2.1%    8.96     7.2      33.9        15.8%          36.2%
   60   15.8%    9.31     5.1      42.2        57.3%          27.3%
   90   20.7%   23.67    14.4      41.5        54.9%          29.7%
```

- mortality is already 15.8% at 60 days, violating the <10% I set myself
- 57% of balls have caution pinned at 100 → that dimension can no longer differentiate (the clamp destroys information)
- the trigger rate falls at 60 days = **survivorship bias**; the balls that would have fired it died
- gap=23.67 at 90 days is not stronger differentiation, it is the weak being eliminated

### 3. The current configuration is a peak, not a plateau

Perturbing `LOCAL_FOOD_REGEN` by ±0.15 (±7%):

```
 regen   total dead   hands-off dead   hands-off scarred   gap   gap/SE
  1.90   15.2%     42.0%      38.9%     3.33     2.0
  2.05    8.6%     25.5%      41.9%     6.99     4.8
  2.20      2.1%           6.3%             36.2%          8.96     7.2   ← the current configuration
  2.35    0.2%      0.6%      17.2%     6.60     5.8
  2.50    0.0%      0.0%      10.8%     5.76     5.2
```

The peak of the gap sits exactly where mortality starts to become non-negligible.

> **Rule four (fluctuation produces a gradient) eased the cliff of experiment 005, but did not remove it.**
> Survival and differentiation are still coupled, only more loosely. A configuration sitting on a peak is most likely overfitted to the seed.

### 4. The daily routines of balls raised by the three users almost coincide

```
              eat     sleep   gather_food  gather_material   build   explore
doting        11.7%    52.4%       3.3%          11.5%         3.4%    17.7%
balanced      11.5%    50.1%       6.8%           9.8%         2.9%    19.0%
hands-off     11.2%    48.7%       7.8%          11.2%         3.3%    17.8%
```

- the three rows essentially coincide, and the one that does differ, gather_food, is exactly the behaviour the user cannot see
- **the ball spends half its life asleep**; eat+sleep account for 62%
- **building is only 3.3%**, while "builds its own home" is the headline selling point

(The sampled comparison in `sim.py` looks very different because `next()` grabs the first ball, not a representative one.)

### Root cause: all attribution rests on one binary switch

```
feeding frequency → condition → crossing the line at 72 → fears_hunger → industry jumps to the floor at 90
```

Splitting each group by whether it fired makes it obvious:

```
             CON flag    SIN flag    trigger rate
doting          —          66.34       0.0%
hands-off     95.06        64.08      36.2%

Among balls that did not fire the ratchet, spread is only 2.26   ← noise level
```

**Those 9 points come entirely from 36% of balls jumping from 64 to 95.** That is not personality growing, it is a switch.
So "spread 8.96" and "hunger-scarred 36.2%" are the same thing measured twice.

| Phenomenon | Because |
|---|---|
| bimodality within a group (a cluster at 64 and one at 95) | the switch has only on/off |
| only industry carries a signal | this chain is wired only to industry |
| extreme sensitivity to regen ±0.15 | the trigger rate depends on the tail of the distribution |

### ⚠ Tooling: the lesson of experiment 009 was never applied retroactively

`sweep.py` / `food_sweep.py` still use `spread > 8`, but the noise floor is tied to the population size:

```
pop=300 (sweep.py)       noise 95th percentile = 10.48   ← the threshold is below the noise
pop=450 (food_sweep.py)  noise 95th percentile =  9.18   ← the threshold is below the noise
pop=999 (sim.py)         noise 95th percentile =  6.47      ok
```

**Those two scripts currently award ★ to pure noise.** The same mistake replaying at a smaller scale.

---

## Experiment 012 — changing the measurement method: the paired experiment (`paired.py`)

### Starting point

`significance.py` asks "do the means of the three groups of balls differ much".
But the question in the user's mind is **"if someone else had raised it, would it be different?"**

A group comparison cannot answer that, because the balls in each group carry different seeds,
and the difference caused by the seed (σ≈34) is far larger than the difference caused by the user, so the signal drowns.

**The method: run the same seed twice, changing only the user.** Identical initial personality → the largest noise source is cancelled.

Sensitivity: paired gives 11.6× the standard error against grouped 7.2×. And it asks exactly the question the product has to answer.

Limitation (already in the docstring): the same seed only guarantees the same **initial state**,
and once the actions diverge the rng streams fall out of step. Pairing cancels seed noise, not world-luck noise.
So the null-hypothesis test uses **sign permutation** (flipping the signs of the differences 2000 times) —
following the lesson of experiment 009, a new method also needs its noise floor measured first.

### Results (400 seeds × 30 days, doting → hands-off, 374 valid pairs)

```
  carrier          mean diff   median     dz   share increased   |d|≥5       p
  caution           +1.53     +0.00   +0.13     48.9%    24.1%   0.009
  curiosity          -0.58     +0.00   -0.08        0.8%          2.1%   0.076  ← noise
  industry          +9.03     +1.34   +0.60     68.7%    47.6%   0.000
  condition        -20.66     +0.00   -0.71      0.8%    41.2%   0.000
  shelter           +9.74     +0.00   +0.42     40.4%    34.8%   0.000
```

The control arm's self-check passes: "storm-fearing" fires for hands-off only in 57 pairs and for doting only in 47, roughly balanced ✓
("hunger-scarred" is 137 pairs to 0.)

### Finding 1 ★ The median of every carrier is 0

```
condition:  p10 = -67.8    median = 0    p90 = 0
industry:   median = +1.34               p90 = +32.8
shelter:    median = 0                   p90 = +43.4
```

**For the median ball, changing the user changed nothing.** 30.2% of pairs show no change on **any** carrier.

> ### An effect with a median of 0 is the same as no effect
> The problem is not "the effect is small" but **"the effect is zero for most balls and drastic for a few"**.
> The mean writes those two situations as the same number. Any paired metric must be read alongside its median.

### Finding 2 State is the strongest carrier, not personality

`condition` has dz = −0.71, stronger than industry's +0.60,
and its directional consistency is **99.2%** (industry only 68.7%).

The guess at the end of the last round (that state and events are more direct than personality) now has numbers behind it,
and **state is the only carrier whose direction almost never reverses**.

### Finding 3 ⚠ The direction of shelter is inverted: hands-off balls have better houses

```
population:  doting 48.5   balanced 48.1   hands-off 56.6 (median 80.4)

hands-off WITH the hunger-scarred flag (n=113):  shelter 96.0   industry 95.1
hands-off WITHOUT it              (n=199):  shelter 34.2   industry 64.1
```

The cause is that the ratchet pours +22 into industry, and industry scores `gather_material` and `build`.

**The narrative has become: "I neglected it, so it fixed its house up better."**

The beautiful story of experiment 004 (doting→stay-at-home architect, shelter 98 / hands-off→wandering adventurer, shelter 0)
has not weakened in the current configuration, it has **inverted**. The paired curiosity difference of −0.58 confirms this.

### Finding 4 The dose response is a step, not a slope

```
                    industry   condition
doting→balanced          +3.15       -1.84
balanced→hands-off       +6.37      -19.58
```

**Feeding once every three days and feeding once a day raise almost the same ball.**
The only user who raises a different ball is the one who is about to churn.

---

## ★ New design rules from this round

6. **An effect with a median of 0 is the same as no effect.** The mean writes "a few balls changed drastically" as "every ball changed a little".

7. **To measure "what if someone else raised it", you have to actually change the person and run it again.**
   In a group comparison, seed noise always buries the user signal. Pairing cancels it.

8. **Priority of attribution carriers: state > events > personality.**
   `condition` has 99.2% directional consistency, personality only 68.7%. The demo should lead with state.

9. **A new metric means measuring the noise floor again.** (A corollary of rule 5 — this time the sign permutation was done from the start.)

---

## Baseline (as of experiment 012; the latest numbers are in experiment 013)

```
industry effect size dz   +0.600    target > 0.8
pairs with no change       30.2%    target < 20%
personality-label flip     12.8%    target > 50%
hands-off mortality         6.5%    target < 10%
```

(The third row depends on `dominant_style()`, whose criterion ordering is wrong: caution=100 gets labelled a workhorse.
The most common transition, "cautious→workhorse" with 24 cases, is largely a product of that bug.)

---

## Next steps

No more parameter tuning — there is no room on a peak. In this order:

1. ✅ Turn the paired experiment into a standard measurement script (`paired.py`)
2. ✅ Make the binary switch continuous → see experiment 013 (**conclusion: this is not the bottleneck**)
3. Open a second and third channel for the user, so that all attribution does not rest on feeding
4. Deal with the ceiling in time (personality topping out, 60-day mortality)

---

## Experiment 013 — the hypothesis is falsified: the bottleneck is not the switch but a leak upstream

### First attempt: making the ratchet continuous (failed)

Done as planned: add a `hardship` accumulator (condition deficit × duration),
raise `trait_floor` continuously along a saturating curve, anchored to "the personality at the moment the crisis began"
(anchoring to the current personality runs away — the floor rises along with the personality). No threshold anywhere.
`fears_hunger` is kept only as a narrative marker.

```
                    experiment 011   after going continuous
industry median          +1.34            +0.96
industry dz             +0.600           +0.524     ← it went down instead
pairs with no change      30.2%            29.9%
```

**Nothing moved.**

> If smoothing the transfer function has no effect, that means **the input itself is binary**.

### Diagnosis: the input really is binary

```
hands-off:  hardship ≈ 0 (never went hungry):  49.1%
        condition == 100 exactly:              53.2%
        hardship quantiles: p50=0.04 → p60=1.38    ← nothing in between
```

### ★ Root cause: explore is an infinite food tap

```
                 explore share   gather_food share   hardship
hit a crisis         0.0%             12.0%           4.66
never in crisis     36.5%              3.4%           0.00
```

**A ball that explores never goes hungry, and a ball that does not explore inevitably does. Zero overlap.**

The code for `explore` is `if rng.random() < 0.28: food += 2`, which is **bounded by no resource cap at all**.
An exploring ball accumulates about 147 portions over 30 days while needing only 79.

The scarcity so carefully manufactured in experiment 004 **had a leak, and half the balls escaped through it**.

> **This was predicted by rule one:**
> "the user's influence = the part the ball cannot solve by itself."
> Exploring is exactly a way the ball solves the problem by itself.
> The rule was right; nobody went back to audit whether the code violated it.

### Incidental finding: what the positive feedback amplifies is the seed, and it happens before the user intervenes

Comparing the **initial** personality (reconstructed from the seed) and the **final** personality of the "hit a crisis" and "never in crisis" groups:

```
                initial                    final
           crisis   no crisis        crisis   no crisis
curiosity  47.1     54.3            47.1     86.7
caution    52.8     46.6            91.6     45.0
```

**A 7-point initial difference is amplified into 40 points.** An amplification factor of about 6.

That is difference source #4 (positive feedback) working as designed — but what it amplifies is **the noise of the seed**,
and it locks the ball into one of two attractors before the user's feeding can have any effect.

### The fix

```python
EXPLORE_FOOD_YIELD  = 0.5   # was hardcoded at 2.0. Exploring is now a subsidy, not a substitute
LOCAL_FOOD_REGEN    = 2.4   # 2.2 → 2.4. With the leak plugged the balls have no fallback, so local supply is loosened
```

(The two magic numbers `0.28` and `2` were promoted to named parameters along the way. The magic numbers hid this bug for an entire round.)

### Results

```
                        exp 011   continuous only    final     target
industry median          +1.34        +0.96         +14.38      ≠ 0
industry dz              +0.600     +0.524     +0.884    > 0.8   ✓
pairs with no change      30.2%        29.9%           6.5%    < 20%   ✓
condition median           0.00         0.00          -6.72      ≠ 0     ✓
hands-off mortality        6.5%         6.5%           7.8%    < 10%   ✓
```

**The dose response went from a step to a slope:**

```
                     industry   condition
doting→balanced      before   +3.15      -1.84       now   +6.60   -12.45
balanced→hands-off   before   +6.37     -19.58       now   +5.92   -13.76
```

The two segments are now nearly equal — **feeding every 3 days and feeding every day finally raise different balls**.

At the population level (`diagnose.py`) all three carriers show a gradient while the control arm stays flat:

```
          hunger-scarred  storm-fearing  industry  condition
doting          0.0%          37.8%        66.3      100.0
balanced       23.4%          37.2%        71.1       87.3
hands-off      49.5%          42.4%        79.7       76.4
```

spread 8.96 → 13.43; the industry signal-to-noise ratio 7.2 → 12.7;
caution goes from 2.1 → 5.4, so it is no longer a single carrier carrying the signal.

---

## ★ New design rules from this round

10. **If one link in the transmission chain is binary, the whole chain is binary.**
    Changing the far end achieves nothing. Walk up the chain until you find the first binary point.
    How to tell: smooth the transfer function, and if the output does not change, the problem is in the input.

11. **Audit the bypasses through which "the ball solves the problem itself" regularly.**
    Rule one had the direction right, but the code can quietly grow something that violates it
    (this time it was the food yield of exploring, hidden inside two magic numbers).
    **Every time an action that produces a resource is added, ask: does this make the user optional?**

12. **Positive feedback amplifies whichever difference entered the loop first.**
    The seed's noise enters on day 0, while the user's feeding takes days to show
    → the loop locks the ball into an attractor and the user can never catch up.
    **The user's input must enter the system before the positive feedback locks in.**

Plus one methodological rule:

13. **A hypothesis being falsified on the spot by your own tool is evidence the tool works.**
    The first thing `paired.py` did once it existed was refute the very hypothesis it was built for.
    Looking only at spread, "going continuous" would have been recorded as a small improvement rather than a falsification.

---

## Still unsolved (after experiment 013)

- **The direction of `shelter` is still inverted** (+9.09). Hands-off balls still fix their houses up better.
  The root cause is unchanged: the ratchet pours into `industry`, and `industry` scores `build`.
- **The paired medians of `caution` / `curiosity` are still ≈ 0.** The user's channel converges on the single dimension `industry`.
- **The personality-label flip rate is 17.1%** (target 50%), and a substantial part of it is the `dominant_style()` bug.
- **Balanced now dies at 2.5%** (previously 0%).
- ⚠ **The new configuration has not been re-tested for 60-day durability or ±7% parameter robustness** (problems 2 and 3 in the stocktake).

---

## Experiment 014 — ablation: how much does each mechanism actually contribute (`ablation.py`)

The method is taken from §6 of [[Generative Agents notes]]: switch off each component of the architecture in turn and see how far the metric drops.
They proved "every component is necessary"; what we want to prove is **that differentiation is not the doing of one knob, and is not random**.

300 seeds × 30 days, paired doting → hands-off:

```
condition                       ind dz   ind median   cond dz   no change   hands-off dead   vs full
full architecture                0.861     12.08      -0.826       6.5%          8.0%       baseline
− personality weight             0.823     13.31      -1.290       5.3%          0.0%          -4%
− positive feedback loop         1.439     14.75      -0.767      16.7%          0.0%         +67%
− ratchet (no mark left)         1.484      6.55      -0.633       5.8%         13.3%         +72%
− seasonal fluctuation           0.732      9.70      -0.713       7.4%          9.3%         -15%
− food deficit                   0.401      0.94      -0.413      32.3%          0.0%         -53%
− user difference (null)         0.000      0.00       0.000     100.0%          3.0%        -100%
```

**The null row is exactly 0** — when the feeding intervals of the three users are made equal,
two runs of the same seed are deterministically identical. The measurement pipeline does not leak.

### The results are uncomfortable but informative

**1. The food deficit is the overwhelming top contributor (−53%).**
Switching it off (= restoring the exploration food leak) takes the median straight down to 0.94, with a third of pairs unchanged.
The judgement of experiment 013 is independently confirmed.

**2. Positive feedback and the ratchet contribute negatively to the "user attribution" metric.**

That looks like bad news, but it actually quantifies the tension of [[Design points and risks]] §5.2:

> Positive feedback (difference source #4) amplifies **the seed**,
> and the seed is **noise** for the user's signal.
> It makes the balls differ from one another (large σ) while making "was this caused by the user" harder to see.

**Difference sources #1/#4 and #3 are competing for the same variance budget.** That is a genuine trade-off, not a bug.

The ratchet is the same: switching it off raises dz to 1.484, **but halves the median (12.08 → 6.55) and takes mortality from 8.0% to 13.3%.**
The ratchet's real contribution is **raising the median and keeping them alive**, not raising dz.

**3. ⚠ Switching off the personality weight barely changes dz (−4%) and takes mortality to zero.**

This one deserves the most caution, because what it exposes is **a problem with our metric**:

> At `PERSONALITY_WEIGHT = 0` the personality numbers **have no effect on behaviour at all**.
> And yet industry dz is still 0.823.
> So dz measures **a difference in a number**, not **a difference in behaviour**.

This is exactly what [[Design points and risks]] §5.5 warned about: "the difference must be visible".
**Every current metric measures numbers, and not one measures behaviour.**

Incidentally: the personality weight is what kills the balls (mortality 8.0% → 0% once it is off), consistent with the observation of experiment 002.

---

## ★ The rules from experiment 014

14. **Positive feedback amplifies whichever difference entered the loop first — it serves "individual diversity", not "user attribution".**
    Those two goals compete for the same variance. Which one you want depends on what the product is selling.

15. **An ablation table exposes the blind spots of the metric, not only the contributions of the mechanisms.**
    dz staying put when the personality weight is switched off means the metric is measuring the wrong thing.
    **What should come next is a behaviour-layer metric** (how far apart the daily action distributions of two paired balls are),
    rather than further optimisation of a numeric-layer dz.

---

## Experiment 015 — filling in the behaviour layer: at which layer does the selling point hold (`behavior.py`)

Rule 15 of experiment 014 put it bluntly: every metric measures numbers and none measures behaviour.
This round fills that in. `action_by_hour` was added to `Agent` along the way (recorded per hour),
and the criterion-ordering bug in `dominant_style()` was fixed.

### Three metrics and their noise floors

TV (total variation distance) is always positive, so sign permutation cannot be used. **The correct control is to change the comparison object:**

```
TV_user  = same seed, different user     ← the behavioural difference caused by the user
TV_base  = same user, different seed     ← the difference two balls have anyway
```

**TV_user must clearly exceed TV_base**, or "my ball is different from yours"
cannot be told apart from "balls differ anyway", and the user still will not feel they raised it.

### ✗ Conclusion one: the behaviour layer does not hold

```
caused by the user (same seed, different user)    TV 0.160
baseline (same user, different seed)              TV 0.286 / 0.223

user / baseline = 0.63×      p = 0.000   ← significant, but in the wrong direction
```

The routine metric puts it even more harshly:

```
hours whose routine differs:   caused by the user 5.05/24 (median 0)   baseline 9.35/24 (median 13)
```

**The median is 0 — in more than half the pairs the two balls have exactly the same daily routine.**
And the entire displacement is concentrated on one action: `gather_food +7.5%`,
which is precisely the behaviour the user cannot see.

### ✓ Conclusion two: the state layer does hold

```
feature                only hands-off   only doting   discordance rate
still looks healthy            0             169          56.3%   ← direction perfect
has a food store              81              79          53.3%
has a decent home             39               0          13.0%   ← direction inverted
often goes out                 0              15           5.0%

★ at least one feature differs: 78.7%     target > 60%   ✓
```

**78.7% of pairs can be told apart at a glance, without looking at any number.**

### Rule 8 needs revising

It used to be "state > events > personality". A fourth must be added, and it comes last:

> ### ★ state > events > personality > **behaviour**
> Behaviour is not only the weakest but **below baseline** — the user's influence on "what the ball does each day"
> is smaller than the seed's influence on it.

### Experiment 015b — a direct test of rule 12, and a false dawn

Rule 12 says the seed competes with the user's signal. So try turning the initial noise down
(`INITIAL_TRAIT_SPREAD`, previously hardcoded at ±15):

```
spread   TV user   TV baseline   ratio   ind dz   visibly distinct   hands-off dead
  15.0   0.146    0.277    0.53     0.86     72.5%      8.0%
   6.0   0.160    0.255    0.63     0.91     78.7%      0.0%
   0.0   0.167    0.138    1.20     0.68     67.0%      0.0%
```

The ratio goes from 0.53 to 1.20, which looks like a solution. **But look at the `TV user` column: it barely moves.**

> ### ★ Rule 16: a better ratio is not a stronger effect
> The numerator did not change; the denominator was cut away.
> In a world with spread=0 every ball is the same, so this trades "abolishing individual diversity"
> for "a larger user share" — throwing away the other half of the product's value.
>
> **The user's behavioural influence has a ceiling, stuck at TV≈0.16, and no amount of seed tuning moves it.**

That said, `spread 15 → 6` is better on every metric and comes free, so it has been adopted.

---

## Experiment 016 — fixing "caring for it actually harms it"

> ### ⚠⚠ The conclusion of this section was overturned by experiment 017, and the weight 1.2 was reverted to 0.6
> Every 30-day number below is real, but **this parameter set does not survive 40 days**:
> at 60 days even the doted-on balls die at 45%. The cause is the caution weight added here.
> **The original text is kept, because this crash is itself the most valuable record.**

### Diagnosis (visible directly in the demo material)

```
hour      0 1 2 3 4 5 6 7 8 91011121314151617181920212223
doting    sl ex ex sl ex ex sl ex sl ex ex sl ex sl ex ex sl ex ex sl ex sl ex ex    shelter  0
hands-off ga ga sl sl ga ga ga sl ga ga ga sl ga sl sl ga ga sl sl sl ga sl sl sl    shelter 99
```

The doted-on ball **explores all day and builds nothing**.

Checking `ACTION_TRAIT_MATCH` makes it clear: `build` does respond to `caution`,
but **`gather_material` responds only to `industry`**, and `industry` only rises through the hunger ratchet.
Without material there is no way to build a house.

> **Taking good care of your ball removes the only motivation it had to build a house.**
> That is a one-line design flaw, not a parameter problem.

### The fix

```python
"gather_material": {"industry": 1.0, "caution": 1.2}   # previously industry only
```

**Wanting safety** should also drive gathering material, not industry alone.
(Adding positive feedback on `caution` at the same time was tried, and "visibly distinct" fell to 52–60% instead —
the positive feedback amplified the seed again. Rule 14 applies once more, so it is not added.)

A weight sweep (re-verified on 700 seeds; 1.2 is a sharp peak and both 1.1 and 1.3 are worse ⚠ robustness test pending):

```
c_match   mean shelter   has a home hands-off/doting    TV ratio   ind dz   visibly distinct
   0.0        +14.07      89/0          0.64     0.91      76.0%
   1.1         -0.08      63/56         0.53     0.69      76.1%
   1.2         -0.78           75/171                     0.53      0.64        82.5%   ← adopted
   1.3         -0.28      52/116        0.52     0.60      73.7%
```

### Results: much better than the sweep suggested

Watching `ind dz` alone would suggest a bad trade (0.91 → 0.67). Across all metrics it is not:

```
                        exp 015     exp 016
condition dz            -0.83      -1.04
condition median          -6.72      -26.40   ← the median finally moves substantially
condition |d|≥5         50.4%      79.7%
caution dz                +0.37       +0.48   (directional consistency 81.7%)
industry dz               +0.88       +0.67   ← the price
shelter                   +9.09       -0.74   (p=0.383, the inversion is gone)
visibly distinct           78.7%       82.9%
"has a decent home" direction   39/0 inverted    30/76 correct
hours whose routine differs   5.05(median 0)  10.58(median 11)
pairs with no change            6.5%        3.8%
hands-off mortality             7.8%        0.2%
```

**0.24 of industry bought: the condition median rising from 6.7 to 26.4,
caution going from no signal to a signal, the inversion disappearing, mortality falling to zero, and 82.9% visibly distinct.**

⚠ But `TV ratio` is still 0.53 — **the behaviour-layer conclusion has not changed.**
(The routine metric rose to 10.58/24 with a median of 11, which fights the TV; two behaviour metrics disagreeing
means TV measures "the overall mix of actions" while routine measures "what it is doing right now",
and the latter is closer to what the user perceives. This is not yet fully understood.)

---

## ★ The rules from experiments 015–016

16. **A better ratio is not a stronger effect.** Check whether the numerator moved before reading the ratio.

17. **Making a trade-off while watching one metric leads you the wrong way.**
    Experiment 016 is a loss viewed through `ind dz` and a large gain viewed across all metrics.
    **Once there are layered metrics, a trade-off must be read off the whole table at once.**

18. **Every time a new behaviour is added, ask which traits drive it.**
    `gather_material` hanging on industry alone accidentally produced "caring for it harms it".
    Every behaviour needs at least two personality pathways, or it becomes the exclusive outlet of one mechanism.

---

## Current state: at which layer does the selling point hold

| Layer | Conclusion | Evidence |
|---|---|---|
| **state** (condition, food store, whether it has a home) | ✓ **holds** | visibly distinct 66% (30 days) to 86% (90 days), robust to ±7% perturbation |
| **events** (the story of nearly starving) | ✓ **holds** | 187/0 discordant pairs, there is a story to tell |
| **personality** (the numbers) | ✓ holds statistically, weak perceptually | condition dz ≈ 1.0 |
| **behaviour** (what it does each day) | ✗ **does not hold** | per-hour TV user/baseline = 0.68–0.80, **three metrics agree, and it is insensitive to both parameters and time scale** |

> **The original selling point, "two users raise balls with different personalities",
> holds at the state and story layers and fails at the personality and behaviour layers.**
>
> This is still a product, but the pitch is different:
> lead with "your ball looks thin" and "it remembers nearly starving",
> and do not lead with "its personality/behaviour differs from everyone else's".

---

---

# Experiment 017 — settling both outstanding debts (both went wrong)

## 17a The two behaviour metrics disagree: I read them wrong

TV fell from 0.160 to 0.113 while the routine difference rose from 5.05 to 10.58. At the time I guessed "routine is closer
to what the user perceives, so the conclusion may not be so bad". **The guess was wrong.**

The key is the **mode margin of the dominant action**:

```
experiment 015:  margin = 0.40
experiment 016:  margin = 0.16    ← collapsed
```

After adding caution the ball starts alternating between gathering material and sleeping,
and the top action leads the second by only 16 percentage points — **the tiniest perturbation flips the "dominant action"**.

What `rhythm_diff` measures the rise of is the fragility of the mode, not a difference in behaviour. The proof: **the baseline
rose in step from 7.73 to 13.88**, leaving the ratio almost unchanged. I looked at the numerator and not the denominator (breaking rule 16 again).

### The correct routine metric: compare distributions per hour

`hourly_tv()` — compare the action distributions hour by hour and average. By convexity it is strictly more sensitive
than an aggregate TV (aggregation only shrinks the distance), and it has no mode-flipping problem.

```
                        user    baseline   ratio
experiment 015  TV aggregate   0.160   0.255   0.63
                TV per-hour    0.244   0.324   0.75
                routine (mode) 5.053   7.733   0.65
experiment 016  TV aggregate   0.113   0.216   0.53
                TV per-hour    0.212   0.307   0.69
                routine (mode)10.582  13.880   0.76
```

**All three metrics agree: the ratio is 0.53–0.76 and not one of them reaches 1.**
`behavior.py` has been switched to `hourly_tv`, and the mode version is kept only as a control with a warning attached.

> ### ★ Rule 19: when metrics disagree, go and check the one more easily pushed by noise first
> Do not pick whichever favours your own conclusion.

## 17b Durability: the experiment 016 parameters wipe the population out

```
days    visibly distinct   cond dz   routine ratio   doting dead   hands-off dead   caution saturated
 15      50.7%    -0.70     0.73      0.0%      0.0%       0.0%
 30      82.9%    -1.02     0.69      0.0%      0.3%       0.0%
 60      91.4%    -1.35     0.52     43.7%     59.3%       7.5%
 90      87.9%    -1.99     0.57     56.3%     75.3%      18.1%
```

**At 60 days even the doted-on balls die at 43.7%.** A simulator that kills half of the best-cared-for balls
is not a valid instrument, whatever the product pitch says.

The attribution is clean:

```
caution weight   60-day doting dead   60-day hands-off dead   material share of the action budget
    0.0          0.0%          16.0%           14.6%
    0.6          0.0%          15.6%           21.7%
    1.2               45.2%                 60.4%              25.3% (as high as 29.7% at 30 days)
```

**It is the weight added in experiment 016.** The balls spend three tenths of their action budget gathering material,
leaving food chronically underinvested; at 30 days the initial stock and the seasons hold it up, and at 60 days it collapses.

### A structural conjecture that was falsified (recorded so it is not walked again)

I thought it was "the need is satisfied but the personality term keeps pushing": the need term of `gather_material` is
`(100-shelter)*0.30`, which is zero at shelter=100; but the personality term `caution` contributes a constant ~36 points
at caution=100, **bounded by no measure of how far the need is satisfied**.

So a gate was added: `shelter > 90 and material ≥ 6 → this action is illegal`.
Result: 60-day mortality 60.4% → 57.6%, **almost no effect**.

The cause: the house decays by 8.4 a day, so shelter can rarely stay above 90 — the ball is not hoarding,
**it is on a treadmill endlessly repairing its house**. The conjecture is falsified.

### Disposition: revert to 0.6

```
days    visibly distinct   cond dz   routine ratio   doting dead   hands-off dead   caution saturated
 15      50.7%    -0.78     0.80      0.0%      0.0%       0.0%
 30      66.0%    -0.91     0.78      0.0%      0.0%       2.0%
 60      73.1%    -1.05     0.70      0.0%     15.7%      78.1%
 90      86.3%    -1.21     0.68      0.0%     27.0%      75.6%
```

- ✓ the wipeout is solved (doting: 0% mortality at 90 days)
- ✗ **the inversion is back** (has a home, doting/hands-off = 1/18; still only hands-off balls have homes)
- ✗ 30-day visibly distinct 82.9% → 66.0% (still above the 60% target, but clearly worse)
- ⚠ **a new problem: at 60 days, 78.1% of balls have caution pinned at 100** (the old configuration gave 57.3%)

> **The inversion is a narrative problem and the wipeout is a validity problem; protect the latter first.**

## 17c Robustness (30 days, ±7%)

```
                        visibly distinct   cond dz   routine ratio   hands-off dead
baseline                     82.9%          -1.02        0.69            0.3%
LOCAL_FOOD_REGEN -7%     90.3%     -1.55     0.67     11.0%   ⚠
LOCAL_FOOD_REGEN +7%     74.2%     -0.70     0.69      0.3%
HUNGER_RATE      +7%     89.3%     -1.70     0.70      9.7%   ⚠
PERSONALITY_W    ±7%     76-79%    -0.8~-1.0 0.70    0~1.7%
caution(material)    -7%     74.2%          -0.97        0.70            0.3%   ← has-a-home direction 32/38, the direction is gone
caution(material)    +7%     72.1%          -0.95        0.68            1.0%
```

- **visibly distinct stays between 71.7% and 90.3% and never falls below target.** That metric is stable.
- **the routine ratio stays between 0.62 and 0.80, completely unmoved.** The behaviour-layer conclusion is entirely insensitive to parameters.
- ⚠ either −7% food supply or +7% hunger rate pushes hands-off mortality to around 10%.
- ⚠ **a ±7% change in the `caution(material)` weight is enough to make the "has a home" direction vanish** — what 016 fixed
  was sitting on a knife edge all along, and this should have been seen before reverting to 0.6.

---

## ★ The rules from experiment 017

19. **When metrics disagree, check the one more easily pushed by noise first, and do not pick whichever favours you.**

20. **Tuning at only one time scale is the same as not tuning.**
    Every 30-day metric of experiment 016 improved, and at 60 days the population was wiped out.
    **Any parameter change must be looked at on at least two time scales.**

21. **"Wipeout" and "the narrative is wrong" are not problems of the same order.**
    The first invalidates the instrument; the second only makes the product story less appealing. When they conflict, protect the instrument's validity first.

---

## Still to do

- ✗ **The shelter inversion is still unsolved** (experiment 016's fix was rejected by 017).
  Next time it must be changed **structurally**: let "wanting safety" drive building in a way that does not consume the long-term action budget,
  rather than tuning a weight yet again.
- ⚠ **78% of balls have caution pinned at 100 at 60 days**; the ceiling problem of the personality system is worse than before
- ⚠ mortality is still sensitive to food supply and hunger rate (±7% → 10%)
- the paired median of `curiosity` is still 0
- `sweep.py` / `food_sweep.py` have been superseded and should be marked deprecated

---

---

---

# Experiment 018 — the v2 refactor: taking the "user" out of the model

> Date: 2026-08-10
> ⚠ **A numeric dividing line**: v2 splits the world and the individual into two independent random streams,
> changing the consumption order, so numbers after 018 **cannot be compared directly with 011–017**.

## 0. First, a reported bug was checked — it does not exist

Someone pointed out that `s += max(0.0, self.hunger - 35) * 0.85` appears twice inside `gather_food`,
so the model actually run would be ×1.7. **Checked: `grep -c` = 1, it appears once (sim.py:220).**
Nothing needs re-running. Recorded here so the same thing does not trip anyone up again.

## 1. Structure: the three layers Agent / World / Influence

The model used to contain:

```python
USER_ARCHETYPES = {"doting": {"feed_every_days": 1.0}, ...}   # difference source #3
```

and the Agent constructor took `archetype` directly. That writes the product philosophy backwards:

```
User type → Feeding → Personality        (before)
World → Experience → Memory → Personality → Goals → Behavior   (now)
```

Split into:

```
sim.py                          scenarios.py
├─ World      resources/weather/objects/events   FEEDING  three feeding frequencies (the old control arm)
├─ Influence  give_food / add_book               WORLDS   11 worlds (the new main line)
│             play_music / change_env
├─ Agent      personality/needs/memory/goals
└─ Life       binds the three together and runs them
```

**The word "user" no longer appears in `sim.py`.** The Agent only sees "two extra portions of food in the world today"
and does not know who gave them. The three archetypes are kept as experiment groups but moved to `scenarios.py`.

`scenarios.run()` attaches a `.scenario` label to the agent it returns —
that is the **experiment ledger**, used by analysis scripts for grouping, and the model never reads it while running.

## 2. The temporal structure of personality (note ⑤): forms fast, fades slow

The old `trait_floor` was a permanent one-way valve. It becomes two layers:

```
soft floor  fades by 0.35 a day; a "medium-term habit"
perm floor  40% of what a landmark raises becomes a permanent bias; an "identity"
                soft is never below perm
```

Plus: on well-fed, sheltered days `hardship` fades by 0.015 a day.

## 3. The Goal layer (note ③): from a reactive agent to an autonomous life

It used to be `tick → score → take the highest`, a perfectly good **Reactive Agent**.
What the user saw was "this tick, build happens to score highest", not "it has been building a home these last few days".

```python
goal = {"type": "improve_home", "priority": 0.72,
        "created_from": "storm_memory", "progress": 0.35}
```

It thinks once every morning (not every tick, which would destroy continuity), and the goal biases the action scores.

### ★ Four traps hit, each worth recording ★

**Trap 1: a count-based progress measure with no baseline stored.**
The progress of `see_the_world` was computed from the cumulative explore count, so it was "complete" the moment it was raised →
completed daily, re-raised daily → re-raising refreshes `created_day` → permanently inside the minimum commitment period
→ **the ball is locked onto this goal and starves to death.**
The same class of error as experiment 009: **a count-based metric must store a baseline.**

**Trap 2: intention overrides survival.**
In the first version the goal bonus applied unconditionally, and the ball starved chasing "go and see distant places".
A suppression term was added: when hunger/condition are critical, the goal bonus decays proportionally to 0.
→ This is the rule "personality needs slack to express itself" restated at the intention layer.

**Trap 3: adding a bonus is not enough; it must also become distractible.**
A ball drifted to curiosity 100 / caution 18 has a +44 personality bonus on explore,
which a +22 goal bonus alone cannot cover — measured, it "wanted to fix its house" for 13 days straight while running around outside,
and the house rotted to 0. `GOAL_OFF_TASK` was added: pastime actions (explore/read) are suppressed while a goal is active.
> **Focus is not only "wanting A more", it is also "wanting B less for now".**

**Trap 4: a refractory period forces out intentions it cannot act on.**
Just after completing see_the_world → the refractory period suppresses it → improve_home is pushed up →
but its personality does not support it at all → it wanted to fix the house for 8 days straight and never picked up a single log.
A stall-abandon rule was added (abandon after 4 days without progress, leaving a memory of "wanted to but never did").
> People are the same: "I have been meaning to fix the roof but never have" — that intention eventually fades by itself.

Result: **each goal is held for 3.7 days on average and 8 things are completed in a lifetime**,
and `storm_memory` and `hunger_memory` appear among the sources — memory really is generating intentions.

## 4. Memory (note ④): from flags+landmarks to structured objects

```python
{"event": "storm_destroyed_roof", "day": 12, "importance": 0.9,
 "emotional_weight": 0.82, "consequence": "shelter_damage",
 "related_traits": ("caution",), "tags": (...)}
```

Split into two kinds:

```
episodic   on day 12 there was a storm and the roof broke       grows without bound, needs forgetting
semantic   without solid shelter, rain is dangerous              capped at a few dozen, what behaviour really depends on
```

`recall(tags, k)` retrieves by **structured tags**, not vector similarity
([[Design points and risks]] §3.4; the most common failure in [[Generative Agents notes]] §6.5.2
is vector retrieval fetching the wrong thing).

`context_packet(day)` is the bundle that will later be fed to an LLM:
**current state + current goal + relevant memories + world knowledge + personality**.
Measured, it produces "goal: stock_food, created_from: hunger_memory" +
"day 25, lived through a stretch of not having enough to eat" — language and behaviour now line up.
Note that traits are read-only: the LLM never owns the personality.

---

## 5. ★ The main result of experiment 018: the environment beat the seed, and feeding never did ★

> ### ⚠ The baseline of the table below has a bug, corrected in experiment 019; the right numbers are there
> The baseline paired survivors within each cohort. The survivors of the barren world are filtered
> (the weak all died) → within-group variance too small → baseline too small → **the ratio is inflated**.
> After correction: rich↔barren 1.56 → **1.51** (conclusion unchanged),
> has-books 1.02 → **0.87 (★ gone)**.
> **"Books alone can clear 1" was an illusion.**

Same seed, same initial personality, same feeding frequency; only the world differs:

```
comparison                    routine TV  base  ratio   goal TV  base  ratio   visibly distinct   dead
rich world↔barren world           0.381  0.245  1.56     0.416  0.247  1.68        68.5%          6.0% ★
has books↔baseline                0.266  0.260  1.02     0.311  0.211  1.47        56.4%          0.0% ★
has music↔baseline                0.203  0.322  0.63     0.099  0.257  0.39        38.0%          0.0%
food-rich↔food-poor               0.162  0.286  0.57     0.182  0.292  0.62        41.7%          3.2%
material-rich↔material-scarce     0.205  0.285  0.72     0.127  0.240  0.53        41.2%          0.0%
rainy↔stable weather              0.253  0.273  0.93     0.228  0.245  0.93        68.4%          0.0%
doting↔hands-off                  0.195  0.279  0.70     0.349  0.228  1.53        71.6%          0.0%  ← the old axis
```

**A ratio of 1.56 is the first time this project has exceeded 1 at the behaviour layer.**
The ceiling on the feeding axis across every experiment from 011–017 was 0.80, and it never reached 1.

Three observations:

1. **Single factors mostly cannot win; the combination can.** Music 0.63, food 0.57, material 0.72
   and rain 0.93 are each below baseline; stacked together they give 1.56.
   The environment's effect is **cumulative**, not one switch.

2. **Goal is a strong carrier.** The goal-TV ratio is generally higher than the routine-TV ratio
   (1.68 vs 1.56 for the world pair; even the old feeding axis gives 1.53 vs 0.70).
   **Adding the goal layer incidentally opened an attribution channel stronger than the action distribution.**

3. **Weather alone changes personality a great deal but not the routine** (caution differs by 27.3 points, routine ratio 0.93).
   Personality and behaviour can decouple — another instance of the finding from the ablation experiment (014).

### Demo material (same seed, two worlds; this is the pair with the largest TV, so it is cherry-picked)

```
▸ rich world   caution 28 | curiosity 100 | industry  70   adventurer
             shelter  0   condition 53   food store 2
             spent its life pursuing: see the world (40%), read a little more (23%)
             completed 14 things, abandoned 1
             learned: books hold worlds I have not seen; there are places with more food far away

▸ barren world   caution 80 | curiosity  45 | industry 100   nest-builder
             shelter 99   condition 76   food store 4
             spent its life pursuing: store more food (90%), make the home sturdier (10%)
             completed 0 things, abandoned 4
             learned: without solid shelter, rain is dangerous
             day 2, a storm tore the roof off
```

> **The same seed. The same initial personality. Only the world differs.**
> This is the direct evidence for "the user changes the world like a god, and life grows into different shapes by itself".

⚠ "rich world vs barren world" changes four variables at once and is **not single-factor attribution**;
all that can be said is "the environment as a whole can produce different lives", not which factor did it.

---

## ★ The rules from experiment 018

22. **Count-based progress must store a baseline.** Same root as rule 5: before using any "cumulative quantity" as a metric,
    be clear about where its zero is.

23. **The intention layer needs slack too.** When survival is critical the goal must give way, or the agent will
    starve chasing an ideal. This is "personality needs slack" restated at the goal layer.

24. **Focus = a bonus + a cost to distraction.** Bonusing the goal action alone cannot cover a personality that has already drifted.

25. **An intention that cannot produce action must be able to fade.** Otherwise "wanting to" and "doing" decouple and the goal layer was added for nothing.

26. **The environment's effect is cumulative.** Single factors are mostly below baseline, and only the combination clears 1.
    → Product implication: **giving the user one prop achieves nothing; give them a whole modifiable world.**

---

## Still to do (after v2)

- ⚠ **No v2 configuration has had a 60/90-day durability test** (the lesson of experiment 017: tuning at one
  time scale is the same as not tuning). The goal layer is new and its long-term behaviour is entirely unknown.
- ⚠ **No ±7% robustness test**; the four new goal parameters (BONUS / OFF_TASK / REFRACTORY /
  STALL_DAYS) were all hand-tuned and have never been swept once.
- **The shelter inversion** has not been re-tested under v2.
- "rich world vs barren world" needs splitting into single factors before we know which one deserves the credit.
- The conclusions of `paired.py` / `ablation.py` / `behavior.py` all need re-running under v2
  (so far only a smoke test has been done, confirming they run and that the null is still 0).

---

---

---

# Experiment 019 — persistence becomes the main metric

> Date: 2026-08-10

Four things: fixing the instrument's validity, fixing the baseline, establishing "persistence" as the main metric, and promoting Goal to the main carrier.

## 1. Fixing validity first (rule 21: a wipeout beats a narrative)

The 60/90-day mortality of v2:

```
             30d     60d     90d
baseline        0.0%   11.5%   43.0%
barren world    5.5%   27.5%   54.0%
```

Diagnosis (90 days, baseline) — the balls that died all fit one profile:

```
          eat  sleep  gather food  gather material  build  explore     caution  curiosity  industry
muertos   11%   40%    2%    1%   0%  46%       18   100    78
vivos     11%   41%    6%   13%   4%  25%       59    83    88
```

**The balls that ran off drifted to "caution 18 / curiosity 100", spending 46% of their time outside and only 2% gathering food.**
Switching the goal layer off takes 90-day baseline mortality from 43.0% down to 7.0% — **it is that intention that kills them**.

### Root cause: note ⑤ incidentally removed the only brake

Positive feedback has no brake of its own (explore → curiosity↑ caution↓ → wants to explore more).
In v1 the **permanent trait_floor happened to serve as the brake**; v2 lets the floor fade, and the brake is gone.

### Two fixes

**Fix A: `TRAIT_SATURATION = 0.90`** — the more extreme the personality, the harder it is to grow more extreme.

```
 SAT     30d    60d    90d   caution pinned   environment ratio   visibly distinct
0.00    0.0%  11.5%  43.0%      44.6%      1.56     68.3%
0.90    0.0%   0.0%  28.5%       0.0%      1.55     79.9%
```

**Everything improves and not a scrap of the environment signal is lost.** It also incidentally cures the ceiling problem of
experiment 017, "78% of balls have caution pinned at 100 at 60 days".

**Fix B: pastime goals must have slack before they can be raised at all.**
The suppression inside `goal_bonus` acts **at execution time**, which is too late. The real problem is
**raising the ambition of "go and see distant places" while there is nothing to eat**.
The priority of `see_the_world` / `learn` is multiplied by
`slack = f(food store) × f(condition)`.

```
             30d    60d    90d
baseline        0.0%   0.0%   2.5%      (was 0.0 / 11.5 / 43.0)
rich world      0.0%   0.0%   4.5%
balanced        0.0%   0.0%   2.5%
hands-off       0.0%   3.0%   6.0%
doting          0.0%   0.0%   0.0%
barren world    6.0%  23.0%  37.5%      ← this world is deliberately extreme
```

> ### ★ Rule 27: the suppression of needs must act on **intention formation**, not **intention execution**
> Waiting until condition has fallen before suppressing the goal means the deficit is already done.
> "Slack" must take part in the judgement at the moment the ambition is raised.

## 2. Fixing the baseline (survivorship)

`environment.py` built its baseline by pairing survivors within each cohort.
The survivors of the barren world are a filtered batch → within-group variance too small → baseline too small → **the ratio is inflated**.
The treatment group uses the intersection of "alive on both sides", so the baseline must use the same batch of seeds.

### The corrected full 018 table (including the validity fix)

```
comparison                    routine TV  base  ratio   goal TV  base  ratio   visibly distinct   dead
rich world↔barren world          0.361  0.239  1.51     0.355  0.274  1.30        82.9%          6.4% ★
has books↔baseline               0.225  0.258  0.87     0.276  0.256  1.08        63.6%          0.0%
has music↔baseline               0.197  0.310  0.64     0.116  0.296  0.39        46.4%          0.0%
food-rich↔food-poor              0.156  0.281  0.56     0.171  0.332  0.51        51.7%          3.2%
material-rich↔material-scarce    0.207  0.276  0.75     0.137  0.285  0.48        53.2%          0.0%
rainy↔stable weather             0.255  0.273  0.94     0.277  0.269  1.03        78.0%          0.0%
doting↔hands-off                 0.190  0.265  0.72     0.417  0.233  1.79        82.4%          0.0% ← the old axis
```

**"Books alone clear 1" was an illusion created by the baseline bug** (1.02 → 0.87).
The conclusion about the combined world is unchanged (1.56 → 1.51).

## 3. ★ The transplant experiment: the difference is personality, not a thermometer ★ (`transplant.py`)

That 1.51 from 018 carries a fatal ambiguity: **at the time the two balls were still in different worlds.**
So it cannot distinguish:

```
(A) experience shaped it    → it survives a return to the same world
(B) only the current conditions differ → it vanishes once the environment matches
```

Method: 30 days of divergence, then **both sides switched to the "baseline" world for the second 30 days**, with measurement only in that second half.

```
condition   window TV   base   ratio   visibly distinct   dead    personality diff
stay          0.303    0.238   1.27         74.6%        24.4%    ca +23.9
move          0.300    0.259   1.16         76.8%         6.8%    ca +27.4

stay 1.27 → move 1.16   retained 91%
★ the ratio is still > 1 after the transplant
```

**With the cause removed the difference remains, and 91% of it is retained. It is (A).**
The product-document line "there was a heavy rain once… ever since then I have not liked being unprepared"
now has empirical support.

## 4. Single-factor persistence (`persistence.py`) — the conjecture was only half right

```
factor          stay routine  move routine  retained   stay goal  move goal  retained
books                0.92          0.87        94%        1.04       0.80       76%
music                0.64          0.62        97%        0.52       0.53      103%
weather              1.00          0.88        88%        0.97       0.94       97%
material             0.67          0.57        85%        0.58       0.53       91%
food rate            0.67          0.58        87%        0.55       0.57      103%
combination (ref)    1.27          1.18        93%        1.16       1.07       92% ★
```

### ⚠ Finding one: the retention rate distinguishes nothing

**Every factor's retention rate is between 85% and 103%.** Food rate retains 87%, books retain 94% — much the same.

> ### ★ Rule 28: persistence is not "how much was retained" but "how much was created in the first place"
> Practically any difference that gets created survives. The real difference is in **magnitude**, not in retention.
> So the main metric should be **the absolute post-transplant ratio**, not the retention percentage.

### Finding two: the conjecture was half right

| Conjecture | Result |
|---|---|
| food rate is weakest (written into no persistent structure) | ✓ **confirmed**. 0.58 after the transplant, the lowest; the personality residue is only +3.0 |
| books are strongest (written into knowledge and goal) | ✗ **merely tied**. Books 0.87, **weather 0.88** |

The mechanism columns (a difference = the second minus the first; a negative sign means the first has more):

```
factor        routine after move   semantic memory diff   permanent identity diff   personality residue after move
books                0.87                -1.01                    +0.04               caution +9.2
weather              0.88                -0.06                    -0.28               caution -26.8  ← nine times
food rate            0.58                +0.08                    -0.05               caution  +3.0
```

**The mechanistic direction is right, but the strongest persistent-write channel is weather, not books.**
Weather writes through storm → landmark → `trait_identity` into a **permanent identity**,
leaving a 26.8-point caution difference 30 days after the transplant. Books write only into `knowledge` and leave 9.2 points.

### ★ Finding three: `knowledge` is write-only — that is why books are weak

Checked the code: `self.knowledge` is written only by `learn()` and read only by `context_packet()`,
and **`score()` has never read it.**

> **Semantic memory is currently an ornament.** It can be recited but changes no behaviour.
> Books lose to weather not because they write less, but because the drawer they write into
> is not wired to behaviour.

That explains another number: **books' goal retention is only 76%, the lowest in the table** —
the `learn` goal needs books in the world, and once transplanted to the baseline world the books are gone and that channel is cut.
Weather is different: what it writes is on the ball itself, and travels wherever the ball goes.

> ### ★ Rule 29: only what is written into the **individual** can persist
> What is written into the world (books, music) vanishes with the environment;
> only what is written into `trait_identity` / `flags` travels with the ball.
> **Product implication: giving it a book is worth less than letting it live through an event.**

## 5. ★ Goal promoted to the main carrier ★

```
                     routine ratio   goal ratio
doting ↔ hands-off        0.72          1.79   ← the old axis, never passing on routine
rich world ↔ barren world  1.51          1.30
```

**The feeding axis never reached 1 on routine (a ceiling of 0.80 before 017), and reaches 1.79 at the goal layer.**

And it can be stated in one sentence:

```
goal                    doting   hands-off     diff
make the home sturdier   39.5%     29.2%     -10.3%
store more food          12.3%     54.0%     +41.7%
see the world            48.2%     16.7%     -31.5%
```

> The pampered ball spends half its life running into the distance; the neglected one spends half its life hoarding food.

This is the first time since experiment 011 that **the user's influence both exceeds the baseline and can be stated as a sentence**.
`behavior.py` has moved the goal layer into the main-carrier position.

The reasoning (written into the script comments): stronger than routine · carries `created_from` for attribution ·
can be stated as a sentence · is the most natural interface once an LLM is wired in (`context_packet` is organised around it).

---

## ★ The rules from experiment 019

27. **The suppression of needs must act on intention formation, not intention execution.**
    Waiting until condition falls before suppressing the goal means the deficit is already done.

28. **Persistence is not "how much was retained" but "how much was created in the first place".**
    Retention rates distinguish nothing between factors (all 85–103%); the main metric must be the absolute post-transplant ratio.

29. **Only what is written into the individual can persist.**
    What is written into the world (books, music) vanishes with the environment; what is written into trait_identity / flags travels with the ball.

30. **A structure that is written and never read is an ornament.**
    `knowledge` has content, can be recited, and affects behaviour not at all — which is why books lose to weather.

---

## Still unsolved

- ⚠ **`knowledge` is not wired into `score()`.** This is the direct to-do of rule 30:
  semantic memory should affect behaviour (for instance "knowing there is food far away" → more inclined to explore in the lean season),
  or the "books" product line cannot stand at the behaviour layer.
- ⚠ **The barren world's 90-day mortality is 37.5%.** An extreme world, but it must be confirmed as the design intent.
- ⚠ **The five goal parameters** (BONUS / OFF_TASK / REFRACTORY / STALL_DAYS / slack)
  have still never been swept for robustness once.
- Not one single factor clears 1 after the transplant; **only the combination does** (rule 26 holds again).
- `paired.py` / `ablation.py` need re-running on the fixed v2 to obtain a baseline.

---

---

---

# Experiment 020 — state levelling + deletion test: where does the difference actually live

> Date: 2026-08-11
> Background: the external ablation (`persistence_ablation.py`) has already shown that persistence is **not hardcoded** —
> with all three floor mechanisms switched off, the transplant ratio is still 1.07 and mortality is only 4%.
> But the margin above 1.0 falls from 0.18 to 0.07, and visibly distinct falls from 74.8% to 60.4%.
> **What is reported externally is the 1.07 row, not 1.18. The floors are not the source but an amplifier of about sixty percent.**

## 1. ★ State levelling: that caution curve is real (`leveling.py`) ★

After the transplant into a neutral world, caution keeps widening. Two readings:

```
strong  differentiation is self-sustaining — internal structure keeps generating caution-raising experiences (path dependence)
weak    state confound — it simply has not recovered; its condition/food store are worse, so it keeps meeting bad things
```

**Method**: at the moment of transplant, force hunger / energy / condition / shelter / inventory
to be exactly equal, leaving only personality / memory / goals different.
(`hardship` is deliberately not cleared — it is experience, not state.)

**★ Methodological correction: settle the surviving set per point ★**
The first version computed every row on "those alive at day 120", a loss of 24.5%/38.0%.
But the survivors are precisely "the balls that did not run off", which is exactly what this curve is about —
**selecting the sample by the conclusion**. Changed to computing each checkpoint separately:

```
[not levelled]        caution  curiosity  industry  condition   valid pairs   loss
day 30 (transplant)     +19.3     -20.8     +10.7      +1.1         188      6.0%
day 60                  +26.3     -17.4      +9.2     +12.9         187      6.5%
day 90                  +30.2     -17.6      +9.7     +13.2         185      7.5%
day 120                 +32.6     -19.2      +9.7     +14.8         151     24.5% ⚠

[levelled]
day 30 (transplant)     +19.3     -20.8     +10.7      +1.1         188      6.0%
day 60                  +28.9     -17.6     +11.7     +18.9         188      6.0%
day 90                  +32.2     -17.9     +11.2     +23.9         180     10.0%
day 120                 +30.3     -17.9      +9.6     +21.4         124     38.0% ⚠
```

Using only the points with loss ≤15% (30/60/90):

```
caution growth after the transplant    not levelled +10.9    levelled +12.9   (118%)
```

> ### ★ The strong reading holds, and more strongly than expected ★
> **After levelling the state, the gap does not narrow; it widens faster.**

The core prediction of the weak reading is "the barren twin is in worse shape so it keeps meeting bad things". The measurement says the opposite:
**at day 90 in the levelled group the barren twin's condition is +23.9 and its food store +8.6 — it is living better,
and still becoming more cautious.** The recovery-curve explanation is falsified outright.

## 2. The deletion test: a four-step ladder (`deletion.py`)

Delete each layer in a ladder at the moment of transplant:

```
condition          caut at move  +30 caut  +60 caut  +30 ratio  +60 ratio  +60 visible  +60 loss
① full                 +19.3       +26.3     +30.2      1.17       1.23       70.6%       6.5%
② −episodic memory     +19.3       +26.3     +30.2      1.17       1.23       70.6%       6.5%
③ −episodic+semantic   +19.3       +26.3     +30.2      1.17       1.23       70.6%       6.5%
④ traits only          +19.3       +26.7     +31.3      1.14       1.32       71.8%       6.0%
```

### ⚠ ②③ match ① to the decimal point — that is not a conclusion, it is evidence of a bug

Checking the code: `self.memories` is read only in `recall()` and `landmarks`,
and `recall()` is called only by `context_packet()`; `context_packet()`
**has never been called by `score()` or `tick()`.** The same goes for `knowledge`.

> ### ★ Rule 31: the entire memory system is currently write-only ★
> Rule 30 of experiment 019 was about `knowledge`. It is now confirmed that **episodic memory is the same**.
> That whole layer of structure added in note ④: retrievable, recitable, and **with zero effect on behaviour**.
>
> So steps ②③ of the deletion test are **no-ops by construction**;
> they cannot measure "how important memory is", only "memory is not wired in".

Step ④ (deleting flags / hardship / goal as well) actually raises the ratio to 1.32.
So the difference is **entirely** settled in the personality vector (+ the floors), and nothing else is carrying it.

## 3. Three code corrections (`persistence.py`)

**(a) The mechanism check counted the wrong thing.** It computed `len(b) - len(a)`, which is "how many more B has than A",
not "how far the two differ". Two balls with 3 completely different knowledge entries each would score 0.
Only after switching to the **symmetric difference of the sets** (how many entries exist on only one side) does the mechanism table carry information:

```
factor        routine after move  goal after move  semantic memory  permanent identity  landmark
books                0.87              0.80             1.54              0.43            1.54
music                0.62              0.53             0.46              0.35            0.46
weather              0.88              0.94             0.97              0.72            0.97
material             0.57              0.53             0.09              0.03            0.09
food rate            0.58              0.57             0.20              0.05            0.20
combination (ref)    1.18              1.07             1.84              0.71            1.84
```

**Weather's permanent-identity difference of 0.72 is the highest of any single factor** (books 0.43).
And books' semantic-memory difference of 1.54 is the highest yet still loses to weather — **precisely because of rule 31: that column does not enter behaviour.**
Material at 0.03 and food at 0.05 write practically nothing persistent, and are indeed the weakest (0.57 / 0.58).

**(b) The restoration phase was run in three directions.** The `objects` of "baseline" are empty, so on the question of "are there books"
it equals the barren world: a rich twin moved there loses its books and the `learn` channel is cut — an asymmetric adaptation cost.

```
factor           →baseline   →rich world   →barren world
books               0.87         0.79           0.88
weather             0.88         0.97           0.88
combination (ref)   1.18         1.22           1.08
```

**The direction dependence is mild, and the combination is ≥1 in all three directions (1.08–1.22), so the conclusion is solid.**

**(c) `cohort()` gained a cache.** With six factors × four cohorts, the baseline world was being recomputed many times over.

---

## ★ The rules from experiment 020

31. **The entire memory system is write-only.** Neither episodic nor semantic memory enters `score()`.
    Retrievable, narratable, and with zero effect on behaviour — deleting it changes no number.

32. **Settle the surviving set per point.** Computing the whole table on "those alive at the end"
    means selecting the sample by the conclusion — especially when the survivors' defining feature is the very feature being measured.

33. **Report the most conservative variant externally.** All floors off gives 1.07 and the full architecture gives 1.18;
    1.07 is what should be reported. The floors are not the source of persistence, but they amplify it by about sixty percent.

---

## Still to do

- ⚠ **Wire memory into behaviour** (rules 30 + 31). This is the biggest structural gap right now:
  `knowledge` should enter `score()` or `propose_goals()`,
  or the "give it a book" product line cannot stand at the behaviour layer,
  and the middle two steps of the deletion test will never measure anything.
- **The novel-situation probe** (state levelling + cross-sample prediction) has not been done.
- **Long-horizon mortality**: the 120-day paired loss is 24.5% (38.0% in the levelled group),
  so the last point of the curve is unusable. Either fix it to <10%, or only ever report up to 90 days.
- The five goal parameters still have not been swept for robustness.

---

---

---

# Experiment 021 — a methodological audit: a precision check-up for writing the paper

> Date: 2026-08-13
> Trigger: preparing to write 018–020 up as a paper, first asking "are there enough runs".
> Conclusion: **the number of runs is not the problem; the upward bias caused by too few is.**
> Every ratio reported until now was optimistic.

## 1. ★ The ratio estimator is systematically biased upward ★

Bootstrapping the transplant ratio (cluster bootstrap, resampling by agent):

```
condition             N=150               N=600               N=1500
full architecture  1.181 [1.030,1.359]  1.150 [1.073,1.231]  1.132 [1.085,1.184] ✅
−all floors ①②     1.065 [0.912,1.244]  1.075 [0.993,1.160]  1.044 [0.996,1.094] ❌
```

The point estimate **falls monotonically** with N. The cause is that `ratio = a ratio of means`, the denominator (baseline TV) is noisy, and
`E[X/Y] > E[X]/E[Y]` (Jensen's inequality). The smaller the sample, the greater the inflation.

> ### ★ Rule 34: a ratio must be reported with its sample size, and the sample size must be maxed out ★
> 1500 seeds take only 44 seconds. Stopping at 150/250 previously was purely a failure to realise there was a bias.
> **Every ratio in the paper is re-run at N=1500.** The headline is corrected from 1.18 to **1.13**.

## 2. ★ Adjacent pairing made the baseline too small ★

The baseline at `transplant.py:106` is `(al[i], al[i+1])` with a step of 2 — each ball used once,
paired by "adjacent seeds". Switching to random pairing (with exactly the same sample size):

```
baseline pairing method      ratio      CI width
adjacent, once (current)    1.1499      0.1402
random pairing K=1          1.1321      0.1360     ← same sample size, merely shuffled
random pairing K=5          1.1248      0.1131     ← 19% narrower, +14 seconds
random pairing K=20         1.1251      0.1077     ← saturated, not worth it
```

Two findings:

1. **Balls generated from adjacent seeds are more alike than two random ones** → baseline too small → ratio inflated by 2.2%.
   This is an implementation problem, not a statistical one: it is worth checking how `scenarios.make` derives
   the child RNG from the seed, since adjacent integers may produce correlated initial personalities.
2. The baseline is a U-statistic, and K=5 already reaches the variance lower bound (the between-agent variance).

> ### ★ Rule 35: baseline pairing must be random and repeated K=5 times ★
> 19% more precision for free, plus removal of a 2.2% bias.

After all three corrections, the evolution of the headline number:
`1.18 (as logged) → 1.13 (N maxed out) → 1.125 (pairing fixed)`. **Always > 1, but shrinking all the way.**

## 3. ⚠ That 1.07 of rule 33 does not stand

`− all floors ①②` at N=1500 is **1.044, 95% CI [0.996, 1.094] — right on the line, containing 1.0**.
More N cannot rescue it, because the true value is around 1.04.

The reviewer's challenge anticipated at the head of `persistence_ablation.py`:

> "You did not discover irreversibility, you wrote irreversibility in."

**The current data cannot answer it.** Once the floors are off, the effect falls into the noise. Two routes:
- **Honest downgrade**: admit that `trait_identity` is a **necessary mechanism** of persistence, not an amplifier.
  The sentence in rule 33, "the floors are not the source but an amplifier of about sixty percent", must be withdrawn.
- **Fix the mechanism and measure again**: wire memory into `score()` (the to-do of rules 30/31),
  give persistence a second channel that does not rely on `max()`, and see whether the no-floor variant can stand.

(The `− all three off` row at 1.04 is even less usable: mortality 28%, survivor contamination.)

## 4. ★ The parameter-randomisation set (`param_sweep.py`) ★

Answering "is this just a hand-tuned parameter set". Not a grid scan: N parameter sets are drawn independently
from a prior (15 knobs randomised simultaneously), the transplant experiment is re-run for each, and **the distribution of the effect** is reported.

Along the way the hardcoded slack in `sim.py` was exposed as `GOAL_SLACK_FOOD` / `GOAL_SLACK_COND`
(defaults unchanged, behaviour bit-identical), so the mechanism of rule 27 can now be swept.

### ★ Official results (500 sets × 300 seeds, 30.7 minutes, 12 processes) ★

```
500 sets sampled → 374 valid → 324 after dropping wipeouts (mortality > 40%)   total attrition 35.2%

transplant ratio (routine)  median 1.058 [1.045, 1.079]   IQR [1.010, 1.128]
                            share > 1  80.2% [75.9%, 84.6%]
transplant ratio (goal)     median 1.061                  share > 1  72.2%
log ratio (routine)         median 0.048                  share > 0  78.4%
```

**Conclusion: the effect is not something a hand-tuned parameter set produced.** The CI of the median clearly excludes 1.0, and the lower quartile
is also above 1 (1.010). The paper can state directly:

> Across 500 randomly sampled parameter configurations (15 parameters jointly randomised, 324 sets after dropping wipeouts),
> the median post-transplant ratio is 1.058 (95% CI [1.045, 1.079]),
> and 80.2% ([75.9%, 84.6%]) of configurations have a ratio > 1.

**The hand-tuned default configuration (1.132) sits at the 75.6th percentile of this distribution** — favourable, but far from
extreme. That sentence should be written into the paper proactively, not left for a reviewer to ask about.
(Incidentally: the floor-ablation variant at 1.044 sits at the 44.1st percentile, exactly mid-range among random configurations.)

### Parameter sensitivity (Spearman ρ against the transplant ratio)

```
TRAIT_DRIFT          +0.432   ← the only one above 0.4
PERSONALITY_WEIGHT   +0.289
LANDMARK_BONUS       -0.153
LANDMARK_PERMANENT   +0.136
GOAL_SWITCH_MARGIN   +0.112
the other 10          |ρ| < 0.09
```

> ### ★ Rule 36: the effect increases monotonically with the positive-feedback gain, and the goal-layer parameters barely affect it ★
> `TRAIT_DRIFT` (ρ=+0.43) is the only major driver, with `PERSONALITY_WEIGHT` second
> (+0.29). All five goal parameters (BONUS / OFF_TASK / REFRACTORY / STALL_DAYS /
> SLACK) have **|ρ| < 0.09** — the "goal parameter robustness" to-do carried over two rounds since 019
> is closed here: the conclusion is entirely insensitive to them.
>
> ⚠ But `TRAIT_DRIFT` must be discussed proactively. **Note that it is evidence, not a threat**:
> if persistence really comes from that self-amplifying loop, then the effect **should** rise with the loop's gain.
> This is the same thing as §3 (switching the floors off drops the effect into the noise), seen from the other side.
> The paper should present it as mechanistic evidence, not hide it as a fragility.

⚠ **The 35.2% attrition is a selection effect and must be disclosed**: what was dropped are configurations where "the parameters
were drawn too harshly and the balls cannot survive", not a random subset. `dead_move` / `dead_stay` are all persisted in
`sweep_results.csv`; the paper must state clearly how many were dropped and under what rule.

⚠ The pilot (31 sets) reported 67.7% and ρ=0.588 at the time, both small-sample noise. **This is itself another instance of rule 34** —
the conclusion from 31 sets differs from the conclusion from 324 by 12 percentage points.

### ★ Holdout confirmation (seeds 10000–10299, never touched) ★

011→021 iterated 21 rounds on seeds 0–299, a textbook garden of forking paths.
Moving the same analysis unchanged onto untouched seeds and re-running 500 sets:

```
                 development (0–299)      holdout (10000–10299)      diff
routine median  1.058 [1.045, 1.079]    1.041 [1.031, 1.050]    +0.016 [+0.001, +0.042]
routine > 1          80.2%                    72.9%                  −7.3 pp
goal median     1.061 [1.050, 1.073]    1.031 [1.015, 1.039]    +0.031 [+0.015, +0.050]
goal > 1             72.2%                    62.2%                 −10.0 pp

TRAIT_DRIFT          ρ=+0.432                 ρ=+0.426
PERSONALITY_WEIGHT   ρ=+0.289                 ρ=+0.288
```

**Three conclusions:**

1. ✅ **The claim stands.** The holdout median is **1.041, 95% CI [1.031, 1.050], excluding 1.0**,
   with 72.9% of random configurations > 1. On a fresh batch of unseen seeds the conclusion is unchanged.
2. ⚠ **But the development set really was inflated.** The difference CIs of both carriers **exclude 0**
   (routine +0.016 [+0.001, +0.042]; goal +0.031 [+0.015, +0.050]).
   21 rounds of iteration really did leave a mark on the seeds — small in magnitude, but **measurable**.
3. ★ **The sensitivity structure reproduces almost perfectly** (0.432→0.426, 0.289→0.288).
   The magnitude was lifted slightly by forking paths, and **the mechanistic conclusion is entirely unaffected**.

> ### ★ Rule 37: the paper reports the holdout numbers, not the development ones ★
> Development gives 1.058 / 80.2% and holdout gives 1.041 / 72.9%. **Report the latter.**
> And put this comparison table itself into the Methods — proactively showing "we quantified our own
> forking paths and reported the more conservative version" is a plus, not an admission of weakness.

## 5. The statistical work still missing (required for the paper)

1. ✅ ~~**A holdout seed set**~~ **done** (see the end of §4): 500 sets on seeds 10000–10299,
   median 1.041 [1.031, 1.050] still excluding 1.0, but with a measurable inflation on the development set.
   → Rule 37: the paper reports the holdout numbers.
2. ✅ ~~**Change the estimator to obtain a p value**~~ **done** (`significance_main.py`).
   Push the statistic down to each seed: `δ_i = TV(same seed across worlds) − TV(same world across seeds)`;
   δ can be either sign → **sign permutation is legitimate**, sidestepping the "TV is always positive" blockage of notes line 804.

```
                      n     numerator TV  baseline TV  ratio   mean δ    dz    δ>0      p
── development set seeds 0+, N=1500 ──
full architecture   1429   0.3103  0.2742  1.132  +0.0362  0.20  40.7%  0.0001 ***
−all floors ①②      1411   0.2960  0.2869  1.032  +0.0092  0.05  35.6%  0.0778 n.s.
── holdout set seeds 10000+, N=1500 ──
full architecture   1411   0.3094  0.2746  1.127  +0.0348  0.20  41.0%  0.0001 ***
−all floors ①②      1399   0.2983  0.2885  1.034  +0.0098  0.05  36.4%  0.0638 n.s.
```

   **The full architecture gives p=0.0001 and the holdout reproduces it exactly** (1.132 vs 1.127).
   **The floor ablation gives p≈0.07, not significant** — consistent with the CI conclusion of 021 §3, with the two methods corroborating each other.

> ### ★ Rule 38: the effect lives in the right tail, it is not uniformly distributed ★
> **`δ>0` is only 41%.** In other words, **for the median seed the baseline actually exceeds the cross-world difference**;
> the mean is positive because a few highly differentiated twins pull it up. Cohen's dz is only **0.20** (a small effect).
>
> The paper must not write "the environment makes agents different" but
> **"the environment makes some agents very different"** — heavy-tailed differentiation.
> That is actually more interesting (a threshold effect / path dependence), but it must be reported faithfully,
> and someone should go and find out what kind of seeds that 40% are (a new experiment).
3. **Multiple-comparison correction.** 6 factors × 3 restoration directions × 2 carriers = 36 tests, not one of them corrected.
   At minimum apply Benjamini–Hochberg FDR, or the ranking "weather 0.88 vs books 0.87" means nothing.
4. **Test-retest reliability (ICC)** and a **generalization test** (the novel-situation probe) are both still at zero.

---

## ★ The rules from experiment 021

34. **A ratio must be reported with its sample size, and the sample size must be maxed out.** A ratio is a biased estimator,
    systematically inflated at small N. 1500 seeds take 44 seconds; there is no reason to stop at 150.

35. **Baseline pairing must be random and repeated K=5 times.** Adjacent pairing makes the baseline 2.2% too small,
    and random K=5 buys 19% more precision for free.

36. **The effect increases monotonically with the positive-feedback gain (`TRAIT_DRIFT`), and the five goal-layer parameters barely affect it.**
    Across 500 random parameter sets, 72.9% (holdout) of configurations have a ratio > 1 — the effect is not hand-tuned.

37. **The paper reports the holdout numbers.** 21 rounds of iteration left a measurable inflation on the development seeds
    (routine +0.016, goal +0.031, both CIs excluding 0), but the mechanistic conclusion reproduces exactly.

---

## Still to do (after 021)

- ✅ ~~run the 500-set parameter sweep formally~~ **done**: 80.2% [75.9%, 84.6%] of configurations > 1,
  median 1.058 [1.045, 1.079]. The goal-parameter robustness to-do is closed at the same time.
- ⚠ **The floor-ablation line either needs a mechanism fix or a change of argument** (§3); this is the paper's biggest risk.
  → A preregistration has been written: [[Experiment 022 preregistration — wiring memory into decisions]] (frozen 2026-08-13, code unchanged).
  ★ While writing the preregistration, checking the code revealed that **rule 31 was half wrong**: `flags` and `hardship`
  **have long been wired into `score()` and `propose_goals()`** (sim.py:682/683/685/527/529/534),
  and the only unwired ones are `knowledge` (semantic) and `memories` (episodic).
  That lowers the prior for 022 — flags is already a "discrete marker → score bonus" design,
  and with the floors off the ratio is still only 1.044. See §2 of the preregistration.
- ⚠ Check the seed derivation in `scenarios.make`: whether adjacent seeds produce correlated initial personalities.
- Not one of the four statistical items in §5 above has been done.
- Carried over from 019/020: wiring memory into `score()`, the 120-day mortality, the novel-situation probe.

---

---

---

---

# Experiment 022 — wiring semantic memory into decisions: P1 passes, P2 does not

> Date: 2026-08-13 / 14
> **Preregistration (frozen before any code change): [[Experiment 022 preregistration — wiring memory into decisions]]**
> Every result, verdict and mid-course implementation correction is recorded in that document; only conclusions and rules are recorded here.

## 1. What was done

`knowledge` had been write-only (rule 30). This time it is wired into `score()` and
`propose_goals()`, and given a **forgetting rate** (use it or lose it),
adding `KNOWLEDGE_WEIGHT / KNOWLEDGE_GOAL_WEIGHT / KNOWLEDGE_FORGET`.
Regression check: with the three parameters zeroed it **reproduces exactly** 021's 1.27/1.18/1.26/1.07.

★ A prior discovery: **rule 31 was half wrong**. `flags` and `hardship` have long been wired into
`score()` and `propose_goals()` (`sim.py:682/683/685/527/529/534`),
and the only unwired ones are `knowledge` and `memories`. This finding is written into §2 of the preregistration,
and **the expectation for this experiment was lowered in advance** on that basis.

## 2. Results

On the preregistration-reserved seeds 20000–21499, N=1500:

```
P1 (ratio > 1 with all floors off)        ✅ pass
  022 off  1.007 [0.969, 1.043]  p=0.824 n.s.   ← a complete zero on the reserved block
  022 on   1.058 [1.029, 1.102]  p=0.0001 ***

P2 (deleting knowledge at transplant should collapse it by ≥0.05)   ❌ fail
  ① delete nothing        1.058 [1.029, 1.102]
  ② delete knowledge only 1.047 [1.011, 1.083]   a drop of only 0.011, CIs overlapping
  ④ delete flags only     1.047 [1.001, 1.074]   ← drops by exactly the same amount
  ⑤ delete all three      1.040 [0.997, 1.068]  p=0.0707 n.s.
```

**By the preregistered decision rule: P1 hits and P2 does not → the knowledge channel is not claimed.**

## 3. ★ The rules from experiment 022 ★

39. **Wiring changes the speed of differentiation, not the retention mechanism.** Once semantic memory enters `score()`,
    the balls of the two worlds separate further **during development**; what remains after the transplant lives in the trait vector
    and is almost independent of whether knowledge is still there (deleting all of it costs only 0.011).
    **"Persistence" and "magnitude of differentiation" are two different things.**

40. **Deleting knowledge and deleting flags cost the same.** Semantic memory is not a special carrier,
    merely one more equivalent discrete marker — consistent with the prior expectation in §2 of the preregistration.

41. **Episodic memory is still a complete no-op.** The variant deleting only memories is **bit-identical** to deleting nothing.
    The episodic half of rule 31 still holds.

## 3b. The relaxation test — ⚠ **unanswered, destroyed by mortality** (`relaxation_test.py`)

The question P2 left open: is the 1.040 remaining after deleting everything persistence, or "30 days is not enough to drift back"?
Run to 120 days and measured in three independent 30-day windows (all floors off, 022 on):

```
                    n      loss    ratio   95% CI
① delete nothing
  days  30– 60    1388    7.5%   1.058  [1.030, 1.103]  ≠1
  days  60– 90    1163   22.5%   1.100  [1.056, 1.135]  ⚠
  days  90–120     832   44.5%   1.109  [1.067, 1.160]  ⚠
⑤ delete semantic+episodic+flags
  days  30– 60    1394    7.1%   1.040  [0.995, 1.069]  contains 1.0
  days  60– 90    1138   24.1%   1.100  [1.057, 1.145]  ⚠
  days  90–120     787   47.5%   1.150  [1.104, 1.218]  ⚠
```

**Neither hypothesis is confirmed: the ratio rises rather than falls. But that rise is almost certainly a survivor effect.**

- The loss goes 7.5% → 22.5% → **44.5%**. The last two windows are far past the 15% threshold and are **unusable**.
- The situation of rule 32 fits exactly: *the survivors are precisely "the balls that did not run off", which is the very property being measured*.
  Those that died are mostly the kind that run into the distance and do not hoard — which is exactly the direction of differentiation.
  **The larger between-group difference left after filtering them out was created by selection, not by time.**
- The only usable window is the first: ① = 1.058, significantly ≠1, and **⑤ = 1.040 with a CI containing 1.0**.
  That is, in the one clean window, deleting everything leaves it **unable to stand**.

> ### ★ Rule 42: running longer cannot answer the relaxation question; fix the mortality first ★
> All floors off in the baseline world gives a 120-day paired loss of 44.5% (020 recorded 24.5% for the full architecture).
> At that loss rate, any long-horizon conclusion is a function of selection effects.
> **要回答"差异会不会漂回去"，必须先把 120 天损失压到 <15%，
> 而不是把窗口拉更长。**

⚠ 因此 P2 剩下的那个 1.040 **仍然悬着**：既没被证明是残留假象，
也没被证明是真持久。论文里只能报第一窗、并注明长时程不可测。

## 3c. ★ 死亡率诊断：两个大发现 ★（`mortality_diagnose.py`）

400 种子 × 2 世界 × 120 天，移植到基准：

```
条件                          死亡率    死时在追求
完整架构 + 022 打开             7.6%    recover 72% / stock_food 28%
地板全关 + 022 打开            22.1%    stock_food 79% / recover 21%
地板全关 + 022 关闭            53.9%    stock_food 62% / recover 38%   ← 最惨
完整架构 + 022 关闭            13.0%    recover 53% / stock_food 47%
```

### 发现一：死因是【睡眠死亡螺旋】，不是"立错了志向"

四档的死亡剖面完全一致：**死时体质 0、饥饿 74–87、存粮 0.5**，
而死前 10 天**睡眠占 53–56%**（幸存者 41–49%），
`gather_material` 只有 0.2–2.8%（幸存者 9–18%）。

**它们不是没想着找吃的**（62–79% 死时正在追求 `stock_food`），
**是没时间醒着。** 机制在 `act()`：

```python
eff = 0.35 + 0.65 * self.condition / 100     # 体质差 → 睡再久也恢复不过来
```

体质掉下去 → 睡眠效率降到 0.35 → 需要睡 3 倍的时间 → 白天没了 →
采不到东西 → 更饿 → 体质更差。**这是个没有出口的正反馈陷阱。**
`sleep` 打分是 `(100−energy)×0.9`，饥饿 80 时 `gather_food` 只有约 38 分，
**睡眠永远赢。** 死亡集中在第 75–105 天，是慢性螺旋不是急性事件。

> ### ~~★ 规则 43：饿到极限时，生存行动必须压过睡眠 ★~~
> ### ❌ **规则 43 已撤回（2026-08-14）—— 见 3d 节，因果推反了**
> ~~这是规则 27 的同类问题、另一个位置。~~
> **睡眠不是死因，是症状。** 三种改法实测全部让死亡率变高，见下。

### ⚠ 发现二：地板消融是**被污染的**，这直接动摇 021 第 3 节

```
完整架构 13.0%  →  地板全关 53.9%     （022 关闭）
完整架构  7.6%  →  地板全关 22.1%     （022 打开）
```

**关掉 `trait_identity` / `trait_floor` 把死亡率翻了 2–4 倍。**
原因：地板把 industry / caution 撑在高位，撑住的是**觅食和筑巢的倾向**。
地板一关，性状漂回中间 → 不再勤劳 → 掉进上面那个螺旋。

> ### ★ 规则 44：地板不只是"持久性机制"，它同时是【生存机制】 ★
> `persistence_ablation.py` 关掉地板时，**同时关掉了两样东西**，
> 于是测到的 1.007 / 1.044 里混着**差异化死亡造成的幸存者偏差** ——
> 它不是"去掉硬编码之后的纯持久性"。
>
> **021 第 3 节、022 的 P1/P2 全部受此影响。**
> 结论方向大概率不变（那些档的 60 天损失只有 4–8%），
> 但"地板全关"这个对照**本身不干净**，必须在修完死亡率后重跑。

### 顺带：022 把死亡率砍了一半以上（53.9% → 22.1%）

语义记忆接进决策之后，球更会照顾自己（知道要囤粮、要修房子）。
这是 022 独立于 P1/P2 的一个正面结果，**而且它是行为层的真实改善**，
不是指标游戏。

## 3d. ★ 三种改法全部失败，规则 43 撤回 ★（`fix_compare.py`）

按规则 43 做了三种候选改法，参数化进 `sim.py`（默认全关）：
A `SLEEP_SUPPRESS` 压制睡眠意图 · B `HUNGER_URGENCY` 抬高觅食急迫度 ·
C `SLEEP_EFF_FLOOR` 抬高睡眠效率下限。

```
改法              死亡%完整   死亡%无地板   比值 完整              比值 无地板
现状               18.7%      40.7%    1.086 [1.043,1.162]  1.097 [1.031,1.160]
A 压睡眠 0.5        19.7%      54.7%    1.084 [1.036,1.160]  1.108 [1.046,1.178]
A 压睡眠 1.0        21.7%      56.7%    1.086 [1.041,1.166]  1.110 [1.048,1.182]
B 抬急迫 25         23.0%      62.3%    1.098 [1.036,1.153]  1.114 [1.057,1.199]
B 抬急迫 50         26.0%      65.3%    1.090 [1.034,1.175]  1.123 [1.060,1.192]
C 睡眠下限 0.60      23.7%      76.7%    1.117 [1.054,1.184]  1.115 [1.053,1.193]
C 睡眠下限 0.80      31.0%      81.0%    1.133 [1.067,1.208]  1.126 [1.061,1.205]
A0.5+C0.6          27.0%      79.7%    1.099 [1.044,1.181]  1.122 [1.061,1.206]
```

**八档没有一档降低死亡率，全部升高。C 尤其惨（40.7% → 81.0%）。**

C 是决定性的反证：抬高睡眠效率 = 睡得更值 = 需要睡得更少 = 白天更多，
按规则 43 的逻辑死亡率应该**降**，实测**翻倍**。

> ### ★ 规则 45：诊断表里"死者做得多的事"不是死因，可能是症状 ★
> `mortality_diagnose.py` 显示死者睡眠占 53–56%、幸存者 41–49%，
> 我据此推出规则 43。**推反了**：体质↓ 同时导致 睡眠↑ 和 死亡，
> 是经典的共同原因混淆。**睡眠是保命的，不是致命的** ——
> 压制它、或者让它变得"不必要"，球就把时间花在探索上，死得更快。
>
> 教训：诊断出相关之后，**必须用一个方向相反的干预去证伪**才能称因果。
> 这次是 C 那一档救了我们。

## 3e. 真因：体质是单调漏斗，这个世界没有稳态

60 颗种子跑到 120 天（地板全关，022 打开），逐段取均值：

```
        世界食物   体质    精力    勤劳
幸存 第 35天   3.20   70.8   39.7   72.2
     第 60天   3.63   53.0   38.7   78.1
     第 90天   4.09   43.3   41.0   82.5
     第115天   2.91   34.9   40.8   85.4
死亡 第 35天   3.84   53.6   37.0   67.4
     第 60天   3.77   31.3   30.4   71.0
     第 90天   3.07   15.5   33.0   79.0
     第115天   0.64    2.8   53.0  100.0
```

三件事一目了然：

1. **世界食物没有枯竭**（一直在 3–4）。不是资源问题。
2. **精力一直在 30–40**。不是精力问题，睡眠机制没有失灵。
3. **体质对所有球单调下降 —— 包括幸存者**（70.8 → 34.9，还在掉）。
   **勤劳反而一路上升**（死者最后顶到 100）—— 它们拼尽全力，仍然在掉。

> ### ★ 规则 46：这个世界没有可持续均衡，所有球都在死亡倒计时上 ★
> 体质只有单向漏，没有任何行为能把它拉回来。死亡不是"掉进了陷阱"，
> 而是**"谁的起点低谁先归零"**。跑到 200 天大概会全灭。
>
> 60 天的实验之所以看起来没事（损失 4–8%），只是**倒计时还没走完**。
> **在体质收支修好之前，任何长时程实验都做不了** —— 这不是统计问题，
> 是模型没有稳态。

## 3f. ★ 体质收支表：恢复通道在移植后【完全关闭】★

体质在整个 `sim.py` 里**只有一处**变动（906–910 行），每 tick：

```python
if self.hunger > 70:    self.condition -= 0.40     # 扣
elif self.hunger < 30:  self.condition += 0.16     # 补
# 30 ≤ hunger ≤ 70：什么都不发生 ← 40 分宽的死区
```

扣的速度是补的 **2.5 倍**，中间还有个死区。实测各档 tick 占比（50 种子，
贫瘠世界 → 第 30 天移植到基准，地板全关）：

```
              饿>70    饿<30    死区    净体质/天
幸存 第 0-29天   6.0%   19.6%   74.4%    +0.18
     第30-59天   7.1%    2.1%   90.8%    −0.61
     第60-89天   1.7%    1.1%   97.2%    −0.12
     第90-119天  1.6%    0.0%   98.4%    −0.15
死亡 第 0-29天  13.6%   17.9%   68.5%    −0.62
     第30-59天   7.5%    0.0%   92.5%    −0.72
     第60-89天   6.2%    0.0%   93.8%    −0.59
     第90-119天 27.4%    0.0%   72.6%    −2.63
```

> ### ★ 规则 47：系统稳定在死区里，恢复通道等于不存在 ★
> **移植之后「饿<30」的时间占比塌到 0–2%**（发育期还有 18–20%）。
> 也就是说 **+0.16 那条恢复通道几乎从不触发**，
> 系统 90–98% 的时间待在什么都不发生的死区里，
> 只被偶发的 −0.40 一点点掏空。
>
> **没有任何球在第 30 天之后有正收支** —— 最健康的幸存者也是 −0.12/天。
> 这不是"某些球运气差"，是**结构上不存在稳态**。
> 死亡率因此完全由"起点体质 + 时间"决定，与行为策略基本无关 ——
> 这也解释了为什么三种行为层改法（3d 节）全部无效：
> **它们动的是分子，问题在分母。**

### 定量目标（改之前先定死）

幸存者 97% 的 tick 在死区、1.7% 在扣、1.1% 在补。要做到净收支为零，
需要在死区里补上约 **0.005/tick**（或等价地把恢复阈值从 30 抬到 ~55，
让死区的一部分变成恢复区）。

三个候选方向（**尚未实现，等定夺**）：

- **① 抬高恢复阈值** `hunger < 30` → `< 55`。最小改动，直接把死区削掉一半。
- **② 死区也缓慢恢复**（例如 +0.05/tick），保留"吃饱才养得快"的层次。
- **③ 恢复不只看饥饿**，让住所 / 睡眠也贡献体质。最贴近直觉，改动最大。

⚠ 三个都会改变**全部历史数字**（011–022）。而且按规则 45 的教训，
**必须同时测死亡率和比值**，任何让球活下来但抹平世界差异的改法都是失败。

## 3g. ★ 修法对比：只有「阈值 65」两项判据全过 ★（`cond_compare.py`）

```
修法               死亡%完整   死亡%无地板   比值 完整              比值 无地板
现状                18.7%⚠     40.7%⚠   1.086 [1.043,1.162]  1.097 [1.031,1.160]
① 阈值 45           15.7%⚠     46.3%⚠   1.082 [1.042,1.169]  1.114 [1.057,1.195]
① 阈值 55           13.7%      43.3%⚠   1.096 [1.044,1.177]  1.130 [1.063,1.206]
① 阈值 65            5.0%       7.3%    1.142 [1.068,1.218]  1.150 [1.072,1.220]  ★
② 死区 +0.03        12.0%      40.3%⚠   1.087 [1.045,1.171]  1.112 [1.057,1.195]
② 死区 +0.06        10.0%      35.3%⚠   1.100 [1.052,1.192]  1.129 [1.060,1.206]
③ 住所 +0.05         7.7%      34.3%⚠   1.099 [1.052,1.185]  1.112 [1.050,1.189]
③ 住所 +0.10         6.7%      34.0%⚠   1.117 [1.078,1.187]  1.130 [1.053,1.188]
①55 + ③0.05        12.0%      45.7%⚠   1.119 [1.048,1.199]  1.139 [1.075,1.215]
```

**只有 ①阈值65 把「无地板」那列压下去了（40.7% → 7.3%）。** 其余八档
在完整架构上都有改善，在无地板上**全部无效**（34–46%）——
而无地板正是规则 44 的污染源，治不好它，021 第 3 节和 022 就重跑不了。

### ★ 意外：比值没有塌，反而普遍上升 ★

事前担心的是"体质变好 → 贫瘠世界压力变小 → 世界差异被抹平"。
实测**九档的比值全部 ≥ 现状**，①65 最高（1.142 / 1.150）。

> ### ★ 规则 48（假说）：生存压力压缩行为方差 ★
> 快饿死的球没有选择，只能觅食；吃饱的球才有余裕表达性格。
> 死亡率一降，**真实的分化幅度反而显露出来**了。
> 这也说明此前 60 天窗口里的比值是被**幸存者筛选压低**的
> —— 与长时程窗口里被抬高的方向相反，两种偏差都存在。
> ⚠ 这条目前只是解释，没有直接检验。

### ⚠ 55 → 65 之间是个悬崖，必须先探清楚

无地板死亡率：阈值 55 时 **43.3%**，阈值 65 时 **7.3%**。
中间没有过渡，说明**均衡饥饿度正好落在 55–65 之间**，
阈值一旦越过它，绝大多数 tick 就从死区翻进恢复区。

**这是个脆弱点**：任何改变均衡饥饿度的参数（HUNGER_RATE、FOOD_NUTRITION、
世界食物再生）都可能让死亡率重新爆掉。
**采用之前必须先扫 58/60/62/65/68/70 把悬崖的位置和陡度测出来**，
并确认选的值离悬崖有足够余量。

> ⚠ **上面这段的诊断是错的，见 3h。** 没有悬崖，也不需要扫阈值。
> "均衡饥饿度卡在 55–65" 这个解释被 `cliff_probe.py` 直接证伪
> （零点在 T≈38）。真相是**丰富世界那一支有个怠惰谷**（规则 49）。
> 保留原文是因为它演示了一个典型错误：**把两条曲线的差解释成一条曲线的阈值。**

## 3h. ★ 悬崖是假的：真相是怠惰谷 + 一半的选择效应 ★
（`cliff_probe.py` · `death_split.py` · `rule48_test.py`）

3g 留了两个待办：扫阈值定悬崖、验规则 48。两个都做了，
**但扫阈值这件事本身被证明是没必要的** —— 悬崖可以直接算出来，而且它不存在。

### 1. 不用扫：净收支是饥饿分布的泛函

体质只在 `sim.py:924-930` 一处变动，所以

```
净体质/tick(T) = COND_RECOVER·P(饿<T) − COND_DRAIN·P(饿>70)
               = 0.16·P(饿<T) − 0.40·P(饿>70)
```

一次分布测量就能预测**整条**阈值曲线。测了（N=60，贫瘠→基准@30，
只统计移植后的 tick），用「现状」的分布外推：

```
T =        30      40      45      50      55      60      65      70
净/tick  −0.009  +0.003  +0.021  +0.048  +0.082  +0.111  +0.133  +0.144
```

**零点在 T≈38，不在 55–65。** 现状（T=30）的 −0.009/tick = −0.22/天，
和 3f 实测的 −0.12 ~ −0.15/天同量级 ✓ —— 规则 46「没有稳态」由此有了闭式来源。

按这条曲线，抬到 45 就该全好了。但 3g 实测 45 档还是 46.3%。**矛盾在哪？**

### 2. ★ 负反馈：饥饿分布会自己上移，吃掉六成修复 ★

因为分布不是外生的。逐档实测（完整架构）：

```
              死亡%    饿的中位   P(饿>70)   p5–p95 宽   用【自己】的分布算 T 处净收支
现状          16.7%     53.8       2.8%       32.5      −0.009  ← 负，无稳态
① 阈值 55      1.7%     56.2       9.0%       35.0      +0.030
① 阈值 60      1.7%     58.8      11.6%       32.5      +0.043
① 阈值 65      1.7%     58.8      14.2%       35.0      +0.056
③ 住所 +0.10   5.0%     56.2       7.4%       32.5      （同上表口径）
```

体质一好，`sim.py:733` 的 `urgency = max((饿−60)/40, (85−体质)/85, 0)` 就松了 ——
球少觅食，**饥饿中位上移 5 分、P(饿>70) 翻五倍**，把抬阈值的收益吃掉约 60%
（T=65 处：外推 +0.133，实际只剩 +0.056）。

> ### ★ 规则 49（上）：体质修复会被行为负反馈部分抵消 ★
> `urgency` 同时读体质和饥饿，所以"让球更健康"会直接"让球更懈怠"。
> 任何体质层的改动都要按**自己那档的饥饿分布**重算收支，
> 拿现状的分布外推会高估两倍以上。
>
> 好消息：负反馈 = 自稳。3g 担心的"任何动 HUNGER_RATE / FOOD_NUTRITION
> 的参数都会让死亡率爆掉"**不成立** —— 系统对扰动有回复力。

顺带：p5–p95 宽度稳定在 30–35 分，和 `FOOD_NUTRITION = 20` 同量级 ——
饥饿确实是一条窄锯齿，两个阶跃阈值（70 和 T）都卡在这条锯齿里。
结构脆弱性是真的，但被负反馈软化了。

### 3. ★ 规则 49（下）：怠惰谷 —— 中间档更致命，而且只打丰富世界 ★

3g 的配对死亡率把两个世界糊成了一个数（`fix_compare.py:52` 的 `live`
要求两支都活）。拆开（`death_split.py`，N=300，120 天）：

```
                  ── 完整架构 ──          ── 地板全关 ──
                丰富    贫瘠   推算配对   丰富    贫瘠   推算配对   3g实测
现状            0.7%   18.7%   19.2%    24.3%   23.3%   42.0%    40.7%
① 阈值 55       7.7%    6.3%   13.5%    36.3%   14.0%   45.2%    43.3%   ← 丰富↑12pp
① 阈值 60       3.7%    5.3%    8.8%    18.0%    8.0%   24.6%      —
① 阈值 65       0.7%    4.3%    5.0%     2.0%    5.3%    7.2%     7.3%
③ 住所 +0.10    0.0%    6.7%    6.7%    25.3%   16.0%   37.3%    34.0%
```

先看对账：「推算配对」= `1−(1−p丰)(1−p贫)`，与 3g 实测**每一格差 ≤3.3pp**。
两支近似独立，且这条独立的新流水线复现了 cond_compare —— 交叉验证通过。

再看真相。**贫瘠世界那一支是单调改善的**（23.3 → 14.0 → 8.0 → 5.3）。
爆掉的是**丰富世界**：`24.3% → 36.3%（T=55） → 18.0%（T=60） → 2.0%（T=65）`。

> ### ★ 规则 49：抬恢复阈值要**越过一个谷**，谷只存在于富养的球身上 ★
> 机制接规则 49（上）：抬阈值 → 体质↑ → urgency 松 → 怠惰 → 饥饿上移。
> **贫瘠世界养出来的球勤劳地板高（规则 47 的 hardship 棘轮），扛得住怠惰；
> 丰富世界的球没有这个刹车，一松就滑进 P(饿>70)。**
> 中间档（55/60）恢复的收益还没盖过怠惰的损失 → 净变差。
> 到 65 才越过谷。
>
> 所以 3g 看到的"55→65 的悬崖"是**怠惰谷的远侧坡**，不是均衡饥饿度的阈值。
> **两条曲线（富/贫）的差被误读成了一条曲线的阶跃。**
>
> 推论：**①阈值 65 的余量方向和 3g 想的相反** —— 危险的是往下调（掉回谷里），
> 往上调是安全的。65 离谷底（55）有 10 分，可以采用。

### 4. hardship 棘轮没被掐掉（这是 3g 判据表测不到的那项）

抬恢复阈值 = 体质常驻高位 = `sim.py:936` 的 `deficit=(100−体质)/100` 趋零
= `sim.py:941` 的 `trait_floor ← hardship_norm × 22` 可能失效。
而 `sim.py:890` 体质 ≥99.5 时 hardship 还会**遗忘**。
**这条棘轮正是 021 第 3 节和 022 在研究的东西，两条判据都看不见它**
（无地板那一列本来就把地板关了）。实测（完整架构，只算幸存者）：

```
              末体质  hardship  hnorm   地板−身份  fears_hunger 触发率
现状           34.9    48.5     0.997    78.18        100%
① 阈值 55      55.1    32.9     0.931    77.15         93%
① 阈值 60      64.1    27.5     0.866    76.40         88%
① 阈值 65      68.6    23.5     0.827    75.68         86%
③ 住所 +0.10   61.9    32.2     0.843    76.15         88%
```

**基本证伪了，①65 可以采用**：hnorm 只从 1.00 掉到 0.83，
棘轮强度 21.9 → 18.2 分，没被掐掉。但挖出两件该记的事：

> ### ★ 规则 50：hardship 棘轮是二值开关，不是渐变信号 ★
> `hardship_norm = 1 − exp(−hardship/1.5)`，`HARDSHIP_SCALE = 1.5` 意味着
> 累积约 5 天赤字就顶到 1.0 —— 而实测 hardship 是 **23–48**。
> **所有球、所有档位都饱和在天花板上。**
>
> 那么地板携带的个体差异就**不可能**来自"苦吃了多少"，只能来自
> `_hardship_anchor`（`sim.py:938`）——**第一次挨饿那一刻的性格快照被冻住**。
> 这正是第 4 节那句"持久性只能来自作用于性状变量本身的棘轮"的机制层版本，
> 可以直接写进论文：**地板不是记忆，是一次不可逆的采样。**
>
> ⚠ 要盯的量因此不是 hnorm 均值，而是 **fears_hunger 触发率：100% → 86%**。
> ①65 让 14% 的球**从不进入棘轮**，这会改变 021 第 3 节消融的分母构成。

> **⚠ 上面这句"14% 从不进入棘轮"是错的，023 第 7 节改正。**
> `fears_hunger` 和 `_hardship_anchor` 是**两个不同的事件**：
> anchor 在 `sim.py:965` 首次 `condition < 100` 时就写入（近乎全员），
> `fears_hunger` 要 `hardship_norm ≥ 0.5`（`HARDSHIP_STORY_AT`）才记，是**叙事路标**。
> 实测 anchor 存在率 v2/v3 **逐位相同**（96.5% / 98.2% / 97.5%）——
> 掉的只有路标。**棘轮本身没有少人进，改变的是采样时刻。**

### 5. ★ 规则 48 降级：一半是选择效应 ★（`rule48_test.py`）

3g 的比值每档算在**各自的幸存子集**上，死亡率一降进入统计的就是另一批球 ——
而规则 48 想说的恰恰是"筛掉谁会改变比值"，两者完全缠在一起。三个改进：
① 共同种子集（全档 × 两世界都活）；② 逐种子配对 δ + 符号置换（3g 比的是
N_BOOT=400 的 CI 重不重叠，本来就判不出显著）；③ 各档共用同一组对手索引。

```
              ── 完整架构 (n共同=741/800) ──        ── 地板全关 (n共同=747/800) ──
            自己集比值  共同集比值  Δvs现状   p      自己集比值  共同集比值  Δvs现状   p
现状          1.098      1.090      —       —        1.082      1.072      —       —
① 阈值 55     1.109      1.092   +0.0027  0.196 n.s.  1.101      1.085   +0.0048  0.003 **
① 阈值 60     1.110      1.100   +0.0053  0.027 *     1.114      1.091   +0.0068  0.001 ***
① 阈值 65     1.134      1.109   +0.0086  0.002 **    1.114      1.090   +0.0068  0.002 **
③ 住所 +0.10  1.117      1.108   +0.0055  0.000 ***   1.087      1.073   +0.0005  0.662 n.s.
```

> ### ★ 规则 48（修正）：比值确实真升了，但一半是选择效应，且效应很小 ★
> ①65 vs 现状的差：自己集 +0.036 → 共同集 **+0.019**。
> **3g 那个"意外"里约 47% 是选择效应**（无地板列 44%，一致）。
> 剩下的一半是真的：p=0.002，但 **dz 只有 0.11–0.14** —— 极小效应，
> 靠 N=741 的配对才测得出来。
>
> 原假说"生存压力压缩行为方差"方向对，**但不足以支撑 3g 那句"含义不小"**。
> 说"此前 60 天窗口的比值被幸存者筛选压低"是对的，
> 说"真实分化幅度显露出来"则夸大了一倍。
>
> 旁证（不是本脚本测的）：规则 34 说比值估计量 N 小则虚高，
> 现状的有效 N 最小、比值却最低 —— **偏差方向解释不了这个现象**，
> 所以剩下的那一半不是 Jensen 偏差伪装的。

**顺带一个判别信息**：③住所 在完整架构上最强（p=0.0001），
在地板全关上**完全归零**（p=0.66）。说明 ③ 的比值增益**依赖地板机制**，
而 ①65 两边都显著、幅度一致（+0.0086 / +0.0068）——
**①65 的增益不走地板通路**。对 021 第 3 节要重跑的东西来说，
①65 是更干净的选择。

### 6. 结论：采用 ① 阈值 65，标 v3

四条判据现在都过了，且都有机制解释而不只是数字：

| 判据 | 结果 |
|---|---|
| 死亡率（配对，完整/无地板） | 5.0% / 7.2%，两列都 <15% ✅ |
| 比值不塌 | 共同集上反而 +0.019，p=0.002 ✅ |
| 参数余量 | 谷底在 55，65 在谷外；危险方向是**下调**不是上调 ✅ |
| hardship 棘轮存活 | hnorm 1.00→0.83，触发率 100%→86% ⚠ 需在重跑时一并报告 |

"为什么是 65"现在有答案了：**不是扫出来的，是因为 55–60 落在怠惰谷里，
65 是越过谷之后的第一个整十值。** 这句话审稿人能接受。

⚠ **重跑 021 第 3 节 / 022 时必须一并报告 fears_hunger 触发率** ——
v2 是 100%，v3 是 86%，消融的分母变了。

## 4. 对论文的影响

审稿人那句"你不是发现了不可逆性，你是把不可逆性写进去了"**仍未被回答**。
诚实的结论（预注册第 4 节第三档预先写好的）：

> 在本架构中，接到行为上的离散结构（flags、knowledge）不足以维持移植后的
> 个体差异；持久性只能来自作用于性状变量本身的棘轮。

**主线应改为：刻画产生持久个体差异所需的最小机制，并指出离散记忆结构不在其中。**

> ### ★ 预注册这次真的起作用了 ★
> 如果没有事先写死 P2 的阈值，看到 P1 的 1.058 / p=0.0001 几乎必然会宣布成功，
> 然后被审稿人用同一个删除测试打回来。**这段经历本身值得写进论文的 Methods。**

---

## 复现方式

```powershell
cd C:\Users\yinan\Desktop\ai-sandbox
python scenarios.py            # 种群报告
python environment.py          # 环境实验（当下差异）
python transplant.py           # 移植：差异是不是性格
python leveling.py             # ★状态拉平：曲线是发现还是伪影★
python deletion.py             # ★删除阶梯：差异存在哪一层★
python persistence_ablation.py # ★持久性是不是写死的★
python persistence.py          # 单因素持久性 + 机制检验 + 三方向还原
python behavior.py             # 行为层 + 目标层主载体
python paired.py               # 配对实验：数值层
python ablation.py             # 消融：机制贡献 + 零假设自检
python diagnose.py             # 关键经历触发率
python significance.py         # 置换检验（分组比较）
python param_sweep.py          # ★参数随机化集合：效应是不是手调出来的★
python sweep_report.py         # 读 sweep_results.csv，出论文能引的那几句
python significance_main.py    # ★主结论的 p 值（逐种子 δ + 符号置换）★
python test_022_regression.py  # 022 回归：KNOWLEDGE_* 归零须复现 021
python p1_test.py              # 022 P1：接线后地板全关还能不能 > 1
python p2_test.py              # 022 P2：非嵌套删除，是不是 knowledge 撑的
python relaxation_test.py      # 弛豫：剩下的 1.04 是持久还是没漂完
python mortality_diagnose.py   # 死因诊断（⚠ 结论被规则 45 推翻，保留作反例）
python fix_compare.py          # 行为层三改法对比（⚠ 八档全部失败）
python cond_compare.py         # ★体质收支三修法 × 死亡率 + 比值★
python cliff_probe.py          # ★悬崖探针：饥饿分布 + 净收支预测 + hardship 棘轮★
python death_split.py          # ★死亡率拆回单个世界 → 怠惰谷（规则 49）★
python rule48_test.py          # ★规则 48 判别：共同种子集 + 逐种子配对★
python v3_revalidate.py       # ★v3 机制重验：021§3 / 022 P1 / P2 同种子对照 v2★
python anchor_probe.py --verify # ★A：anchor 日 v2/v3 逐种子核对（证伪 023§7.5）★
python anchor_probe.py         # ★B：anchor 内容干预 + 阴性对照（规则 54）★
python sweep.py                # ⚠ 已废弃
python food_sweep.py           # ⚠ 已废弃
```

---

# 实验 023 —— 模型版本化：v2 冻结，v3 分叉

> **分界线。** 今天这一步不是"又一次调参"，而是模型从
> **exploratory architecture** 进入 **论文候选 architecture**。
> 011–022 全部在 v2 下完成，作为开发历史保留；v3 从这里分叉出去。

> Experiments 011–022 were conducted under model v2 and are retained as
> development history rather than overwritten by subsequent model correction.

## 1. v2 冻结

`ai-sandbox/v2_frozen/`（2026-08-15）：改动之前的**完整**源码 + 原始结果
（30 个文件 + `SHA256SUMS.txt` + `README.md`）。自包含，
`cd v2_frozen && python <脚本>.py` 可以直接复现任何 011–022 的历史数字。

⚠ **2306 行以前的旧数字一律保留**，包括已被推翻的（规则 43 被规则 45 推翻、
3g 的"悬崖"被 3h 推翻）。保留原文 + 注明何时被何证据推翻 ——
这个习惯在论文里就是 Methods 里那段"预注册起了作用"的同类材料。

## 2. v3 的定义：只改了一个数

```python
# sim.py
MODEL_VERSION = "v3"
COND_RECOVER_AT = 65.0   # v3: condition-stability correction（v2 = 30.0）
```

逐位对比确认：`v2_frozen/` 与主目录的**唯一可执行差异**就是这个常量
（其余全是注释和新增的 `MODEL_VERSION`）。所以"v2 臂"= 在 v3 代码里设回 30.0，
与跑 `v2_frozen/` 等价 —— 重验脚本就是这么做的。

### 为什么是 65（这一句要能顶住审稿人）

**不是"扫参数发现 65 死亡率最低"**，而是有完整的闭环机制解释（3h 节 / 规则 49）：

```
提高恢复阈值 → condition 改善 → survival urgency 减弱
             → 富养 agent 减少觅食 → 饥饿反升 → 死亡率【上升】= 怠惰谷
             → 到 65，condition 的余量足以跨过这段负反馈区 → 死亡率重新下降

死亡率
  ^
  |        _
  |      _/ \_          ← 怠惰谷（T=55 时丰富世界 36.3%）
  |  ___/     \
  |            \______  ← T=65，2.0%
  +---------------------> COND_RECOVER_AT
     30   55  60  65
```

**65 是越过怠惰谷之后的第一个整十值。**
余量方向也因此明确：**危险的是下调（掉回谷里），上调是安全的。**

> ### ★ 规则 51：闭环系统里"更健康的局部规则"不一定单调提高适应度 ★
> agent 是 behavior–physiology 闭环：`condition ↑ → urgency ↓ → 觅食 ↓ →
> 饥饿 ↑ → 死亡 ↑`。局部直觉（"让身体恢复得更快当然更好"）在闭环里可能反号。
> **ABM / Artificial Life 的参数不能靠局部直觉调**，必须测端到端。
> 这条不是论文主结论，但很适合做 supplementary figure / 模型审计那一节。

## 3. 规则 50 的最终措辞

3h 节测到 `HARDSHIP_SCALE = 1.5` 让 `hardship_norm` 迅速饱和
（实测 hardship 23–48，约 5 天就顶到 1.0），**所有球、所有档位都在天花板上**。
所以机制不是"越饿 → hardship 越强 → 性格变化越多"，而是：

```
首次 condition < 100（sim.py:965）—— 早，且近乎全员
        ↓ 一次性写入
_hardship_anchor = 当时的 trait 快照        ← write-once，此后不再改写
        ↓
trait_floor ← min(anchor[t] + w×22×hnorm, 90)（sim.py:970）
```

> ### ★ 规则 50（终稿 · 已按实验 024 修订）★
> **Hardship consolidation is initiated by an early, near-universal,
> write-once capture of the agent's trait state. The v3 condition
> correction does not alter the timing of this capture; instead, it alters
> the subsequent accumulation and behavioral expression of hardship.**
>
> hardship 机制通过一次**早期、近乎普遍发生的 write-once 性格快照**启动。
> v3 的体质修正**并没有改变快照写入时间**，而是改变了快照写入之后
> hardship 的累积及其行为表达。
>
> 证据：实验 024 A 部分，anchor 首次写入日 v2/v3 **300/300 逐种子相同**
> （中位第 6 天 / 第 12–14 天，取决于架构）。机制上也必然如此 ——
> anchor 写入之前两版逐位相同。

> ### ★ 规则 50b：`fears_hunger` 是 narrative marker，不是固化时刻 ★
> 它只在 `hardship_norm ≥ 0.5`（`HARDSHIP_STORY_AT`）时才记，
> 比 anchor 晚 13–20 天。它最多告诉你
> **"agent 什么时候积累到了足够强的 hardship，可以在叙事层面称为'怕挨饿'"**，
> **不是**"人格什么时候被固化"。
> ⚠ 以后**不许**再用 `fears_hunger` 的日期或触发率去论证 consolidation ——
> 023 §7.5 就是这么翻车的。

**这条已经开始回答论文那个大问题："历史到底是怎么被保存的？"**
答案看起来不是传统 episodic memory，不是 semantic knowledge，
也不是连续累积的 hardship 标量，而是 **event-triggered consolidation**。
—— 这正好接得上后面要做的 state transplant。

## 4. 重验的性质（必须写清楚，否则会被当成 confirmatory）

我们已经看过数据、改了模型，而且 65 本身是诊断实验选出来的。
所以接下来这一步的正确名字是：

> **v3 mechanistic revalidation / robustness reanalysis** ——
> 不是新的 confirmatory experiment。

用**原来的种子**重跑是优势不是问题：唯一变量是 `COND_RECOVER_AT 30 → 65`，
同种子对照能干净地把"结论变了"归因到这一个数，而不是归因到"换了一批球"。
**但它不能承担最终确认。** 最终确认要等模型完全冻结后，
用一段**从未运行过的新种子块**做。

### 不重跑 011–020

011–020 是建立模型、发现问题的 development history，任务已经完成。
需要重新验证的只有**依赖 survival confound 的因果主张**：

| 重验项 | 问题 |
|---|---|
| 021 §3 | 地板消融：`−全部地板①②` 还站不站得住 |
| 022 P1 | 接线后无地板档比值 > 1 |
| 022 P2 | 删掉 knowledge 后 persistence 是否消失 |
| 规则 50 诊断 | fears_hunger 触发率 / 首次触发日 / anchor 存在率 |

Methods 里的说法：*模型发现结构性 survival confound 后完成修正，
然后重新验证所有依赖该 confound 的核心结论。*

### 整条路线

```
v2 → 发现 mortality / survivor confound → 机制诊断 → 发现怠惰谷
   → v3 (COND_RECOVER_AT 65) → 旧种子 mechanistic revalidation
   → 冻结全部模型 + 预测 → 全新 seeds final confirmation
```

**这比"第一次什么都设计对了"更可信。**

## 5. 原始结果的版本标记（`resultmeta.py`）

v2 → v3 从 CSV 内容上完全看不出来。所以约定：任何写盘的原始结果，
前五列固定是 `model_version / experiment / condition / seed / cond_recover_at`
（最后一项冗余但值得 —— 出问题时不用翻代码）。`param_sweep.py` 已接入。

⚠ 已有的 `sweep_results.csv` / `holdout.csv` 是 v2 的，表头没有这几列。
v3 要重扫的话换个 `--out`，**不要混进同一个文件**。

## 6. ⚠ fears_hunger 触发率下降怎么处理

3h 测到完整架构下触发率 100%（v2）→ 86%（v3）。这必须认真处理：

- **主效应一律报全部预定义种子**，不能为了让效应好看只分析触发者。
  "有没有触发 fears_hunger"**本身就是模拟过程产生的结果**，
  事后只取触发者会重新制造 selection 问题 —— 和我们刚修掉的是同一类错误。
- 正确写法：`86% triggered the hardship mechanism.`
  然后把触发者内部的结果作为 **secondary descriptive analysis**。
- 021§3 重跑时同时报告：
  `floor ON` → 触发率 / 首次触发日 / anchor 存在率 / 存活率；
  `floor OFF` → 存活率。


## 7. ★ v3 机制重验结果 ★（`v3_revalidate.py`，N=1500，同种子）

74 个任务 / 10 进程 / 约 40 分钟。唯一变量 `COND_RECOVER_AT: 30 → 65`。

**先验证流水线**：v2 臂跑出 022 P1 = **1.058 [1.029, 1.102] p=0.0001**，
与 022 正文发表的数字**逐位一致** ✓。所以下面的 v2/v3 差是真的差，不是实现差。

### 7.1 修正确实生效（死亡率）

```
                        v2 死亡    v3 死亡
022 P1 完整架构           8.1%      4.3%
022 P1 −全部地板①②        7.5%      4.1%
021§3 有效 n（/1500）    1411       1430
```

60 天窗口上死亡率**减半**。（120 天上的效果见 3h：40.7% → 7.2%。）

### 7.2 022 P1：过，而且更强

```
条件                        v2                          v3
022关闭 −全部地板①②  1.007 [0.969,1.043] n.s. ✗   1.013 [0.971,1.049] n.s. ✗
022关闭 完整架构      1.106 [1.068,1.135] ***  ✓   1.124 [1.090,1.166] ***  ✓
022打开 −全部地板①②  1.058 [1.029,1.102] ***  ✓   1.090 [1.047,1.128] ***  ✓  ← P1 判据
022打开 完整架构      1.066 [1.035,1.101] ***  ✓   1.124 [1.077,1.161] ***  ✓
```

**P1 在 v3 下依然通过，且从 1.058 抬到 1.090。** 与 3h 规则 48 的方向一致
（修掉 survival confound 之后效应**略微变大**），幅度也相称。

### 7.3 022 P2：仍然不过 —— 预注册的结论不变

```
移植那刻删掉什么          v2 比值   落差      v3 比值   落差
① 什么都不删（=P1）        1.058     —        1.090     —
② 只删语义 knowledge       1.047   −0.011     1.057   −0.033
③ 只删情节 memories        1.058    0.000     1.090    0.000   ← 仍是逐位 no-op
④ 只删 flags               1.047   −0.011     1.038   −0.052
⑤ 删语义+情节+flags        1.040   −0.018     1.029   −0.061
```

**P2 判据（②比①低 ≥0.05 且 CI 不重叠）：v2 ✗，v3 仍 ✗**
（落差 0.033 < 0.05，CI [1.047,1.128] 与 [1.015,1.095] 重叠）。

> ### ★ 预注册结论在 v3 下原样成立 ★
> "接到行为上的离散结构不足以维持移植后的个体差异" —— 这句**不是**
> survival confound 的产物。修掉 confound 之后 P2 依然不过。
> 这是今天最值钱的一条：**它把主结论从"可能是伪影"升级成"经过修正后仍成立"。**

但有两处必须改动已有规则：

> ### ★ 规则 40（修正）：在 v3 下，flags 掉得比 knowledge 多 ★
> v2 里删 knowledge 和删 flags **掉得一样多**（各 −0.011），
> 据此说"语义记忆不是特殊载体，只是又一个等价的离散标记"。
> v3 下两者分开了：**flags −0.052 > knowledge −0.033**。
> "等价"那半句要撤回；"knowledge 不是特殊载体"那半句仍然成立
> （它反而是三者里较弱的一个）。

> ### ★ 规则 41 加强：情节记忆在 v3 下仍是**逐位** no-op ★
> ③ 与 ① 在两个版本上都完全相同（1.058 / 1.090，一位不差）。
> 跨越一次模型修正还能逐位相同，这条可以写死了。

⚠ 一个要留意的量：⑤（三个全删）在 v2 只抹掉超出 1 的部分的
**31%**（0.018/0.058），在 v3 抹掉 **68%**（0.061/0.090）。
也就是说 v3 下离散存储承担的份额**变大**了 —— 但 ⑤ 的 CI 仍含 1.0
（1.029 [0.983,1.062] p=0.217），所以还不能反过来说"离散结构其实是载体"。
**这是留给 final confirmation 的问题。**

### 7.4 021 §3 地板消融：诚实降级站得住，但两个种子块不一致 ⚠

```
                          v2                       v3
seeds 0+     完整架构    1.132 p=.0001 ***       1.172 p=.0001 ***
seeds 0+     −全部地板   1.032 p=.078  n.s.      1.036 p=.057  n.s.
seeds 10000+ 完整架构    1.127 p=.0001 ***       1.148 p=.0001 ***
seeds 10000+ −全部地板   1.034 p=.064  n.s.      1.057 p=.0029 **   ← ⚠
```

**主结论：规则 33 的撤回仍然正确。** 地板一关，比值掉到 1.03–1.06，
而且**这次不能再用"死亡率污染"解释了** —— 021 第 3 节末尾那两条路
（诚实降级 / 修机制再测）现在有了答案：**机制修了，效应还是没回来。**

> ### ★ 规则 52 ⚠：无地板档在两个种子块上给出不一致的显著性 ★
> v3 下 seeds 0+ 是 1.036 n.s.，seeds 10000+ 是 1.057 p=.003。
> **同一个模型、同样 N=1500、只换种子块，结论就翻。**
> 说明真值就在检出限附近，单个种子块的显著性**不可信**。
> 论文里报这一档必须**同时报两个块**，不能只挑显著的那个。
> 这个悬案交给 final confirmation（全新种子块）去定。

### 7.5 规则 50 的诊断 ⚠ 本节的解释已被实验 024 推翻，表本身有效

```
版本  世界    架构      存活%   fears_hunger%  anchor%  fears_hunger日中位
                                                       ↑ 这一列不是 anchor 日
v2   丰富   完整架构   100.0%     95.1%       98.5%        20
v3   丰富   完整架构   100.0%     94.3%       98.5%        27
v2   贫瘠   完整架构    91.9%     92.7%       98.2%        23
v3   贫瘠   完整架构    95.7%     83.0%       98.2%        31
v2   贫瘠   地板全关    92.5%     92.5%       97.5%        26
v3   贫瘠   地板全关    95.9%     85.9%       97.5%        33
```

**★ 更正 3h ★** 我在 3h 写过"①65 让 14% 的球从不进入棘轮"，**这是错的**。
`_hardship_anchor` 和 `fears_hunger` 是两个不同的事件：

- `_hardship_anchor`（`sim.py:965`）：首次 `condition < 100` 就写入 → **近乎全员**
- `fears_hunger`（`HARDSHIP_STORY_AT = 0.5`）：要累积约 1 天满赤字 → **叙事路标**

实测 **anchor 存在率 v2/v3 逐位相同**（96.5% / 97.5% / 98.5% / 98.2%），
掉的只有路标（92.7% → 83.0%）。

> ### ~~★ 规则 50 的推论：v3 移动的是 consolidation 的**时刻** ★~~ ⚠ 撤回
> ~~首次触发日中位 20–26 天 → 27–33 天……采得更晚 → 采到更成熟的性格。~~
>
> **⚠ 这条整段撤回，见实验 024 A 部分。** 上表那一列 `首次触发日` 记的是
> **`fears_hunger`**，`v3_revalidate.py` 根本没有记录 `_hardship_anchor`
> 的首次写入日 —— 我拿路标的日期去论证快照的日期，是张冠李戴。
>
> 而且从代码上这个推论**本来就不可能成立**：anchor 写在首次
> `condition < 100` 的那个 tick，condition 只能被 `COND_DRAIN`（饿>70）
> 拉下 100；在 condition 仍等于 100 时，抬高 `COND_RECOVER_AT` 带来的
> gain 全被 `clamp` 吃掉。**anchor 写入之前 v2/v3 逐位相同**，
> 所以 anchor 日必然相同。实验 024 实测：**300/300 逐种子相同**。

### 7.6 状态小结

| | v2 | v3 | 结论 |
|---|---|---|---|
| 022 P1 | 1.058 ✓ | 1.090 ✓ | 通过，更强 |
| 022 P2 | ✗ | ✗ | **预注册结论不变** |
| 021§3 无地板 | 1.032/1.034 n.s. | 1.036 n.s. / 1.057 ** | 降级站得住，⚠ 块间不一致 |
| 情节记忆 | 逐位 no-op | 逐位 no-op | 规则 41 加强 |
| flags vs knowledge | 等价 | flags 更重 | 规则 40 修正 |
| 60 天死亡率 | 7.5–8.1% | 4.1–4.3% | 修正生效 |

**主故事已经开始闭合**：

> Experience-dependent differentiation can be enhanced by semantic knowledge,
> but long-term persistence is primarily carried by a separate
> event-triggered consolidation mechanism.

## 8. 还没做的（023 之后）

1. **冻结全部模型 + 写下预测**，然后用**从未运行过的新种子块**做 final
   confirmation。规则 52 那个悬案（无地板档）由它裁决。
2. **anchor 时刻的因果检验**：人为把 `_hardship_anchor` 固定在第 10/20/30 天，
   看 P1 比值怎么变。直接检验规则 50 的推论。
3. **state transplant + novel-situation generalization** —— 这两刀决定这篇
   东西是"一个不错的 ABM 实验"，还是真的回答了那个问题：
   **相同的个体，因为经历了不同的过去，是否真的成为行为上不同的"个体"。**
4. ⑤（三个全删）在 v3 抹掉 68% 的效应（v2 只有 31%），需要解释。

---

# 实验 024 —— v3 冻结 + anchor 内容因果探针

> **v3 已冻结**：`ai-sandbox/v3_frozen/`（32 文件 + 完整 sha256 + README）。
> 从这一刻起 `sim.py` 的默认机制不再改动。后续实验只能是
> **experiment-level intervention**（改 agent 实例状态或临时开关，跑完恢复）。
> 若某实验暴露必须改模型的结构问题 → **分叉 v4，重走冻结流程**，不要就地改 v3。

## 1. A 部分：证伪"v3 推迟了 consolidation"（`anchor_probe.py --verify`）

023 §7.5 那条推论是错的，本节把它钉死。

```
世界      架构        anchor日 v2  anchor日 v3   逐种子相同   fears日 v2  fears日 v3
丰富     完整架构         6.0        6.0      1500/1500      19.0       24.0
丰富     地板全关        14.0       14.0      1500/1500      24.0       27.0
贫瘠     完整架构         6.0        6.0      1500/1500      22.0       24.0
贫瘠     地板全关        11.0       11.0      1500/1500      25.0       23.0
```

**anchor 写入日 v2/v3 逐种子 1500/1500 完全相同。**
机制上必然如此：anchor 写在首次 `condition < 100` 的 tick，
而 condition 只能被 `COND_DRAIN`（饿>70）拉下 100；condition 仍等于 100 时
`COND_RECOVER_AT` 带来的 gain 全被 `clamp` 吃掉 ——
**anchor 写入之前两版逐位相同**。

后移的是 `fears_hunger`（+2~5 天）。规则 50 / 50b 已按此改写（023 §3）。

> ### ★ 规则 53：不要拿一个变量的时间戳去论证另一个变量的时间戳 ★
> 023 §7.5 用 `fears_hunger` 的日期论证 `_hardship_anchor` 的日期，
> 而脚本**根本没记录后者**。两个事件差 13–20 天，结论整个反了。
> **报"某某什么时候发生"之前，先确认脚本记的就是那个量。**

## 2. B 部分：anchor 内容因果探针 —— anchor-content transplant

不用"第 N 天才开始写 anchor"（那会同时改①快照内容②floor 起效时间）。
改成：正常跑完 development（0–29 天，途中存 day 5/10/20/29 的 trait 快照）→
第 30 天 `deepcopy` 出**完全相同的状态（含 RNG）**→ **只改 `_hardship_anchor`**
→ 所有分支从同一状态进入 common garden。唯一变量 = anchor 里装的历史切片。

### ★ 阴性对照：完美通过 ★

```
−全部地板①② · N=1500 · n=1448
分支          比值      Δ vs 自然      p
自然 anchor  1.146        —          —
Day 5        1.146     +0.0000    1.0000 n.s.
Day 10       1.146     +0.0000    1.0000 n.s.
Day 20       1.146     +0.0000    1.0000 n.s.
Day 29       1.146     +0.0000    1.0000 n.s.
无 anchor     1.146     +0.0000    1.0000 n.s.
```

**六个分支逐位相同。** `_hardship_anchor` 的唯一作用路径确实是
anchor → `trait_floor`（`sim.py:970`），地板一冻成 `FrozenZero`，
anchor 里放什么都不影响任何一个 tick。**没有泄漏，没有第二条通路。**

### primary：通过，但效应极小

```
完整架构 · N=1500 · n=1446
分支          比值      δ均值    Δ vs 自然     dz       p
自然 anchor  1.150    0.0457       —        —        —
Day 5        1.150    0.0458    +0.0001   0.02   0.4287 n.s.
Day 10       1.150    0.0457    +0.0000   0.00   0.9559 n.s.
Day 20       1.153    0.0467    +0.0010   0.06   0.0255 *
Day 29       1.156    0.0476    +0.0019   0.09   0.0004 ***
无 anchor     1.155    0.0474    +0.0017   0.08   0.0029 **
```

**primary 预测成立**：anchor 内容干预确实产生可检出的差异（Day20/Day29/无 anchor）。
**但幅度极小**：最大的 Δ = +0.0019，相对于"超出 1 的部分"（0.150）只占 **1.3%**。

**secondary（未预注册）**：Day 5 ≈ Day 10 ≈ 自然 —— 意料之中，
自然 anchor 中位就写在第 6 天，Day5/Day10 的快照和它几乎是同一张。
真正有差别的是 Day 20 之后。方向是**越晚（或干脆没有）→ 比值越高**，
即**早期 anchor 轻微压低了世界间差异**（把地板钉在尚未分化的性格上）。

> ### ★ 规则 54：起作用的是"地板存在过"，不是"地板锚在哪张快照上" ★
> 把两个实验并排看：
> - 021§3（地板消融）：完整 1.150 → 无地板 1.036，**地板一关塌掉 76%**
> - 024 B（换 anchor 内容）：自然 → 无 anchor 只动 **1.3%**
>
> 所以 persistence 依赖的是 **floor 这条棘轮通道本身存在过**，
> 而**不敏感于它锚定的是哪一张历史切片**。
> 规则 50 那句"write-once 采样是持久性的载体"要**降级**：
> 采样确实是 write-once、确实是因果的，但它**携带的个体信息几乎不进入结果**。

⚠ **本实验的射程限制（必须写进论文）**：干预点在第 30 天，
而 `trait_floor` 用 `max()` 累积 —— development 期间由自然 anchor 抬起来的地板
**已经烙进去了，本实验没有拆掉它**。所以这里测的是
**"anchor 在移植后还剩多少因果影响"**，不是"anchor 机制整体有多重要"。
后者由 021§3 的地板消融回答（很大）。两个数字不矛盾，量的是不同的东西。

## 3. ⚠ 本次实验自身的两个错误（记下来当反例）

**(a) mp.Pool 的 worker 复用造成版本污染。**
A 部分的 `task_verify` 在 worker 进程里设 `sim.COND_RECOVER_AT = 30.0/65.0`，
而 B 部分的 `_prep()` 没有显式设回来 —— **worker 进程是复用的**，
于是 B 跑的是 v2 还是 v3 取决于任务调度顺序。同一条命令两次跑出完全不同的数
（自然 anchor 1.260 vs 1.119）。第一版"阴性对照完美 + 完整架构全显著"的结果
**是污染出来的，已作废**。

> ### ★ 规则 55：子进程里改过的全局量，每个任务都要显式设定，不能靠继承 ★
> `mp.Pool` 复用 worker。任何 `setattr(sim, ...)` 都会留在进程里影响后续任务。
> **每个任务函数开头必须把它依赖的所有全局量显式写一遍**，
> 哪怕看起来是默认值。
> 自检方法：**同一条命令换一个 `--workers` 跑第二遍，结果必须逐位相同。**
> （修好之后 workers=12 与 workers=5 已核对一致。）

**(b) `FrozenZero` 的 deepcopy 陷阱。**
`FrozenZero(dict)` 的 `__setitem__` 是 no-op，而 `copy.deepcopy` 重建 dict 子类
**正是通过 `__setitem__` 灌数据** → 复制出一个**空 dict** → 读 `trait_floor['industry']`
直接 `KeyError`。v3 已冻结，所以在实验脚本里重建 `FrozenZero()` 补回
（它不携带状态，读恒 0、写恒丢，重建等价）。
**以后所有 state transplant 类实验都会踩到这个**，先记着。

## 4. 状态

| 问题 | 答案 |
|---|---|
| v3 推迟了 consolidation？ | ❌ 否，anchor 日 1500/1500 逐种子相同 |
| anchor 只走 trait_floor？ | ✅ 是，阴性对照六分支逐位相同 |
| anchor 内容是因果载体？ | ✅ 是（p=0.0004），但只解释 1.3% |
| 持久性靠 anchor 的内容？ | ❌ 否，靠"地板存在过"（规则 54） |

**下一步：写死 FINAL PREREGISTRATION，然后才开全新种子块。**
见 `ai-sandbox/FINAL_PREREGISTRATION.md`。

---

# 实验 025 —— FINAL CONFIRMATION（预注册执行）

> 预注册全文：`ai-sandbox/FINAL_PREREGISTRATION.md`（2026-08-15 写死，跑前未改）
> 执行脚本：`ai-sandbox/final_confirm.py`（从 `v3_frozen/` 导入，启动即校验 sha256）

## 0. ⚠ 这次确认的射程（先写在最前面，防止日后误引）

**这是「当前 persistence architecture 的最终确认」，不是整篇研究核心目标的
最终确认。**

它确认的是：不同的过去，会不会在**同一个 common garden 里**留下持久的行为差异，
以及这个差异由哪些机制携带。

它**没有测**：这些差异能不能在一个**双方都从未经历过的新情境**里
泛化成不同的决策。

所以即使全部判据漂亮通过，能写的是
**"persistent individuality / path dependence 的基础已经很稳"**，
**不是** "generalized individuality 已经证明"。
后者是下一阶段 **novel-situation generalization** 的事。**论文里这两句不能混。**

## 1. persistence 这一层的收敛状态（跑 final 之前的盘点）

| 命题 | 状态 | 依据 |
|---|---|---|
| 不同经历 → 持久的行为差异 | ✓ | 018–022，023 v3 重验 1.124–1.172 |
| 不是 mortality artifact | ✓ | 023：死亡率减半后效应**更强**不是更弱 |
| episodic memory 不是载体 | ✓ 很强 | 删 memories 在 v2/v3 都**逐位** no-op（规则 41） |
| semantic knowledge 不是主要载体 | ✓ 越来越强 | P2 在 v2/v3 都不过（023 §7.3） |
| floor architecture 很重要 | ✓ | 021§3：1.150 → 1.036，塌 76% |
| anchor 的具体 snapshot 在移植后几乎不重要 | ✓ 新 | 024：只解释 1.3%（规则 54） |
| 无 floor 是否还有微弱 residual | **？** | 规则 52：两个种子块结论相反 → **R52 裁决** |

**只有最后一行是未知的。** 其余五项在 final 里是**复制，不是发现** ——
论文里必须这样写，不能把复制说成确认。

## 2. 执行前的三道闸（全部通过）

1. **冻结校验**：`v3_frozen/SHA256SUMS.txt` 32 个文件全部匹配 ✓
   模型确认来自 `v3_frozen`，`MODEL_VERSION=v3`，`COND_RECOVER_AT=65.0` ✓
2. **规则 55 自检**：`--workers 12` 与 `--workers 5` 输出**逐字节相同** ✓
3. **全流程调通**：开发种子上走通五个条件 + 四条判据 + 阴性对照 ✓
   （阴性对照 fingerprint：删 memories 与不删 **完全相同**）

## 3. ⚠ 起飞前拦下：R52 判据不可判定（`r52_precision.py`）

彩排（**开发种子** 0–1499，N=1500，非 final）：

```
条件                    n     死亡丰  死亡贫    比值   95% CI
H1  完整架构           1447   0.0%   3.5%   1.153  [1.113, 1.196]  ✓
P1  −全部地板①②        1448   0.0%   3.5%   1.139  [1.098, 1.183]  ✓
P2② 删 knowledge     1449   0.1%   3.3%   1.102  [1.062, 1.144]  ✗（落差 .037，CI 重叠）
NC③ 删 memories      1448   0.0%   3.5%   1.139  [1.098, 1.183]  ✓ 与 P1 逐位相同
R52 −地板 · 022关     1430   1.5%   3.2%   1.037  [1.000, 1.084]  ⚠
```

R52 的 CI 下界打印出来正好是 **1.000**。判据是「下界 > 1.00」，
于是"过/不过"取决于 bootstrap 分位数的第 4 位小数 —— 而那一位带蒙特卡洛误差。

**只换分析层随机种子**（不换数据、不换模型、不换估计量），跑 8 次：

```
分析种子    CI 下界    判据          分析种子    CI 下界    判据
777       1.00054    ✓ 过         4777      1.00011    ✓ 过
1777      0.99875    ✗ 不过        5777      0.99938    ✗ 不过
2777      1.00118    ✓ 过         6777      1.00121    ✓ 过
3777      1.00145    ✓ 过         7777      0.99972    ✗ 不过

下界范围 [0.99875, 1.00145]   抖动 0.00271
|中位下界 − 1.00| = 0.00032   vs 抖动 0.00271      → 5/8 判「过」
```

> ### ★ 规则 56：bright-line 判据必须先证明它在预期效应量上可判定 ★
> 「CI 下界 > 1.00」写起来很干净，但当真值就压在 1.00 上时，
> 它把科学结论交给了**分析层随机种子**。5/8 vs 3/8 = 掷硬币。
> **预注册写判据时，要同时预注册"这个判据在预期效应量下的可判定性"** ——
> 或者干脆允许第三种结局「落在检出边界，判据无法裁决」。
>
> 这条是在**烧掉 final block 之前**抓到的，靠的是一次只用已烧种子的彩排。
> **一次性资源，必须先彩排。**

### ⚠ 加 bootstrap 次数救不了

抬 `N_BOOT` 只压缩蒙特卡洛误差，不改变 bootstrap 分位数的**极限值**。
`N_BOOT → ∞` 时下界收敛到 ≈ **1.0003** —— 判读会从"随机的过/不过"
变成"稳定地判过，但只赢了万分之三"。
**那是把随机的任意变成确定的任意，不是把它变成有意义。**

真正的问题不是精度，是 **R52 的真值就坐在检出限上**：
021 开发块 1.036 n.s. / 留出块 1.057 **，现在开发块 N=1500 下界 ≈ 1.0003。
规则 52 说的"两个种子块结论相反"，本质就是这个。

**决策权交回，final block 未动。** 50000–51499 仍然完好未使用。

## 4. ⚠ 第一次 `--final` 是空跑 —— 事故记录

首次执行 `--final` 输出全部条件 `n = 0`。**这不是结果，是分块索引 bug。**

```python
jobs = [... (ci, w, s0, min(CHUNK, N - s0)) ...          # 应为 seed0 + N - s0
        for s0 in range(seed0, seed0 + N, CHUNK)]
```

`seed0 = 0` 时两者恰好相等；`seed0 = 50000` 时 `N − s0 = 1500 − 50000` 为**负数**
→ `range(s0, s0 + 负数)` 为空 → 每个任务模拟 0 颗种子。

**关键：`scenarios.make` 对 50000–51499 一次都没被调用，没跑过任何一个 tick，
没有产生任何观测。** 所以 final block **未被烧掉**，修复后重跑不构成
adaptive analysis —— 那段种子的数据我们一个字节都没看到。
作废文件保留为 `final_confirm_result.VOID_bug.txt`（开头写明作废原因）。

> ### ★ 规则 57：彩排必须用与正式运行**同样形状**的参数 ★
> 全尺寸彩排做在 `seed0 = 0` 上，而那正是这个 bug 唯一不发作的取值 ——
> 等于把正式要走的代码路径整条跳过了。
> **不要用 0 / 1 / 空集这类会让边界情况消失的特例做彩排。**
> 修复后的复检改用 `--seed0 20000`（已烧掉的 022 段，不消耗新种子），
> 走的是和 final 完全相同的非零偏移路径。

**一个正面结果**：预注册第 4 节那条「有效 n 不足判为**无效**而非不显著」
把故障显示成了 `⚠ 无效`，而不是悄悄输出一个基于空样本的数字。
如果当初写的是"n 太小就报不显著"，这份空跑看起来会像一个真实的阴性结论。

事后加的两道硬拦截（都会直接中止、不产生输出文件）：
① 覆盖率自检：计划模拟次数必须精确等于 `条件数 × 2 × N`；
② `n = 0` 拦截，并声明「n=0 是故障不是死亡率」。

## 5. ★ FINAL CONFIRMATION 结果 ★（seeds 50000–51499，只跑一次）

```
条件                    n     死亡丰  死亡贫    比值   95% CI              δ均值   dz      p
H1  完整架构           1441   0.0%   3.9%   1.142  [1.098, 1.183]  +0.0444  0.20  0.0001
P1  −全部地板①②        1449   0.0%   3.4%   1.134  [1.090, 1.175]  +0.0417  0.18  0.0001
P2② 删 knowledge     1448   0.1%   3.3%   1.102  [1.056, 1.141]  +0.0309  0.14  0.0001
NC③ 删 memories      1449   0.0%   3.4%   1.134  [1.090, 1.175]  +0.0417  0.18  0.0001
R52 −地板 · 022关     1429   1.7%   3.1%   1.046  [1.002, 1.086]  +0.0147  0.06  0.0154
```

### 判据裁决

| 判据 | 结果 | 数值 |
|---|---|---|
| **H1** 主效应 | **✓ 过** | 1.142 [1.09816, 1.18343] |
| **P1** 地板全关后仍 > 1 | **✓ 过** | 1.134 [1.09043, 1.17507] |
| **P2** 删 knowledge | **✗ 不过** | 落差 +0.032 < 0.05，CI 重叠 |
| **R52** | **◐ 落在检出边界，本判据无法裁决** | 1.046 [1.00208, 1.08609] |
| 阴性对照 情节记忆 | **✓ 逐位相同** | 0.344305459704 vs 0.344305459704 |

### 事前预测对照（预注册第 7 节，逐条照抄）

```
        预测                  实测              符合？
H1      过, 1.12–1.16        过, 1.142         ✓ 完全符合
P1      过, 1.07–1.10        过, 1.134         ⚠ 方向对，点估计【高出预测区间】
P2      不过, 落差≈0.03       不过, 落差 0.032   ✓ 精确命中
R52     不过, 1.03–1.06      边界, 1.046       比值落在预测区间内，判读为「无法裁决」
情节记忆 逐位相同             逐位相同           ✓
```

⚠ **P1 的点估计高于事前预测区间**（预测 1.07–1.10，实测 1.134）。
如实记下，**不事后加宽预测区间**。原因大概率是预测抄的是 023 v3 重验值
（1.090，seeds 20000+），而种子块之间本来就有 ±0.04 的浮动
（H1 在三个块上分别是 1.172 / 1.148 / 1.142）。

### R52：为什么 8/8 仍然判「无法裁决」

边界诊断：8 个分析种子的下界范围 `[1.00100, 1.00454]`，MC SD = 0.00103，
**8/8 都 > 1.00** —— 蒙特卡洛意义上它是稳的。

但预注册修订 A 的门槛是 `|lo − 1.00| ≥ 0.01`，实测 `lo − 1 = 0.00208`。
**照预注册判「◐ 无法裁决」。**

> ### ★ 这一条要抵住诱惑 ★
> 「8/8 都过了，为什么不算过？」—— 因为门槛是**跑之前**定的，
> 且定的理由不只是蒙特卡洛噪声，还有"只赢万分之二十的 CI 下界，
> 不足以支撑一个科学主张"。
> **看到结果之后再去争论门槛该不该是 0.01，就是 adaptive analysis。**
> 修订 A 写在没看 final 数据的时候，就照它执行。

### R52 的实质（描述性，非判据）

三个独立种子块上的点估计高度一致，方向从未变过：

```
021 开发块   1.036   n.s.
021 留出块   1.057   **
FINAL 块     1.046   p=0.0154, dz=0.06
```

**一个方向稳定、幅度很小（≈+0.04）、始终贴着检出限的残余效应。**
诚实的表述：*地板全关之后仍有一个小的残余差异，方向在三个独立种子块上一致，
但幅度小到我们预注册的判据无法裁决它是否 > 1。*
规则 52 的悬案**保持公开**，不用一次性资源硬判。

## 6. persistence 这一层的收口

| 命题 | 最终状态 |
|---|---|
| 不同经历 → 持久的行为差异 | **✓ 确认**（H1，全新种子块，1.142） |
| 不是 mortality artifact | ✓（v3 死亡率 3–4%，效应未减反增） |
| episodic memory 不是载体 | **✓ 很强**（三次独立运行都逐位 no-op） |
| semantic knowledge 不是主要载体 | **✓**（P2 在 v2/v3/final 三次都不过） |
| floor architecture 很重要 | ✓（1.142 → 1.046） |
| anchor 的具体 snapshot 几乎不重要 | ✓（024，只解释 1.3%） |
| 无 floor 的微弱 residual | **◐ 未决**，方向稳定、幅度 ≈+0.04 |

**可以写进论文的主句：**

> Experience-dependent differentiation can be enhanced by semantic knowledge,
> but long-term persistence is primarily carried by a separate
> event-triggered consolidation mechanism.

⚠ **射程**（预注册第 0.5 节）：以上确认的是 **persistence architecture**。
**没有**证明 generalized individuality —— 即这些差异能否在**双方都没经历过的
新情境**里泛化成不同决策。那是下一阶段 novel-situation generalization 的事。
**论文里这两句不能混。**

## 7. 下一步

persistence 这一层到此收口，不再解剖当前模型。
下一个问题就是最开始那个：**历史留下来的东西，能不能作用在从未见过的未来。**

---

# ★ persistence 阶段封存 ★（2026-08-16）

实验 011–025 到此结束。执行部分全部跑完，无遗留进程。

```
v2_frozen/   COND_RECOVER_AT = 30    实验 011–022 的原始模型
v3_frozen/   COND_RECOVER_AT = 65    论文候选架构，MODEL_VERSION = "v3"
FINAL_PREREGISTRATION.md             写死并执行完毕（含修订 A）
final_confirm_result.txt             seeds 50000–51499，只跑一次
final_confirm_result.VOID_bug.txt    第一次空跑的作废记录（见 025 §4）
```

已烧掉、不可再作 holdout 的种子段：
`0–1499`、`10000–11499`、`20000–21499`、`50000–51499`。

**从这里之后的工作属于新阶段，不再回头解剖 persistence。**

---

# 实验 026 —— NOVEL-SITUATION（设计 v3 定稿，未执行）

设计全文：`ai-sandbox/NOVEL_SITUATION_DESIGN.md`（v3）
**设计已收敛，不再发散。** 未碰 `60000–61499`，未改 `v3_frozen/`。
下一步：写机制层与 group-blind 校准脚本，在 `20000+` 上定 `S` 与 `λ`。

## ★★ 规则 61：counterfactual sibling branches ★★

**这是整个设计里最重要的一条，比 RF 用 8 层还是 12 层重要得多。**

**错的做法**（v2 的隐含假设）：

```
agent → 熟悉世界跑 W 天测 B_familiar → 再进冻土测 B_novel
```

**那 W 天的 familiar 测量本身就是一段额外经历**，会继续改变
traits / goal / trait_floor / knowledge / hardship。
到进冻土时，预测的**已经不是"同一个历史状态面对两个未来"**。

**必须的做法**：

```
development 结束 → 状态拉平 → 完整 snapshot（含 RNG）
                                   ↙            ↘
                              clone F          clone N
                              熟悉世界          Novel 世界
                                 ↓                ↓
                             B_familiar        B_novel
```

两个 clone 在**分叉瞬间**完整可执行状态与 **RNG state 相同**，
**任何一支之后发生的事都不得反馈给另一支**，两支跑**同样长度 W**。

⚠ 分叉后必须重建 `FrozenZero()`（024 踩过的 deepcopy 陷阱）。

## 特征 / 目标 / 损失（定稿）

- **`B_familiar` = 182 维**：168（24 小时 × 7 动作，每小时内归一）
  + 7（全窗口动作占比）+ 7（后半段 − 前半段变化量）。
  后 14 维是确定性摘要，**不引入新信息**，只让 RF 更容易读到"几点做什么"
  和"熟悉环境中行为是否还在漂移"。
  **不用 7 维** —— 否则审稿人一句"history 只是补回了你自己压缩掉的
  circadian/temporal 信息"就挡不住。182 维让 G1 更难过，**但过了更硬**。
- **`B_novel` = 7 维动作占比**（刻意让 M0 占便宜：182 维 → 预测 7 维）
- **损失 = TV 距离**（接得上项目一贯的行为指标）：
  `d_i = TV(实际, M0预测) − TV(实际, M1预测)`。
  通俗含义：**知道过去以后，对这只球在新世界里怎么分配行为时间，
  预测得更准了多少。** 一颗 seed 的双胞胎**先取平均**，再做 seed-level 推断。
- ⚠ **拉平后 `entry_state` 在主分析里是常量**（按构造全同），
  `M0 = f(B_familiar)`；它只在未拉平的配对匹配次分析里才是真变量。

## ★ 规则 56 强化：消灭分析随机性，而不只是测量它 ★

R52 的教训是"换个分析种子结论就翻"。这次从源头堵死：

- **CV fold 确定性**：`fold = deterministic_hash(seed) % K`，双胞胎永远同 fold
- **RF `random_state` 固定**，`n_estimators = 1000` 压低森林随机性
- **bootstrap 固定 analysis seed，replicates 提到 10 000**

**正式分析本质上是 deterministic 的。** 8 种子彩排降级为稳定性诊断。

## 模型与判据

- **RF 为 primary**，二次基展开 Ridge 作稳健性，**不要求都显著**；不用 k-NN。
- 超参 group-blind 小网格（`max_depth {8,12,None}` × `min_samples_leaf {5,10,20}`
  × `max_features {sqrt,0.5,1.0}`），**只优化 M0** ——
  调参脚本不接收 history，**更不许看哪个模型让 M1−M0 最大**；
  **性能接近时预先规定选更正则化的那个。**
- 推断：`ΔOOS` 的种子聚类 bootstrap 95% CI 下界 > 0。置换检验降为 secondary。
- **容量对照判「容量不足」需两个条件同时成立**：对照自身 CI 下界 > 0，
  **且**点估计 ≥ 真 history 的 50%。（只看点估计会让一个很噪的 C1
  恰好到 51% 就把实验判死。50% 是人为护栏，不假装是理论常数。）

## 校准（规则 58，group-blind）

pooled 合格条件：两策略各 20–80%；总存活 ≥80%；5 天内达标 ≤50%；
**门确实打得开**（窗口结束前达标 20–80%）；
**不是伪分岔**（两策略存活率**各 ≥80% 且相差 ≤10pp**）。取满足条件的最小 `S`/`λ`。

> ### ★ 找不到满足条件的 S / λ 怎么办 ★
> **说明这个 probe 的设计本身不够干净，不应该为了让它能跑而放宽标准。**
> 026 测的是 strategy transfer，**不是重新研究 survival selection**。

Probe B 压成一维 λ：`c_f = λ·k_food`（k=1）、`c_s = λ·k_shelter`（k=22）——
二维空间里"最小耦合强度"没有唯一含义。

## 规则 60：可供性门控必须 non-destructive

Probe A **绝不能**写 `world.food = 0`。`take_food` 是从**库存**扣
（`sim.py:181-186`），清零 = 每 tick 烧掉世界存粮 → 那是"毁掉食物"，
不是"取不到食物"。改用 `GatedWorld` 子类：库存照常 regen，只改取用规则；
`shelter` 在调用时刻读取（无一 tick 延迟）；门关着时按 v3 相同条件消耗一次
rng 抽样，**让门只改可供性、不扰动随机流**。

> 一般教训：**在有库存/存量语义的变量上做临时限制，不能改写存量，
> 要改取用规则。**

## G3 仍是机制问题，不是必要条件

若 persistence 本来就由 floor 携带，
`history → floor consolidation → novel context → new divergence`
**完全可以是真正的 generalization**。**载体可以还是同一个，
新的是它对未见问题产生了新的功能后果。**
关 floor 后 G1 消失 → *generalization depends on the same consolidation
architecture*，**不是失败**。

## 命名判据

**两个结构正交的 probe 都过 G1 → 才允许用 *generalized individuality*；
只过一个 → 只能写 *novel-context transfer*。** 禁止事后追加 probe。

## ★★ 规则 62：behavior window 与 consequence window 必须分离 ★★

校准允许 novel probe 里死掉近 20%，但 G1 预测的是 **7 维动作占比**。
若一只球第 8 天死、另一只活满窗口：

- **删掉死亡个体** → 又制造 **survivor selection**
  —— 那正是 persistence 阶段花大量实验才清理掉的东西（规则 44）
- **直接用死亡前的行为** → **观察窗口长度不同**，占比不可比；
  而且死亡本身可能就是 rich/poor 历史造成的
  → G1 会把**"谁活得久"**和**"怎么做决策"**混在一起

所以拆成两个窗口：

```
进入 Novel world
      ↓
【decision window】W_dec 天 ——— B_novel → G1（行为）  窗内存活率须 ≥ 95%
      ↓
继续运行
      ↓
【consequence window】跑满 ——— survival / food / shelter / condition → G2（后果）
```

> **G1 测「面对陌生情境时怎么选择」，G2 测「这些选择后来造成什么后果」。
> 这两个不许混。禁止用"只分析幸存者"来定义 G1。**

`B_familiar` 同样只取 decision window（两支等长，规则 61）；
两支都继续跑到 consequence window —— 熟悉支的后果就是 G2 的轭式对照基线。

`W_dec` 与 `S`/`λ` 同等待遇，**不凭感觉选**：候选集 `{5,7,10,14}` 天先写死，
在 `20000+` 上 group-blind 选。二维用**字典序**取唯一解
（先最短 `W_dec`，再最小 `S`/`λ`），避免重蹈 `c_f/c_s` 那种"最小无唯一含义"。

## 两条实现层提醒（已写进设计 §9）

- **C2 的中位数只能用 training fold 算**，再应用到 held-out fold ——
  用全数据中位数会造成 test information leakage。
  （C1 = `explore × build` 是纯乘积，无此问题。）任何标准化/分箱同理。
- **sibling 隔离要主动证明**：分叉后不只检查"没有共享引用"，
  还要做**突变测试** —— 改 clone F 的 `inventory`/`traits`/`world.food`，
  **断言 clone N 逐位不变**，反向再做一次。很便宜，但能直接证明分支真隔离。
  **不过不往下走。**

## 替代解释的封堵清单（设计阶段到此完成）

| 替代解释 | 封堵手段 |
|---|---|
| 顺序测量污染 | **规则 61** counterfactual sibling branches |
| 熟悉行为被压缩过度 | **182 维** `B_familiar` |
| M0 被故意做弱 | **容量对照** C1 / C2（护栏，非证明） |
| 挑参数挑出效果 | **规则 58** group-blind 校准 |
| 分析随机性 | **规则 56 强化**：确定性 fold + 固定 random_state + 固定 bootstrap 种子 |
| 冻土错误烧掉库存 | **规则 60** `GatedWorld` non-destructive |
| 死亡造成的选择偏差 | **规则 62** decision / consequence 窗口分离 |

**设计到此为止，不再发散。** 下一步：mechanism implementation →
`20000+` group-blind calibration → `NOVEL_PREREGISTRATION.md` → 才碰 `60000–61499`。

## ★ 规则 63：「完整可执行状态」必须逐项审计，不能凭印象列 ★

机制层第一版把状态 hash 写成 `"memories": len(ag.memories)` ——
**"有 5 条 memory" ≠ "5 条 memory 内容相同"**，而 `memories` 会被
`recall()` 回读（`sim.py:517/554/563`）。于是两个 agent 可以 hash 相同
但记忆内容不同 → **全拉平阴性对照会漏掉隐藏差异**，这个对照就是假的。

审计方法：对 v3 的 Agent / World / Life **逐字段** grep 读取点 ——
**有回读 → EXEC（进 hash，全拉平时必须一起拉平）；只写不读 → LOG。**

```
Agent EXEC  traits / trait_floor / trait_identity / hunger / energy / shelter /
            condition / inventory / hardship / _hardship_anchor / flags /
            knowledge / knowledge_strength / alive / rng
            memories        ★ recall() 回读（517/554/563）★ 必须全量，不能只存长度
            goal_satiation  ★ sim.py:694 回读 —— 目标不应期 ★
            action_log      ★ sim.py:619/626 回读 —— 目标进度 ★
Agent LOG   action_by_hour / goal_by_day / goal_history      （sim.py 内无回读）
World EXEC  food / objects / p / weather / rng
            storm_damage    ★ 动态属性，仅暴雨后存在；sim.py:942 回读 ★
World LOG   events                                            （仅 influence 写入）
Life  EXEC  inf_rng
```

⚠ 审计比预想的多抓到两个：**`action_log`**（以为是纯日志，其实喂目标进度）
和 **`storm_damage`**（**动态属性**，只在暴雨后才存在于 `__dict__` 里，
靠"列一遍字段"根本发现不了）。

### 落地方式：结构性断言，而不是手写清单

`audit_fields()` 对 `vars(agent/world/life)` 求差集，
**任何未被分类的字段都会让它抛错**。
这防的不是"以后 v3 变了"（v3 已冻结），而是**"我漏看了一个字段"** ——
第一版正是这么错的。

另外分成两个作用域：
- `exec_state()` = EXEC only → **全拉平阴性对照**用（拉平后 LOG 本来就该不同）
- `full_state()` = EXEC + LOG → **分叉隔离 / 确定性测试**用（更严格）

### 机制层自检（`novel_situation.py`，全部通过）

```
✓ 规则 60：门关闭不烧库存、regen 正常、开门可取
✓ 规则 61：sibling 突变测试双向通过（含 memories 内容 / goal_satiation /
           action_log / world.p）
✓ 阴性对照：完整状态相同 → 逐位相同
✓ 地板全关下分叉不触发 FrozenZero 的 deepcopy 陷阱
✓ 规则 63：字段审计断言有效，memories 内容 / goal_satiation 都进 hash
✓ Probe B：λ=0 等价于无耦合，λ>0 确实改变轨迹
```

> **⚠ 全拉平阴性对照的一个后果**：既然 `action_log` / `memories` /
> `goal_satiation` 都是 EXEC，**全拉平时必须连它们一起拉平**，
> 否则"两组在任何维度上都不可区分"这句话不成立。写对照脚本时不能只拉
> traits/floor/knowledge。


## ★ group-blind 校准结果：两个 probe 都不合格 ★（`novel_calibrate.py`，N=300）

阴性对照先过：**规则关闭（S=0 / λ=0）时决策窗与后果窗存活率都是 100.0%**，
两条策略各自也都 100% —— 实现正确，下面的失败是真的设计问题。

### Probe A「冻土」：24 格全不合格

```
 W_dec   S    决策窗存活  后果窗存活  盖房派  探索派  盖房存活  探索存活   差
   5   0.00   100.0%   100.0%  24.2%  75.8%  100.0%  100.0%   0.0%   ←基线
   5  55.00   100.0%    54.7%  17.4%  75.5%   98.1%   49.8%  48.3%
   5  80.00   100.0%    41.3%  17.3%  75.5%   85.3%   35.2%  50.1%
```

失败频次：③后果窗存活 24/24、⑥策略存活 24/24、①两策略占比 22/24。

> ### ⚠ 我在设计里的论证是错的，此处更正 ⚠
> 设计 §2 写：「`explore` 的产出走 `EXPLORE_FOOD_YIELD`，不经过 `world.food`
> → 两条都能活的策略」。**"绕开门" ≠ "能活"。** 算速率就清楚：
>
> ```
> explore 期望产出 = 0.28 × 0.5      = 0.14 食物/tick
> 维持饥饿所需     = 2.2 / 20        = 0.11 食物/tick
> ```
>
> 余量只有 27%，而 explore 每次扣 9 点精力（基础消耗才 1.2），
> 球必须分出大量 tick 睡觉 → **实际探索占比下净收支为负**。
> 实测探索派存活 35–51%。
>
> **我从代码结构读出"可能性"，没有验证"量级"** ——
> 与 3g「悬崖」那次同型的错误（规则 49 之前）。

### Probe B「盐碱地」：28 格全不合格

```
 W_dec    λ    后果窗存活  盖房派  探索派  盖房存活  探索存活   差    耦合改变
   5   0.00    100.0%   24.2%  75.8%  100.0%  100.0%   0.0%    ←基线
   5   0.10     96.4%   24.2%  75.8%   85.3%  100.0%  14.7%    0.059
   5   0.20     79.0%   24.2%  75.8%   13.3%  100.0%  86.7%    0.063
   5   0.30     75.6%   24.2%  75.5%    0.0%   99.8%  99.8%    0.068
```

λ=0.1 时七条只差 ⑥ 一条。N=60 时差 12.0pp，**N=300 时差 14.7pp** ——
样本加大后**离合格更远**，不是噪声。λ≥0.2 是断崖：盖房派存活 13% → 0%。

### ★ 规则 64：v3 只有一套食物经济，任何动它的 probe 都产生生存分裂而非策略分裂 ★

两个 probe 失败的形状**完全相同：总有一条策略变成致命的**。

- Probe A 门控 `world.food` → **探索派**断了食物来源 → 死
- Probe B 采材料毁 `world.food` → **盖房派**挖空自己的食物来源 → 死

根因是同一个：**`world.food` 是 v3 唯一真正的食物来源**，
`explore` 的产出率不足以独立维生（见上）。所以**任何对食物可得性的
结构性操作，都会把"策略差异"变成"生存差异"**。

还有一层我也弄错了：**策略归类（b vs e）并不对应食物来源依赖**。
被归为"探索派"的球**照样在采集**；它们只是探索占比更高。
所以 Probe A 的前提「有两条独立的食物路线」**双重不成立**。

> **结论：v3 的动作经济太窄，不足以支撑"在新结构上产生策略分岔"这类 probe。**
> 这不是参数没调好，是模型的经济结构决定的。

### 为什么现在可以放心迭代 probe 设计

**校准是 group-blind 的** —— 脚本结构上拿不到发育世界标签，
输出里也只有 pooled 量。**所以关于 rich/poor 差异的信息一个比特都没泄漏。**
基于校准结果重新设计 probe，**不损害 `60000–61499` 的 final 地位**。

这正是先做 group-blind 校准的价值：**它在烧掉 final 之前就抓到了
"这个实验根本测不了它想测的东西"。**

### 三条路（待拍板，我不自行选择）

1. **换赛道**：设计不触碰食物经济的 probe（材料/住所经济、信息经济
   `read`/`book`、时间结构），保住生存率，才可能出现真正的策略选择。
2. **承认射程**：v3 的动作经济不足以测 novel-situation generalization，
   如实写进论文 —— 这本身是个诚实的架构性结论。
3. ⚠ 灰色地带：λ 网格是 `{0.1, 0.2, …}`，没有 0.05。看到 0.1 接近之后再往下加
   **不是放宽判据，但确实是事后扩大搜索空间**（grid fishing）；
   且更小的 λ 会让 ⑧「耦合咬得住」变弱，不是免费的。**需要明确授权才做。**


## ★ 规则 65：novel probe 不许动粮食 ★

> **Novel probe 的主要操纵不得直接改变 hunger、condition 或长期可持续的
> food supply；生存只能作为安全性检查，不能成为 probe 的策略回报函数。**

要测的是「过去让两个 agent 面对新问题采取不同办法没有」，
**不是**「谁比较会在一个人为制造的饥荒机制里活下来」。

所以新 probe 的目标形状是：

```
两条路都能继续正常活
        ↓
但得到不同的【非生存】后果
```

**Probe A「冻土」与 Probe B「盐碱地」正式退役**（记录保留，见上一节）。

### 为什么不选另外两条路

- **不给 v3 补探索觅食机制**（提高 `EXPLORE_FOOD_YIELD` 或新增食物经济）：
  那实际上已经分叉成 **v4**，011–025 关于 v3 persistence 的证据就接不上，
  还得重新确认"v4 还有没有原来的 persistence architecture"，
  把项目拖回模型验证阶段。更要命的是它会制造一个完全合理的质疑：
  **"是不是为了让 generalized individuality 出现，特意改了 agent？"**
  即使做得完全诚实，也没必要给自己背这个解释负担。
- **不急着宣布"v3 做不到"**：目前只证明了**不能拿食物经济做这类 probe**，
  没有证明 v3 在任何结构新颖情境下都不行。
  正确的结论是**"我们选错了战场"**，不是"架构做不到"。

## ★ 行为经济审计（group-blind）★（`novel_econ_audit.py`，n=591）

选新赛道之前先量速率 —— 这正是 Probe A 栽跟头的地方。
common garden 30 天，存活 100.0%：

```
动作                均值占比   跨个体SD   变异系数    p90−p10   >0 的球
eat               0.108    0.0007    0.01     0.001   100.0%   ← 代谢刚性，几乎无个体差异
sleep             0.315    0.0524    0.17     0.146   100.0%
gather_food       0.041    0.0412    1.02     0.113    78.7%
gather_material   0.120    0.1676    1.40     0.426    58.4%   ★
build             0.022    0.0295    1.34     0.054    58.2%
explore           0.395    0.2453    0.62     0.640    76.0%   ★
read              0.000    0.0000     —       0.000     0.0%   ← 基准世界没有书
```

> ### ★ 规则 66：`explore ↔ gather_material` 是 v3 里唯一有足够个体方差的策略轴 ★
> 这两个动作的 `p90−p10` 分别是 **0.640 / 0.426**，远超其余动作；
> 而 `eat` 的跨个体 SD 只有 **0.0007** —— **进食是代谢刚性的，
> 几乎不携带个体差异**。这从另一个角度解释了规则 64：
> **动食物 = 动一个本来就没有个体差异的维度，只能压出生存差异。**
>
> 新 probe 应当建在 `explore ↔ gather_material` 这条轴上：
> 方差最大、两条路在**两个发育世界里都合法**（只是 `material_yield` 2.0 vs 0.5
> 速率不同）、且不碰食物供给。

### ⚠ read / book 这条赛道有一个致命的不对称，建议放弃

实测 **`read` 在 common garden 的占比是 0.0000，0% 的球做过** ——
因为 `ACTION_REQUIRES_OBJECT = {"read": "book"}` 而 `基准` 世界没有书。

而两个发育世界是：**丰富世界 `objects = ("book","music")`、贫瘠世界 `objects = ()`。**

所以往 novel 世界里放一本书：

```
对丰富世界出身的球 = 【旧经验】（它发育期读过书、有 knowledge）
对贫瘠世界出身的球 = 【全新事物】（从未见过书）
```

**这不是"对双方都 novel"，而是把一个发育期差异重新暴露一次。**

更糟的是：`B_familiar` 里 `read` 恒为 0（common garden 没书），
所以这份"先前经验优势"**根本不会出现在 `B_familiar` 里** ——
它会直接灌进 `ΔOOS`，让 G1 因为一个**平凡理由**而通过。
**这正是 G1 最需要挡住的那种假阳性。**

> ### ★ 规则 67：novel 情境必须对两组【同等新颖】 ★
> 若某个可供性在一个发育世界里存在、另一个没有，
> 那么在 novel 情境里引入它 = 重新暴露发育期差异，
> 属于 N0（参数外推）的变体，**不是结构新颖**。
> 选 probe 之前必须核对：**这个可供性在两个发育世界里的可及性是否相同。**
> `material` 两边都有（只是 2.0 vs 0.5 的速率差）→ 合格；
> `book` / `music` 只有丰富世界有 → 不合格。

## ⚠ 一个必须一起说清的射程限制

v3 **没有在场因果学习**，所以 agent **不可能"发现"新规则并据此选路线**。
它只能**被动地**对改变后的收益作出反应（通过 goal 进度、inventory、状态）。

因此新 probe 的novel 结构必须**经由反应式通路**产生行为分化
（`gather_material` 收益变了 → `improve_home` 的目标进度变了 → 目标切换变了），
**不能依赖"agent 意识到应该先做 X 才能做 Y"**。
设计文案里也不许那样写（措辞纪律，§0）。

## 下一步待拍板

新 probe 建在 `explore ↔ gather_material` 轴上、不碰食物、两组同等新颖。
具体机制**未定**，按指示不自行敲定。候选方向（都满足规则 65/66/67）：

1. **材料可及性依赖探索历史**：`material_yield` 取决于近期 explore 量
   —— 新关系（两个世界都没有），两条路都活得好好的
2. **材料枯竭/轮休**：连续采集使 `material_yield` 递减，需要交替
3. **住所—材料的新耦合**：`build` 的收益取决于材料的"来源多样性"

三者都只动材料/住所经济，`eat` 与 `world.food` 一律不碰。

## Probe A2「探路」：可行性校准不合格（`novel_calibrate2.py`，N=300）

机制（按精确定义实现）：必须执行 `gather_material` 才拿得到材料，
**该次采集的 yield 取决于最近 τ tick 内 explore 的比例**（加成 α）。
纯 explore 拿不到材料；纯 gather 只能低效拿；受益的是**时序组合**。

```
   τ    α    存活    命中率  命中SD  单次收益  收益提升  轨迹TV   三档材料(低/中/高探索)
   6  0.5  100.0%  13.4%  0.143  1.005   +0.5%  0.000   116.2   0.8   0.0
  24  4.0  100.0%  49.7%  0.441  1.091   +9.1%  0.010   116.4   1.0   0.0
  48  4.0  100.0%  52.1%  0.459  1.120  +12.0%  0.011   116.6   1.2   0.0
```

**规则 65 完全达标**：存活 100%，与规则关闭时逐格无差别 ——
**"不碰粮食"这条原则确实消除了生存混淆**，这是本轮实打实的收获。
命中率随 τ 从 13% 升到 54%，跨个体 SD 到 0.46 —— 机制本身生效。

**但 ⑤轨迹 TV 只有 0.000–0.011（阈值 0.02），16/16 格失败。**
**代码上有新规则，行为上没有形成新的 strategy landscape。**
⚠ 这正是本轮新增的 manipulation check 抓到的 —— 没有它，
这个 probe 会带着"机制生效"的假象一路走到 final。

### ⚠ 更正：材料**不是**过剩，而是**双峰**

我先前根据三档均值（116 / 0.8 / 0.0）判断"材料严重过剩"。**这是错的。**
直接测 common garden 30 天后的材料库存（n=237）：

```
中位 0.0    p10 0.0    p90 203.0
库存 < 3（盖一次房的成本）的比例：76.8%
```

**中位数是 0，77% 的球连一次盖房都买不起。** 分布是极端双峰：
少数采集者囤到 100–200，绝大多数**一直是 0**。

> ### ★ 规则 68：乘性加成对"从不执行该动作"的个体恒等于零 ★
> A2 给的是 `material_yield × (1 + α·f)` 的**乘性**加成。
> - 对 77% 从不采集的球：**乘的是 0**，加成再大也没有任何效果
> - 对 23% 采集者：他们已经囤到 116，加成落在**用不掉的地方**
>
> **加成落不到任何"既够得着又用得上"的人群上。**
> 设计 probe 时必须先查：**这个操纵作用的动作，有多少比例的个体真的会做？**
> 近乎全员执行的非食物动作只有 `sleep`(100%) 与 `explore`(76%)。

### 夹击结构（三轮 group-blind 证据）

```
资源        是否紧约束                     是否有个体方差
食物/hunger  是（规则 64）                  否 —— eat 跨个体 SD = 0.0007
材料         对 77% 是（库存恒 0）           是 —— p90−p10 = 0.426
             但那 77% 从不采集 → 操纵够不着
```

**动紧约束的（食物）只能压出生存差异；
动有方差的（材料）够不着真正被约束的那群人。**

这不是第四次"选错战场"，而是开始成为一个**关于 v3 动作经济的结构性结论**：
v3 里似乎没有一个维度**同时**满足「近乎全员参与」「个体差异大」「非食物」。

### 下一步的证据约束（不自行决定）

按规则 68，操纵必须落在**近乎全员执行**的动作上。排除食物后只剩：

- `sleep`（100% 执行，p90−p10 = 0.146）—— 但它经 `SLEEP_EFF_FLOOR` 与
  condition 相连，**算不算触犯规则 65 需要拍板**，我不自行扩大解释
- `explore`（76% 执行，p90−p10 = 0.640，方差最大）—— 它的**非食物**产出是
  landmark / flag / knowledge 与性状反馈（curiosity +0.20、caution −0.10）。
  一个作用于 explore **信息性产出**的新结构，可能是唯一还没被证伪的方向


## ★ v3 novel-probe capacity audit（统一资格标准，group-blind）★

三个 probe 连续失败后，**不再凭感觉找第四个**，改成把 v3 所有现有行为通道
用**同一套六条资格标准**扫一遍（`novel_capacity_audit.py`，n=591，存活 100%）：

```
  Q1 近乎全员可参与  参与率 ≥ 70%          Q4 不决定生死    （规则 65）
  Q2 个体差异足够    p90−p10 ≥ 0.10        Q5 有回读通路    进 score()/goal
  Q3 确实是紧约束    ≥20% 个体被它限制住    Q6 两世界同等可及（规则 67）
```

```
通道                    Q1参与率  Q2方差  Q3紧约束  Q4非生死 Q5回读 Q6同等   资格
sleep / energy         100.0%✓  0.146✓  54.0%✓     ✗      ✓     ✓    不够格
explore / 非食物产出       76.0%✓  0.640✓  23.0%✓     ✓      ✓     ✓    ★够格
material / build        58.4%✗  0.426✓  75.5%✓     ✓      ✓     ✓    不够格
goal 结构               99.3%✓  0.533✓  87.1%✓     ✓      ✓     ✓    ★够格
knowledge              99.7%✓  0.500✓  87.8%✓     ✓      ✓     ✓    ★够格
shelter / storm        100.0%✓  0.976✓  51.6%✓     ✗      ✓     ✓    不够格
objects / 动作合法性         0.0%✗  0.000✗   0.0%✗     ✓      ✓     ✗    不够格
```

### ★ 结论：026 不封存 —— 有三个通道够格 ★

**"三次失败已足够宣布 v3 做不到"这个判断早了一步。**
三次失败的其实是**同一类通道**（资源经济：食物、材料），
而 v3 还有**非资源类**通道从未被测过：`goal 结构`、`knowledge`、
`explore` 的**信息性产出**。

> ### ★ 规则 69：连续失败要先归类，再决定是"换战场"还是"宣布不可能" ★
> Probe A / B / A2 全部建在**资源经济**上（食物 → 食物 → 材料）。
> 三次失败只证明**资源经济这一类**不行，不能外推到"v3 的动作经济不行"。
> **宣布架构性不可能之前，必须先做一次覆盖全部通道的统一标准扫描。**

### 三个够格通道的附加警告（下一轮必须先堵）

- **`goal 结构`（最强）**：99.3% 的球采用过 ≥2 种目标、主目标占比 p90−p10 = 0.533、
  87.1% 没有被单一目标垄断。goal 直接进 `score()`，两个世界共用同一套
  `GOAL_ACTIONS`。⚠ Q4 是"不直接决定生死"而非"不可能影响存活" ——
  可行性校准仍须照常验存活 ≈ 100%。
- **`knowledge`**：⚠ **key 级别的 Q6 不对称** —— `books` 这条 knowledge
  只能由 `read` 获得，而 `read` 需要书，**书只在丰富世界**。
  通道整体合格（其余 key 两边都拿得到），但**任何 probe 都不得触碰
  book 来源的 knowledge**，否则退回规则 67 的陷阱。
- **`explore` 非食物产出`**：⚠ **Q3 只有 23.0%，刚过 20% 线** ——
  意思是 **77% 的球已经拿到 `loves_exploring`**，信息性产出**接近饱和**。
  这与 A2 的失败机理（加成落在用不掉的地方）同型，**风险最高**。

### 若下一轮三个通道也全部不合格

那时才以「v3 不具备可干净检验 generalization 的动作经济」封存 026，
并分叉 v4。**v4 的设计目标届时非常明确 —— 不是让模型更复杂，
而是补上被实验暴露的缺口：至少一个【不决定生死】【近乎全员可参与】
【具有多种有效策略】【允许 agent 对新 contingency 产生行为适应】的经济。**

> ★ 方法论上的关键区别 ★
> 升级 v4 **不是为了"把论文结果调出来"**，
> 而是因为 **group-blind feasibility testing 已经明确证明
> frozen v3 缺少测量这个问题所需的自由度**。这两个动机差别极大。


## goal-pair 小审计：Probe C 的放行前提（`goal_pair_audit.py`，n=591）

capacity audit 的「99.3% 用过 ≥2 种 goal」不能自动说明
`see_the_world` / `improve_home` 这**两个特定目标**够普遍。单独查：

```
goal              立过的 agent   占 goal-days   人均天数   个体占比 p90−p10
improve_home         95.9%        25.3%       7.6        0.433  ★
stock_food           94.2%        25.3%       7.6        0.567
see_the_world        96.1%        48.0%      14.4        0.533  ★
learn                 0.0%         0.0%       0.0        0.000
recover              16.6%         1.3%       0.4        0.067

两种【都】经历过的 agent ： 92.7%      ← 冲突才有对象
这一对合计占 goal-days  ： 73.3%
目标切换次数（30 天）    ： 中位 10（p10 2，p90 12）
```

**放行条件大幅满足。** 这一对是 common garden 里的**主导目标对**，
不是边角料，而且 92.7% 的球两种都立过 —— 冲突有充分的作用对象。

⚠ 顺带确认了两件事：
- **`learn` 参与率 0.0%** —— 与 `read = 0` 一致（基准世界无书）。
  所以 M0 的 goal 特征里，`learn` 与 `recover`（16.6%）接近死维度，
  **别把特征集用死维度撑数**。
- 目标切换中位 10 次/30 天 → **goal switch 动力学本身很活跃**，
  Probe C 想作用的就是这个。

### shelter 的两个结构点（核对了代码，支持 40 这个下限）

```
sim.py:792   s += 10 if self.shelter > 30 else -5        ← 睡眠打分的阶跃
sim.py:662   if self.shelter < 75:  pri = (75-shelter)/75*0.8 + c   ← improve_home 优先级
sim.py:611   clamp(self.shelter / 80.0, 0, 1)            ← improve_home 目标进度
```

**shelter = 30 确实是个结构点**（睡眠打分从 +10 跳到 −5）。
所以硬下限取 **40** 是有依据的：既避开 30 的阶跃，
又落在 `improve_home` 优先级**有响应**的区间（< 75）内 ——
而拉平点 shelter = 50 本来就在这个区间里，进入时 `improve_home` 已经是活跃的。


## Probe C「离家失修」：退役（`novel_calibrate3.py`，N=300）

机制：每次 explore 使 shelter 损耗 κ（硬下限 40），`build` 按原规则修复；
**ON/OFF 背景完全同构**（都 `storm_chance=0`），唯一差异是 κ；
分叉后只清 `agent.goal`，不动 traits/floors/knowledge/flags/goal_satiation。

```
   κ      饱和率    被截断率    失败频次（20 格）
 0.05     75.3%     0.0%      ②未饱和<20%      20/20
 0.10     76.1%     0.1%      ④动作landscape变 20/20
 0.20     77.6%     0.1%      ⑤goal层也变      19/20
 0.40     80.4%     0.1%      ③两goal仍活跃     5/20
 0.80     85.0%     0.3%
```

### ★ 规则 70：饱和度要量"干预还能不能施加"，不是"变量贴没贴边" ★

我最初把饱和定义成 `P(shelter == 40)`（贴边时间比例）。**这是错的。**
Probe C 的守卫是 `if shelter > 40`，而 shelter 有 **0.35/tick 的自然衰减**，
会自己滑到 40 以下；此后 explore 再多也**静默失效**，
但 shelter 并不会停在 40，所以"贴边比例"接近 0 —— **严重低估饱和**。

正确定义：**explore 发生时因 `shelter ≤ 40` 而无法再施加损耗的比例**。
实测 **75–85%**（阈值 20%）。两个口径差了两个数量级，结论相反。
**被截断率只有 0.0–0.3%**，正是"贴边口径会显示无饱和"的直接证据。

### ⚠ 真正的原因：shelter 是**双峰**的，不是"稳态在 32"

我上一条说"稳态 ≈ 32"也不准确。直接测 OFF 条件下的逐日轨迹（n=237）：

```
进入后第N天    中位    p10    p90    <40 的比例   <30 的比例
第 0          41.6   41.6   99.7      0.0%       0.0%
第 1          33.2   33.2   99.0     63.6%       0.0%
第 2          24.8   24.8   97.9     61.9%      61.9%
第 5           0.0    0.0   99.3     51.7%      51.7%
第 29          0.0    0.0   97.6     54.4%      53.4%
```

**p10 = 0.0 而 p90 = 97.6 —— 极端双峰。**
约 52% 的球把 shelter 彻底放弃、长期为 0；另外约 48% 一直维持在 ~98。
"均值 32–41"完全是双峰混出来的假象。

对 Probe C 而言：

- **52% 的球**：第 2 天起 shelter ≤ 40 → κ **永远打不到**
- **48% 的球**：shelter ~98，一次 build 就 +22 → κ=0.8 也是**毛毛雨**

**没有任何人群落在 κ 能起作用的区间里。**

### ★ 规则 71：v3 的资源状态普遍双峰，梯度型干预没有中间地带可作用 ★

把四轮并起来看，同一个形状反复出现：

```
材料    77% 恒为 0    23% 囤到 100–200        （规则 68）
shelter 52% 恒为 0    48% 维持 ~98           （本节）
食物    全员紧约束     但 eat 跨个体 SD=0.0007  （规则 64/66）
```

**v3 的正反馈（性状漂移 + 目标持续）会把 agent 推向专精**，
于是每条资源轴都塌成"全投入 / 全放弃"两堆。

> **讽刺的是：正是这套产生持久个体差异的正反馈机制，
> 同时消灭了梯度型 novel contingency 可以作用的中间地带。**

这可能才是 A / B / A2 / C 四次失败的**共同根因**，
而不是四个各自独立的设计失误。

⚠ **但不据此宣布 026 终结** —— 上次就是这么早了一步（规则 69）。
capacity audit 里还有一个通道**不是双峰**：

```
knowledge   99.7% 至少有 1 条    87.8% 少于 4 条    → 分布是【梯度】的，不是双峰
```

`knowledge` 是唯一一个**近乎全员参与、且取值连续分布**的通道。
下一轮该不该去它那里，等拍板。


## ★ 规则 72：manipulation check 的窗口口径必须与 G1 一致 ★

`novel_calibrate3.py` 里发现一个真实实现错误（**记录下来，不悄悄改**）：

```python
def act_share(r, w_dec):        # ← w_dec 传进来了，但函数体里根本没用
    acc = Counter()
    for h in r["per_hour"]:     # ← 汇总的是【整个 consequence window】
        acc.update(h)
```

而 goal 那一侧用的是 `r["goals"][:w_dec]`。于是：

```
goal manipulation check   = decision window   ✓
action manipulation check = 整个 consequence window   ✗
```

**这与规则 62「decision / consequence 窗口分离」没有对齐。**

> ### 规则 72 ###
> **所有 manipulation check 必须与 G1 用同一个窗口口径。**
> 两侧窗口不一致时，"goal 变了但动作没变"这类判读**没有意义** ——
> 你比较的是两个不同时间尺度上的量。
> 实现上：动作轨迹要按天（或按 decision window）单独存，
> 不能只留 `per_hour` 的全窗口汇总。

⚠ **这不影响 Probe C 退役的结论** —— 退役靠的是 intervention saturation
（75–85%）与 shelter 双峰轨迹，两者都是独立证据，且都在窗口口径之外。
但 Probe D 若继续，**必须先修**。

## knowledge effective-support audit（group-blind，已排除 books，n=591）

沿用规则 70：不问"变量看起来连不连续"，问**"固定大小的干预还能不能改变
argmax"**。knowledge 进决策的通路是
`score += KNOWLEDGE_WEIGHT(12.0) × know(key) × slack`（`sim.py:835`），
所以可动用幅度上限是 12.0，能否改变行为取决于**决策时 top1−top2 的间距**。

```
【1】knowledge_strength（★不是条数★）
key            持有比例   均值强度    p10     p50     p90
far_places      77.0%    0.746    0.000   0.979   0.980
shelter         46.4%    0.439    0.000   0.000   0.980
food            88.8%    0.646    0.000   0.680   0.979

【2】决策间距 margin = top1 − top2   （n = 425,520 个决策 tick）
    p10 0.59   p25 1.76   中位 4.57   p75 9.22   p90 16.42

【3】有效支撑
   Δ     可翻转的决策占比   responsive agent 占比
  1.0        15.7%            67.9%
  3.0        37.4%           100.0%
  6.0        59.1%           100.0%
 12.0        83.8%           100.0%
```

### ⚠ 我的放行判据口径写错了（更正，不追认）

我把放行条件写成「responsive **agent** 占比 ∈ [20%, 80%]」，于是只有
Δ=1.0 "合格"。**但那个上界是错的**：

- 规则 70 担心的饱和是**低端**（干预再也改不动任何东西）
- **高端**的风险是"干预压倒一切"，而那要用**可翻转的决策占比**衡量，
  不是用 agent 占比。Δ=3.0 时 100% 的 agent responsive，
  意思只是"每只球都还有活动空间"，那是**好事**，不是饱和。

正确读法：**Δ ∈ [1, 6] 给出 16–59% 的决策可翻转，且每只球都有余量
—— 这是四轮以来第一个真正有动态范围的通道。**
对照 Probe C：75–85% 的干预时刻**根本无法施加**。

**判据该怎么定，我不自行改口径**（那正是 adaptive analysis）——
需要拍板。我的建议：门槛应设在**可翻转决策占比 ∈ [20%, 60%]**（对应 Δ≈2–6）。

### ★ 规则 73：knowledge_strength 本身是近乎二值的，梯度在 margin 里 ★

【1】那张表要看仔细：`far_places` 的 p10 = 0.000、p50 = 0.979 ——
因为 strength 学到即回满 1.0，之后每天只衰减 0.02。
**所以"有没有这条知识"几乎是 0/1，不是梯度** —— 规则 71 在这里同样成立。

真正梯度的是 **决策间距 margin**（p10 0.59 → p90 16.42）。

> 所以 Probe D 必须**作用于 margin 结构**，
> **不能依赖"knowledge 强度是连续的"** —— 它不是。
> 这条要写进 Probe D 的设计约束，否则会重蹈 A2「乘性加成乘到 0 上」的覆辙。


---

# ★ 实验 026 封存 —— v3 的 novel-situation generalization 无法干净检验 ★

**不再设计 Probe D。026 到此结束。**

## 结论（诚实版，可直接进论文）

> 在冻结的 v3 架构中，我们**没有找到任何可以干净检验
> novel-situation generalization 的动作经济**。这不是"没想到好 probe"，
> 而是四轮 **group-blind feasibility testing** 得出的结构性结果。

四个 probe，四种失败，**每一次都在烧掉 final block 之前被拦下**：

| Probe | 机制 | 失败原因 | 规则 |
|---|---|---|---|
| A 冻土 | shelter 门控 world.food | 生存分裂：探索派存活 35–51% | 64 |
| B 盐碱地 | 采材料↔觅食零和耦合 | 生存分裂（反向）：盖房派存活 13%→0% | 64 |
| A2 探路 | explore 提高采集 yield | **乘性加成落空**：77% 的球从不采集，乘的是 0 | 68 |
| C 离家失修 | explore 损耗 shelter | **干预饱和 75–85%**：shelter 双峰，无人在作用区 | 70 / 71 |

## ★ 共同根因：规则 71 ★

```
材料      77% 恒为 0     23% 囤到 100–200
shelter   52% 恒为 0     48% 维持 ~98
knowledge 近乎 0/1（学到即回满 0.98，每天只衰减 0.02）  ← 规则 73
食物      全员紧约束      但 eat 跨个体 SD = 0.0007
```

**v3 的正反馈（性状漂移 + 目标持续）把 agent 推向专精，
每条资源轴都塌成"全投入 / 全放弃"，梯度型干预没有中间地带。**

> **同一套产生持久个体差异的正反馈机制，
> 同时消灭了梯度型 novel contingency 可以作用的中间地带。**
>
> 这解释了为什么本项目在 **persistence 阶段很成功、
> 在 generalization 阶段这么困难 —— 是同一个机制的两面。**

## 唯一逃出去的东西：decision margin

`knowledge effective-support audit` 发现：内部状态高度极化，
**但最终的决策间距没有完全极化**（margin p10 0.59 → p90 16.42）。
Δ=3.0 的标准化扰动可以翻转 **37.4%** 的决策，且每只球都有余量。

通俗地说：**这些小球的"性格"已经很固定，但在那些它们自己也有点犹豫的决定上，
仍然留着一个入口。** 这一点被保留下来，但**不再用它去承担 generalization 这个
大结论** —— 它转为规则 71 周边的一个机制探针（见下）。

## 026 留下的资产（不作废）

`novel_situation.py` 的机制层（GatedWorld / 三个 probe / 拉平 / 规则 61 分叉 /
完整可执行状态序列化）、四套 group-blind 校准脚本、
以及规则 **60–73**。这些在 v4 阶段可以直接复用。

---

# 收尾三件事（论文剩余工作）

1. **规则 71 因果消融** —— 证明是不是那套正反馈同时造成
   specialization 与 plasticity 下降。**比开发 v4 更科学**：
   v4 会改变模型，消融是直接问 v3 里的机制到底是不是原因。
   附带机制探针：**标准化决策扰动（Δ=3.0）下的 susceptibility**
   —— ⚠ 它只作 mechanistic assay，**不承担 generalization 结论**。
2. **v3 参数稳健性** —— 目前最明确的投稿硬缺口。
   现有 `sweep_results.csv` / `holdout.csv` 是 **v2** 的；
   论文的 candidate architecture 是 frozen v3，
   审稿人必然会问"为什么 robustness 分析用的是旧模型"。
   → 已启动 `param_sweep.py --out sweep_results_v3.csv`（500 组 × 300 种子，
   带 `resultmeta` 版本列）。
3. **reproducibility + ODD + repo 清理** —— prereg / seed ledger / frozen dirs /
   SHA256 已经到位，但工程入口还不行：
   `pytest -q --collect-only` 会因为 `v2_frozen/`、`v3_frozen/` 与根目录
   **同名 test module** 而 collection error。
   目标：**fresh clone 后一条命令跑完核心 regression / self-check。**


## ★ v3 参数稳健性（`sweep_results_v3.csv`，500 组 × 300 种子，45.5 分钟）★

补上投稿硬缺口：论文的 candidate architecture 是 frozen v3，
但此前的 robustness 分析用的是 v2。现在有了 v3 的自己的一份。

```
                      v2（372→324 组）              v3（372→337 组）
移植比值（作息）★头条★  1.058  IQR[1.010,1.128]      1.076  IQR[1.010,1.153]
                      > 1 的比例 80.2%              > 1 的比例 78.3%
移植比值（目标）        1.061  IQR[0.992,1.116]      0.998  IQR[0.941,1.052]
                      > 1 的比例 72.2%              > 1 的比例 48.7%   ← ⚠
对数比值（作息）        0.048  > 0 的 78.4%           0.062  > 0 的 76.6%
```

### ★ 头条稳健性在 v3 下保住了 ★

**作息（动作分布）轴**：中位 1.058 → **1.076**（略强），
参数集合里 **78.3%** 的组合仍然 > 1（v2 是 80.2%）。
对数比值同样保住（76.6% vs 78.4%）。
**这是论文的头条指标，跨 500 组随机参数依然成立。**

顺带：剔除团灭的组数 **50 → 35**（v3 死亡率修正的直接体现）。

### ⚠ 但目标（goal）轴在 v3 下塌到随机水平

`72.2% → 48.7%`，中位 `1.061 → 0.998`。**基本就是抛硬币。**

机制上说得通：v3 唯一的改动是 `COND_RECOVER_AT 30→65`，
体质常驻高位 → `recover` 目标很少被触发（goal-pair 审计实测只有 16.6%）
→ 两个世界的**目标剖面因此收敛**。
换句话说，**v2 里"目标层的世界差异"有相当一部分是体质差异的投影**，
而那个体质差异正是我们在 v3 里修掉的东西（规则 46/47/49）。

> ### ★ 规则 74：v3 只保住了动作层的稳健性，目标层的没有 ★
> 论文里必须**分开报**：
> - **动作分布轴**：中位 1.076、78.3% 的参数组合 > 1 —— 稳健，可作头条
> - **目标轴**：中位 0.998、48.7% > 1 —— **在参数集合上不稳健，不得作为主张**
>
> ⚠ 这条不是坏消息，而是**修正 confound 之后应有的结果**：
> 目标层的差异原来是搭了体质差异的便车。
> **修掉 mortality confound 的代价，就是失去一个原本不干净的次指标。**

### 参数敏感度：v2 / v3 高度一致

```
              v2       v3
TRAIT_DRIFT        +0.432   +0.442   ← 两版都是第一
PERSONALITY_WEIGHT +0.289   +0.357   ← 两版都是第二
GOAL_BONUS         −0.050   −0.214   ← v3 里升到第三
LANDMARK_BONUS     −0.153   −0.028   ← v3 里退出
```

**`TRAIT_DRIFT` 在两个版本上都是最敏感参数（ρ≈0.44）** ——
这与规则 71 消融的独立发现互相印证：**正反馈增益是 persistence 的主要来源。**
两条完全独立的分析（参数随机化 vs 定向消融）指向同一个机制，
这在论文里是很强的一句话。


## ★ 规则 71 因果消融结果：后半部分撤回 ★（`rule71_ablation.py`，N=300）

```
TRAIT_DRIFT   n    (a)移植比值  (b)shelter极化  (b)material两极  (c)可翻转决策  margin中位  material中间层
   0.00     289      1.021        31.1%         93.8%         41.1%      3.95      6.2%
   0.30     288      1.012        56.2%         93.8%         38.6%      4.29      6.3%
   0.60     290      1.058        60.9%         93.6%         37.6%      4.57      6.4%
   1.20     289      1.157        58.7%         94.6%         38.0%      4.67      5.4%   ← v3 默认
   2.40     286      1.575        78.8%         89.7%         44.2%      3.81     10.3%
```

### ✓ 前半部分：正反馈**因果地**造就 persistence

移植比值 `1.021 → 1.575`，基本单调，幅度很大。
**drift = 0 时比值只有 1.021 —— 几乎没有个体差异残留。**

这与 v3 参数扫描**独立印证**：`TRAIT_DRIFT` 是 500 组随机参数里
最敏感的旋钮（Spearman ρ = **+0.442**，v2 上是 +0.432）。
**两条完全独立的分析（参数随机化 vs 定向消融）指向同一个机制。**

### ✗ 后半部分：不成立，**撤回**

> ### ~~规则 71（原文）：同一套正反馈既造就 persistence，又消灭了梯度干预
> ~~可以作用的中间地带~~ ★ 撤回 ★

事前预测是"(c) 可翻转决策随 drift 单调下降"。实测：

```
41.1% → 38.6% → 37.6% → 38.0% → 44.2%
```

**从 0 到默认值 1.2 只掉了 3.1pp，而且到 2.4 反而升回 44.2%。
这不是"可塑性被消灭"，这是几乎不动。**

更关键的是 **material 两极程度与 drift 完全无关**：
`93.8% → 89.7%`，**drift = 0（完全没有性状正反馈）时就已经是 93.8%**，
中间层始终只有 5–10%。

> ### ★ 规则 71（修订版）★
> `TRAIT_DRIFT` 正反馈**因果地**产生 persistence（1.02 → 1.58），
> 并且**部分地**造成 shelter 的极化（31% → 79%）。
> **但它既不造成 material 的双峰（drift=0 时就已 93.8%），
> 也不显著降低决策层可塑性（Δ=3 可翻转决策始终在 37–44%）。**

### ⚠ 连带更正：026 封存词里那句"漂亮的讽刺"是错的

我在 026 封存时写过：

> ~~"同一套产生持久个体差异的正反馈机制，同时消灭了梯度型 novel contingency
> 可以作用的中间地带…… 这是同一个机制的两面。"~~

**这句话被本次消融证伪，撤回。** 正确的说法是：

> **阻挡 026 四个 probe 的资源双峰，主要是 v3【资源动力学本身】的性质
> （material 只被 build 以 3/次消耗、shelter 以 0.35/tick 单调衰减），
> 与产生 persistence 的性状正反馈基本无关。**

所以 026 的封存结论要**降级为更保守、也更准确的版本**：

> **v3 的资源经济不支持梯度干预** —— 而不是 ~~"正反馈消灭了可塑性"~~。

前者数据撑得住，后者是个更漂亮但**没有证据**的机制故事。

> ### ★ 规则 75：机制故事越漂亮，越要用定向消融去证伪 ★
> "同一个机制的两面"读起来非常像论文的 highlight，
> 而且它与 026 的全部观察都相容 —— 但**相容不等于因果**。
> 一次 5 档的定向消融（约 20 分钟）就把它推翻了。
> **在把一个机制解释写进论文之前，先问：能不能直接把那个机制关掉试试。**


---

# ★ v3 persistence paper package 收尾 ★

## 1. repo 修复 + 复现入口

`pytest --collect-only` 从 **10 个 collection error / 收不到测试**
变成 **8 个测试正常收集、全绿（0.6 秒）**。

根因：根目录、`v2_frozen/`、`v3_frozen/` 各有一套同名模块
（`p1_test.py` / `p2_test.py` / `relaxation_test.py` / `rule48_test.py` /
`test_022_regression.py`），pytest 按 basename 建模块名 → `import file mismatch`。
**不能靠改 frozen 目录解决**（有 SHA 校验），所以在根目录加 `pytest.ini`
限定 `testpaths = tests` 并排除两个 frozen 目录。
顺带解决了另一个隐患：根目录那些 `*_test.py` **不是 pytest 测试而是实验脚本**，
之前会被 `*_test.py` 模式误收，一跑就是几十分钟的模拟。

新增：`tests/test_selfcheck.py`（冻结完整性 / 冻结导入 / AST 比对 v2-v3 唯一差异 /
机制层 6 项 / 规则 72 回归 / 确定性）、`pytest.ini`、`requirements.txt`、
`REPRODUCE.md`（三层复现 + 产物来自哪个模型 + 种子账本）。
废弃与退役脚本加了头部标记，**一个都没删**。

> ### ★ 规则 76：测试写完要做突变检验，否则"全绿"可能是假的 ★
> 8 个测试 0.6 秒跑完，看着像没真跑。故意改坏
> `v3_frozen/SHA256SUMS.txt` 的一个校验值 → 测试立刻变红；还原 → 全绿。
> **没有突变检验的绿色不算数。**
>
> 另：第一版的"v2/v3 只差一个常量"测试用**剥掉 `#` 注释后逐行比对**，
> 结果 v3 docstring 里那段说明被当成代码差异。改用 **AST 比对并剥 docstring**
> 才是真正的"可执行差异"。

## 2. ODD 模型描述（`ODD.md`）—— 当作最后一次静态审计

按 ODD 规范写，每一句都回代码核对。**审计出七条"我知道所以没写"的隐含机制**：

```
take_food            以为可清零 world.food 封锁 → 实为从【库存】扣，清零 = 烧存粮
memories             以为纯日志 → 被 recall() 回读
action_log           以为纯日志 → 喂【目标进度】
goal_satiation       漏了 → 被回读（不应期）
storm_damage         漏了 → 【动态属性】，暴雨后才存在
explore 食物产出      以为足以独立维生 → 0.14/tick vs 需 0.11/tick，扣睡眠为负
knowledge_strength   以为是连续通道 → 近乎二值（0 或 0.98）
```

### ★ 规则 77：行号引用必须标明是哪一版的行号 ★

`v2_frozen/sim.py` 1013 行，`v3_frozen/sim.py` 1043 行，
**偏移不是常数**（头部 docstring +27，中部 `MODEL_VERSION` 再 +3）：

```
                        v2     v3    偏移
def take_food           154    181   +27
KNOWLEDGE_WEIGHT×know   805    835   +30
hardship += deficit     936    966   +30
_hardship_anchor        938    968   +30
```

⚠ **本记录里实验 023 及更早引用的 `sim.py:NNN` 用的是 v2 编号**，
在 `v3_frozen/` 里要 +27 或 +30。`ODD.md` 的行号已统一为 v3_frozen 编号。

### 新发现的隐藏机制：平局裁决

`max((score, action))` 在分数相同时按**动作名字母序**裁决 →
`sleep` 恒胜、`build` 恒败。**实测 19,200 个决策 tick 中精确平局 0 次**，
存在但从未触发。仍然记下 —— 若日后有人改动打分让平局变常见，
行为会系统性偏向 `sleep`，而这一点此前不在任何文档里。

## 3. Paper-claim audit（`CLAIMS.md`）

每个 claim 落到三类之一：**A 主结果**（v3 冻结后直接支持）、
**B 机制结果**（定向消融支持）、**C 限制**（无证据，明确不声称）。

```
A1 持久行为差异          final H1 = 1.142 [1.098,1.183] + 稳健性 78.3%
A2 不是 mortality artifact 死亡率 8.1%→4.3% 而效应未减反增
A3 不依赖地板的通路       final P1 = 1.134 [1.090,1.175]
A4 离散记忆不是长期载体   final P2 不过（v2/v3/final 三次一致）
A5 情节记忆逐位 no-op     三次运行 fingerprint 完全相同

B1 TRAIT_DRIFT 因果驱动   消融 1.021→1.575 + 参数扫描 ρ=+0.442（两法独立印证）
B2 地板承担大部分持久性   1.142 → 1.046
B3 起作用的是"地板存在过" anchor 内容只解释 1.3%，阴性对照逐位相同
B4 阈值 65 需跨过怠惰谷   丰富世界 24.3%→36.3%→2.0%

C1 无地板残余效应         ⛔ 落在检出边界，无法裁决（不许说有，也不许说没有）
C2 目标轴                 ⛔ 不作主张（v3 参数集合 48.7%）
C3 novel generalization   ⛔ 不许写"失败"；只能写"v3 架构无法提供干净的
                            novel-contingency 测试接口"
C4 正反馈降低可塑性        ⛔ 整条删除（被消融证伪）
C5 intended purpose       ⛔ 不许声称模拟真实人格形成
C6 架构射程               ⛔ 禁止"agent 学会/理解/意识到"这类措辞
```

另附**禁止措辞速查表**与**数字来源核对表**
（标明哪些数字来自 v2，不得当作 v3 的证据）。

---

## ★ 阶段线：v3 persistence paper package 收尾完成 ★

实验阶段到此结束。产出清单：

```
v2_frozen/ v3_frozen/            两版冻结 + SHA256
FINAL_PREREGISTRATION.md         预注册（含修订 A）
final_confirm_result.txt         预注册最终确认（seeds 50000–51499，跑过一次）
sweep_results_v3.csv             v3 参数稳健性
NOVEL_SITUATION_DESIGN.md        026 设计（已封存，阴性结果）
ODD.md                           模型描述 / 静态审计
CLAIMS.md                        claim ↔ 证据对照 + 禁止措辞
REPRODUCE.md  pytest.ini  tests/ 复现入口
模拟实验记录.md                    全部过程（含所有被推翻的结论，原文保留）
```

规则累计 **1–77**，其中 **43、48、50、71 的一部分、规则 33** 是被后续实验
**撤回或修正**的 —— 原文一律保留并注明何时被何证据推翻。

---

# ★★ v3 线锁死 ★★（2026-08-17）

**不再挖 v3 persistence，不再补第 78、79 条机制实验。**

唯一的重开条件：**发现会改变已有结论的真 bug**。
（"想到一个新的机制解释""想再验一个漂亮的假说"都不算。）

## 分工写死

```
v3   回答：过去能不能【留下】。            —— 已完成，见 CLAIMS.md 的 A/B 两类
v4   回答：留下来的东西能不能【用于未来】。 —— 实验 027
```

## 实验 027 —— Novel-Task Transfer（下一阶段，未开始）

**唯一的研究问题：**

> 两只起点完全相同、过去经历不同、后来已经形成持久差异的 agent，
> 在第一次面对一个**双方都从未见过的新问题**时，
> 会不会因为过去不同而**学得不同、选择不同、或适应路径不同**？

### ★ 不许再硬塞进 v3 ★

026 已经给出证据：**v3 的 food / material / shelter 世界不是一个好用的
generalization test bed**。四个 probe 全部在**碰 final seeds 之前**
被机制审计拦下 —— 它们实际上**替我们省掉了一次错误的"确认实验"**。

### v4 的明确设计要求（由 026 的失败反推，不是"让模型更复杂"）

v3 缺的是一条**原生通道**：

```
外部新规则  →  agent 原生感知  →  自己评估  →  自己选择
```

v3 只有 `score()` 这一层反应式打分，**没有在场因果学习**，
所以任何"新契约"都只能靠实验层偷偷给 `score()` 加分来实现 ——
**那是把结论写进去，不是测出来。**

配套要求（同样来自 026 的实测，不是凭空加）：

| 要求 | 来源 |
|---|---|
| 至少一个**不决定生死**的经济 | 规则 65（动食物只能压出生存差异） |
| **近乎全员参与**（≥70%） | 规则 68（乘性加成对不做该动作的人恒为 0） |
| **不被正反馈塌成双峰**、有连续中间态 | 规则 71 修订版 + 规则 73 |
| 多种**都能活**的有效策略 | 规则 64（否则是生存分裂不是策略分岔） |
| 两个发育世界**同等新颖** | 规则 67（books 那种不对称不行） |

### 027 可以直接继承的资产

- `novel_situation.py` 机制层：sibling 分叉（规则 61）、完整可执行状态
  序列化与突变测试（规则 63）、状态拉平、non-destructive gate（规则 60）
- **group-blind feasibility calibration 这套纪律本身** —— 这是 026 最大的产出：
  **在烧掉 final block 之前证明"这个实验测不了它想测的东西"**
- 规则 55–77（确定性、可判定性、窗口口径、饱和度量、突变检验……）
- **种子账本：`60000–61499` 因 026 封存而从未使用，仍然干净**

### ⚠ 027 开始时要先做的一件事

v4 一旦分叉，**v3 的全部结论不自动继承**。
必须先回答：**v4 还有没有原来的 persistence architecture？**
（照 023 的做法：同种子重验 H1 / P1 / P2 / 情节记忆 no-op。）
**不重验就把 v3 的结论挂到 v4 上，是方法学错误。**

---

## 这条线最终的位置

> v3 证明了 **experience leaves persistent differences**。
>
> 027 要问的是更强的那个问题 ——
> **过去是否真正塑造了一个 artificial agent 以后面对未知世界的方式。**


---

# ★★ 实验 027 —— Novel-Task Transfer + Reversal · FINAL ★★

**seeds 60000–61499，只跑一次，已执行完毕（2026-08-17）。**
模型：**v4 = `v3_frozen/` 核心（逐字节不动）+ `novel_task.py`**
参数指纹 `26778f672e9e7009`（α=0.05 β=0.05 τ=0.20）
记录：`final_027_result.txt` + `final_027_console.txt`（两份，全文抄录如下）

## 结果（逐项从文件抄，未凭记忆）

```
n = 1428 / 1500
attrition   rich = 0.0000   poor = 0.0480   keep = 0.9520   ✓ 通过 90% 闸

臂           指标                              配对差均值        95% CI              p
main        H2 restricted switch latency   -0.0798  [-0.1632, -0.0035]   0.0464  *
main        H1 trial 1–10 exploration      +0.0006  [-0.0002, +0.0015]   0.1375
hist_blind  两项                            +0.0000   逐位为零
trait_level 两项                            +0.0000   逐位为零

可判定性诊断（8 个分析种子）
  H2  下界范围 [-0.1632, -0.1611]  MC SD 0.0009  判显著 8/8
  H1  下界范围 [-0.0003, -0.0002]  MC SD 0.0000  判显著 0/8
```

## ★ 判读（按修订 01 的三值规则）★

> ### PRIMARY H2 = ◐ 统计上存在 history effect，但**功能意义未建立**
>
> `Δ = −0.0798 trial`，95% CI `[−0.1632, −0.0035]` **排除 0**，
> 但**整段落在 ±1 trial 的 practical-equivalence region 之内**。

- 方向：`d = L_rich − L_poor < 0` → **丰富世界出身的球在反转后切换略快**
- 幅度：**0.08 trial**，量程 0–36，约 **0.22%**，约 **0.01 SD**
- 8/8 个分析种子都判 CI 排除 0 → **不是蒙特卡洛噪声**，是真的可检出
- **但它小到没有功能意义。**

**secondary H1 不获支持**（CI 含 0，p=0.1375）。
⛔ 按预注册，H1 不得替代 primary。

**两个 pathway-isolation control 逐位为零** —— 无泄漏，
history effect 按设计经 `curiosity/caution → novelty_style → β_i` 进入任务。

## ★ 规则 79：修订 01 正好救下了这一次 ★

如果没有 SESOI，这份结果会被写成：

> ~~"H2 显著（p = 0.046），developmental history 改变了 reversal adaptation。"~~

而真相是：**在 n=1428 下，0.08 个 trial 的差异就足以"显著"。**
量程是 36 个 trial。

**SESOI 是在彩排之后、看 final 之前加的，而且是从 pooled latency 尺度
（mean 18.04 / SD 8.15 / 最小自然单位 1 trial）推的，不是从组间对比推的。**
它是这次唯一挡住"大样本把微小差异包装成发现"的东西。

⚠ 一个诊断输出的弱点（记下，不改）：可判定性诊断打印的是**下界**范围，
而本例中决定"CI 是否排除 0"的是**上界**（−0.0035，贴着 0）。
`判显著 8/8` 已覆盖实质（8 个种子都排除 0），但打印的区间不是关键那一端。
下次应打印**离 0 最近的那一端**。

## 027 能写什么 / 不能写什么

| | |
|---|---|
| ✅ 可写 | 在一个双方都从未见过的新任务中，**检测到**由发育史带来的 reversal adaptation 差异（rich 略快），但**幅度低于预设的功能显著性门槛**，因此**不声称有实际量级的迁移效应** |
| ✅ 可写 | 该效应按设计经 `curiosity/caution → novelty style` 进入任务；两个 pathway-isolation control 逐位为零 |
| ⛔ 不可写 | ~~developmental history transferred to learning and adaptation in a jointly novel task~~ —— **功能门槛未过，这句话现在不能写** |
| ⛔ 不可写 | *generalized individuality*（本来就要等第二个正交任务） |
| ⛔ 不可写 | H1 的任何主张（未获支持） |
| ⛔ 不可写 | "搜索了所有历史载体" —— 任务没给别的载体输入口 |

## 这次实验最有信息量的地方

**不是"有没有效应"，而是"效应有多大"。**

v3 已经证明**过去能留下**（final H1 = 1.142，稳健性 78.3%）。
027 现在说明：那些留下来的差异，**确实能被一个全新任务读到**
（8/8 个分析种子都判可检出），
**但通过预先指定的通用探索接口传进去之后，只剩 0.08 个 trial** ——
在功能上接近于无。

> **过去留下的东西很实在；
> 它经由这条特定接口迁移到未知未来的部分，非常微弱。**

这是一个**信息量很高的阴性/边界结果**，而不是失败：
它把"个体差异能否影响未来"从一个模糊的大问题，
变成了一个**有量级、有门槛、有接口依赖性**的具体结论。

## 027 之后

按 closure rule，**看到结果后不再改任何关键设计**。027 到此结束。
`60000–61499` 已烧，不可再用。


## ★ 027 结论定稿（措辞已收紧）★

> **过去形成的差异可以在一个全新任务中留下统计上可检测的痕迹，
> 但通过 `curiosity/caution → novelty style` 这一条【预先指定的接口】
> 传过去以后，效应只有约 0.08 trial，远低于预设的 1-trial 功能门槛 ——
> 因此 persistence 并没有自动转化成有实际量级的 novel-task adaptation。**

### ⚠ 更正："8/8" 必须写成 analysis-level Monte Carlo stability

我先前把 `判显著 8/8` 表述成"8/8 可检出"，容易被读成"重复了 8 次都复现"。
**不对。** 那 8 次用的是**同一批 1428 对数据**，只更换**分析层**随机种子。

- ✅ 它证明的是：`p = 0.0464` **不是 bootstrap / 置换的蒙特卡洛抖动造成的**
- ⛔ 它**不能**证明 sampling replication 强
- ⚠ 而且 **CI 上界只有 −0.0035** —— 统计证据本身就贴着零边界

论文里只能写 **analysis-level Monte Carlo stability**。

> ### ★ 规则 80：区分"分析层稳定"与"抽样层可复制" ★
> 换分析随机种子重跑 = 只排除了 MC 噪声；
> 换**数据**重跑 = 才是复制。两者在报告里绝不能混用同一个词。

## ★ 全研究现在有两个不同量级的事实 ★

```
过去 → 持久行为差异              明显
    v3 final persistence ratio = 1.142；500 组参数中 78.3% 同向

持久差异 → 陌生任务中的功能迁移    极弱
    027 reversal latency = −0.0798 trial，整个 CI 落在 ±1 等价区间内
    初始学习（H1）甚至没有证据
```

> ### ★ 核心命题（这可能就是这套实验独有的贡献）★
> **Persistent individuality ≠ automatically functional generalization.**
>
> 一个 AI 可以真的被过去"养成不一样"，
> **但这并不意味着这种不同会在它以后遇到的新问题上产生明显作用。**

---

# 实验 028 —— Interface-Width Test of Historical Transfer（设计中，未开始）

**名字刻意不叫 generalization。** 因为 027 逼出了一个关键的概念区分：

```
有没有历史信息            ← v3 证明存在
新任务能不能【访问】这些信息  ← 027 证明：经一条窄接口只读得到极微弱的功能影响
```

**028 专门把这两件事拆开。**

## ★ 铁律：接口更宽 ≠ 给历史更大权重 ★

⛔ **绝不能**做成 `027: β=0.05 → 0.08 trial` / `028: β=0.5 → 2 trial`，
然后说"看，宽接口能迁移"。**那只是我们自己把历史信号放大了三倍/十倍。**

✅ 正确做法：**固定历史→任务的总耦合强度，只改变任务能读取多少个
彼此不同的历史维度。**

```
窄接口   只读 curiosity / caution           （= 027）
宽接口   读 curiosity / caution / industry   ← 但总 coupling budget 与窄接口相同
```

不是"一根管子 0.05 → 三根管子各 0.05（信号变三倍）"，
而是**同一份预算 K 分布到更多历史维度上**。

## primary question（不是"宽接口显不显著"）

> **在总 coupling strength 相同的情况下，
> broad-history interface 是否产生比 narrow interface 更大的
> 跨历史 novel-task effect？**

三种结局都有信息量：

| 结局 | 含义 |
|---|---|
| 宽接口明显更强 | 027 的 0.08 主要是因为**只给过去开了一根很窄的管子** |
| 宽接口仍接近 0 | agent 内部虽保存了明显的过去差异，但这些差异**总体上缺乏功能迁移能力** |
| 只有某一个维度有效 | **persistence 的不同组成部分具有不同的 transferability** |

## ⚠ 两个必须在开工前解决的设计问题（我提，待拍板）

### ① "总 coupling budget 相同"要定义在什么单位上

"相同"必须可操作。我认为唯一自洽的定义是
**由接口产生的 `beta_i` 在群体中的标准差 SD(beta_i) 相同** ——
因为**能造成组间差异的正是这个离散度**，不是维度个数、也不是权重之和。

### ② 等预算下加入一个"历史无关"的维度**必然稀释**

若 `industry` 携带的历史信息很少，把预算分给它就是把信号换成噪声，
于是 **"宽接口 ≤ 窄接口"可能是构造上注定的**，
而不是"接口宽度不管用"的证据。

**这不是设计缺陷，但必须提前声明**：
"宽接口更弱"是一个**可解释的结局（稀释）**，
它恰好对应上表第三行 —— **不同历史成分的 transferability 不同**。

### ③ 因此建议 028 不止两个臂，而是**按维度分解**

```
臂 A   只读 curiosity−caution        （= 027 的接口）
臂 B   只读 industry
臂 C   三维联合，总预算与 A/B 相同
```

**每个臂的 SD(beta_i) 都对齐到同一个 K。**
这样才能直接回答"哪一个历史成分可迁移"，而不只是"宽的好还是窄的好" ——
也正好覆盖用户列的第三种结局。


---

# ★★ 实验 028 —— Interface Breadth and Component Transfer · FINAL ★★

**seeds 70000–71499，只跑一次，已执行完毕（2026-08-17）。**
`interface_sha=f82497fb5b1ff535…`　`task_fp=26778f672e9e7009`
记录：`final_028_result.txt` + `final_028_console.txt` + `final_028_STARTED.lock`

## 1. Validity gates（先于 outcome 判读）—— 全部通过

```
contemporaneous A: μ=0.036750  SD=0.012280
臂      越界     边界质量   |Δμ|/SD_A  |ΔSD|/SD_A  support  budget
Bp     0.14%    0.14%       2.3%       0.4%        ✓        ✓
Bm     0.14%    0.14%       0.5%       0.2%        ✓        ✓
Cp     0.07%    0.14%       2.6%       1.0%        ✓        ✓
Cm     0.10%    0.10%       0.1%       0.9%        ✓        ✓

primary (C±) ✓ valid      secondary (B±) ✓ valid
```

门槛 support 2% / budget 10%，实测最坏 0.14% / 2.6% —— **余量 4–14 倍**。
frozen transform 在 confirmatory population 上 transport 干净。

pre-task attrition diagnostic（非 binding gate）：
rich 0.00% · poor 4.60% · 有效双胞胎 **1431/1500 = 95.40%**。

## 2. 结果（逐项从文件抄）

```
臂       E（配对差均值）        95% CI
A        -0.0391      [-0.0818, +0.0028]
Bp       -0.0252      [-0.0783, +0.0245]
Bm       +0.0433      [-0.0070, +0.1034]
Cp       -0.0741      [-0.1377, -0.0245]
Cm       -0.0370      [-0.0720, -0.0035]

★PRIMARY G = -0.0021 trial   95% CI [-0.0307, +0.0231]   SESOI = 1.0 trial
 secondary R_B = 0.0252      95% CI [+0.0007, +0.0650]
```

## 3. ★ PRIMARY 判读：CI 包含 0 ★

> **没有证据表明 broader historical readout 比 027 的窄接口更强。**
> `G = −0.0021 trial`，95% CI `[−0.0307, +0.0231]`。

对应预注册 §6 的**第二种模式**：

> **C ≈ A —— 更宽的历史 readout 没有增加 transfer；额外维度没有提供净增益。**

⚠ **不许**简化成"宽接口无效"。等预算下**多读一份与 A 正交的历史成分，
transfer magnitude 没有变化**，这是本实验的结论，不是关于"接口宽度"的普遍断言。

### ★ min(·) 这一刀救下了一个会成立的错误结论 ★

```
|E_Cp| = 0.0741      |E_Cm| = 0.0370      |E_A| = 0.0391
min(|E_Cp|, |E_Cm|) = 0.0370  ≈  |E_A| = 0.0391   →  G ≈ 0
```

**如果只看 C+，会得到 `0.0741 vs 0.0391`，接近两倍，
而且 C+ 的 CI `[−0.1377, −0.0245]` 排除 0** ——
足以写成"更宽的读取接口使 transfer 幅度翻倍"。

**但 C− 只有 0.0370。** 也就是说这个"增益"**完全取决于把 industry 残差
按哪个符号接进去** —— 而那个符号我们**没有任何机制理由**可以事先指定。

> ### ★ 规则 83：无语义方向的成分，必须用 worst-sign 判据 ★
> 预注册写死 `G = min(|E_C+|, |E_C−|) − |E_A|`，正是为了这一刻。
> 若当初只跑一个符号（哪怕事前随机选定），**有 50% 的概率得到
> "breadth gain 显著"的结论，而它完全是符号任意性的产物**。

### joint bootstrap 的收益也直接可见

`G` 的 CI 宽 **0.054**，而单臂 CI 宽约 **0.08** ——
**差值的 CI 比任一单臂还窄**，正是同种子相关性被逐 replicate 抵消的结果。
若用端点相减，宽度会是虚高的（对抗性测试实测 29.2×）。

## 4. ⚠ secondary R_B 的 CI 排除 0 **不构成证据**

`R_B = min(|E_B+|, |E_B−|) = 0.0252`，CI `[+0.0007, +0.0650]`。

**CI 排除 0 在这里几乎是自动的** —— `R_B` 是绝对值的最小值，
**按构造恒 ≥ 0**，bootstrap 分布整个落在 `[0, ∞)`，
所以 2.5% 分位数只要不大量取到恰好 0，就必然 > 0。

> ### ★ 规则 84：非负统计量的"CI 排除 0"没有信息量 ★
> 预注册定义了 `R_B` 却**没有为它写判读规则**（不像 `G` 有 SESOI）。
> 这是预注册的一个缺口。**现在只能把 R_B 作描述性报告**，
> 明确写"其 CI 排除 0 不构成 component transfer 的证据"，
> **不得**事后补一个门槛把它变成阳性结论。
>
> 描述性事实：`B+ = −0.0252`、`B− = +0.0433`，两个符号**方向相反**，
> 幅度都远小于 1 trial 的功能门槛。

## 5. ★ A 臂：027 的窄接口效应**未能复制** ★

```
028 A 臂    E_A = -0.0391   95% CI [-0.0818, +0.0028]   ← CI 含 0
027 原值    E   = -0.0798   95% CI [-0.1632, -0.0035]   ← CI 排除 0
```

**点估计约为 027 的一半，且 CI 现在包含 0。**

> **027 narrow-interface effect did not replicate on the new sampling block.**

这是 **sampling-level replication**（换了一整批新种子），
**区别于** 027 内部那次 analysis-level Monte Carlo stability（规则 80）——
后者只证明 `p=0.0464` 不是 bootstrap 抖动。

⚠ 按预注册 §5，**A 的成败与 G 分开判**：A 未复制**不使 G 失效**，
G 仍按自己的 CI + SESOI 判为"CI 包含 0"。

## 6. 028 能写什么 / 不能写什么

| | |
|---|---|
| ✅ | 在总 coupling budget 相同的条件下，**读取一份与 exploration 轴正交的额外历史成分，没有增加** novel-task transfer magnitude（G = −0.002，CI [−0.031, +0.023]） |
| ✅ | 该结论对 industry 残差的**接入符号稳健**（worst-sign 判据） |
| ✅ | **027 的窄接口效应在全新采样块上未能复制**（E_A CI 含 0，点估计减半） |
| ⛔ | ~~宽接口无效~~ —— 只能说"这一份正交成分、在这个等预算设定下没有净增益" |
| ⛔ | 任何基于 `R_B` CI 排除 0 的 component transfer 主张 |
| ⛔ | *generalized individuality* |

## 7. 027 + 028 合起来说明了什么

```
v3     过去 → 持久行为差异                 明显（1.142，参数集合 78.3% 同向）
027    持久差异 → 陌生任务功能迁移           极弱（0.08 trial，低于功能门槛）
028    加宽历史读取接口（等预算）             没有改善（G ≈ 0）
028-A  027 那个已经极弱的效应                 换一批种子就测不到了
```

> ### ★ 核心命题（较 027 更强）★
> **Persistent individuality ≠ automatically functional generalization.**
>
> 027 之后还可以说"也许是接口太窄"。
> **028 在等 coupling budget 下加宽读取接口，没有带来任何增益；
> 而且 027 那个原本就微弱的效应，在新采样块上没有复制出来。**
>
> 所以现在更准确的表述是：**这些持久差异，通过我们所能构造的
> 这一类通用探索接口，几乎不携带可复制的功能迁移。**


---

# 实验 029 —— Memory Transfer（设计中，未开始）

**2026-08-18 · 今天只做了一件事：开 `MEMORY_TRANSFER_DESIGN.md`**

⚠ **那个文件不是预注册**，是设计草案，今天允许反复改。
预注册（`NOVEL_TASK029_PREREGISTRATION.md`）等五个问题全部拍板、
且 group-blind 校准通过之后才写。

## 029 的问题（已写死）

> **Can structurally relevant past experience be retrieved and causally used
> to adapt to a surface-novel problem?**

## 与前面几个实验的分工

```
025 / v3   过去能不能【留下】？                      ✓ 明显
027        留下的 personality 会自动迁移吗？          极弱（0.08 trial）
028        多读一些 personality history 能救吗？      没有（G ≈ 0）
029        过去的经验能否被【真正检索】并用于类比？   ← 新问题
```

## 为什么 029 不能是 028 的续集

028 已经把"读得更宽"这条路走完了，而且 **027 A 在新 sampling block 上没有复制**。
所以 029 换掉的必须是**通路的类型**，不是带宽：

```
027 / 028   历史 → 我们替它读出的一个标量 → β → 探索加成
029         历史 → 可寻址的条目 → agent 自己按相似度取用 → 决策
```

**如果 029 最后退化成"experimenter 挑一个更好的 readout"，它就是 028 的第三个臂，
不该单独立项。**

## 第 1 版只回答五个问题（②–⑤ 全是草案，待拍板）

① 029 到底测什么 —— **已写死**
② 「记忆」在模型里是什么对象、「检索」是哪个动作 —— 待定
③ 什么叫"表面新颖、结构相关"、怎么保证不是自欺 —— 待定
④ 「检索并因果使用」怎么落成 primary —— 待定
⑤ 什么结果算失败、怎么在跑之前知道设计干净 —— 待定

## 已经挂在草案里的几条纪律（承前）

- **铁律（承 028）**：检索通道更强 ≠ 给历史更大权重。029 同样要等预算对照。
- **最大风险**：相似度函数若由我们手写、且我们知道哪条经验"应该"有用，
  那测的是**我们的相似度函数**，不是 agent 的检索。→ 必须 designer-blind。
- **必须成对**：match 臂之外必须有 **structure-mismatch 臂**（surface 同等新颖），
  否则任何增益都可能只是"有记忆的 agent 更爱探索"。
- **规则 84 提前挂账**：若 primary 用了 `min(|·|)` 这类非负统计量，
  必须**同时**写判读门槛，否则跑完只能当描述性报告。
- **承规则 67 / 026**：两个发育世界要同等新颖，结构相关性不能只对 rich 一支存在。

## ★ 跑之前就写死：029 阴性也有信息量 ★

核心命题现在是 **Persistent individuality ≠ automatically functional generalization**。
029 若也 ≈ 0，命题不变，只会加强为"即使给它一条**真正的 episodic 检索通道**，
持久个体差异仍然几乎不携带可复制的功能迁移"。

**这一段现在就写死，是为了防止跑完之后为了拿阳性而回头改设计。**

## 种子

```
80000–81499     ★ 029 FINAL 预留 ★   已核实：全库从未作为种子出现
```
calibration / rehearsal 用哪一段待定，**不得**动 80000 段。

## 复现方式（新增）

- `AI SANDBOX/MEMORY_TRANSFER_DESIGN.md` —— 029 设计草案（活文档，带版本记录）

---

## ★ 029 识别性探针 —— `memory_transfer_probe.py`（2026-08-18）★

**程序故意不叫 `experiment029.py`。** 今天只问一件事：
**这条 memory → retrieval → evidence → choice 的通路，有没有能力影响 outcome。**
（以前吃过太多次亏：机制根本没能力，却直接跑 group comparison。）

底座 = 027 的任务，**一个数都没改**（80 trial，第 41 trial 反转，α/β/τ 同，指纹
`26778f672e9e7009`）。种子 = development 段 `0–399`。**80000–81499 没碰。**

### 今天定下来的三件事

**① development history 不用 rich/poor**，改成干净的小型 learning history：

```
Stable    Problem 1/2/3 规则从不反转
Volatile  问题数、reward magnitude、trial 数完全相同，但每个都有 change point
```

stable/volatile **不是性格**，只是让 agent 拥有不同的**经验库**；
所有具体符号 counterbalance，学到的必须是
**"过去有效的 relation 有时会失效"**，而不是"B 后来总会变好"。

**② 029 自建 Episode 结构**（不复用 `{event, day, importance, text}` ——
那适合自传体记忆，不足以做 causal transfer）：

```
Episode: context / previous_expectation / observation / prediction_error
         / action_relation / outcome
```

> ### ★ 规则 85：可迁移的记忆存 relation，不存 identity ★
> `action_relation` 只能是 **stay / switch**，**绝不能是 A / B**。
> 存了选项身份，换一个新任务之后就没有任何可迁移性 —— 新任务里根本没有 A 和 B。
> 已实现为**硬约束**（`Episode.__post_init__` + `_assert_relational_only()`），
> 字段里出现选项身份直接报错。

**③ 极简 relational retrieval**（第一版故意不上"真正智能"的检索）：

```
当前：旧策略过去很好 + 最近连续 prediction error
  → 检索 "previously-good strategy + persistent surprise"
  → m = E[R|switch, similar past] − E[R|stay, similar past]
  → logit(switch) = base_learning + λ·m
```

与 027 的本质差异：`027: trait→β` 是我们替它读一个标量；
`029: current situation → retrieval → past outcomes → evidence → choice`。

### 工程自检 —— 全过

```
关系性约束     Episode 只存 stay/switch   m(S)=−0.667  m(V)=+0.667  m(空库)=0
确定性         同 body+memory+种子 → 逐 trial 相同
memory-blind   λ=0 时两个记忆库 400/400 种子逐 trial 完全相同
```

### ★ POSITIVE CONTROL：通过 ★（同 body/Q/奖励表/u，只换 memory）

```
λ       轨迹改变      Δlatency(V−S)    Δ反转后正确率
0.00      0.0%           +0.000          +0.0000   ← memory-blind，必须为 0
0.25      4.5%           −0.095          +0.0015
0.50      9.2%           −0.138          +0.0021
1.00     17.8%           −0.125          +0.0029
2.00     28.5%           −0.180          +0.0068
4.00     41.5%           −0.168          +0.0099
```

方向正确：Memory V（过去 switch 划算）→ 切换更快 + 反转后正确率更高。

### ★ SWAP TEST：未通过（所有 λ）★

```
λ       |memory 效应|   |body 效应|    比值
0.25        0.091          0.351      0.26×
0.50        0.140          0.370      0.38×
1.00        0.104          0.384      0.27×
2.00        0.134          0.399      0.34×
4.00        0.107          0.447      0.24×
```

memory 效应在**两个 body 上方向一致**，但幅度只有 body 的 1/4–1/3。
**换了 memory，结果仍然主要跟 body/traits 走** —— 这正是 SWAP 要拦的情况。

### ★ 诊断：不是 λ 的问题 ★

```
检索触发   180/400 种子曾触发（45.0%）；平均每个种子只触发 0.69 / 80 个 trial
           首次触发 trial 中位数 43（反转在 40）；反转前几乎不触发（0.04）
触发时刻的 base p(switch)   中位数 0.208   IQR [0.179,0.245]   ≥0.9 占 0.0%
```

> ### ★ 规则 86：正控制通过 ≠ 机制够格，还要看 exposure ★
> 触发时 base p(switch) 只有 0.21 → **决策没饱和，记忆有发挥空间**。
> 但记忆平均只在 **0.69 个 trial** 上进入决策，而 body 的 β 在**全部 80 个**
> trial 上进入决策 —— **约 116× 的 exposure 不对称**。
>
> 所以调大 λ 只让**更多轨迹**被改（4.5%→41.5%），却不改变**终点**
> （Δlatency 一直在 −0.1 附近）：单 trial 的推力只挪动"哪一 trial 切换"，
> 随后被冲掉。
>
> **该修的是检索的暴露/持续性，不是耦合强度。**
> 而且按 028 的等预算铁律，**现在这个 SWAP 比较本身就不是等 exposure 的**，
> 且不对称方向对 memory 不利。

### 下一步候选（★ 今天不选，等拍板 ★）

```
(a) evidence 在情境持续期间保持在决策里，而不是触发一次就清零
(b) 放宽 SURPRISE_RUN_MIN，让检索更早、更常触发
(c) 重新定义 SWAP 判读：|memory|>|body| 是不是过严？等 exposure 才是正确口径
(d) 底座换成多 change point 的任务 —— 一次反转只给记忆一次机会
```

⚠ (c) 是**判读口径**，(a)(b)(d) 是**设计改动**。
**先定 (c)**，否则会变成"改设计直到指标好看"。

### 今天故意没做

```
⛔ Stable vs Volatile 正式比较   ⛔ 029 final seeds   ⛔ preregistration
⛔ SESOI                         ⛔ λ 最终值          ⛔ 把 memory 加进 sim.py
⛔ LLM / embedding               ⛔ episodic+semantic+abstraction 三套同时上
```

### 复现方式（新增）

- `memory_transfer_probe.py` —— 029 识别性探针（正控制 + SWAP + 诊断）
  → `memory_transfer_probe_result.txt`、`memory_transfer_probe_console.txt`
- `AI SANDBOX/MEMORY_TRANSFER_DESIGN.md` v2 —— 029 设计草案（活文档）

---

## ★ (c) 判据修正 + 探针 v2：stateful retrieval（2026-08-18，同日晚些）★

### ⛔ SWAP dominance criterion 正式撤回 ⛔

> **原文保留，不删**（见上一节）：
> `|memory 效应| > |body 效应|`，五个 λ 全部未通过。

> Original SWAP dominance criterion failed at all tested λ, after which
> inspection showed that the criterion compared an event-triggered channel
> active on ~0.69/80 trials with an always-on trait channel. The dominance
> criterion was therefore **retired before any Stable/Volatile outcome was
> observed**.

**撤回理由不是"它没通过"，而是它测的不是我们想知道的东西。**
它回答"memory 的终点效应是否比 body 还大"；
SWAP 该回答的是"**body 完全固定时，只换 memory，未来行为是否随记忆内容发生
预测方向的改变**"。两个完全不同的 estimand。

> ### ★ 规则 87：event-triggered 机制不能直接与 always-on 机制比终点效应 ★
> **修正规则 86 的方向。** 规则 86 说"该修的是 exposure"是对的，
> 但它暗示的"比较前必须 equal exposure"是**错的**：
> memory 与 personality 本来就不该有相同 exposure —— 人格是一直存在的 prior，
> 记忆应该**遇到相关情况时才被调用**。强行让 memory 80/80 trial 在线，
> 会毁掉本设计最重要的理论特征：**context-dependent retrieval**。
>
> 正确做法：把 **exposure** 与 **per-opportunity influence** 分开报告。
> ```
> A. Exposure   E_i = #{retrieval-eligible trials}
> B. Potency    Δp_t = p_switch(M_V) − p_switch(M_S)，在完全相同的 decision state 上算
> ```
> potency 用 **λ=0 的 memory-blind 轨迹冻结 decision state** 再反事实换记忆。

> ### ★ 规则 88：retrieval 的 potential 与 realized 必须分开 ★
> `fired` 本身受前面 choice sequence 影响（cautious body 更容易连续 stay 三次，
> 于是更容易触发检索）—— **触发次数本身就是 task dynamics 的产物**。
> ```
> potential retrieval opportunity   在 memory-blind（λ=0）轨迹上定义 → 查机制 exposure
> realized retrieval                memory-enabled 轨迹上实际发生   → 是结果的一部分
> ```
> ⛔ **绝对不许**只分析"成功想起了记忆"的 agent —— 那是 survivor conditioning。
> 已写成断言：所有汇总必须用全部 400 个种子。

### 新 SWAP estimand

```
M_C = L(Body C, Mem V) − L(Body C, Mem S)
M_K = L(Body K, Mem V) − L(Body K, Mem S)
M   = (M_C + M_K)/2          body effect 仅作 robustness diagnostic
```
关心：方向一致性 / pooled M / Body×Memory interaction / （将来）SESOI。

### 机制改动：(a) one-shot → stateful（**不是**"固定保持 N trial"）

固定 N 会新增一个任意参数。改成状态机，**两个 resolution 条件都只用已有量**：

```
NORMAL →（连续 persistent surprise ≥3 且手上策略过去很好）→ RETRIEVE
      记下 suspect strategy → ACTIVE：m 持续进入 working decision state
ACTIVE →① Q[另一个] > Q[suspect]        "哦，看来真的变了"      → RESOLVED
       →② 在 suspect 上连续 3 次不再意外 "刚才只是偶然"        → RESOLVED
```

★ **ACTIVE 期间 m 作用于 suspect，不是作用于"switch 这个动作"** ★
v1 每 trial 都把 `+λm` 加在 switch 上，推成一次切换后下一 trial 就变成"再换回去"，
语义错误、会来回抖。改为 `logit(switch) += λ·m·s`，
`s=+1` 若 switch 是**离开** suspect，`s=−1` 若是**回到** suspect。
这才是"我怀疑规则变了"，而这个怀疑会持续到被确认或被打消。
（`suspect` 是决策时的工作变量，**不是** Episode 字段 —— 规则 85 不变。）

**其余一律不动**：三个阈值、单次 reversal、种子 0–399、λ 只扫不选。
v1 文件原封保留，且有断言硬保证它仍逐位复现原结果（λ=1：71/400，−0.125）。

### ① ② EXPOSURE

```
机制            eligible 种子   potential trial   realized trial(λ=1)
v1 one-shot        45.0%           0.75              0.69
v2 stateful        45.0%           7.18              6.96
```
exposure 0.75 → 7.18（9.6×）。**仍然是 event-triggered（7.2/80），
没有、也不该被拉成与 body 一样的 80/80。**

### ③ POTENCY（λ=0 冻结 decision state 上反事实换记忆）

```
              机会数    base p(switch) 中位数   饱和比例   mean|Δp| (λ=1)
v1 one-shot     300          0.208               0.0%        0.2205
v2 stateful    2873          0.400               0.0%        0.2807
```

> **v1 的 per-opportunity potency 本来就不低（λ=1 时 0.22）。
> v1 缺的是 exposure，不是 potency。** 这直接证实了规则 86 的诊断。

### ④ 新 SWAP —— Directional check: **PASS**

```
机制         λ       M_C      M_K   pooled M      95% CI（描述性）    方向一致  interaction
v1 one-shot 1.00   -0.125   -0.083    -0.104   [-0.410, +0.215]      是      -0.042
v2 stateful 0.25   -0.875   -0.900    -0.887   [-1.343, -0.471]      是      +0.025
v2 stateful 1.00   -4.058   -3.920    -3.989   [-4.785, -3.231]      是      -0.138
v2 stateful 4.00   -9.607   -9.710    -9.659   [-10.815, -8.549]     是      +0.103
```

- **M_C 与 M_K 在两套机制、所有 λ 上全部同号** → Directional SWAP check: **PASS**
- Body×Memory interaction 相对 M 极小（λ=1 时 −0.138 vs −3.99）
  → **memory 不依赖某一种特定 body 才能工作**
- CI 是**描述性**的（seed cluster bootstrap，n_boot=10000，分析种子 8181）。
  **今天不定 SESOI，所以不做功能意义判读。**

### ⑤ DOWNSTREAM（只作 consequence，不作判据）

```
机制         λ      轨迹改变   Δlatency(V−S)   Δ反转后正确率
v1 one-shot 1.00     17.8%       -0.125         +0.0029
v2 stateful 0.25     30.8%       -0.875         +0.0115
v2 stateful 1.00     43.2%       -4.058         +0.0535
v2 stateful 4.00     45.0%       -9.607         +0.1688
```

⚑ λ=4 时轨迹改变 **45.0%，恰好等于 eligible 种子比例** ——
上限是 eligibility，符合构造：没触发过检索的种子按定义完全不受影响。

### ★ 探针阶段的结论 ★

> **v1 的问题确实是"retrieved evidence 没有形成持续的 decision state"，
> 而不是 λ 不够。**
> 阈值、任务、种子一个没动，只把检索改成 stateful，
> pooled M 就从 −0.10 走到 **−3.99 trial**（λ=1，38×）。

### ⚠ 风险方向已经翻转（留给校准，今天不处理）

```
机制现在可能【太强】：λ=4 时 −9.7 trial，而 latency 量程只有 0–36。
手工记忆处在【最大可能对比度】（m_S=−0.667，m_V=+0.667）。
真实的 Stable/Volatile 历史产生的 |m| 会小得多。
→ −4 trial 是【最大记忆对比度下的上界】，不是预期效应量。
```

⚠ 另一条要盯住的：**ACTIVE 窗口与 latency 终点在构造上重叠**
（怀疑大致在切换成功时被解除）。做强结论之前需要一个
**不由同一窗口定义的终点**。

### 今天仍然没做

```
⛔ (b) 放宽 SURPRISE_RUN_MIN     ⛔ (d) 多 change-point 任务
⛔ λ 最终值   ⛔ final seeds   ⛔ preregistration   ⛔ SESOI
⛔ Stable/Volatile outcome      ⛔ 把 memory 加进 sim.py
```

**这仍然不是 029 scientific success**：记忆是手工造的、λ 没冻结、
Stable/Volatile 根本还没跑。

### 复现方式（新增）

- `memory_transfer_probe2.py` —— v2 stateful retrieval + exposure×potency 分解
  → `memory_transfer_probe2_result.txt`、`memory_transfer_probe2_console.txt`
- v1 `memory_transfer_probe.py` **保留不动**，v2 里有断言保证它仍逐位复现

---

## ★ probe v3：resolution 时序 bug 修正 + endpoint 改组（2026-08-18）★

### 修的 bug

v2 的循环顺序是 `choice → reward → PE → 判 RESOLVED（用旧 Q）→ 更新 Q`。
于是这一 trial 的新证据**刚好**让新策略 Q 超过 suspect 时，判定时它还没写进 Q。

> **resolution test was originally evaluated before incorporating the current
> outcome into Q, allowing retrieved evidence to persist for one extra decision
> after the resolution criterion had effectively been met.**

修正为 `… → PE → **更新 Q** → 用更新后的 Q 判 RESOLVED`。
`calm_run` 那条保持不变（它本来就该用 pre-update 的 PE ——
prediction error 按定义就是对**当时的**预期而言）。

**v1、v2 的文件与结果原封保留、不覆盖**，v3 里有断言硬保证它们仍逐位复现。

### 修正的影响：效果缩水，故事不变

```
λ      pooled M pre-fix   pooled M fixed      Δ     方向一致
0.25       -0.887            -0.786       +0.101      是
1.00       -3.989            -3.621       +0.368      是
4.00       -9.659            -9.486       +0.173      是
λ=1  potential exposure 7.18 → 6.77   realized 6.96 → 6.53
λ=1  Δ反转后正确率 +0.0535 → +0.0499
```

> ### ★ 这个 bug 的方向会【放大】效果 ★
> 修掉以后核心机制**仍然明显存在**，M_C / M_K 在所有 λ 上依旧同号。
> 「bug 存在、方向利于自己、修掉后结论不变」——
> 这是最好的一种情况，必须**主动记录**，不能等别人问。

### ★ endpoint 改组：latency 降级 ★

> ### ★ 规则 89：primary endpoint 不能与机制自身的活跃窗口构造性重叠 ★
> `ACTIVE` 的退出条件 ≈「Q 证明新策略更好」，
> restricted switch latency ≈「新策略开始稳定占优」——**两者天然绑在一起**。
> latency 仍可报（它很好地描述"memory 让切换发生得多快"），
> 但**不能**当 029 最强的科学 endpoint。

**新 primary candidate：post-change cumulative errors**

```
C_i = Σ_{t=40..79} 1(choice_t ≠ correct_option_t)      规则变化后一共选错多少次
ΔC  = C(V-memory) − C(S-memory)                        V 有帮助时 ΔC < 0
```

与 `post_correct` 恒等（`C = 40(1 − post_correct)`，已写成断言），但单位直接是 trial。
好处：窗口由任务事先固定 / 不读 ACTIVE 或 RESOLVED / 无 never-switch censoring /
所有 agent 都有 / 好定 SESOI / 测的就是实际 functional cost。

```
ΔC（primary 候选）    M_C      M_K   pooled        95% CI（描述性）    方向一致
v3 fixed  λ=0.25   -0.415   -0.480   -0.448   [-0.616, -0.279]        是
v3 fixed  λ=1.00   -1.995   -2.053   -2.024   [-2.394, -1.670]        是
v3 fixed  λ=4.00   -6.340   -6.433   -6.386   [-7.176, -5.629]        是
Δlatency（secondary） λ=1     -3.708   -3.535   -3.621                 是
```

**Primary 问"实际少犯多少错"，secondary（latency / exposure / potency /
ACTIVE 段长 / realized retrieval）解释"为什么"。**

⚠ 手工 MEM_S/MEM_V = ±0.667 是**最大对比度** → 以上全是**上界**，不是预期效应量。

---

## ★ 手工 memory probe 阶段结束 → 进入 acquisition（`memory_acquisition_probe.py`）★

**下一步不是校准 λ。** 在不知道真实 Stable/Volatile 到底产生 m = 0.03 还是 0.30 之前，
争论 λ 取 .25 还是 1 没有科学意义。正式顺序：

```
修 resolution bug → 锁 independent endpoint → 造真实 Stable/Volatile histories
→ 让 history 自己生成 Episode → 观察真实 memory evidence 分布 → 最后才校准 λ
```

### ★ 关键设计：两边都经历 surprise ★

❌ 「Stable 从来没有 surprise，Volatile 有很多」→ memory 区别会退化成
"一个有数据、一个没数据"，太容易。
✅ **同一种表面现象，意味着不同的东西。**

```
t <  20     原策略 p_high、另一个 p_low        ← 两条件相同
t 20–27     ★两个都掉到 p_low★                ← 两条件【逐位相同】
t ≥  28     Stable：原策略恢复 / Volatile：另一个变好
```

奖励抽样共用同一条随机流 → **两个条件在 t<28 上逐位相同**（已核 100 种子 ×3 问题）。
**光看异常本身分不出身处哪个世界**，差异只在"这次异常意味着什么"。

### matching diagnostics

```
① 总 trial 数            150.00 = 150.00   ✓
② 总 reward opportunity  105.60 = 105.60   ✓
④ first-good=index0      0.4783 = 0.4783   ✓
③ episode 数              2.88 vs 3.67     ≠（行为产物，报告）
  实际拿到的总 reward     82.99 vs 73.19    ≠（见下面 caveat）
```

### ★ 真实经历长出来的 m —— 方向完全正确 ★

```
             n(可定义 m)   mean m     SD      p10     中位数     p90    m>0
Stable            94      -0.3783  0.3410  -0.7500  -0.4000  0.0000    8.5%
Volatile          96      +0.5257  0.2240  +0.2647  +0.5000 +0.8333  100.0%
分离度 = +0.9040   手工版 = +1.3333   →  真实经历达到手工版的 67.8%
```

**Stable 为负（stay 划算）、Volatile 为正（switch 划算），与设计一致。**
真实经历确实能自己长出我们手工 memory 所代表的那种 relational evidence。

### ⚠⚠ 但卡在 yield：只有 24% 的 agent 长出可定义的 m ⚠⚠

```
episode completeness（同时有 stay 与 switch 条目）  Stable 23.5%  Volatile 24.0%
→ 大约 3/4 的 agent 发育结束时【根本没有可用记忆】
```

yield 诊断（每个 problem，入场要两半同时满足）：

```
            异常起点 Q≥0.60   曾达成 stay-run≥3   两者同时   最长 run
Stable          57.8%              56.9%          17.2%      2.98
Volatile        57.8%              77.0%          17.2%      3.62
```

> ### ★ 规则 90：入场条件的两半可能在构造上互相拆台 ★
> 进入情境窗口要求「策略仍被信任（Q ≥ .60）」**且**「连续三次失望」——
> 但**每一次失望都在把 Q 压下去**。α=.05 时三个 0 把 Q 从 .76 压到 .65，
> 所以 Q 没爬够高的 agent 会被这条筛掉。
> **卡的是前一半**（异常起点 Q≥.60 只有 57.8%）→ 该动的是
> **异常前的经验量**，不是 surprise 那一半。
>
> ⛔ 绝不许用"只分析长出了记忆的 agent"来绕过（规则 88：survivor conditioning）。

### caveat：realized reward 无法匹配

Volatile 的 agent 总收益更低（73.19 vs 82.99），因为 change point 之后要重新学。
**opportunity 已逐位匹配**；realized reward 要匹配就等于取消这个 manipulation 本身。
**记录、不修**。

### 本阶段故意没算

```
⛔ novel-task latency   ⛔ post-change errors   ⛔ Stable vs Volatile transfer effect
```
**代码里也没有这些量** —— 这样才保留调 acquisition 机制的自由，
而不会开始围着 final outcome 调设计。

### 复现方式（新增）

- `memory_transfer_probe3.py` → `memory_transfer_probe3_result.txt` / `_console.txt`
- `memory_acquisition_probe.py` → `memory_acquisition_probe_result.txt` / `_console.txt`
- v1 `memory_transfer_probe.py`、v2 `memory_transfer_probe2.py` **保留不动**，
  v3 里有断言保证两者仍逐位复现

---

## ★ acquisition 参数冻结 + λ 接口容量校准（2026-08-18）★

### 冻结：只加 anomaly 前的学习长度

拍板：**只增加 pre-anomaly experience**，不动 GOOD_THRESH / PE_THRESH /
SURPRISE_RUN_MIN，也不增加 problem 数量。纯上游 sweep（0–399，未接 novel task）：

```
pre-anomaly   Stable completeness   Volatile completeness   complete-only m 分离度
   20              23.5%                  24.0%                  +0.904
   28              49.2%                  52.0%                  +0.872
   34              61.0%                  69.3%                  +0.902
★  36 ★            65.8%                  73.3%                  +0.894
   40              69.5%                  76.8%                  +0.884
```

> ### ★ 增加 pre-anomaly experience 主要修 yield，几乎不改 memory contrast ★
> 这是一个**干净的 engineering correction**：把被入场条件筛掉的 agent 救回来，
> 而不是把 Stable/Volatile 的对比越调越强（separation 在 34/35/36/38 都差不多）。

**冻结为 029 acquisition candidate：**

```
ANOMALY_AT  = 36      （原 20）
ANOMALY_LEN =  8      （不变）
T_PROBLEM   = 66      使 anomaly 后仍为 66−36−8 = 22（与原来相同）
```

选 36 而不是 40 的理由是 **elbow**，不是 separation 最大：
20→36 换来 +42pp / +49pp，36→40 只再换 3–4pp。
（`memory_acquisition_probe.py` 里写了断言：anomaly 后必须仍是 22 个 trial。）

### ★ 规则 91：memory availability 本身就是发育结果 ★

> **Memory availability is itself a developmental outcome. Do not condition
> transfer or calibration on successful memory formation. Report the extensive
> margin (P[m usable]) and intensive margin (m | usable) separately, but all
> primary analyses use the full predefined population.**

ANOMALY_AT=36 下的实测（缺 stay 或 switch 任一侧 → m=0，表示"没有可用证据"）：

```
              extensive: P[m 可用]   intensive: mean(m|可用)   全体 mean m   全体 median
Stable              65.8%                  −0.4099             −0.2695        −0.2440
Volatile            73.2%                  +0.4842             +0.3546        +0.4099

population-level 分离度（全部 agent，含 m=0） = +0.6241   ★这是真值★
complete-only 分离度（只看长出记忆的）        = +0.8940   ⚠ 夸大
手工版 = +1.3333 → 真实 population 达到 46.8%，complete-only 会显得有 67.1%
```

⛔ 先筛掉"没有成功形成可用 memory"的 agent、再用剩下最有信息的一批做 calibration，
会**系统性夸大 memory channel 的真实输入强度** —— 与 survivor conditioning
（规则 88）在结构上是同一个错误。

### Stable/Volatile 的 yield 不相等（65.8% vs 73.2%）**不修**

Volatile 本来就更容易同时积累 stay 与 switch 两类经验，这属于
`history → memory availability → future behavior` 的一部分。
**强行把 completeness 配平 = 修改 post-treatment mediator。**
未来把 memory effect 拆成 extensive margin（有没有形成可用 relational memory）
与 intensive margin（形成了的话方向多大），由 SWAP / DELETE / SHUFFLE 检验因果。

### realized reward 同样**不修**

Stable 117.24 vs Volatile 103.42（新参数下）。Volatile 低是因为 change point
后必须重新学习。**为 matching 把 realized reward 做到一样 ≈ 给 Volatile 额外补偿、
取消 volatility 本身的成本。** 真正需要匹配的是 trial opportunity、
reward schedule 的机会量、first-good identity、pre-anomaly observations、
task length structure —— 这些已经逐位相等（198.00 / 144.00 / 0.4783）。

---

## ★ λ 接口容量校准（`memory_lambda_calibration.py`）★

问的是：**真实 memory 输入经过这个接口后，单次决策能不能产生一个不饱和、
但也不是微不足道的影响？** ⛔**不是**"哪个 λ 最容易让 029 成功"。

### group-blind 是结构性的

```
pooled_empirical_m()  两个 condition 汇入同一池 → ★包含 m=0★ → 排序
                      排序摧毁 m ↔ condition 的对应，本模块【无法】恢复分组
```
输入：n=800，mean +0.0426，|m| 中位数 0.3571，**m=0 占 31.2%**
（≈1/3 的 agent 在任何 λ 下接口都是惰性的 —— 这正是规则 91 的 extensive margin）。

`Δp` 口径 = 相对**没有记忆**的反事实，decision states 取自 λ=0 memory-blind 轨迹
（probe3 的 frozen-state pipeline，2708 个 state，base p 中位数 0.382，本身饱和 0.0%）。

```
   λ    mean|Δp|  median|Δp|  p90|Δp|   推后饱和   P(翻转偏好)
 0.25    0.0176     0.0182    0.0382      0.0%       3.2%
 0.50    0.0352     0.0363    0.0764      0.0%       6.6%
 1.00    0.0699     0.0717    0.1520      0.0%      13.4%
 2.00    0.1339     0.1354    0.2923      0.6%      24.8%
 4.00    0.2272     0.2250    0.5046     12.7%      33.5%
 8.00    0.3050     0.2952    0.6694     46.3%      35.5%

active-memory exposure 全网格稳定在 ~7/80 → memory 仍是 event-triggered ✓
```

### 三条判据（读数口径为本文件所定，**非预注册值**）

```
① 不饱和            推后落入 p≤0.05 或 ≥0.95 的比例 ≤ 5%
② 有实质不过强      median|Δp| ≥ 0.02 且 P(翻转偏好) ≤ 25%
③ event-triggered   active exposure ≤ 20/80

   λ      ①        ②                        ③
 0.25   通过    ✗ med 0.018（微不足道）      通过
 0.50   通过    通过 med 0.036 flip 6.6%     通过
 1.00   通过    通过 med 0.072 flip 13.4%    通过
 2.00   通过    通过 med 0.135 flip 24.8%    通过（flip 正踩在 25% 边上）
 4.00   ✗ 12.7%  ✗                          通过
 8.00   ✗ 46.3%  ✗                          通过
```

**合格带 = λ ∈ {0.50, 1.00, 2.00}**

### 建议（★ 本文件不替使用者冻结 ★）

> **λ = 1.00** —— 合格带的中心，两侧都不贴边。
> 0.25 低于"不是微不足道"这条线；2.00 正踩在翻转率 25% 的边上且已开始饱和
> （0.6%）；4.00 起硬饱和。λ=1 时 median|Δp| 0.072、flip 13.4%、饱和 0.0%、
> exposure 6.73/80。

⚠ 三条判据的**数值阈值也需要拍板** —— 它们是本文件的读数口径，不是预注册值。

⛔ 本文件没有、也无法计算：Stable vs Volatile ΔC / latency /
哪个 λ 最能拉开两个 group。condition label 在输入处即被丢弃。

### 复现方式（新增）

- `memory_lambda_calibration.py` → `memory_lambda_calibration_result.txt` / `_console.txt`
- `memory_acquisition_probe.py` 已冻结 ANOMALY_AT=36 / LEN=8 / T=66，
  并新增 extensive / intensive margin 报表（规则 91）

---

## ★★ λ 正式冻结 + OWN/DELETE/SWAP/SHUFFLE rehearsal（2026-08-18）★★

### 冻结（★ 从这一刻起不再因为任何 Stable/Volatile outcome 改动 ★）

```
SATURATION_MAX       = 0.05    # p ≤ .05 或 ≥ .95
MEDIAN_ABS_DP_MIN    = 0.02
PREF_FLIP_MAX        = 0.25
ACTIVE_EXPOSURE_MAX  = 20      # /80 trials
MEMORY_LAMBDA        = 1.00
```

admissible 必须**同时**满足四条，且 exposure 一条用 **max 而不是 mean**：

```
max( E[m10], E[m50], E[m90] ) ≤ 20/80
```

> **event-triggeredness 不应该允许"某一种 memory sign 已接近常驻，
> 却被另外两种平均掉"。** λ=1 的最大 exposure 只有 6.95/80，判定不受影响
> （已重跑确认：合格带仍是 {0.5, 1.0, 2.0}）。

这四个数是 **engineering admissibility gates，不是 scientific significance
thresholds**：5% 饱和 = 记忆不该把超过 1/20 的 eligible decision 推成近乎确定性；
median|Δp| ≥ .02 = 连 2 个百分点都推不动就谈不上进入决策；
flip ≤ 25% = 最多四次里一次翻面，有影响但不是记忆说了算；
exposure ≤ 20/80 = 把 event-triggered 钉死成"最多参与四分之一任务"
（实测仅 ~7/80，这条主要防未来架构漂移）。

### ★ 规则 92：selection rule 必须连"怎么选的"一起写死 ★

> **Lambda was calibrated without condition labels or downstream transfer
> outcomes. Values were required to satisfy prespecified interface-capacity
> constraints on saturation, median probability shift, preference reversal,
> and retrieval exposure. Among admissible values, the log-scale midpoint of
> the admissible range was selected.**
>
> 合格带 {0.5, 1.0, 2.0} 在倍增网格上，`1.0 = √(0.5×2)` 恰是 log 尺度中心 ——
> **选的是"距离上下两个失效方向最远的"，不是"potency 最大的"**。
> 代码里写了断言：λ 若不再等于合格带的 log 中心就直接报错。
>
> 这样即使 029 FINAL 是负结果，也没人能问"是不是换个 λ 就能阳"——
> 答案是：**不知道，也不允许事后换**，λ 在看到 group transfer outcome 之前
> 已经由接口性质冻结。

λ=1 对应的实际接口行为：记忆被真正想起来时，典型情况把选择概率推动约
**7 个百分点**（median|Δp| 0.0717，p90 0.1520），约 **13.4%** 的 eligible
decision 因此跨过原偏好边界，**不把决策推到接近确定**（饱和 0.0%），
且只在约 **8–9% 的任务时间**里在线（6.5–7.0 / 80）。
—— 有能力影响决定，但既不是装饰品，也不是外挂控制器。

---

## ★ rehearsal：第一次把自然记忆接到 novel task（开发种子 0–399）★

### ⚠⚠ 先说清楚：本架构下 DELETE 与 SWAP 是**代数恒等式** ⚠⚠

body 是常数（NeutralBody），发育史除记忆外**不携带任何东西**进入任务，
于是同一种子的两个 condition **只差记忆**：

```
DELETE   两边都空库 → 逐 trial 相同 → ΔC ≡ 0             （恒等，已断言通过）
SWAP     记忆互换 → 就是 OWN 换个标签 → ΔC ≡ −ΔC(OWN)     （恒等，已断言通过）
```

> ### ★ 规则 93：只有一条通路时，DELETE / SWAP 退化为断言，不是证据 ★
> 当发育史**只通过一条通路**进入测试时，"删掉它效应就没了"和
> "换掉它结果就跟着换"在**构造上必然成立** —— 它们证明的是
> **"没有第二条泄漏通路"**，不是"记忆有因果作用"。
>
> **要让 SWAP 成为非平凡检验，发育史必须还携带记忆以外的东西**
> （例如 027/028 那条 trait 通路），否则 agent 的全部身份就是它的记忆。
> 这是给真正 029 的一个设计结论。
>
> 本文件把它们当**断言**跑（不符即报错），**不当结果解释**。

### PRIMARY：ΔC = C(Volatile) − C(Stable)，同种子配对，★全人群★

```
臂          C Stable   C Volatile      ΔC        95% CI（描述性）    相对 OWN
OWN          20.867      19.940      -0.927   [-1.202, -0.677]        1.00
DELETE       20.545      20.545      +0.000   [+0.000, +0.000]        0.00   ←恒等
SWAP         19.940      20.867      +0.927   [+0.680, +1.202]       -1.00   ←恒等
SHUFFLE      20.490      20.578      +0.087   [-0.068, +0.242]       -0.09   ★
SWAP-XS      20.812      19.922      -0.890   [-1.140, -0.660]        0.96   ★
```

### ★ 真正有信息量的两个控制 ★

**SHUFFLE**（在 agent 自己的条目内打乱 `action_relation`：episode 数、
stay/switch 条数、outcome 边际分布**全部保留**，只摧毁 action↔outcome 的关系）：

> ΔC 从 **−0.927 塌到 +0.087**（OWN 的 −9.4%），CI 跨 0。
> **效应来自关系结构，不是记忆库的 marginal statistics。**

**SWAP-XS**（种子 s 改用种子 s+200 的对侧记忆）：

> ΔC = **−0.890**，保留 OWN 的 **96.0%**。
> **效应由记忆内容携带，不靠"发育与测试共享同一个种子"的耦合。**

### SECONDARY mechanistic

```
臂         Δlatency   exposure S   exposure V   ACTIVE 段长 S/V
OWN         -1.962       6.92         6.65        6.81 / 6.56
SHUFFLE     +0.275       6.82         6.70        6.72 / 6.60
SWAP-XS     -1.810       6.82         6.55        6.71 / 6.45
```
memory 全程保持 event-triggered（~6.6–6.9 / 80）。

### extensive margin 的两个定义**不要混用**

```
usable（m ≠ 0）          Stable 64.2%   Volatile 73.2%
complete（两侧都有条目）  Stable 65.75%  Volatile 73.25%
```
差在 **6 个 Stable agent（1.5%）两侧都有条目、但两侧均值恰好相等 → m = 0**。
**报哪个就一直报哪个，不许混。**

### 读法

自然的 Stable/Volatile 发育史，经过**冻结的 λ=1 接口**，
产生约 **少犯一次 post-change error** 的下游差异；
该差异在**跨种子重新配对后仍在**（96%），
但在**保持 marginal、只打乱 action–outcome 关系后被摧毁**（−9.4%）。

⚠ CI 全是**描述性**的；没有 SESOI → **不做功能意义判读**。
⚠ 这是**开发种子上的 rehearsal**，不是 029 的确认性结果。
⛔ 不许据此改 λ 或任何 acquisition 参数。

### 还差什么才能写预注册

```
① 决定发育史是否还要携带 trait 通路（否则 SWAP 永远是恒等式）——规则 93
② SESOI（ΔC 的单位是 trial，现在 OWN ≈ 0.93）
③ fresh final seeds（80000–81499 仍然干净）
④ MEMORY_TRANSFER029_PREREGISTRATION.md
```

### 复现方式（新增）

- `memory_transfer_rehearsal.py` → `memory_transfer_rehearsal_result.txt` / `_console.txt`
- `memory_lambda_calibration.py` 已冻结四个 gate + λ=1.00，exposure gate 改用 max，
  并加了"λ 必须等于合格带 log 中心"的断言

---

## ★★ 预注册前的最后一轮拍板（2026-08-18）★★

### ① 029 primary **不加** trait 通路 —— 规则 93 修订

> ### ~~规则 93（原文，保留）：要让 SWAP 成为非平凡检验，发育史必须还携带记忆以外的东西~~
> **⚠ 已修订。** 原话数学上没错，但**实验设计推论不对** ——
> 为了让一个控制"非平凡"而故意加入 trait channel，会把原本干净的
> `history → relational memory → novel adaptation`
> 重新变成 `history → memory + traits → novel adaptation`，
> 然后又要处理 memory/trait competition、interaction、budget，
> 即 027/028 那一整套。**没有必要。**

> ### ★ 规则 93（最终版）★
> **When memory is the sole developmental pathway into the test task, DELETE
> and within-seed SWAP are algebraic integrity checks rather than independent
> causal evidence. A second developmental pathway should not be introduced
> merely to make these controls non-trivial; causal support should instead come
> from interventions on memory structure such as relational shuffling and
> cross-seed donor tests.**
>
> 中文：当 memory 是 development 进入测试任务的唯一通路时，DELETE 与同种子
> SWAP 是**代数上的完整性检查**，不是独立因果证据。**不能为了让这些控制变得
> "非平凡"而人为增加第二条发育通路**；真正的因果支持应来自对**记忆结构本身**
> 的干预，例如 relational SHUFFLE 和跨种子 donor 检验。

**029 的目标不是证明"memory 比人格更重要"**，而是证明：真实经历能够产生
relational memory，而这种关系结构足以在结构相似的新问题中产生功能性 transfer。
所以 `NeutralBody` 不动，architecture 保持 memory-only。

命名也一并冻结：`SWAP-XS` **正式改名 `XSEED-DONOR`** ——
它和 SWAP 问的不是同一件事（SWAP 问"结果跟不跟记忆身份走"，此架构下是恒等式；
XSEED-DONOR 问"效应是不是靠发育与测试共享种子"，非平凡）。

### ② extensive margin 正式选 **complete**

```
primary extensive margin = P(relational memory complete)
                           complete := 至少 1 条 stay 且至少 1 条 switch
Stable 65.75%   Volatile 73.25%

另报（可报告，但不许叫 extensive / availability）：
non-zero evidence rate     Stable 64.25%   Volatile 73.25%
```

> ### ★ 规则 94：m = 0 不等于"没有记忆" ★
> 那 6 个 Stable agent（1.5%）**两侧都有条目**，只是
> `mean(switch reward) == mean(stay reward)` → m = 0。
> **它们形成了完整的关系性记忆**，只不过这份经验告诉它
> "**过去 switch 和 stay 没有区别**" —— 这是**有意义的零证据**。
> 把 `m ≠ 0` 定义成 memory availability，就会把"形成了一份中性经验"
> 错误归类成"没有记忆"。
>
> 所以：completeness 与 non-zero evidence rate **是两个不同的量，
> 报哪个就一直报哪个，不许混用**。
> 规则 91 不变：**所有 primary transfer 分析仍使用全部预定义 agent，
> 含 incomplete 与 m = 0。**

### ③ SESOI = **1.0 post-change error**

```
ΔC = C_Volatile − C_Stable      负值 = Volatile 记忆更好
SESOI: |ΔC| = 1.0 error   ⇔  40 个 post-change trial 里少犯 1 次  ⇔  2.5% accuracy
```

理由：与 027/028 的 **1 trial 功能单位一致**，不是凭 rehearsal 的 −0.927
临时创造一个 0.5 / 0.75 的门槛。而且**开发结果 −0.927 恰好落在门槛下方**，
所以这个门槛**不会**把已看到的开发结果事后包装成"功能成功" ——
按此判读，开发结果只能算 *detectable / directionally strong，功能意义尚未建立*。
**这对预注册可信度是加分。**

三档判读（沿用 027/028 逻辑）：

```
CI 包含 0            No evidence of memory-mediated transfer
CI < 0 但未越过 −1   Detectable, but functional significance not established
CI 整体 < −1         Functionally meaningful memory-mediated transfer established
CI 完全 > 0          明确是反方向 / 有害 transfer
```
（开发 rehearsal `[−1.202, −0.677]` 正属于第二档。）

### ④ SHUFFLE 的 confirmatory 判据 —— ⚠ 有一处必须先拍板

不再只写"SHUFFLE 应该变小"，而是冻结 **retention ratio**：

```
R = |ΔC_SHUFFLE| / |ΔC_OWN|
joint same-seed bootstrap，★abs 与除法逐 replicate 施加★（承 028 教训）
⚠ 规则 84：R 恒 ≥ 0，"CI 排除 0" 无信息 → 判据只看【上界】
```

**开发 rehearsal 实测（n=400）：**

```
R 点估计 = 0.094      95% CI [0.005, 0.261]
```

> ### ⚠⚠ 两种写法判读不同 ⚠⚠
> ```
> (A) 点估计 < 0.25      → 满足（0.094）    用户原话"绝对点估计不超过 OWN 的 25%"
> (B) CI 上界 < 0.25     → 不满足（0.261）  更保守
> ```
> **建议 (B)**：只有 (B) 才真正回答"摧毁 relation 后**至少 75%** 的 transfer
> 是否消失"。FINAL 的 N=1500 是 rehearsal 的 3.75 倍，CI 宽度约缩到 1/1.94，
> 0.261 很可能落到 0.25 以下 —— 但**这是功效推断，不是保证**，(B) 有真实失败风险。
> 采用 (A) 会让这条控制几乎不可能失败，那它就失去了控制的意义。
>
> ⚠ **必须诚实记录**：这个选择是在**已经看到 rehearsal 的 0.094 / 0.261 之后**
> 做的，但**在见到 FINAL 块任何数值之前**写死。结果里必须写明这一点。

分层后果：primary CI 含 0 → **R 不计算不解释**（分母不可辨识时比值无意义）；
primary 可检出但 R 不满足 → 不许声称关系结构承载，只能写
"marginal statistics 的贡献无法排除"。**primary 的成败不因 R 而改变。**

### ⑤ FINAL 块冻结：`80000–81499, N=1500`

已核实：整个仓库与实验记录中 `80000` 只出现在"untouched / 不碰 / 预留"这类说明里，
**没有任何 simulation 路径使用过这一段**。沿用 028 的工程保护：
`final_029_STARTED.lock` 一旦创建，**哪怕崩溃该 block 永久 burned**；
seed guard 只接受 `seed0=80000, N=1500`；指纹 + 常量 + sha256 校验。

---

## ★ 预注册已写：`MEMORY_TRANSFER029_PREREGISTRATION.md` ★

冻结状态一览：

```
architecture      memory-only / NeutralBody              FROZEN
acquisition       36 + 8 + 22                            FROZEN
retrieval         stateful + post-Q resolution           FROZEN
λ                 1.00                                   FROZEN
capacity gates    5% / .02 / 25% / 20-of-80（取 max）     FROZEN
primary           ΔC post-change errors                  FROZEN
SESOI             1.0 error                              FROZEN
extensive margin  P(memory complete) 65.75% / 73.25%     FROZEN
scientific control SHUFFLE（判据 §6.3 待拍板 A/B）        待拍板
seed-coupling     XSEED-DONOR                            FROZEN
integrity         DELETE / within-seed SWAP（非科学结果） FROZEN
FINAL             80000–81499, N=1500                    FROZEN
```

新增 validity gate **G2 interface capacity transport**：
在 FINAL 块上用 **group-blind（pooled、含 m=0、排序）** 的 empirical m
重算四个 capacity 读数，**先于 outcome 判读**；失败的固定措辞：

> Interface capacity calibrated on the development block did not transport to
> the confirmatory population; the memory channel is not cleanly interpretable
> under the preregistered capacity constraints.

⛔ gate 失败**不许重估 λ**。

### 复现方式（新增）

- `AI SANDBOX/MEMORY_TRANSFER029_PREREGISTRATION.md` —— 029 预注册（一次性文件）
- `memory_transfer_rehearsal.py` 已更新：`XSEED-DONOR` 改名、
  extensive margin 口径改为 completeness、新增 retention ratio 的 joint bootstrap

---

## ★★ §6.3 拍板 B + `final_029.py` 全尺寸彩排（2026-08-18）★★

### ① SHUFFLE 判据选 **B**：`CI_97.5%(R) < 0.25`

只要求点估计，会让"**至少 75% 的 transfer 被摧毁**"这句话说得**比证据强**。
既然要声称"relational structure 被破坏后大部分 transfer 消失"，
**不确定性本身也必须支持这句话**。

开发 rehearsal（n=400）`R = 0.094, CI [0.005, 0.261]` 的诚实写法是：

> **point estimate strongly supports collapse, but the rehearsal sample is
> insufficient to establish ≥75% attenuation with 95% confidence.**

**不是**"差一点所以改成 A"。

必须随结果写明的披露（已写进预注册 §6.3.1 与 runner 输出）：

> §6.3 的 CI-upper interpretation was finalized after observing the development
> rehearsal retention estimate R=0.094, 95%CI[0.005,0.261], **but before any
> observation from the confirmatory seed block.**

> ### ★ 规则 95：比值型判据必须写"分母不可辨识时怎么办" ★
> 若 `ΔC_OWN ≈ 0`，`R` 的分母接近 0 → 比值不稳定甚至爆炸。
> **这时不能说 "SHUFFLE control failed"** —— 根本没有 transfer 可供"保留多少"。
>
> **The SHUFFLE retention criterion is interpreted only if the OWN primary
> effect shows evidence of transfer (its 95% CI excludes 0 in the preregistered
> direction). If OWN does not establish transfer, the retention ratio is
> reported descriptively but no relational-mediation claim is evaluated.**

### ② G2 保留，且失败语义写死

> G2 failure does **not** mean "no memory transfer". It means the confirmatory
> contrast is **not cleanly interpretable under the preregistered
> calibrated-interface regime.**

λ=1 的正当性来自开发块上的承诺（event-triggered、有实际影响、不饱和、不接管
policy）。若 FINAL 的自然 m 分布漂移，虽然 λ 没改，**测的已经不是原本校准出的
接口性质**。与 028 transport gate 同逻辑：**失败后不许重估 λ**。

### ③ 两个实现细节已在预注册里冻结

```
XSEED donor mapping   donor_index(i) = (i + N//2) % N
                      FINAL N=1500 → (i+750)%1500；rehearsal N=400 → (i+200)%400
                      无 self-donor / 一一映射 / 两 condition 共用同一 permutation /
                      ⛔ 不许依据任何 memory 或 outcome 选 donor
SHUFFLE permutation   rng = Random(SHUFFLE_SALT ^ seed ^ (len(episodes)<<8))
                      SHUFFLE_SALT = 0x29C10；⛔ 不许运行时现场生成新方案
```

---

## ★ `final_029.py` —— 全尺寸彩排全过（种子 10000–11499，N=1500）★

**80000–81499 一颗未碰，未创建 FINAL lock**（已核验：仓库里 `80000` 只出现在
"不碰/预留"说明和 runner 的 `FINAL_SEED0` 常量里）。

### preflight（全过）

任务指纹 + 五个模块 sha256 + 15 个冻结常量 + donor mapping + **预注册 sha256**
`29e45930a07f2649…`。任一不符直接 `SystemExit`，并提示"必须先写 AMENDMENT
再重新冻结，不许直接改常量后开跑"。

### 自检（全过）

```
lock helper        O_CREAT|O_EXCL 原子独占，二次创建被拒
worker determinism acquisition 与 transfer 逐 trial 可复现
XSEED mapping      N=400 / N=1500 均无 self-donor、一一映射
SHUFFLE            同 (seed, n_episodes) 置换确定；stay/switch 条数与 outcome 边际不变
analysis ordering  1→2→3→4→5→6→7→8→9 用断言核过
```

★ **STARTED lock 在【第一条 acquisition 轨迹】之前创建** —— 029 的种子从
acquisition 阶段就开始产生信息，不是等 novel task 开跑才算 burned。lock 永不自动删除。

### 彩排结果（已烧段，N=1500）

```
completeness      Stable 70.07%   Volatile 76.40%
non-zero evidence Stable 67.93%   Volatile 75.87%

G2   saturation 0.0000 ✓   median|Δp| 0.0742 ✓   flip 0.1443 ✓   max expo 6.50/80 ✓
G1 ✓   G3 ✓   → validity 全过

臂              ΔC          95% CI
OWN          -0.8187   [-0.9387, -0.6993]
DELETE       +0.0000   [+0.0000, +0.0000]     ← 恒等
SWAP         +0.8187   [+0.6993, +0.9393]     ← 恒等
SHUFFLE      +0.0200   [-0.0520, +0.0933]
XSEED-DONOR  -0.9180   [-1.0527, -0.7880]     保留 OWN 的 112.1%

SESOI 判读  →  Detectable memory-mediated transfer, but functional
               significance not established.（第二档）

retention  R = 0.0244   95% CI [0.0016, 0.1132]   上界 < 0.25  →  ★满足★
```

### ⚠ 三条必须在起飞前知道的事

**(a) 判据 B 在 N=1500 下确实可满足。**
功效尺度检查预期 `[0.014, 0.182]`，全尺寸彩排实测 `[0.0016, 0.1132]`，
上界离 0.25 有余量。**B 不是一个注定失败的 gate。**

**(b) ★ 两个独立块的 ΔC 都在 SESOI 下方 ★**

```
开发块 0–399（N=400）        ΔC = -0.927   CI [-1.202, -0.677]
彩排块 10000–11499（N=1500） ΔC = -0.819   CI [-0.939, -0.699]
SESOI = 1.0
```

> **两块都落在 −0.8 ~ −0.9，且 N=1500 的 CI 已经很窄。
> 因此 FINAL 最可能的结果是第二档（detectable，功能意义未确立）。**
> 这**不是**改任何东西的理由 —— 恰恰相反，它证明 SESOI=1.0 不是照着结果定的。
> 但起飞前必须知道：**大概率不会拿到"functionally meaningful"那一档。**

**(c) extensive margin 有块间波动。** 预注册 §14 依开发块预测
"Stable ≈ 66% / Volatile ≈ 73%"，彩排块实测 70.07% / 76.40%（约 +4pp）。
**预注册不改**（已冻结），但判读时要知道这个量本身有 ±4pp 的块间变异。
XSEED 保留比例同理：开发块 96.0%、彩排块 112.1%，都与"无 seed 耦合"一致。

### 复现方式（新增）

- `final_029.py`（`--rehearse` / `--final`）
  → `final_029_rehearsal_result.txt`、`final_029_rehearsal_console.txt`
- 预注册 sha256 `29e45930a07f2649c7958fdc0cd20a389005ca43e93287b9f69e2ccdcf867145`

---

## ★ 起飞前最后两处执行完整性 hardening（2026-08-18）★

**不是科学修改**：没有改 hypothesis / endpoint / SESOI / λ / seed / SHUFFLE 判据 /
任何 treatment。

### ① 冻结清单漏了一个运行时依赖

`final_029.py` 直接调用 `REH.BODY` 与 `REH.shuffled()`，
但 `memory_transfer_rehearsal.py` **不在 `FROZEN_MODULES` 里** ——
误改它 preflight 仍会全绿。已补入：

```
"memory_transfer_rehearsal.py": "b29b2d417fdaed52"
```

**是否需要 amendment：不需要。** 预注册 §12.5 逐字写的是"各模块 sha256"，
**没有枚举模块数**，所以补一个已有运行时依赖的 hash 不构成对预注册的偏离。
（若正文当初写死"五个模块"，就必须补一份 implementation amendment。）

> ### ★ 规则 96：冻结清单必须覆盖【全部运行时依赖】，不是"主要那几个" ★
> 漏掉一个被 import 的模块，等于给 preflight 开了一扇后门：
> 它会全绿，而实际跑的代码已经变了。
> 检查方法是看 runner 的 import 与属性访问，不是凭印象列文件。

### ② G2 fail path 会让两句互相矛盾的话同时出现

修改前：G2 失败会正确打印 *calibrated-interface validity compromised*，
但随后**仍继续进入 SESOI 判读**，可能在同一份 FINAL 里再打印
*Functionally meaningful memory-mediated transfer established.*

已锁成一个总开关：

```
primary_interpretable = g1_ok and g2_ok and g3_ok

not primary_interpretable →
    verdict = "DESCRIPTIVE ONLY — confirmatory interpretation disabled
               because a preregistered validity gate failed."
    own_transfer = False        → SHUFFLE 因此自动只作描述性
```

**gate 失败时仍然落盘全部 raw outcome** —— FINAL block 已经烧掉，
数据必须透明保存；但**不允许**再产生 primary success / functional success /
SHUFFLE mediation 中的任何一条。

⚠ 顺带把 G1/G3 失败从 `SystemExit` 改成**同一条路径**（作废但仍落盘），
理由相同：块已烧掉就不该连记录都没有。"整批作废"的语义不变 ——
作废指**不许作任何 confirmatory 声称**，不是删数据。

> ### ★ 规则 97：validity gate 失败必须【禁用判读】，不能只【追加警告】 ★
> 只打印一句"validity compromised"却让后面的三档判读照常输出，
> 等于把互相矛盾的两句话留在同一份结果里，日后一定会被断章取义地引用。
> 正确做法是设一个总开关，让**成功判读在物理上无法生成**。

### ★ fail path 已实测，不是靠读代码 ★

把 `SATURATION_MAX` 临时设成不可能满足的值、在已烧种子 0–59 上跑：

```
G2 判为失败                    ✓
confirmatory 已禁用            ✓
verdict = DESCRIPTIVE ONLY     ✓
SHUFFLE 只作描述性              ✓
"Functionally meaningful" 未出现        ✓
"Detectable memory-mediated transfer" 未出现  ✓
"≥75% attenuation established" 未出现   ✓
raw outcome 仍然落盘            ✓
分析顺序完整                    ✓
```

### ★ 最终 rehearsal：五项要求全过 ★

`python final_029.py --rehearse`（10000–11499，N=1500）

```
① 所有 preflight 仍 ✓                        ✓
② 现在显示 ★6 个★ 冻结模块                    ✓
③ 10000–11499 的所有数值【逐位不变】          ✓（diff 只多"confirmatory
   interpretation：启用"一行 + 两行断言措辞，数值一个不差）
④ analysis order 不变
   1-acquisition→2-G2→3-validity→4-primary→5-sesoi→6-shuffle→7-xseed
   →8-integrity→9-secondary                   ✓
⑤ 80000–81499 仍 untouched                    ✓
   final_029_STARTED.lock 不存在               ✓
```

**状态：可以起飞。等一声"走"就跑 `python final_029.py --final`。**

⚠ 已知且不构成停飞理由：开发块 ΔC=−0.927、彩排块 −0.819，
**两块都在 SESOI=1.0 下方** → FINAL 大概率落第二档。
**正因为已经知道这点，更不能再碰 SESOI / λ / acquisition / task。**
029 最有价值的结果很可能就是：

> relational memory 确实可以迁移到表面陌生、结构相似的新问题，并因果性地
> 减少错误；但这种收益**是否达到预注册的实际功能门槛**，
> 由全新 FINAL block 独立裁决。

---

# ★★★ 实验 029 —— Memory-Mediated Transfer · FINAL ★★★

**2026-08-18 · 种子 `80000–81499`（N=1500）· 该 block 已永久 burned**

预注册：`MEMORY_TRANSFER029_PREREGISTRATION.md`，sha256 `29e45930a07f2649…`
（runner 已校验）。`final_029.py` sha 前缀 `fb6a0cb672e33101`，
6 个冻结模块 hash 全过，任务指纹 `26778f672e9e7009`。
`final_029_STARTED.lock` 在**第一条 acquisition 轨迹之前**创建。用时 16.8s。

## 结果（逐项从 `final_029_result.txt` 抄，未凭记忆）

### 1. Acquisition / completeness

```
memory completeness（primary extensive margin）  Stable 65.40%   Volatile 74.80%
non-zero evidence rate                          Stable 64.13%   Volatile 74.53%
★ 所有 primary 分析使用全部 1500 × 2 个预定义 agent，含 incomplete 与 m=0 ★
```

### 2–3. Validity gates —— ★全部通过，confirmatory interpretation 启用★

```
G2  saturation 0.0000 ✓   median|Δp| 0.0737 ✓   flip 0.1476 ✓   max expo 6.36/80 ✓
    （pooled m: n=3000，m=0 占 30.7%；eligible states 9324；label 在输入处丢弃）
G1  异常前逐位相同 ✓，reward opportunity 逐位相等 ✓
G3  integrity assertions ✓
```

### 4. ★ PRIMARY ★

```
臂              ΔC          95% CI
OWN          -0.8833   [-1.0160, -0.7533]
DELETE       +0.0000   [+0.0000, +0.0000]     ← 恒等
SWAP         +0.8833   [+0.7540, +1.0160]     ← 恒等
SHUFFLE      +0.0093   [-0.0733, +0.0913]
XSEED-DONOR  -0.9240   [-1.0533, -0.7960]     保留 OWN 的 104.6%
```

### 5. ★★ SESOI 三档判读 ★★

```
95% CI [-1.0160, -0.7533]        SESOI = 1.0 post-change error
```

> ### ★ Detectable memory-mediated transfer, but functional significance not established. ★

⚠ **CI 下界 −1.0160 已经越过 −1，但上界 −0.7533 没有** ——
预注册的第三档要求**整个 CI 低于 −1**，所以判第二档。**不许**因为下界过线就
说"接近功能显著"。

### 6. ★ SHUFFLE conditional retention ratio ★

```
R = |ΔC_SHUFFLE| / |ΔC_OWN| = 0.0106      95% CI [0.0015, 0.1102]
判据（§6.3 B）：CI 上界 < 0.25   →   ★满足★
```

> **≥75% attenuation established：transfer 由关系结构承载。**

条件性判读的前提已满足（OWN 的 CI 完全 < 0，§6.3.2）。

必须随结果写明的披露：

> The CI-upper interpretation in §6.3 was finalized after observing the
> development rehearsal retention estimate R = 0.094, 95% CI [0.005, 0.261],
> **but before any observation from the confirmatory seed block.**

### 7–9

```
XSEED-DONOR   ΔC = -0.9240，保留 OWN 的 104.6% → 效应不靠发育-测试共享种子
integrity     DELETE 1500/1500 ≡ 0 ✓    SWAP 1500/1500 ≡ −OWN ✓（代数恒等式，非证据）
secondary     Δlatency OWN -1.5733 / SHUFFLE +0.0527 / XSEED -1.8433
              exposure 全程 6.2–6.3 / 80 → memory 始终 event-triggered
```

## ★ 事前预测 vs 实际（照抄预注册 §14 对比）★

```
项                     预测                          实际                    
ΔC 方向                < 0（有方向预测）              −0.8833                ✓
ΔC 是否越过 SESOI      未知（唯一真正未知项）          否，第二档              —
G1 / G3                必过                          过                     ✓
G2 capacity transport  预计通过                       过（四项均有余量）      ✓
SHUFFLE R 点估计       ≈ 0.1                         0.0106                 ✓（更小）
SHUFFLE CI 上界<0.25   不预设                        0.1102，满足            —
XSEED-DONOR            保留 ≥ 80%                    104.6%                 ✓
memory completeness    ≈ 66% / 73%                   65.40% / 74.80%        ✓
```

**唯一未知的那一项落在第二档 —— 与三个块的一致趋势相符。**

```
开发块 0–399（N=400）        ΔC = -0.927   CI [-1.202, -0.677]
彩排块 10000–11499（N=1500） ΔC = -0.819   CI [-0.939, -0.699]
★FINAL 80000–81499（N=1500） ΔC = -0.883   CI [-1.016, -0.753]★
```

三个独立块 **−0.82 ~ −0.93**，高度一致。**起飞前已公开写下"大概率落第二档"，
结果如此。这不是事后合理化。**

## ⚠⚠ 协议偏离：必须如实记录 ⚠⚠

> ### ★ 规则 98：预注册写在哪个阶段做的检查，就必须在那个阶段做 ★
> 预注册 §10 要求：**彩排阶段**换 8 个分析随机种子重跑，
> 若判读会被分析种子左右，**在跑 FINAL 之前**改成加宽的三值判读。
>
> **这一步在彩排阶段没有做。** 是在 FINAL 跑完之后才补做的。
> 补做**不能**假装是按计划做的 —— 如实记为**协议偏离**。

补做结果（**描述性**，不改变任何判读；同 027 的 analysis-level MC stability，规则 80）：

```
分析种子    CI_lo     CI_hi     判读                      R CI 上界   <0.25
  8181★   -1.0160   -0.7533   档2 可检出/功能意义未确立    0.1102      ✓
     1    -1.0160   -0.7547   档2                        0.1083      ✓
     2    -1.0167   -0.7573   档2                        0.1115      ✓
     3    -1.0147   -0.7547   档2                        0.1102      ✓
     4    -1.0160   -0.7560   档2                        0.1086      ✓
     5    -1.0180   -0.7560   档2                        0.1111      ✓
     6    -1.0147   -0.7560   档2                        0.1107      ✓
     7    -1.0133   -0.7547   档2                        0.1090      ✓

8/8 判读一致；8/8 R 判据一致
CI_hi 的 MC SD = 0.00115
距离 0 的边界 0.7533 = 655 × MC SD；距离 −1 的边界 0.2467 = 214 × MC SD
```

**判读离两条 bright line 都极远（远超预注册要求的 10 × MC SD），
所以这次偏离没有造成实质风险 —— 但下一个实验必须按阶段执行。**

## 029 能写什么 / 不能写什么

| | |
|---|---|
| ✅ | 真实发育经历自然长出的 **relational memory**，经一条**独立校准（group-blind）的接口**，在表面陌生、结构相似的新问题中**因果性地减少了错误**（ΔC = −0.88，CI [−1.02, −0.75]） |
| ✅ | 该效应**由关系结构承载**：保持 episode 数、stay/switch 条数与 outcome 边际不变、只打乱 action↔outcome 关系后，**≥75% 的 transfer 消失**（R = 0.011，CI 上界 0.110 < 0.25） |
| ✅ | 效应**不靠发育与测试共享种子**（XSEED-DONOR 保留 104.6%） |
| ✅ | **功能意义未确立** —— 未达到预注册的 1-error 门槛 |
| ⛔ | ~~functionally meaningful transfer~~ —— 第三档要求整个 CI < −1，没有达到 |
| ⛔ | ~~analogical reasoning~~ / agent"理解了结构 / 理解了因果" |
| ⛔ | ~~generalized individuality~~ |
| ⛔ | 把 DELETE / within-seed SWAP 写成因果证据（规则 93：memory-only 架构下是代数恒等式） |
| ⛔ | 把 `m ≠ 0` 叫 memory availability（规则 94：completeness 与 non-zero evidence rate 是两个量） |
| ⛔ | 只报 complete-only 的分离度（规则 91） |

## ★ 025 + 027 + 028 + 029 合起来说明了什么 ★

```
025/v3  过去能不能【留下】                     明显
027     留下的 personality 会自动迁移吗         极弱（0.08 trial），且新块未复制
028     等预算下加宽 personality readout        没有增益（G ≈ 0）
★029★  真实经历长出的【关系性记忆】能否迁移    ★能，−0.88 error，且由关系结构承载★
                                               但未达 1-error 功能门槛
```

> ### ★ 核心命题（最终形态）★
> **Persistent individuality ≠ automatically functional generalization —— 但
> relational memory 不是同一回事。**
>
> 027/028 表明：把发育史压成一个 personality readout 送进新任务，
> 几乎不携带可复制的功能迁移。
> **029 表明：当发育史以【关系性经验】的形式被存下、并在遇到结构相似的情境时
> 被检索，它确实能因果性地减少新问题中的错误** ——
> 这个效应稳定（三块 −0.82~−0.93）、可归因于关系结构（SHUFFLE 摧毁 ≥75%）、
> 且不依赖种子耦合（XSEED 104.6%）。
>
> **但它没有跨过我们预先定下的功能门槛。**
> 迁移是**真实的、机制清楚的、但幅度小于 1 个 post-change error**。

## 复现方式（新增）

- `final_029.py --final` → `final_029_result.txt`、`final_029_console.txt`、
  `final_029_STARTED.lock`
- 种子账本更新：`80000–81499` = **029 FINAL（已烧）**
