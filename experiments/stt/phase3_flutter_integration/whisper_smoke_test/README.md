# whisper_smoke_test

Standalone Flutter harness used in STT phase 3 to check that Whisper (`tiny-q5_0`),
running inside the Flutter runtime through the bundled `libwhisper-server.so`,
produces the same transcriptions as the command-line tool. The analysis and results
live in `experiments/stt/phase3_flutter_integration/`.
