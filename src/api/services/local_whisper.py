"""Local Whisper STT using faster-whisper for reliable on-device transcription."""

import os
import re
import tempfile
from typing import Optional, Tuple

from faster_whisper import WhisperModel

_DOMAIN_PROMPT = (
    "UFV campus navigation. "
    "Keywords: classroom 0.1, classroom 0.3, classroom 1.1, classroom 1.4, classroom 2.1, "
    "building G, building CD, building H, main entrance, ground floor, first floor, second floor, "
    "elevator, stairs, cafeteria, gym, restroom, AI laboratory, mentoring room, EPS faculty offices, "
    "yes, no, start, done, repeat, cancel, I am lost, I am in a hurry, "
    "I want to go to, navigate to, take me to."
)

_model: Optional[WhisperModel] = None


def _get_model() -> WhisperModel:
    """Lazy-load the Whisper model (singleton)."""
    global _model
    if _model is None:
        model_size = os.getenv("WHISPER_MODEL", "small")
        device = os.getenv("WHISPER_DEVICE", "cpu")
        compute_type = "int8" if device == "cpu" else "float16"
        print(f"[LOCAL-WHISPER] Loading model '{model_size}' on {device} ({compute_type})...")
        _model = WhisperModel(model_size, device=device, compute_type=compute_type)
        print("[LOCAL-WHISPER] Model loaded successfully.")
    return _model


def _is_hallucination(text: str) -> bool:
    """Detect Whisper hallucination patterns (repetitive / nonsensical output)."""
    if not text:
        return False
    words = text.lower().split()
    if len(words) < 4:
        return False
    # Repeated short phrases: split into 3-word windows and check uniqueness
    if len(words) >= 10:
        trigrams = [" ".join(words[i:i+3]) for i in range(len(words) - 2)]
        unique_ratio = len(set(trigrams)) / len(trigrams)
        if unique_ratio < 0.25:
            print(f"[LOCAL-WHISPER][HALLUCINATION] Rejected: unique trigram ratio {unique_ratio:.2f}")
            return True
    # Repeated single word dominance
    from collections import Counter
    counts = Counter(words)
    most_common_word, most_common_count = counts.most_common(1)[0]
    if most_common_count > len(words) * 0.6 and len(words) > 6:
        print(f"[LOCAL-WHISPER][HALLUCINATION] Rejected: '{most_common_word}' appears {most_common_count}/{len(words)} times")
        return True
    # Excessively long output for short audio (campus commands are <30 words)
    if len(words) > 60:
        print(f"[LOCAL-WHISPER][HALLUCINATION] Rejected: {len(words)} words (too long for a navigation command)")
        return True
    return False


def transcribe_audio_local(audio_data: bytes) -> Tuple[bool, str, Optional[str]]:
    """
    Transcribe raw audio bytes using local Whisper.

    Returns (success, text, error).
    """
    if len(audio_data) < 1000:
        return False, "", f"Audio too small ({len(audio_data)} bytes)."

    model = _get_model()

    tmp = None
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.write(audio_data)
        tmp.close()

        passes = [
            {
                "name": "pass1_balanced",
                "beam_size": 5,
                "best_of": 5,
                "vad_filter": True,
                "vad_parameters": {
                    "min_silence_duration_ms": 500,
                    "speech_pad_ms": 350,
                    "threshold": 0.28,
                },
            },
            {
                "name": "pass2_relaxed_vad",
                "beam_size": 3,
                "best_of": 3,
                "vad_filter": True,
                "vad_parameters": {
                    "min_silence_duration_ms": 700,
                    "speech_pad_ms": 500,
                    "threshold": 0.20,
                },
            },
            {
                "name": "pass3_no_vad",
                "beam_size": 2,
                "best_of": 2,
                "vad_filter": False,
                "vad_parameters": None,
            },
        ]

        best_text = ""
        best_meta = None

        for p in passes:
            kwargs = dict(
                language="en",
                task="transcribe",
                beam_size=p["beam_size"],
                best_of=p["best_of"],
                temperature=0.0,
                initial_prompt=_DOMAIN_PROMPT,
                vad_filter=p["vad_filter"],
            )
            if p["vad_parameters"] is not None:
                kwargs["vad_parameters"] = p["vad_parameters"]

            segments, info = model.transcribe(tmp.name, **kwargs)
            text_parts = [seg.text.strip() for seg in segments if seg.text.strip()]
            full_text = " ".join(text_parts).strip()
            print(
                f"[LOCAL-WHISPER][{p['name']}] {full_text!r} "
                f"(lang={info.language} prob={info.language_probability:.2f})"
            )

            if _is_hallucination(full_text):
                continue

            if full_text and len(full_text) > len(best_text):
                best_text = full_text
                best_meta = info

            if len(full_text) >= 8:
                return True, full_text, None

        if best_text and not _is_hallucination(best_text):
            print(
                f"[LOCAL-WHISPER][BEST] {best_text!r} "
                f"(lang={best_meta.language if best_meta else 'n/a'})"
            )
            return True, best_text, None

        return False, "", "No speech detected in audio after 3 local passes."

    except Exception as e:
        return False, "", f"Local Whisper error: {e}"
    finally:
        if tmp and os.path.exists(tmp.name):
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
