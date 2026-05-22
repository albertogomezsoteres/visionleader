# Reproducibility

Every experiment runs under fixed settings so its numbers can be reproduced. This
page lists where each one runs, how it is pinned, and how to rerun it.

## How runs are pinned

- Vision and grounding: greedy decoding (`do_sample=False`, `num_beams=1`), fixed seed.
- Speech: greedy decoding, fixed seed, and the same 30 audio files across all STT phases.
- Planner: deterministic search; the 12 problems are fixed on disk.

Each experiment writes a reproducibility card (a JSON with the environment, the
decoding settings, the seed, the hardware and the SHA-256 hashes of its inputs), so a
rerun can be checked against the recorded one.

## Per experiment

| Experiment | Hardware | How to run |
|-|-|-|
| STT | Colab GPU (phase 1), Pixel 10 Pro (phases 2 and 3) | Notebooks in `experiments/stt/`; `bench.py` on the phone for phase 2 |
| VLM | Colab A100 GPU | Notebooks in `experiments/vlm/` |
| Symbolic grounding | Colab GPU | Notebooks in `experiments/symbolic_grounding/` |
| Planner | Docker (Fast Downward) | `python experiments/planner/evaluate_planner.py` |
| End to end | Backend + Docker | `python experiments/end_to_end/scripts/build_validation_csv.py` |

## Datasets

The inputs live under `data/` and are pinned by SHA-256 hashes (see `data/README.md`).
The audio and images are not committed, but their hashes are, so a held copy is
verified identical to the one benchmarked.

## Results

Result files (CSVs) are regenerable and kept local, not committed. Rerunning the
command or notebook regenerates them; the headline numbers are recorded in each
experiment's README.
