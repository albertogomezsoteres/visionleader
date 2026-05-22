# Symbolic grounding experiments

These experiments test the interface between the neural and symbolic sides: turning
a raw input into a single PDDL atom the planner can use, of the form
`(at user LOCATION_ID)`. Both sub-experiments use the chosen model, Gemma 4 E4B-it,
with greedy fixed-seed decoding on Colab, and compare two prompt variants, a basic
one against an optimized one. Test sets are in `data/symbolic_grounding/`.

## Text to PDDL

`text/`. A Whisper transcript is grounded into a location atom. 51 transcripts: 20
canonical (clean, expected phrasing) and 31 robustness cases (spelled-out numbers,
phonetic spellings, extra words). Each transcript is run under both prompt variants.

## Image to PDDL

`vlm/`. A photo of a room plate or directory sign is grounded into a location atom.
46 images: 26 room plates and 20 directory signs. Each image is run under both
prompt variants.

Each folder holds its notebook and the two prompt variants in `prompts.json`.

## Outcome

The optimized prompt clearly improves exact-match accuracy: 0.20 to 0.84 on text
and 0.35 to 0.96 on images. On text it also raises format validity from 0.76 to
1.00 (on images both variants were already at 1.00), so every output the optimized
prompt produces is a valid atom the planner can read.
