# Reproducibility

Every experiment runs under fixed settings so its numbers can be reproduced. This
page lists where each one runs, how it is pinned, and how to rerun it.

## How runs are pinned

- Vision and grounding: greedy decoding (`do_sample=False`, `num_beams=1`), fixed seed.
- Speech: greedy decoding, fixed seed, and the same 30 audio files across all STT phases.
- Planner: deterministic search over the 12 problems frozen in `pddl/problems/evaluation/`,
  with Fast Downward pinned to `release-24.06.1`.

Each experiment writes a reproducibility card (a JSON with the environment, the
decoding settings, the seed, the hardware and the SHA-256 hashes of its inputs), so a
rerun can be checked against the recorded one.

## Per experiment

| Experiment | Hardware | How to run |
|-|-|-|
| STT | Colab GPU (phase 1), Pixel 10 Pro (phases 2 and 3) | Notebooks in `experiments/stt/`; `bench.py` on the phone for phase 2 |
| VLM | Colab A100 GPU | Notebooks in `experiments/vlm/` |
| Symbolic grounding | Colab GPU | Notebooks in `experiments/symbolic_grounding/` |
| Planner | Docker (Fast Downward) | `make benchmark-planner` |
| End to end | Backend + Docker | `python experiments/end_to_end/scripts/build_validation_csv.py` |

## Datasets

The inputs live under `data/` and are pinned by SHA-256 hashes (see `data/README.md`).
The audio and images are not committed, but their hashes are, so a held copy is
verified identical to the one benchmarked.

## Results

The result CSVs are committed under `experiments/*/results/`, next to the code that
produced them. Rerunning the command or notebook regenerates them.

Two automated checks keep them honest:

- `tests/test_data_and_results.py` recomputes every headline number in the docs from
  the CSVs (runs in CI on every push).
- `tests/test_planner_integration.py` re-solves all 36 planner runs with the pinned
  Fast Downward image and requires identical plan cost, plan length and expanded,
  generated and evaluated states (`make test-planner`; also in CI).

## Environment

- Backend and tests: Python 3.10 to 3.12, every dependency pinned in `uv.lock`
  (`make install`).
- Planner: Fast Downward `release-24.06.1`, built by `docker/fast-downward/Dockerfile`
  (`make planner-image`).
