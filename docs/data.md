# Data

The test sets the experiments use, under `data/`, one folder per component. The code
and results live elsewhere (`experiments/`); this folder is only the inputs and their
ground truth.

| Folder | Contents |
|-|-|
| `data/stt/` | 30 campus utterances: manifest, reference transcripts, audio hashes. |
| `data/vlm/` | 80 campus images: manifest, ground truth, hashes. |
| `data/planner/` | The 12 PDDL routing problems: manifest and hashes. |
| `data/symbolic_grounding/` | The text-to-PDDL and image-to-PDDL test sets with the expected atoms. |

## What is not committed

Two kinds of input are kept local and not uploaded:

- The audio (`data/stt/audios/`): it contains the author's voice.
- The images (`data/vlm/images/`): kept out to keep the repository light.

They are documented instead by a manifest and a SHA-256 hash per file, so a private
copy can be verified byte for byte against the set that was used. The hashes match
the ones recorded by the experiments, so a held copy is provably identical to the one
that was benchmarked.

## Manifests and hashes

Each folder has a `manifest.csv` (one row per item, with its ground truth and
metadata) and a `dataset_hashes.json` (the SHA-256 of every file). Together they make
the dataset reproducible without publishing the source media.
