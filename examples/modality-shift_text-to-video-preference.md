# Worked example — Modality-shift: text-preference-rlhf → video preference

**Operator:** modality-shift. **Source card:** `text-preference-rlhf` (text / preference / crowd).
**Target:** video preference data for a video-generation model.

The partner keeps the skeleton + patterns, re-derives the modality-specific parts from each
pattern's `modality_notes`, surfaces failure modes the new modality introduces, and transplants
patterns from other cards where the modality forces a change. Every move cites its
pattern / inherited signature / cost (the guardrail).

---

## 1. Kept (modality-independent skeleton)
Pairwise A-vs-B preference · qualified crowd · honeypots + IAA + qualification/calibration ·
position randomization · aggregate to reward labels.
*[from the source card's `uses_patterns`; patterns are invariant by definition]*

## 2. What swaps (re-derived from `modality_notes`)

- **Cost regime flips the bottleneck.** A text pair is read in seconds; a video pair must be
  *watched*. Per-judgment time explodes and viewing time — not calibration authoring — becomes
  the bottleneck. *[cost_profile, re-derived for video]*
- **Agreement gets noisier** *(inter-annotator-agreement → modality_notes)*. Two raters can pick
  the same clip for incompatible reasons (one for motion smoothness, one for prompt adherence),
  so holistic A/B IAA drops. → refine the task: **multi-attribute preference** (motion / prompt-
  adherence / aesthetics) instead of one holistic vote. *Defends `under_specification`; costs more
  rater time per pair.*
- **Honeypots weaken** *(gold-honeypots → modality_notes: "known answer is fuzzier for generative
  tasks")*. A known-better video pair is expensive to author and the bank is small enough to
  memorize. → lean more on **human-gold-anchor** + agreement, less on honeypots.
  *Shifts weight across patterns; defends `inflation` but raises gold-set cost.*

## 3. New failure modes video introduces (not in the text card)

- `confounded` — rendering artifacts / resolution / framerate / presence of audio become spurious
  cues that swamp content. (Text's analog was the length/verbosity confound.)
  *Caught by: multi-attribute decomposition; UNGUARDED for audio — add a muted/normalized pass.*
- `priming` (worse than text) — opening-frame dominance + within-pair watch order. Raters judge
  the first seconds. *Caught by: A/B randomization (kept) + clip-order randomization (new).*
- **Attention/coverage** — did the rater watch the whole clip? Text has no analog.
  *UNGUARDED — no pattern in the library defends this. ← corpus gap discovered (see §6).*

## 4. Transplants the modality forces (from other cards)

- **active-learning-loop + human-audit-sample** *(from `synthetic-with-audit`)* — because human
  viewing is so expensive, pre-screen pairs with an automatic reward model and put humans on the
  most-discriminable / stratified sample, not every pair. *Defends the new cost `bottleneck`;
  **conflicts with `lock-then-score`** and risks sampling away the model's blind spots — surface
  this as a choice, don't hide it.*
- **deployment-stratified / diverse-prompt sampling** *(echoes the rare-class over-sampling in
  `image-bbox-adjudicated`)* — sample diverse motion regimes and prompt types so the reward model
  isn't blind to rare video behaviors. *Defends `class_imbalance` / `sampling_frame`.*

## 5. The open design choice the partner surfaces
You can't have a **frozen rubric** (`lock-then-score`) *and* an **adapting sample**
(`active-learning-loop`) — the library marks them `conflicts_with`. Video's cost pressure pushes
toward active learning; reward-model stability pushes toward freezing. Which matters more here?

## 6. Corpus gap discovered
The "did they actually watch it" failure mode has no defending pattern. That's a new pattern to
write — `engagement-gate` (attention/watch-time check) — and it generalizes to audio and any
time-based modality. **The demo found the next card to write.**
