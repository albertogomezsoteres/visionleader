# VisionLeader UFV mobile app

Flutter client for VisionLeader UFV (Android). It lets a visually impaired user ask
where to go by voice, take photos of the surroundings when the assistant needs them,
and hear step-by-step navigation spoken back through text-to-speech.

Speech-to-text runs on the device: the app bundles Whisper (tiny, q5_0) through
whisper.cpp, so transcription does not need the network.

The Whisper binary and model are not committed to the repository (binary, and the
model is large). To build a working app, place `libwhisper-server.so` under
`android/app/src/main/jniLibs/arm64-v8a/` and `ggml-tiny-q5_0.bin` under
`assets/models/`.

## Requirements

- Flutter SDK
- The backend running (see the README at the repository root)
- An Android device or emulator (iOS is not supported: the on-device Whisper binary ships for Android arm64 only)

## Run

```bash
flutter pub get
flutter run
```

## Backend URL

The API base URL is set in `lib/core/app_config.dart`. You can override it at build
time without touching the code:

```bash
flutter run --dart-define=API_BASE_URL=http://192.168.1.50:8000
```

On the Android emulator, use `http://10.0.2.2:8000` to reach the host.

### Shortcut: auto-detect the host IP (Windows)

So you do not have to look up the IP by hand every time the network changes, a
PowerShell script detects it and launches the app:

```powershell
cd mobile_app
.\run_dev.ps1
```

It uses port 8000 by default. For another port: `.\run_dev.ps1 -Port 8001`.

## Layout

- `lib/main.dart`: app entry point.
- `lib/screens/home_screen.dart`: start screen.
- `lib/screens/conversation/`: the conversation flow (voice, photo, TTS, steps).
- `lib/services/whisper_service.dart`: on-device speech-to-text (Whisper via whisper.cpp).
- `lib/services/api_service.dart`: HTTP client for the backend.
- `lib/core/app_config.dart`: base URL and timeouts.
- `lib/core/app_theme.dart`: dark theme.
