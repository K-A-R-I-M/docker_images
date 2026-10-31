"""Speech utilities and the whisper/Piper clients."""
from __future__ import annotations

import array
import io
import json
import math
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import wave
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core import Core

def pcm_to_wav(pcm: bytes, rate: int = 16000, channels: int = 1, width: int = 2) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(width)
        wav.setframerate(rate)
        wav.writeframes(pcm)
    return buf.getvalue()


def rms_s16(data: bytes) -> float:
    if len(data) < 2:
        return 0.0
    samples = array.array("h")
    samples.frombytes(data[: len(data) - (len(data) % 2)])
    if not samples:
        return 0.0
    return math.sqrt(sum(x * x for x in samples) / len(samples))


def detect_lang(text: str, forced: str = "auto") -> str:
    forced = (forced or "auto").lower()
    if forced in ("en", "fr"):
        return forced
    low = text.lower()
    if re.search(r"[àâçéèêëîïôûùüÿœ]", low):
        return "fr"
    words = re.findall(r"[a-zàâçéèêëîïôûùüÿœ']+", low)
    if not words:
        return "en"
    fr = sum(1 for w in words if w in FR_WORDS)
    en = sum(1 for w in words if w in EN_WORDS)
    return "fr" if fr > en else "en"


_SENT_RE = re.compile(r"[^.!?…]+[.!?…]*")


def split_sentences(text: str) -> list[str]:
    parts = []
    for match in _SENT_RE.finditer(text or ""):
        sentence = match.group(0).strip()
        if sentence:
            parts.append(sentence)
    return parts


class SpeechFence:
    """Drop fenced blocks (such as mermaid diagrams) from spoken sentences."""

    def __init__(self) -> None:
        self.inside = False

    def feed(self, text: str) -> list[str]:
        out: list[str] = []
        for index, part in enumerate((text or "").split("```")):
            if index:
                self.inside = not self.inside
            if not self.inside and part.strip():
                out.append(part.strip())
        return out


class SentenceBuffer:
    """Split streamed text into speakable sentences."""

    def __init__(self) -> None:
        self.buf = ""

    def feed(self, delta: str) -> list[str]:
        self.buf += delta or ""
        out: list[str] = []
        while True:
            match = re.search(r"[.!?…](?:\s|$)", self.buf)
            if not match:
                break
            end = match.end()
            sentence = self.buf[:end].strip()
            self.buf = self.buf[end:].lstrip()
            if sentence:
                out.append(sentence)
        while "\n" in self.buf:
            head, self.buf = self.buf.split("\n", 1)
            head = head.strip()
            if head:
                out.append(head)
        return out

    def flush(self) -> list[str]:
        sentence = self.buf.strip()
        self.buf = ""
        return [sentence] if sentence else []


class SpeechError(RuntimeError):
    pass


class Speech:
    def __init__(self, core: "Core"):
        self.core = core

    def transcribe(self, pcm: bytes, lang: str = "auto") -> tuple[str, str]:
        wav = pcm_to_wav(pcm)
        try:
            return self._server_stt(wav, lang)
        except Exception as exc:
            self.core.store.event("warn", "whisper_server", str(exc))
        return self._cli_stt(wav, lang)

    def _server_stt(self, wav: bytes, lang: str) -> tuple[str, str]:
        with tempfile.NamedTemporaryFile(suffix=".wav") as handle:
            handle.write(wav)
            handle.flush()
            cmd = [
                "curl", "-sS", "--max-time", str(int(self.core.speech_timeout)),
                "-F", f"file=@{handle.name}",
                "-F", "response_format=json",
                "-F", "temperature=0",
            ]
            if lang in ("en", "fr"):
                cmd += ["-F", f"language={lang}"]
            cmd.append(self.core.whisper_url.rstrip("/") + "/inference")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=self.core.speech_timeout + 2)
            if result.returncode != 0:
                raise SpeechError(result.stderr.strip() or "whisper server failed")
            data = json.loads(result.stdout or "{}")
            text = (data.get("text") or "").strip()
            if not text:
                raise SpeechError("empty transcription")
            return text, data.get("language") or lang

    def _cli_stt(self, wav: bytes, lang: str) -> tuple[str, str]:
        binary = self.core.whisper_cli
        model = self.core.whisper_model
        if not binary or not model or not Path(binary).exists() or not Path(model).exists():
            raise SpeechError("no whisper server or whisper-cli available")
        with tempfile.NamedTemporaryFile(suffix=".wav") as handle:
            handle.write(wav)
            handle.flush()
            cmd = [binary, "-m", model, "-f", handle.name, "-nt"]
            if lang in ("en", "fr"):
                cmd += ["-l", lang]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=self.core.speech_timeout)
            if result.returncode != 0:
                raise SpeechError(result.stderr.strip() or "whisper-cli failed")
            text = result.stdout.strip()
            if not text:
                raise SpeechError("empty transcription")
            return text, lang

    def synthesize(self, text: str, lang: str) -> bytes:
        text = (text or "").strip()
        if not text:
            return b""
        voice_name = self.core.voice_names.get(lang, self.core.voice_names.get("en", ""))
        voice_path = self.core.voice_paths.get(lang, self.core.voice_paths.get("en", ""))
        if not voice_name:
            raise SpeechError("no voice configured")
        try:
            payload = json.dumps({"text": text, "voice": voice_name}).encode("utf-8")
            request = urllib.request.Request(
                self.core.piper_url.rstrip("/") + "/synthesize",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=self.core.speech_timeout) as response:
                audio = response.read()
            if audio[:4] != b"RIFF":
                raise SpeechError("piper returned non-wav audio")
            return audio
        except Exception as exc:
            self.core.store.event("warn", "piper_http", str(exc))
        return self._cli_tts(text, voice_path)

    def _cli_tts(self, text: str, voice: str) -> bytes:
        if not voice:
            raise SpeechError("no piper voice available")
        with tempfile.NamedTemporaryFile(suffix=".wav") as handle:
            cmd = [sys.executable, "-m", "piper", "-m", voice, "--output-file", handle.name]
            result = subprocess.run(
                cmd,
                input=text.encode("utf-8"),
                capture_output=True,
                timeout=self.core.speech_timeout,
            )
            if result.returncode != 0:
                raise SpeechError(result.stderr.decode("utf-8", "replace")[-300:] or "piper failed")
            handle.seek(0)
            audio = handle.read()
            if not audio:
                raise SpeechError("piper returned empty audio")
            return audio


