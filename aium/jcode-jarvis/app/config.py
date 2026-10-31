"""Paths, version, defaults, and persisted configuration."""
from __future__ import annotations

import json
import os
import threading
import tomllib
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION = "2.0"
DEFAULT_BRAIN = {
    "backend": "jcode",
    "provider": "deepseek",
    "model": "deepseek-v4-flash",
    "fallback": [],
    "timeout_ms": 30000,
}

def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def load_json(path: Path, default):
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return default


def load_brain(path: Path) -> dict:
    config = dict(DEFAULT_BRAIN)
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle).get("brain", {})
        if isinstance(data, dict):
            config.update(data)
    except FileNotFoundError:
        pass
    except Exception:
        pass
    config["provider"] = os.environ.get("JARVIS_BRAIN_PROVIDER", config.get("provider", ""))
    config["model"] = os.environ.get("JARVIS_BRAIN_MODEL", config.get("model", ""))
    config["provider"] = str(config.get("provider") or "").strip()
    config["model"] = str(config.get("model") or "").strip()
    fallback = config.get("fallback") or []
    if isinstance(fallback, str):
        fallback = [part.strip() for part in fallback.split(",") if part.strip()]
    config["fallback"] = [str(item).strip() for item in fallback if str(item).strip()]
    try:
        config["timeout_ms"] = int(config.get("timeout_ms", 30000))
    except Exception:
        config["timeout_ms"] = 30000
    return config


def save_brain(path: Path, config: dict) -> None:
    fallback = ", ".join(json.dumps(item) for item in config.get("fallback", []))
    text = (
        "[brain]\n"
        f'backend = {json.dumps(config.get("backend", "jcode"))}\n'
        f'provider = {json.dumps(config.get("provider", ""))}\n'
        f'model = {json.dumps(config.get("model", ""))}\n'
        f"fallback = [{fallback}]\n"
        f'timeout_ms = {int(config.get("timeout_ms", 30000))}\n'
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


SETTINGS_DEFAULTS = {
    "tts": True,
    "lang": "auto",
    "voice_en": "",
    "voice_fr": "",
}
SETTINGS_LANGS = {"auto", "en", "fr"}


class Settings:
    """Small persisted preferences file. Loading never raises."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.lock = threading.RLock()
        self.values = dict(SETTINGS_DEFAULTS)
        self.load()

    def load(self) -> dict:
        data = load_json(self.path, None)
        if isinstance(data, dict):
            self.merge(data, save=False)
        return self.as_dict()

    def as_dict(self) -> dict:
        with self.lock:
            return dict(self.values)

    def get(self, key: str, default=None):
        with self.lock:
            return self.values.get(key, SETTINGS_DEFAULTS.get(key, default))

    def merge(self, data: dict, save: bool = True) -> dict:
        if not isinstance(data, dict):
            return self.as_dict()
        with self.lock:
            if isinstance(data.get("tts"), bool):
                self.values["tts"] = data["tts"]
            lang = data.get("lang")
            if isinstance(lang, str) and lang in SETTINGS_LANGS:
                self.values["lang"] = lang
            for key in ("voice_en", "voice_fr"):
                value = data.get(key)
                if isinstance(value, str):
                    self.values[key] = value.strip()[:120]
            if save:
                self.save()
            return dict(self.values)

    def save(self) -> None:
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.values, indent=2) + "\n", encoding="utf-8")
            os.replace(tmp, self.path)


