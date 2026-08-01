"""F-007/9 speech-to-text: pretrained multilingual Whisper (openai/whisper-small),
NOT trained or fine-tuned here -- per the plan, training a Conformer ASR
model from scratch is out of reach for this project; this integrates an
existing, already-strong multilingual ASR model instead.

Deliberately avoids librosa/soundfile for audio loading -- both pull in
numba, which cannot import on this machine (see scoring_service/requirements.txt
for the same numba/llvmlite Application Control block that ruled out the
`shap` package). Uses Python's stdlib `wave` module instead, which only
handles simple PCM WAV files -- good enough for a 16kHz/16-bit mono voice
note, not a general audio-decoding solution. A real deployment ingesting
arbitrary WhatsApp voice-note codecs (usually Opus/OGG) would need an
actual decoder (e.g. ffmpeg) upstream of this.

HONEST LIMITATION: no real Hindi/Tamil audio sample was available to test
transcription QUALITY in this session (unlike intent_classifier.py, whose
Hindi/Tamil text-matching accuracy was empirically verified). What's
verified here is that the pipeline loads and runs end-to-end without
crashing (see the module's __main__ smoke test) -- not transcription
accuracy on real speech. Test with a real Hindi/Tamil voice sample before
trusting this in a demo.

Run (smoke test only, see caveat above): python -m scoring_service.voice.asr
"""

from __future__ import annotations

import sys
import wave
from pathlib import Path
from typing import Literal

import numpy as np
from transformers import pipeline

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")  # Windows console defaults to cp1252, breaks on Hindi/Tamil text

WHISPER_MODEL_NAME = "openai/whisper-small"
WhisperLanguage = Literal["hindi", "tamil", "english"]

_asr_pipeline = None


def _get_pipeline():
    global _asr_pipeline
    if _asr_pipeline is None:
        _asr_pipeline = pipeline("automatic-speech-recognition", model=WHISPER_MODEL_NAME)
    return _asr_pipeline


def load_wav_as_array(path: str | Path) -> tuple[np.ndarray, int]:
    """Reads a 16-bit PCM mono/stereo WAV file into a float32 [-1, 1] array.
    Raises wave.Error on anything else (compressed WAV, non-PCM) -- that's
    intentional, not a bug to silently paper over.
    """
    with wave.open(str(path), "rb") as wf:
        sample_rate = wf.getframerate()
        n_channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        raw = wf.readframes(wf.getnframes())

    if sample_width != 2:
        raise ValueError(f"Only 16-bit PCM WAV supported, got sample_width={sample_width} bytes")

    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if n_channels > 1:
        audio = audio.reshape(-1, n_channels).mean(axis=1)  # downmix to mono
    return audio, sample_rate


def transcribe(audio_path: str | Path, language: WhisperLanguage | None = None) -> dict:
    audio_array, sample_rate = load_wav_as_array(audio_path)
    asr = _get_pipeline()
    generate_kwargs = {"language": language} if language else {}
    result = asr({"array": audio_array, "sampling_rate": sample_rate}, generate_kwargs=generate_kwargs)
    return {"text": result["text"].strip(), "language_hint": language, "model": WHISPER_MODEL_NAME}


if __name__ == "__main__":
    # Mechanical smoke test only -- confirms the pipeline loads and runs on a
    # WAV file end to end. A short synthesized silent/tone clip, NOT real
    # speech, so this cannot and does not validate transcription quality.
    import tempfile

    sr = 16000
    duration_s = 1.0
    silence = np.zeros(int(sr * duration_s), dtype=np.float32)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        with wave.open(tmp.name, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes((silence * 32767).astype(np.int16).tobytes())
        result = transcribe(tmp.name, language="hindi")

    print("Smoke test (silent clip, NOT a real speech/quality test):")
    print(result)
