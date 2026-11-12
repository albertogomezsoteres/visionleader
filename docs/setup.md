# Setup

How to install and run the system. The backend, the vision model, the planner and
the mobile app each run in their own place.

## Prerequisites

- Python 3.10 or newer
- Flutter SDK (the app targets Android)
- Docker, with the `fast-downward:latest` image
- A Colab GPU runtime for the vision model

## 1. Backend

With [uv](https://docs.astral.sh/uv/) (installs the exact versions in `uv.lock`):

```bash
make install                    # uv sync --frozen --extra dev + pre-commit hooks
cp .env.example .env            # then fill in the values
make serve                      # API on http://localhost:8000, docs at /docs
```

Or with plain pip: `pip install -e ".[dev]"`, then `python scripts/start_api.py`.

`.env` holds:

| Variable | Purpose |
|-|-|
| `COLAB_API_URL` | URL of the Colab vision server (no trailing slash). |
| `GOOGLE_MAPS_API_KEY` | Google Maps Directions key, for the outdoor walk between buildings. |
| `TELEMETRY_JSONL_PATH` | Optional. Telemetry log path used by the end-to-end validation. |

## 2. Vision model (Colab)

Open `deploy/colab_inference_server.ipynb` in Colab on a GPU runtime, add the Colab
secrets `HF_TOKEN` (the Gemma model is gated) and `NGROK_TOKEN`, run the cells, and
copy the printed tunnel URL into `.env` as `COLAB_API_URL`.

## 3. Planner (Docker)

Build the Fast Downward image once:

```bash
make planner-image   # docker build -t fast-downward:latest docker/fast-downward
```

The backend calls it on every routing request. Without it, routes that change floor
or building cannot be computed.

## 4. Mobile app

```bash
cd mobile_app
flutter pub get
flutter run
```

Point the app at the backend with `--dart-define=API_BASE_URL=http://<host>:8000`,
or edit `mobile_app/lib/core/app_config.dart`. On the Android emulator use
`http://10.0.2.2:8000`.

## 5. Tests

```bash
make test           # unit, dialogue, API and data tests (no Docker or GPU needed)
make test-planner   # re-solves the planner benchmark with the Docker image
make lint           # ruff lint and format check
```
