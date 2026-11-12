# Datasets

The test sets used by the experiments, kept separate from the experiment code and
results (those live under `experiments/`). Each subfolder holds the inputs for one
part of the system.

| Module | Folder | Contents |
|-|-|-|
| Speech to text | `stt/` | 30 campus utterances: manifest, reference transcripts and audio hashes. |
| Vision language | `vlm/` | 80 campus images: manifest, ground truth and hashes (the image files are local and gitignored). |
| Planner | `planner/` | The 12 PDDL routing problems: manifest and hashes (the files themselves are in `pddl/problems/evaluation/`). |
| Symbolic grounding | `symbolic_grounding/` | The text-to-PDDL and image-to-PDDL test sets, with the expected atoms. |

Private or large inputs, such as the author's recorded voice and the campus photos,
are not shipped. They are documented here by manifest and SHA-256 hash, so the
dataset stays reproducible without publishing the source files.

The hashes were taken on a Windows checkout, so text files (the PDDL problems) are
hashed with CRLF line endings; git stores them with LF. `tests/test_data_and_results.py`
checks every manifest against its hash file and the 12 problems against their hashes.
