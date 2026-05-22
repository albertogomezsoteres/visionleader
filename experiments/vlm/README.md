# VLM experiments

These experiments select the vision language model that reads campus photos. Both
phases run server-side on a Colab A100 GPU with greedy, fixed-seed decoding, so the
runs are reproducible. Test images and ground truth are in `data/vlm/`.

The selection has two stages: phase 1 evaluates seven models on a recognition task,
and phase 2 takes the two best forward to the harder extraction task.

## Phase 1: element and state recognition

`phase1_state_recognition/`. Three questions are scored per model: identify the
element in the photo (34 images across stairs, elevators and restroom signs), read
the stair direction (15 images, up or down) and read the elevator state (10 images,
open or closed). The metrics are accuracy and macro F1 per question, plus a combined
state-recognition macro F1.

Seven models are compared: five PaliGemma 2 variants (3B-pt, 3B-mix, 10B-pt,
10B-mix, 10B-ft-docci) and two Gemma 4 variants (E2B-it, E4B-it). PaliGemma2-3b-mix
and Gemma 4 E4B-it tie at the top (0.96 overall accuracy, 0.93 state macro F1), so
both advance to phase 2.

## Phase 2: location extraction

`phase2_location_extraction/`. Run only on the two phase-1 finalists. Two questions:
read the floor from a directory sign (20 images, four balanced floor classes) and
read the room code from a classroom plate (26 images). The metrics are floor,
building and location accuracy, room-code accuracy and BERTScore.

Gemma 4 E4B-it scores 1.00 on every metric; PaliGemma2-3b-mix reaches 0.74 overall.
Gemma 4 E4B-it is therefore the model used in the app.

The prompts shared by both phases are in `evaluation_prompts.json`.
