# VLM Smoke Test — Gemma 3n E2B INT4

Minimal Flutter app to validate on-device multimodal inference of **Gemma 3n E2B INT4** on a Pixel 10 Pro.

## What it does

1. Downloads the official `gemma-3n-E2B-it-int4.task` file from HuggingFace (~3.14 GB, one-time).
2. Loads the model into memory using `flutter_gemma` (LiteRT backend).
3. Lets the user pick a photo from the gallery and one of five canonical prompts:
   - Stage 1 — classifier (element type)
   - Stage 2 — directory sign (building + floor)
   - Stage 2 — classroom door (room code)
   - Stage 2 — elevator (state)
   - Stage 2 — staircase (direction)
4. Runs the inference, shows the **raw response** and wall-clock latency.
5. Exports the run history as CSV.

The prompts replicate the two-stage pipeline defined in `src/api/services/vision_analyzer.py` of the main project, adapted for Gemma 3n (no PaliGemma task prefixes).

## Prerequisites

- Flutter SDK installed (`flutter --version` should work).
- Pixel 10 Pro with USB debugging enabled.
- HuggingFace account with the Gemma license accepted at
  <https://huggingface.co/google/gemma-3n-E2B-it-litert-preview>.
- HuggingFace read token placed in `lib/secrets.dart` (this file is gitignored).

## First-time setup

```
cd vlm_smoke_test
flutter pub get
```

Plug in the Pixel and confirm it is detected:

```
flutter devices
```

## Run on device

```
flutter run -d <pixel_device_id>
```

The first launch will:

1. Show "Model not downloaded yet." — tap **Download model**. Requires WiFi; the ~3 GB download takes 10–15 min.
2. When it finishes, tap **Load model**. This takes 15–30 s on the Pixel 10 Pro.
3. Tap **Pick image from gallery**, choose a campus photo.
4. Select one of the 5 prompts from the dropdown.
5. Tap **Run inference**. The response and latency appear in the history below.

Tap **Export CSV** to save the history under the app's documents directory.

## Notes

- The `.task` file is cached on the device, so subsequent launches skip the download.
- Decoding is deterministic (temperature 0, `topK=1`, fixed seed), so repeated
  runs with the same image + prompt give identical output.
- Backend is set to CPU. Reported Samsung S25 Ultra latency for Gemma 3n E2B is
  ~6.7 s time-to-first-token on CPU; Pixel 10 Pro numbers may differ and are
  what this test is measuring.
