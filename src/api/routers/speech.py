"""Speech-to-text endpoint: receive audio, return transcribed text.

By default uses Colab/Groq Whisper (STT_MODE=colab).
Set STT_MODE=local in .env to use faster-whisper on your PC instead.
"""

import os
import requests

from fastapi import APIRouter, UploadFile, File

from api.models import TranscribeResponse
from api.dependencies import load_campus_graph, COLAB_API_URL
from api.services.transcription import correct_whisper_transcription
from api.services.local_whisper import transcribe_audio_local, _is_hallucination

router = APIRouter()

STT_MODE = os.getenv("STT_MODE", "colab").lower()


@router.post("/transcribe-audio", response_model=TranscribeResponse)
async def transcribe_audio(file: UploadFile = File(...)):
    """Transcribe audio via Colab/Groq or local Whisper, then apply campus corrections."""
    try:
        audio_data = await file.read()
        audio_size = len(audio_data)
        print(f"\n[TRANSCRIBE] filename={file.filename} size={audio_size} bytes  mode={STT_MODE}")

        if audio_size < 1000:
            return TranscribeResponse(
                success=False, text="",
                error=f"Audio file too small ({audio_size} bytes). Microphone may not be capturing.",
            )

        if STT_MODE == "local":
            transcribed, local_err = _transcribe_local(audio_data)
        else:
            local_err = None
            transcribed = _transcribe_colab(audio_data, file)

        if transcribed is None:
            return TranscribeResponse(
                success=False, text="",
                error=(
                    f"Transcription returned no result. {local_err}"
                    if local_err else
                    "Transcription returned no result. Try speaking louder or closer to the mic."
                ),
            )

        if _is_hallucination(transcribed):
            print(f"[TRANSCRIBE][HALLUCINATION-REJECTED] {transcribed!r}")
            return TranscribeResponse(
                success=False, text="",
                error="Could not understand clearly. Please try again.",
            )

        campus_graph = load_campus_graph()
        corrected = correct_whisper_transcription(transcribed, campus_graph)
        print(f"[TRANSCRIBE][FINAL] {corrected!r}")

        if not corrected.strip():
            return TranscribeResponse(
                success=False, text="",
                error="No speech detected. Please speak clearly and try again.",
            )

        return TranscribeResponse(success=True, text=corrected, error=None)

    except Exception as e:
        print(f"[TRANSCRIBE][ERROR] {e}")
        return TranscribeResponse(success=False, text="", error=f"Error transcribing audio: {e}")


def _transcribe_local(audio_data: bytes) -> tuple[str | None, str | None]:
    """Run faster-whisper on this machine."""
    success, text, error = transcribe_audio_local(audio_data)
    if not success:
        print(f"[TRANSCRIBE][LOCAL-ERR] {error}")
        return None, error
    return text, None


def _transcribe_colab(audio_data: bytes, file: UploadFile) -> str | None:
    """Forward audio to the Colab Groq/Whisper endpoint."""
    if not COLAB_API_URL:
        raise RuntimeError("COLAB_API_URL not configured in .env")

    send_filename = file.filename or "audio.wav"
    mime = (
        "audio/wav" if send_filename.lower().endswith(".wav")
        else (file.content_type or "application/octet-stream")
    )
    resp = requests.post(
        f"{COLAB_API_URL}/transcribe",
        files={"file": (send_filename, audio_data, mime)},
        timeout=30,
    )

    if resp.status_code != 200:
        raise RuntimeError(f"Colab returned status {resp.status_code}")

    data = resp.json()

    transcribed = data.get("text", "")
    if "error" in data and not transcribed:
        raise RuntimeError(data["error"])

    print(f"[TRANSCRIBE][COLAB-RAW] {transcribed!r}")

    if not transcribed.strip() and len(audio_data) > 120_000:
        print("[TRANSCRIBE][COLAB] Empty result, retrying...")
        retry = requests.post(
            f"{COLAB_API_URL}/transcribe",
            files={"file": ("audio.wav", audio_data, "audio/wav")},
            timeout=30,
        )
        if retry.status_code == 200:
            rd = retry.json()
            transcribed = rd.get("text", "")
            print(f"[TRANSCRIBE][COLAB-RETRY] {transcribed!r}")

    return transcribed.strip() or None
