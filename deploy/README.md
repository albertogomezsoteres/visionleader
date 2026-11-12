# Deploy: Colab inference server

`colab_inference_server.ipynb` serves the vision-language model (Gemma 4 E4B-it) as
an HTTP endpoint over an ngrok tunnel, so the backend can send it a campus photo and
get a reading back. The model needs a GPU, so it runs on Colab; speech-to-text runs
on the phone and planning runs in Docker, so this is the only model served remotely.

## Endpoint

`POST /analyze` with an image and a prompt. The notebook runs the model with
deterministic decoding (greedy, seed 0) and a fixed system prompt, the same setup
used to evaluate it. The prompts come from `config/prompts.json`; the backend
(`src/visionleader/api/services/image_analysis.py`) builds them and sends them here.

## Run it

1. Open the notebook in Colab and select a GPU runtime.
2. Add two secrets in Colab (the key icon): `HF_TOKEN` (the Gemma model is gated) and `NGROK_TOKEN`.
3. Run the cells top to bottom. The first cell restarts the runtime so the pinned Pillow loads cleanly; continue from there.
4. Copy the printed tunnel URL into the backend `.env` as `COLAB_API_URL`.

The server then waits for requests. The first call takes a couple of minutes while
the model loads.
