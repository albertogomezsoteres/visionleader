# Symbolic grounding test sets

Symbolic grounding is the step where a raw input is turned into a structured PDDL
atom the planner can act on: it is the point where the neural and symbolic sides of
the system meet. These test sets validate the prompts that perform that step,
comparing a basic prompt against an optimized one.

Two grounding paths are covered:

- `text/`: text to PDDL. A Whisper transcript is turned into a location atom such as `(at user classroom_g_0_3)`.
- `vlm/`: image to PDDL. A campus photo (room plate or directory sign) is turned into a location atom by the vision language model.

## text/

Self-contained: the transcripts are the data, so no external files are referenced
and no hashes are needed.

- `manifest.csv`: 20 canonical transcripts.
- `manifest_robust.csv`: 31 noisier transcripts (spelled-out numbers, hedging, filler words) that stress the parser.

Columns: `id`, `type` (`initial_location` or `destination`), `whisper_transcript`,
`expected_location_id`, `expected_pddl_atom`.

## vlm/

- `manifest.csv`: 46 images (26 room plates, 20 directory signs) with their expected atom.
- `dataset_hashes.json`: SHA-256 of every referenced image, so a held copy can be verified byte for byte.

Columns: `id`, `prompt_id` (`room_plate` or `directory_sign`), `image_rel_path`,
`expected_location_id`, `expected_pddl_atom`.

The images are not duplicated here: `image_rel_path` resolves against the shared
campus image set in `data/vlm/images/`, and the hashes pin the exact bytes used.

## Ground truth

Every row carries `expected_location_id` and `expected_pddl_atom`, the correct
symbolic output. A grounding is correct when the model returns that atom.
