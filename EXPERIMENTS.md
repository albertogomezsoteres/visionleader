# Experiments — PaliGemma Evaluation for Indoor Campus Navigation

This document describes the complete evaluation framework used to assess PaliGemma vision-language models for assisting visually impaired users navigating the UFV campus. Two experiments are defined, each covering a different cognitive task. Both experiments run over the same set of 12 PaliGemma models and share the same annotation infrastructure.

---

## Directory Structure

```
tfg/
├── data/ufv_campus/
│   ├── images/
│   │   ├── staircase/         (13 positive + 2 negative images)
│   │   ├── elevator/          (8 positive + 2 negative images)
│   │   ├── door/              (5 positive + 2 negative images)
│   │   ├── door_sign/         (5 positive + 2 negative images)
│   │   ├── obstacle/          (7 positive + 2 negative images)
│   │   ├── building_sign/     (12 images: 6 complete, 3 sign_only, 3 wall_number)
│   │   └── door_room/         (10 images)
│   └── experiments/
│       └── annotations/
│           ├── questions.json              (all prompts for both experiments)
│           ├── exp1_expected_answers.json  (ground truth for experiment 1)
│           └── exp2_expected_answers.json  (ground truth for experiment 2)
├── notebooks/
│   ├── Experiment 1/
│   │   ├── experiment1_evaluation.ipynb   (single model, exp1)
│   │   └── experiment1_all_models.ipynb   (12 models sequentially, exp1)
│   └── Experiment 2/
│       ├── experiment2_evaluation.ipynb   (single model, exp2)
│       └── experiment2_all_models.ipynb   (12 models sequentially, exp2)
└── config/
    └── models.json                        (12 PaliGemma model definitions)
```

---

## Models

Both experiments evaluate the same 12 PaliGemma models defined in `config/models.json`. The set covers:

- PaliGemma v1 and v2
- 3B and 10B parameter counts
- Input resolutions of 224px and 448px
- Pre-trained (pt) and fine-tuned mixture (mix) variants

Models are loaded from HuggingFace using `AutoProcessor` and `PaliGemmaForConditionalGeneration`. Token extraction uses `output[0][input_len:]` to decode only the generated tokens, not the prompt.

Between models, GPU memory is released explicitly:
```python
del model, processor
gc.collect()
torch.cuda.empty_cache()
```

---

## Annotation Files

### `data/ufv_campus/experiments/annotations/questions.json`

Defines all prompts for both experiments. Structure:

```
questions.json
├── experiment1
│   └── categories
│       ├── staircase   (4 questions)
│       ├── elevator    (3 questions)
│       ├── door        (3 questions)
│       ├── door_sign   (4 questions)
│       └── obstacle    (3 questions)
└── experiment2
    └── categories
        ├── building_sign  (1 question)
        └── door_room      (3 questions)
```

Each question defines: `id`, `type` (closed / element / extraction), `question` text, `expected_answer_key`, and `metrics`.

Question types:
- `closed`: constrained answer expected (yes/no, open/closed, up/down). Evaluated with exact match.
- `element`: free single-word answer about what is visible. Evaluated with keyword recall and BERTScore.
- `extraction`: free answer extracting text from a sign. Evaluated with custom accuracy metrics.

### `data/ufv_campus/experiments/annotations/exp1_expected_answers.json`

Ground truth for Experiment 1. Structure: category -> image filename -> question answers.

Each image entry contains:
- One expected value per question ID (e.g., `staircase_detection: "yes"`)
- `element_keywords`: list of accepted keywords for keyword recall
- `bertscore_reference`: reference string used for BERTScore on element questions
- **Negative images:** expected `*_detection: "no"` for that category, and the notebook still runs **element** (and other detection-style) questions with the gold defined in JSON (e.g. which object is actually visible). State/detail questions (direction, handrails, open/closed) are skipped for negatives.

### `data/ufv_campus/experiments/annotations/exp2_expected_answers.json`

Ground truth for Experiment 2. Structure: category -> image filename -> answers.

For `building_sign` images, each entry contains:
- `type`: `"complete"` (building + floor visible), `"sign_only"` (floor only), or `"wall_number"` (painted floor number)
- `building`: expected building code string or null
- `floor`: expected floor number string
- `building_acceptable`: list of acceptable building code variants (e.g., `["G", "g", "edificio g"]`)
- `bertscore_reference`: reference string for BERTScore, e.g., `"EPS 0"`. Null for non-complete images.

For `door_room` images, each entry contains:
- `doorroom_detection`: `"yes"` for all 10 images
- `room_code`: canonical room code (e.g., `"1.2"`, `"IA"`)
- `doorroom_state`: `"open"` or `"closed"`
- `room_code_acceptable`: list of accepted response variants, including no-dot forms for decimal codes (e.g., `"14"` accepted alongside `"1.4"` to account for models that drop the decimal separator)

---

## Experiment 1 — Navigation Element Recognition

### Objective

Evaluate whether PaliGemma can correctly identify navigation elements that a visually impaired user may encounter on an indoor campus: staircases, elevators, doors, signed doors, and obstacles blocking the path.

### Dataset

Images are stored in `data/ufv_campus/images/<category>/`. Each category includes positive images (showing the element) and negative images (showing a different scene without the element).

| Category | Positive images | Negative images | Total |
|----------|----------------|-----------------|-------|
| staircase | 13 | 2 | 15 |
| elevator | 8 | 2 | 10 |
| door | 5 | 2 | 7 |
| door_sign | 5 | 2 | 7 |
| obstacle | 7 | 2 | 9 |
| **Total** | **38** | **10** | **48** |

Negative images are essential for binary detection metrics. Without them, a model that always answers "yes" would score perfect accuracy.

Negative images per category use scenes from other categories (e.g., a corridor photo used as a negative for staircase detection).

### Questions and Prompts

Defined in `questions.json` under `experiment1.categories`. Questions that apply only to positive images are not executed for negative images.

**Staircase (4 questions):**

| ID | Prompt | Applies to | Metrics |
|----|--------|-----------|---------|
| `staircase_detection` | "Is there a staircase visible in this image? Answer yes or no." | All images | exact_match, precision, recall, TP/FP/TN/FN |
| `staircase_direction` | "Are the stairs going up or down as seen from the camera? Answer with one word: up or down." | Positive only | exact_match |
| `staircase_handrails` | "Does the staircase have handrails? Answer yes or no." | Positive only | exact_match |
| `staircase_element` | "What is the main navigation element visible in this image? Answer with one word." | Positive only | keyword_recall, bertscore_f1 |

**Elevator (3 questions):**

| ID | Prompt | Applies to | Metrics |
|----|--------|-----------|---------|
| `elevator_detection` | "Is there an elevator visible in this image? Answer yes or no." | All images | exact_match, precision, recall, TP/FP/TN/FN |
| `elevator_doors` | "Are the elevator doors open or closed? Answer with one word: open or closed." | Positive only | exact_match |
| `elevator_element` | "What is the main navigation element visible in this image? Answer with one word." | Positive only | keyword_recall, bertscore_f1 |

**Door (3 questions):**

| ID | Prompt | Applies to | Metrics |
|----|--------|-----------|---------|
| `door_detection` | "Is there a door visible in this image? Answer yes or no." | All images | exact_match, precision, recall, TP/FP/TN/FN |
| `door_state` | "Is the door open or closed? Answer with one word: open or closed." | Positive only | exact_match |
| `door_element` | "What is the main navigation element visible in this image? Answer with one word." | Positive only | keyword_recall, bertscore_f1 |

**Door Sign (4 questions):**

| ID | Prompt | Applies to | Metrics |
|----|--------|-----------|---------|
| `doorsign_bathroom` | "Is this a bathroom door? Answer yes or no." | All images | exact_match, precision, recall, TP/FP/TN/FN |
| `doorsign_exit` | "Is this an exit door? Answer yes or no." | All images | exact_match, precision, recall, TP/FP/TN/FN |
| `doorsign_state` | "Is the door open or closed? Answer with one word: open or closed." | Positive only | exact_match |
| `doorsign_element` | "What navigation sign is visible on this door? Answer with one word." | Positive only | keyword_recall, bertscore_f1 |

**Obstacle (3 questions):**

| ID | Prompt | Applies to | Metrics |
|----|--------|-----------|---------|
| `obstacle_detection` | "Is there an object blocking the walking path? Answer yes or no." | All images | exact_match, precision, recall, TP/FP/TN/FN, hazard_miss_rate |
| `obstacle_safety` | "Is the path ahead clear to walk through? Answer yes or no." | All images | exact_match, precision, recall, TP/FP/TN/FN, safety_hazard_miss_rate |
| `obstacle_object` | "What is the main object blocking the walking path? Answer with one word." | Positive only | keyword_recall, bertscore_f1 |

### Metrics

**Closed questions (yes/no, open/closed, up/down):**

| Metric | Definition |
|--------|-----------|
| Accuracy (exact match) | Semantic exact match: checks first token, substrings, and common variants. Not strict character-level equality. |
| Precision | TP / (TP + FP) — for binary detection questions |
| Recall | TP / (TP + FN) — for binary detection questions |
| F1 | 2 * Precision * Recall / (Precision + Recall) |
| Hazard Miss Rate | 1 - Recall, applied to `obstacle_detection`. Fraction of real obstacles the model failed to detect. Lower is safer. |
| Safety Hazard Miss Rate | FP / (FP + TN), applied to `obstacle_safety`. Among scenes that are NOT safe to treat as clear, the fraction where the model answers "clear". Lower is safer. Note: this is a different formula from hazard_miss_rate. |

**Element questions (free single-word answer):**

| Metric | Definition |
|--------|-----------|
| Keyword Recall | Binary hit: 1.0 if any expected keyword appears in the prediction, 0.0 otherwise. Keywords are strict (2 terms max) so BERTScore can capture additional variants. |
| BERTScore F1 | Semantic similarity between prediction and reference using BERT embeddings (`lang='en'`). Reference is the canonical element name (e.g., "staircase"). Computed in batch after all inferences. |

**Efficiency (per model, over all inferences):**

| Metric | Unit |
|--------|------|
| `n_parameters` / `n_parameters_billions` | parameter count (exact + rounded billions) |
| VRAM peak | GB — `torch.cuda.max_memory_allocated()` |
| `model_load_time_s` | seconds to load processor + weights |
| `total_wall_time_s` | wall-clock seconds for the full inference loop |
| `total_inference_time_s` | sum of per-call inference times (from row timings) |
| Average inference time | ms per inference call |
| `throughput_img_per_s` | unique images / total inference seconds |
| `throughput_inf_per_s` | inference calls / total inference seconds |
| Average output length | words per prediction |
| Max output length | words |

### Output Files (Experiment 1)

**Single-model notebook** (`experiment1_evaluation.ipynb`): flat layout under `results/exp1/`:

```
results/exp1/
├── {model_safe}_exp1_results.csv
├── {model_safe}_exp1_aggregate.csv
├── {model_safe}_exp1_efficiency.json
├── {model_safe}_exp1_matrices.json
└── plots/
    ├── {model_safe}_accuracy_by_category.png
    ├── {model_safe}_state_open_closed.png
    ├── {model_safe}_state_up_down.png
    ├── {model_safe}_nav_elements.png
    ├── {model_safe}_detection_staircase.png
    ├── {model_safe}_detection_elevator.png
    ├── {model_safe}_detection_door.png
    ├── {model_safe}_detection_obstacle.png
    ├── {model_safe}_detection_doorsign_bathroom.png
    ├── {model_safe}_detection_doorsign_exit.png
    └── {model_safe}_safety_obstacle.png
```

**All-models notebook** (`experiment1_all_models.ipynb`): one subfolder per checkpoint:

```
results/exp1/
├── {model_safe}/
│   ├── results.csv
│   ├── aggregate.csv
│   ├── efficiency.json
│   ├── matrices.json
│   └── plots/   (same PNG types as above, filenames prefixed with {model_safe}_)
├── all_models_summary.csv
├── all_models_expanded.csv
├── comparison_plots/
└── exp1_reproducibility.json
```

**Per-model results CSV** — one row per image × question. Filename: `{model_safe}_exp1_results.csv` (single-model notebook) or `{model_safe}/results.csv` (all-models notebook).

| Column | Description |
|--------|-------------|
| model_id | HuggingFace model ID |
| category | staircase / elevator / door / door_sign / obstacle |
| image | image filename |
| is_negative | True if negative image |
| question_id | e.g., staircase_detection |
| question_type | closed or element |
| question | prompt text sent to the model |
| prediction | model output (generated tokens only) |
| expected | expected answer from exp1_expected_answers.json |
| inference_time_ms | inference time in milliseconds |
| output_length_words | number of words in prediction |
| exact_match | 1.0 / 0.0 for closed questions |
| keyword_recall | 1.0 / 0.0 for element questions |
| bertscore_f1 / bertscore_p / bertscore_r | BERTScore for element questions |
| bertscore_reference | reference string used per image |

**`*_exp1_aggregate.csv`** — one row per category with mean metrics:

Columns include: accuracy, keyword_recall, bertscore_f1/p/r, avg_output_length, detection_tp/fp/tn/fn, detection_precision/recall/f1, hazard_miss_rate, safety_tp/fp/tn/fn, safety_precision/recall/f1, safety_hazard_miss_rate, bathroom_tp/fp/tn/fn, bathroom_precision/recall/f1, exit_tp/fp/tn/fn, exit_precision/recall/f1.

**`*_exp1_efficiency.json`** — efficiency metrics for the full experiment run.

**`*_exp1_matrices.json`** — confusion matrices:

- `state_open_closed`: 2x2 matrix aggregating elevator_doors, door_state, and doorsign_state. Rows = expected (open/closed), columns = predicted. Includes accuracy, correct, total, and unknown_predictions count.
- `state_up_down`: 2x2 matrix for staircase_direction. Rows = expected (up/down), columns = predicted.
- `navigation_elements`: 7x7 matrix for element identification across all categories. Rows = ground truth element (staircase/elevator/door/sign/obstacle/corridor/other), columns = predicted element mapped from free-text response via keywords. Out-of-vocabulary responses map to "other".

**Plots:**

| File | Content |
|------|---------|
| `*_accuracy_by_category.png` | Bar chart of exact match accuracy per category |
| `*_state_open_closed.png` | 2x2 heatmap for open/closed classification |
| `*_state_up_down.png` | 2x2 heatmap for up/down classification |
| `*_nav_elements.png` | 7x7 heatmap for navigation element recognition |
| `*_detection_{category}.png` (x4) | 2x2 binary detection heatmap per category |
| `*_detection_doorsign_bathroom.png` | 2x2 heatmap for bathroom sign detection |
| `*_detection_doorsign_exit.png` | 2x2 heatmap for exit sign detection |
| `*_safety_obstacle.png` | 2x2 heatmap for obstacle safety classification |

### Notebooks (Experiment 1)

**`notebooks/Experiment 1/experiment1_evaluation.ipynb`** — single model evaluation:

Cells cover: imports, configuration (model ID, paths), model loading, dataset loading from `exp1_expected_answers.json`, inference loop per image and question, BERTScore computation in batch, per-category metric aggregation, confusion matrix construction, plot generation, and CSV/JSON file saving. The model ID is set manually at the top.

Key design decisions:
- `build_state_confusion()` returns **4** values: `(matrix, correct, total, unknown_pred)`. Accuracy is computed afterward as `correct / total`.
- `compute_confusion_matrix()` used for binary detection; returns TP, FP, TN, FN.
- Safety Hazard Miss Rate computed as `FP / (FP + TN)` where the positive class is "clear" (yes). This is NOT the same formula as Hazard Miss Rate (which is `1 - recall`).

**`notebooks/Experiment 1/experiment1_all_models.ipynb`** — sequential evaluation of all 12 models:

Wraps the single-model logic into `run_experiment1_for_model(model_meta)` which: loads the model, runs all inferences, computes all metrics, saves all output files and plots, frees GPU memory, and returns a summary dictionary. After all models, generates `all_models_summary.csv` and comparison plots in `comparison_plots/`.

Key design decisions:
- `build_state_confusion()` returns 5 values (adds accuracy as the 5th) in this notebook — different from the single-model version, both internally consistent.
- `safety_hmr = round(fp_s / (fp_s + tn_s), 4) if (fp_s + tn_s) > 0 else 0.0`

Additional outputs generated only by the all-models notebook:
- `all_models_summary.csv` — one row per model with all aggregated metrics and efficiency data
- `comparison_plots/` — cross-model bar charts (accuracy, safety metrics, BERTScore, state accuracies, VRAM, etc.)

---

## Experiment 2 — Location State Extraction

### Objective

Evaluate whether PaliGemma can read building information signs and classroom door signs on the UFV campus, extracting the building code, floor number, and room code. This directly tests the perception capability required by the navigation agent (Agent1) when localizing the user.

### Dataset

Images are stored in `data/ufv_campus/images/<category>/`.

**building_sign (12 images):**

Images are classified into three types based on what information is visible:

| Type | Count | Description |
|------|-------|-------------|
| complete | 6 | Full directory sign showing building code (EPS or G) and floor number |
| sign_only | 3 | Sign showing floor number only; no building code visible |
| wall_number | 3 | Large floor number painted on corridor wall; no sign structure |

Buildings represented: EPS (Engineering building), G (Main building). Floors represented: -2, -1, 0, 1, 2.

**door_room (10 images):**

All 10 images show classroom doors with a room code visible. Codes follow the pattern `floor.room` (e.g., `1.2`, `0.4`) except for one special case (`IA` for the AI lab). All 10 doors are present (no negatives), since the detection question checks real visibility.

### Questions and Prompts

Defined in `questions.json` under `experiment2.categories`.

**building_sign (1 question):**

| ID | Prompt | Metrics |
|----|--------|---------|
| `building_sign_combined` | "What building code and floor number are shown in this sign? Answer with the building code followed by the floor number, separated by a space (for example: EPS 0, G 1, EPS 2). If only the floor number is visible, answer with only the number (for example: -1, 0, 1, 2). If no information is visible, answer none." | building_accuracy, floor_accuracy, location_accuracy, bertscore_f1 |

A single combined prompt is used for both building code and floor number to reduce the number of inference calls and because the model can extract both in one response (e.g., "EPS 0").

**door_room (3 questions):**

| ID | Prompt | Applies to | Metrics |
|----|--------|-----------|---------|
| `doorroom_detection` | "Is there a room code or number visible on this door or next to it? Answer yes or no." | All images | exact_match |
| `doorroom_code` | "What is the room code shown on or next to this door? Answer with only the room code (for example: 1.2, 0.4, or IA)." | All images | room_code_accuracy |
| `doorroom_state` | "Is the door open or closed? Answer with one word: open or closed." | All images | exact_match |

### Metrics

**building_sign:**

| Metric | Definition | Applies to |
|--------|-----------|-----------|
| Building Accuracy | 1.0 if the predicted building code matches any value in `building_acceptable` (case-insensitive substring check). | Images where building is not null (complete type) |
| Floor Accuracy | 1.0 if the predicted floor number matches the expected floor string. | All building_sign images |
| Location Accuracy | 1.0 if both building and floor are correct simultaneously. | Complete type images only |
| BERTScore F1 | Semantic similarity between full prediction and `bertscore_reference` (e.g., "EPS 0"). Computed in batch after all inferences. | Complete type images only (bertscore_reference is not null) |
| Hallucination Rate | Fraction of non-complete images where the model invents a building code that was not visible. | sign_only and wall_number images |

Type-breakdown reporting:
- `complete_floor_accuracy`: floor accuracy on the 6 complete images
- `sign_only_floor_accuracy`: floor accuracy on the 3 sign_only images
- `wall_number_floor_accuracy`: floor accuracy on the 3 wall_number images

**door_room:**

| Metric | Definition |
|--------|-----------|
| Exact Match (doorroom_detection) | 1.0 if prediction matches "yes" or "no" |
| Room Code Accuracy | 1.0 if any string from `room_code_acceptable` appears as a substring in the prediction (case-insensitive). Flexible to handle variants like "room 1.2", "1.2 is the code", or models that omit the decimal separator ("14" for "1.4"). |
| Exact Match (doorroom_state) | 1.0 if prediction matches "open" or "closed" |

**Efficiency:** Same metrics as Experiment 1.

### Output Files (Experiment 2)

**Single-model notebook** (`experiment2_evaluation.ipynb`): flat `results/exp2/` with prefixed filenames.

**All-models notebook** (`experiment2_all_models.ipynb`): `results/exp2/{model_safe}/` with the same four artefact types plus `plots/` inside each model folder.

Per-model plots (same names in both pipelines):

```
plots/
├── {model_safe}_floor_confusion.png
├── {model_safe}_door_state_confusion.png
├── {model_safe}_type_breakdown.png      # floor accuracy by image type (complete / sign_only / wall_number)
├── {model_safe}_room_code_accuracy.png
└── {model_safe}_accuracy_by_category.png  # summary bar: building, floor, location, room code, detection EM, state EM
```

At `results/exp2/` root (all-models run): `all_models_summary.csv`, `comparison_plots/`, `exp2_reproducibility.json`.

**Per-model results CSV** — one row per image × question. Filename: `{model_safe}_exp2_results.csv` (single-model) or `{model_safe}/{model_safe}_exp2_results.csv` (all-models subfolder).

| Column | Description |
|--------|-------------|
| model_id | HuggingFace model ID |
| category | building_sign or door_room |
| image | image filename |
| image_type | complete / sign_only / wall_number / door_room |
| question_id | e.g., building_sign_combined |
| question | prompt text |
| prediction | model output |
| expected_building | expected building code or empty |
| expected_floor | expected floor number or empty |
| expected_value | canonical expected answer string |
| inference_time_ms | ms |
| output_length_words | words in prediction |
| building_accuracy | 1.0 / 0.0 (building_sign rows) |
| floor_accuracy | 1.0 / 0.0 (building_sign rows) |
| location_accuracy | 1.0 / 0.0 (complete images only) |
| hallucination | True/False (sign_only and wall_number images) |
| room_code_accuracy | 1.0 / 0.0 (door_room rows) |
| exact_match | 1.0 / 0.0 (closed questions) |
| bertscore_f1 / bertscore_p / bertscore_r | BERTScore (complete images only) |
| bertscore_reference | e.g., "EPS 0" |

**`*_exp2_aggregate.csv`** — one row per category:

Columns include: building_accuracy, building_n, floor_accuracy, floor_n, location_accuracy, location_n, bertscore_f1/p/r, complete_floor_accuracy, complete_building_accuracy, complete_location_accuracy, sign_only_floor_accuracy, wall_number_floor_accuracy, hallucination_rate, avg_output_length, doorroom_detection_accuracy, doorroom_state_accuracy, room_code_accuracy.

**`*_exp2_efficiency.json`** — same structure as exp1 efficiency file.

**`*_exp2_matrices.json`** — confusion matrices:

- `floor_confusion`: 6x6 matrix for floor number prediction. Labels: -2, -1, 0, 1, 2, other ("other" = extracted value not in valid floor set). Rows = expected, columns = predicted. Includes accuracy, correct, total.
- `door_state`: 2x2 matrix for door state classification on door_room images. Rows = expected (open/closed), columns = predicted. Includes accuracy, correct, total, unknown count.
- `type_breakdown`: per-type floor accuracy (complete, sign_only, wall_number).
- `hallucination`: hallucination rate, count, and total for non-complete images.

**Plots:**

| File | Content |
|------|---------|
| `*_accuracy_by_category.png` | Bar chart of main metrics (building_sign + door_room aggregates) |
| `*_floor_confusion.png` | 6×6 heatmap for floor (expected vs predicted, including `other`) |
| `*_door_state_confusion.png` | 2×2 heatmap for open/closed on `doorroom_state` |
| `*_type_breakdown.png` | Bar chart: **floor** accuracy by `complete` / `sign_only` / `wall_number` |
| `*_room_code_accuracy.png` | Bar chart of room-code accuracy per door image |

### Notebooks (Experiment 2)

**`notebooks/Experiment 2/experiment2_evaluation.ipynb`** — single model evaluation:

Cells cover: imports, configuration, model loading, dataset loading from `exp2_expected_answers.json`, inference loop per image and question, BERTScore computation (complete images only), metric computation with type-based breakdowns, confusion matrix construction, plot generation, and file saving.

Response parsing for `building_sign_combined`: the prediction is split on spaces and digits are searched to extract the floor number, while the building code is checked against the `building_acceptable` list. The parsing is tolerant to formats like "EPS 0", "EPS floor 0", and "0" (floor-only responses).

Hallucination check: for sign_only and wall_number images, a hallucination is flagged if the predicted string contains any building code string not in a safe set.

**`notebooks/Experiment 2/experiment2_all_models.ipynb`** — sequential evaluation of all 12 models:

Wraps the single-model logic into `run_experiment2_for_model(model_meta)` which: loads the model, runs all inferences, computes all metrics, saves all output files and plots, frees GPU memory, and returns a summary dictionary with approximately 30 fields covering all accuracy metrics, type breakdowns, efficiency, and matrix accuracies.

After all models, generates:
- `all_models_summary.csv` — one row per model with all aggregated metrics
- `comparison_plots/` — cross-model bar charts (accuracies, VRAM, inference time, floor-by-type grouped, etc.)
- `exp2_reproducibility.json` — environment and run metadata for reproducibility

---

## Cross-Experiment Notes

### Safety Metrics (Experiment 1, obstacle category)

Two distinct safety metrics are reported for the obstacle category. They measure different failure modes:

- `hazard_miss_rate` (`obstacle_detection`): `1 - recall`. Measures how often a real obstacle is not detected at all. Formula: `FN / (TP + FN)`.
- `safety_hazard_miss_rate` (`obstacle_safety`): `FP / (FP + TN)`. Among scenes that are NOT safe to treat as clear, measures how often the model incorrectly says "clear". The positive class here is "clear" (yes = no obstacle); a false positive means the model says "clear" when the path is blocked.

Both metrics are lower-is-better and critical for user safety. They are not interchangeable.

### BERTScore Usage

BERTScore is applied only where the reference is meaningful:
- Experiment 1: element questions only (staircase_element, elevator_element, door_element, doorsign_element, obstacle_object). Reference is the canonical element name.
- Experiment 2: building_sign images of type "complete" only. Reference is the full combined string (e.g., "EPS 0", "G 1"). Not applied to sign_only or wall_number images (no bertscore_reference). Not applied to door_room (room codes are too short; room_code_accuracy is sufficient).

### Token-Based Extraction

Generated tokens are decoded **without** re-encoding the prompt (slice after `input_len`):

```python
input_len = inputs["input_ids"].shape[-1]
response = processor.decode(output[0][input_len:], skip_special_tokens=True).strip()
```

Case folding for scoring is applied in metric helpers (e.g. `normalize()` → `.lower()`) rather than on the raw decode, so the saved `prediction` text matches model casing. This keeps the prompt out of the measured answer.

### Constrained Prompting

All closed questions use explicit format constraints:
- Yes/no questions end with "Answer yes or no."
- State questions end with "Answer with one word: open or closed." or "Answer with one word: up or down."
- Element questions end with "Answer with one word."
- Extraction questions provide format examples inline.

Constraints are designed to minimize formatting ambiguity. Exact match evaluation uses semantic normalization (first-token check, common variant mapping) rather than strict string equality.
