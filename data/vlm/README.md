# VLM dataset (UFV campus images)

A custom vision test set built for this project: 80 campus photos across five
categories, used to evaluate the vision language models. Every image is labelled
with its ground truth.

## Images

The image files are not committed to the repository. They are kept locally under
`images/` (organised by category) and documented here by manifest and SHA-256 hash,
so a held copy can be verified byte for byte. Each image resolves to
`images/<category>/<filename>`.

## Experiments that use this set

- State recognition (`experiments/vlm/phase1_state_recognition/`): the element type, the stair direction (up or down) and the elevator state (open or closed). Seven models are compared on this set.
- Location extraction (`experiments/vlm/phase2_location_extraction/`): directory signs and room plates. Only the two best models from the first phase are compared here.

The room plate and directory sign images are reused by the symbolic grounding study
(`data/symbolic_grounding/vlm/`). The restroom signs are used in phase 1, where the
model identifies the element as a restroom.

## Files

- `manifest.csv`: one row per image (columns below).
- `dataset_hashes.json`: SHA-256 of every image.
- `ground_truth.json`: the structured ground truth (building, floor, room code or state per image) used by the notebooks for the per-field metrics.

## manifest.csv columns

| Column | Meaning |
|-|-|
| `image_id` | Stable identifier (the file name without extension). |
| `filename` | Image file name, found at `images/<category>/<filename>`. |
| `category` | One of `room_plates`, `directory_signs`, `elevators`, `stairs`, `facility_signs`. |
| `ground_truth` | The expected answer for the image (see below). |

`ground_truth` by category:

- `stairs`: `up` or `down`.
- `elevators`: `open` or `closed`.
- `facility_signs`: `male` or `female`.
- `directory_signs`: building and floor, for example `G Agora`.
- `room_plates`: building and room code, for example `CD 1` or `G 0.1`.

## Composition

80 images: room_plates 26, directory_signs 20, stairs 15, elevators 10,
facility_signs 9.
