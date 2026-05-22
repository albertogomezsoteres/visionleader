# Experiments

Each component was chosen and checked with its own set of experiments, and the
assembled system was then tested end to end. This is a summary; each folder under
`experiments/` has its own README with the full protocol and results.

| Experiment | Question | Outcome |
|-|-|-|
| STT (`experiments/stt/`) | Which speech model on the phone | Whisper tiny q5_0, 100% Domain Keyword Accuracy |
| VLM (`experiments/vlm/`) | Which vision model | Gemma 4 E4B-it |
| Planner (`experiments/planner/`) | Which search configuration | A* with LM-Cut, optimal |
| Symbolic grounding (`experiments/symbolic_grounding/`) | Basic vs optimized prompt | optimized prompt |
| End to end (`experiments/end_to_end/`) | Do the parts work together | 3 of 3 scenarios pass |

## STT

Eight speech models ranked on 30 campus utterances. The key metric is Domain Keyword
Accuracy (DKA): whether the campus keywords the planner depends on are all
transcribed correctly. All six Whisper sizes reach 100% DKA, so the smallest, tiny,
is taken on device; the quantised `tiny-q5_0` keeps 100% DKA at about 3 seconds per
utterance.

## VLM

Two phases. Phase 1 screens seven models (five PaliGemma 2 variants, two Gemma 4) on
element and state recognition; PaliGemma2-3b-mix and Gemma 4 E4B-it tie. Phase 2 runs
the two best on location extraction, where Gemma 4 E4B-it scores 1.00 against 0.74
for PaliGemma. Gemma 4 E4B-it is the model used in the app.

## Planner

Twelve hand-written PDDL problems solved with three Fast Downward configurations. A*
with LM-Cut solves all twelve optimally and explores about 75 times fewer states than
blind A*; greedy search is faster but returns a more costly plan on 4 of the 12. A*
with LM-Cut is the chosen search.

## Symbolic grounding

Tests the prompts that turn an input into a PDDL atom, comparing a basic prompt
against an optimized one with Gemma 4 E4B-it. The optimized prompt clearly improves
exact-match accuracy: 0.20 to 0.84 on text and 0.35 to 0.96 on images.

## End to end

Three scenarios run the whole system from voice to door-to-door route. All three
complete, with full marks on the validation checks, STT keywords, vision grounding
and route correctness.
