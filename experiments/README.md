# Experiments

Each component of the system was selected and validated through its own set of
experiments, and the assembled system was then tested end to end. The experiments
share one method: a measurable objective, a custom UFV campus dataset (under
`data/`), fixed decoding settings for reproducible runs, and a quantitative
comparison whenever a model has to be chosen.

Each experiment runs in the environment where its component runs: the vision model
and the server-side speech benchmark on Colab GPUs, the on-device speech tests on a
Pixel 10 Pro, and the planner in a Docker container.

## Overview

| Folder | Question | Outcome |
|-|-|-|
| `vlm/` | Which vision model recognises campus elements and reads locations | Gemma 4 E4B-it |
| `stt/` | Which speech model transcribes campus utterances on device | Whisper tiny (q5_0) |
| `planner/` | Which search configuration solves campus routes | A* with LM-Cut |
| `symbolic_grounding/` | Whether an optimized prompt grounds inputs to PDDL better than a basic one | optimized prompt |
| `end_to_end/` | Whether the components work correctly when composed, door to door | 3 of 3 scenarios pass |

Each folder has its own README with the full protocol. Result files are
regenerable and kept local, not committed to the repository.
