"""Speech-to-text endpoint: receive audio, return transcribed text via Colab Whisper."""

import time
import requests
from collections import Counter

from fastapi import APIRouter, UploadFile, File

from api.schemas import TranscribeResponse
from api.dependencies import COLAB_API_URL

router = APIRouter()


def _isHallucination(text: str) -> bool:
    """
    Detects Whisper hallucination patterns: repetitive or nonsensical output.

    Whisper occasionally generates looping text or excessively long responses
    for short audio clips. These are rejected before returning to the app.
    """
    if not text:
        return False

    words = text.lower().split()
    if len(words) < 4:
        return False

    # Repeated trigrams: genuine speech has varied word sequences
    if len(words) >= 10:
        trigrams = [" ".join(words[i:i + 3]) for i in range(len(words) - 2)]
        uniqueRatio = len(set(trigrams)) / len(trigrams)
        if uniqueRatio < 0.25:
            print(f"[TRANSCRIBE][HALLUCINATION] Rejected: unique trigram ratio {uniqueRatio:.2f}")
            return True

    # Single word dominates: likely a stuck loop
    counts = Counter(words)
    topWord, topCount = counts.most_common(1)[0]
    if topCount > len(words) * 0.6 and len(words) > 6:
        print(f"[TRANSCRIBE][HALLUCINATION] Rejected: '{topWord}' appears {topCount}/{len(words)} times")
        return True

    # Campus navigation commands are short: reject unusually long outputs
    if len(words) > 60:
        print(f"[TRANSCRIBE][HALLUCINATION] Rejected: {len(words)} words (too long for a navigation command)")
        return True

    return False


@router.post("/transcribe-audio", response_model=TranscribeResponse)
async def transcribe_audio(file: UploadFile = File(...)):
    """Transcribe audio via Colab Whisper and return the transcribed text."""
    try:
        audioData = await file.read()
        audioSize = len(audioData)
        print(f"\n[TRANSCRIBE] filename={file.filename} size={audioSize} bytes")

        if audioSize < 1000:
            return TranscribeResponse(
                success=False, text="",
                error=f"Audio file too small ({audioSize} bytes). Microphone may not be capturing.",
            )

        if not COLAB_API_URL:
            raise RuntimeError("COLAB_API_URL not configured in .env")

        started = time.time()
        transcribed = _transcribeColab(audioData, file)
        elapsed = time.time() - started
        print(f"[TRANSCRIBE] colab roundtrip in {elapsed:.2f}s")

        if transcribed is None:
            return TranscribeResponse(
                success=False, text="",
                error="Transcription returned no result. Try speaking louder or closer to the mic.",
            )

        if _isHallucination(transcribed):
            print(f"[TRANSCRIBE][HALLUCINATION-REJECTED] {transcribed!r}")
            return TranscribeResponse(
                success=False, text="",
                error="Could not understand clearly. Please try again.",
            )

        print(f"[TRANSCRIBE][FINAL] {transcribed!r}")

        if not transcribed.strip():
            return TranscribeResponse(
                success=False, text="",
                error="No speech detected. Please speak clearly and try again.",
            )

        return TranscribeResponse(success=True, text=transcribed, error=None)

    except Exception as e:
        print(f"[TRANSCRIBE][ERROR] {e}")
        return TranscribeResponse(success=False, text="", error=f"Error transcribing audio: {e}")


def _transcribeColab(audioData: bytes, file: UploadFile) -> str | None:
    """Forward audio to the Colab Whisper endpoint and return the transcribed text."""
    filename = file.filename or "audio.wav"
    mime = (
        "audio/wav" if filename.lower().endswith(".wav")
        else (file.content_type or "application/octet-stream")
    )

    resp = requests.post(
        f"{COLAB_API_URL}/transcribe",
        files={"file": (filename, audioData, mime)},
        timeout=30,
    )

    if resp.status_code != 200:
        raise RuntimeError(f"Colab returned status {resp.status_code}")

    data = resp.json()
    transcribed = data.get("text", "")

    if "error" in data and not transcribed:
        raise RuntimeError(data["error"])

    print(f"[TRANSCRIBE][COLAB-RAW] {transcribed!r}")

    # Retry once for large audio files that return empty on the first attempt
    if not transcribed.strip() and len(audioData) > 120_000:
        print("[TRANSCRIBE][COLAB] Empty result, retrying...")
        retry = requests.post(
            f"{COLAB_API_URL}/transcribe",
            files={"file": ("audio.wav", audioData, "audio/wav")},
            timeout=30,
        )
        if retry.status_code == 200:
            transcribed = retry.json().get("text", "")
            print(f"[TRANSCRIBE][COLAB-RETRY] {transcribed!r}")

    return transcribed.strip() or None
