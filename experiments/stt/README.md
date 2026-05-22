# STT experiments

These experiments select and validate the speech-to-text model that runs on the
phone. Test utterances and references are in `data/stt/`. The metric that matters
most is Domain Keyword Accuracy (DKA): the fraction of utterances whose campus
keywords (building codes, room numbers, place names) are all transcribed correctly,
since those are what the planner depends on.

## Phase 1: server benchmark

`phase1_server_benchmark/`. Eight speech models are ranked on a Colab GPU over 30
campus utterances (six categories of five). The eight are six Whisper sizes (tiny,
base, small, medium, large-v3-turbo, large-v3) and two other architectures
(`wav2vec2-base-960h`, `s2t-small-librispeech-asr`). Each Whisper model is run both
without and with a domain prompt; the two non-Whisper models take no prompt.

With the domain prompt, all six Whisper sizes reach 100% DKA, while the two
non-Whisper models stay near 55%. Since the smallest Whisper, tiny, already reaches
100% DKA, it is the one taken forward to the on-device phase.

## Phase 2: on-device

`phase2_ondevice/`. Whisper is run on the target phone (Pixel 10 Pro) with
whisper.cpp, across seven quantised variants of tiny and base. `bench.py` performs
the runs on the phone, and the notebook analyses the resulting CSV with the same
metrics as phase 1. `tiny-q5_0` is the smallest variant that keeps 100% DKA, at
about 3 seconds per utterance.

## Phase 3: Flutter integration

`phase3_flutter_integration/`. The chosen model is run inside the Flutter app
through the bundled `libwhisper-server.so` and compared against the phase-2
command-line run of `tiny-q5_0`. The transcriptions match and the latency is
comparable, confirming the integration does not change the result.

## Outcome

Whisper `tiny-q5_0`, running on the phone.
