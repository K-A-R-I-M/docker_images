"""Core state: settings, memory, speech, brain, and one turn."""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

from app.brain import Brain
from app.config import ROOT, VERSION, Settings, load_brain, load_json, now_iso
from app.language import detect_lang
from app.router import Router
from app.speech import Speech, SpeechFence
from app.store import Store
from app.supervisor import check_http, check_port

class Core:
    def __init__(self, args: argparse.Namespace):
        self.data_dir = Path(args.data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.persona_dir = Path(os.environ.get("JARVIS_PERSONA_DIR", str(ROOT)))
        self.brain_path = self.data_dir / "brain.toml"
        seed_brain = self.brain_path if self.brain_path.exists() else ROOT / "brain.toml"
        self.brain_config = load_brain(seed_brain)
        self.pricing = load_json(ROOT / "pricing.json", {})
        self.store = Store(self.data_dir / "jarvis.db")
        self.settings = Settings(self.data_dir / "settings.json")
        self.router = Router()
        self.speech = Speech(self)
        self.brain = Brain(self)
        self.state = "idle"
        self.session_enabled = False
        self.turn_lock = threading.Lock()
        self.cancel_event = threading.Event()
        self.last_turn: dict | None = None
        self.usage_cache: tuple[float, dict | None] = (0.0, None)
        self.speech_timeout = int(os.environ.get("JARVIS_SPEECH_TIMEOUT", "35"))
        self.whisper_url = os.environ.get("JARVIS_WHISPER_URL", "http://127.0.0.1:8178")
        self.piper_url = os.environ.get("JARVIS_PIPER_URL", "http://127.0.0.1:5000")
        self.whisper_cli = os.environ.get("JARVIS_WHISPER_CLI", "/opt/whisper/whisper-cli")
        profile = os.environ.get("JARVIS_PROFILE", "standard").lower()
        self.profile = "low" if profile == "low" else "standard"
        default_model = "/opt/whisper/models/ggml-tiny-q5_1.bin" if self.profile == "low" else "/opt/whisper/models/ggml-base-q5_1.bin"
        self.whisper_model = os.environ.get("JARVIS_WHISPER_MODEL", default_model)
        self.default_voice_names = {
            "en": os.environ.get("JARVIS_VOICE_EN_NAME", "en_US-lessac-medium"),
            "fr": os.environ.get("JARVIS_VOICE_FR_NAME", "fr_FR-siwis-medium"),
        }
        self.default_voice_paths = {
            "en": os.environ.get("JARVIS_VOICE_EN", "/opt/piper/voices/en_US-lessac-medium.onnx"),
            "fr": os.environ.get("JARVIS_VOICE_FR", "/opt/piper/voices/fr_FR-siwis-medium.onnx"),
        }
        self.voice_names = dict(self.default_voice_names)
        self.voice_paths = dict(self.default_voice_paths)
        self.apply_settings()
        self.started_at = now_iso()
        self.started_ts = time.time()

    def set_session(self, enabled: bool) -> None:
        self.session_enabled = bool(enabled)
        self.state = "listening" if enabled else "idle"
        self.store.event("info", "session", "enabled" if enabled else "disabled")

    def status(self) -> dict:
        return {
            "state": self.state,
            "session": self.session_enabled,
            "lang": self.settings.get("lang", "auto"),
            "profile": self.profile,
            "brain": {
                "provider": self.brain_config.get("provider", ""),
                "model": self.brain_config.get("model", ""),
                "backend": self.brain_config.get("backend", "jcode"),
                "fallback": self.brain_config.get("fallback", []),
            },
            "session_id": self.store.session_id,
            "turns": self.store.session_turns(),
            "facts": self.store.facts_count(),
            "db_bytes": self.store.db_size(),
            "cost_usd": round(self.store.session_cost(), 8),
            "last_turn": self.last_turn,
            "started_at": self.started_at,
            "spend_today": round(self.store.spend_today(), 8),
            "uptime_s": int(max(0.0, time.time() - self.started_ts)),
            "version": VERSION,
            "arch": platform.machine(),
        }

    def settings_dict(self) -> dict:
        values = self.settings.as_dict()
        return {
            "tts": bool(values.get("tts", True)),
            "lang": values.get("lang", "auto"),
            "voice_en": values.get("voice_en", ""),
            "voice_fr": values.get("voice_fr", ""),
            "whisper_model": self.whisper_model,
            "profile": self.profile,
        }

    def apply_settings(self) -> None:
        for code in ("en", "fr"):
            self.voice_names[code] = self.default_voice_names[code]
            self.voice_paths[code] = self.default_voice_paths[code]
            chosen = re.sub(r"[^A-Za-z0-9._-]", "", str(self.settings.get(f"voice_{code}", "") or ""))
            if chosen:
                self.voice_names[code] = chosen
                voices_dir = Path(os.environ.get("JARVIS_PIPER_VOICES", "/opt/piper/voices"))
                self.voice_paths[code] = str(voices_dir / (chosen + ".onnx"))

    def health(self) -> dict:
        whisper = check_port(self.whisper_url)
        piper = check_http(self.piper_url.rstrip("/") + "/info")
        jcode = shutil.which("jcode") is not None
        db = self.store.facts_count() >= 0
        return {
            "ok": bool(piper and whisper and jcode and db),
            "whisper": whisper,
            "piper": piper,
            "jcode": jcode,
            "db": db,
            "brain": self.brain_config.get("provider", "") + "/" + self.brain_config.get("model", ""),
        }

    def machine_usage(self) -> dict | None:
        now = time.time()
        if now - self.usage_cache[0] < 300 and self.usage_cache[1] is not None:
            return self.usage_cache[1]
        try:
            result = subprocess.run(
                ["jcode", "usage", "--json"],
                capture_output=True, text=True, timeout=6,
                env={**os.environ, "JCODE_NO_TELEMETRY": "1", "DO_NOT_TRACK": "1"},
            )
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip()[:200])
            data = json.loads(result.stdout)
            out = {"spend": "", "balance": "", "provider": ""}
            for provider in data.get("providers", []):
                out["provider"] = provider.get("provider_name", "")
                for key, value in provider.get("extra_info", []):
                    if key.startswith("Local spend"):
                        out["spend"] = value
                    elif key == "Balance":
                        out["balance"] = value
            self.usage_cache = (now, out)
            return out
        except Exception:
            self.usage_cache = (now, None)
            return None

    def turn(self, text: str | None = None, pcm: bytes | None = None, lang: str = "auto", emit=None) -> dict:
        if not self.turn_lock.acquire(blocking=False):
            raise BusyError("a turn is already running")
        success = False
        try:
            self.cancel_event.clear()
            lang = (lang or "auto").strip().lower()
            if lang == "auto":
                configured = self.settings.get("lang", "auto")
                if configured in ("en", "fr"):
                    lang = configured
            started = time.time()
            stt_ms = 0
            if pcm:
                self.state = "thinking"
                self.emit(emit, {"type": "stage", "stage": "transcribing"})
                text, detected = self.speech.transcribe(pcm, lang)
                stt_ms = int((time.time() - started) * 1000)
                if lang == "auto" and detected:
                    lang = detected
            text = (text or "").strip()
            if not text:
                raise ValueError("nothing was heard")
            lang = detect_lang(text, lang)
            self.emit(emit, {"type": "transcript", "text": text, "lang": lang})
            self.state = "thinking"
            self.emit(emit, {"type": "stage", "stage": "thinking"})
            route = self.router.route(text, lang, self.store)
            usage = {}
            cost = None
            provider = "local"
            model = "router"
            ttft_ms = 0
            speech = SpeechFence()
            if route.reply is not None:
                reply = route.reply
                for speakable in speech.feed(reply):
                    self.emit(emit, {"type": "sentence", "text": speakable})
            else:
                def on_delta(delta: str) -> None:
                    self.emit(emit, {"type": "delta", "text": delta})

                def on_sentence(sentence: str) -> None:
                    for speakable in speech.feed(sentence):
                        self.emit(emit, {"type": "sentence", "text": speakable})

                result = self.brain.complete(text, lang, on_delta, on_sentence)
                reply = result.text
                usage = result.usage
                cost = result.cost
                provider = result.provider
                model = result.model
                ttft_ms = result.ttft_ms

            total_ms = int((time.time() - started) * 1000)
            self.store.add_turn("user", text, lang, stt_ms=stt_ms, total_ms=stt_ms)
            self.store.add_turn(
                "assistant", reply, lang, ttft_ms=ttft_ms, total_ms=total_ms,
                usage=usage, cost=cost, provider=provider, model=model,
            )
            self.last_turn = {
                "reply": reply,
                "lang": lang,
                "stt_ms": stt_ms,
                "ttft_ms": ttft_ms,
                "total_ms": total_ms,
                "usage": usage,
                "cost_usd": cost,
                "provider": provider,
                "model": model,
            }
            self.state = "listening" if self.session_enabled else "idle"
            done = {
                "type": "done",
                "transcript": text,
                "reply": reply,
                "lang": lang,
                "action": route.action,
                "provider": provider,
                "model": model,
                "usage": usage,
                "cost_usd": cost,
                "timings": {"stt_ms": stt_ms, "ttft_ms": ttft_ms, "total_ms": total_ms},
                "session_cost_usd": round(self.store.session_cost(), 8),
                "facts": self.store.facts_count(),
            }
            self.emit(emit, done)
            success = True
            return done
        finally:
            if not success:
                self.state = "listening" if self.session_enabled else "idle"
            self.turn_lock.release()

    @staticmethod
    def emit(emit, event: dict) -> None:
        if emit:
            try:
                emit(event)
            except (BrokenPipeError, ConnectionResetError):
                raise


class BusyError(RuntimeError):
    pass


