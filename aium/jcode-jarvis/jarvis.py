#!/usr/bin/env python3
"""Jarvis: a small, local-first voice companion around jcode.

The browser or a microphone adapter sends speech, the local whisper server
transcribes it, a local router handles small intents, and the cloud brain
(jcode) answers everything else. Audio never leaves this process.
"""

from __future__ import annotations

import argparse
import array
import base64
import io
import json
import math
import os
import platform
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
import wave
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERSION = "2.0"
DEFAULT_BRAIN = {
    "backend": "jcode",
    "provider": "deepseek",
    "model": "deepseek-v4-flash",
    "fallback": [],
    "timeout_ms": 30000,
}
FR_WORDS = {
    "le", "la", "les", "un", "une", "des", "de", "du", "et", "est", "je", "tu",
    "il", "elle", "nous", "vous", "ils", "elles", "que", "qui", "quoi", "pour",
    "avec", "dans", "sur", "pas", "ne", "ce", "cette", "mon", "ma", "mes",
    "ton", "ta", "tes", "son", "sa", "ses", "au", "aux", "en", "y", "oui",
    "non", "bonjour", "salut", "merci", "s'il", "plaît", "oublie", "retiens",
    "souviens", "heure", "date", "arrête", "au", "revoir",
}
EN_WORDS = {
    "the", "a", "an", "and", "is", "are", "i", "you", "he", "she", "we",
    "they", "that", "this", "what", "who", "why", "how", "for", "with", "in",
    "on", "not", "do", "does", "my", "your", "his", "her", "our", "their",
    "yes", "no", "hello", "hi", "thanks", "please", "remember", "forget",
    "time", "date", "stop", "goodbye", "bye",
}
MAX_BODY = 16 * 1024 * 1024


class BodyTooLarge(Exception):
    pass


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


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


def compute_cost(pricing: dict, provider: str, model: str, usage: dict | None) -> float | None:
    if not usage:
        return None
    rates = (
        pricing.get(provider, {}).get(model)
        or pricing.get(model, {})
        or None
    )
    if not isinstance(rates, dict):
        return None
    try:
        input_tokens = int(usage.get("input_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or 0)
        cache_read = int(usage.get("cache_read_input_tokens") or usage.get("cache_read") or 0)
        cache_write = int(usage.get("cache_creation_input_tokens") or usage.get("cache_write") or 0)
        uncached = max(input_tokens - cache_read, 0)
        cost = (
            uncached * float(rates.get("input", 0))
            + cache_read * float(rates.get("cache_read", 0))
            + cache_write * float(rates.get("cache_write", 0))
            + output_tokens * float(rates.get("output", 0))
        ) / 1_000_000
        return round(cost, 8)
    except Exception:
        return None


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.fts = False
        self._init()
        self.session_id = self._ensure_session()

    def _init(self) -> None:
        with self.lock, self.conn:
            self.conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    turns INTEGER NOT NULL DEFAULT 0,
                    cost_usd REAL NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    text TEXT NOT NULL,
                    lang TEXT,
                    stt_ms INTEGER,
                    ttft_ms INTEGER,
                    total_ms INTEGER,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    cache_read INTEGER,
                    cache_write INTEGER,
                    cost_usd REAL,
                    provider TEXT,
                    model TEXT,
                    ts TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL,
                    tags TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    last_used TEXT
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    level TEXT NOT NULL,
                    event TEXT NOT NULL,
                    detail TEXT,
                    ts TEXT NOT NULL
                );
                """
            )
            try:
                self.conn.execute(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(text, tags, content='facts', content_rowid='id')"
                )
                self.conn.executescript(
                    """
                    CREATE TRIGGER IF NOT EXISTS facts_ai AFTER INSERT ON facts BEGIN
                      INSERT INTO facts_fts(rowid, text, tags) VALUES (new.id, new.text, new.tags);
                    END;
                    CREATE TRIGGER IF NOT EXISTS facts_ad AFTER DELETE ON facts BEGIN
                      INSERT INTO facts_fts(facts_fts, rowid, text, tags) VALUES ('delete', old.id, old.text, old.tags);
                    END;
                    CREATE TRIGGER IF NOT EXISTS facts_au AFTER UPDATE ON facts BEGIN
                      INSERT INTO facts_fts(facts_fts, rowid, text, tags) VALUES ('delete', old.id, old.text, old.tags);
                      INSERT INTO facts_fts(rowid, text, tags) VALUES (new.id, new.text, new.tags);
                    END;
                    """
                )
                self.fts = True
            except sqlite3.OperationalError:
                self.fts = False

    def _ensure_session(self) -> str:
        with self.lock:
            row = self.conn.execute(
                "SELECT id FROM sessions WHERE ended_at IS NULL ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
            if row:
                return str(row["id"])
        return self.new_session()

    def new_session(self) -> str:
        session_id = "s_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        with self.lock, self.conn:
            self.conn.execute("UPDATE sessions SET ended_at = ? WHERE ended_at IS NULL", (now_iso(),))
            self.conn.execute(
                "INSERT INTO sessions (id, started_at) VALUES (?, ?)",
                (session_id, now_iso()),
            )
        self.session_id = session_id
        return session_id

    def remember(self, text: str, tags: str = "") -> None:
        text = text.strip()[:1000]
        if not text:
            return
        with self.lock, self.conn:
            row = self.conn.execute("SELECT id FROM facts WHERE text = ?", (text,)).fetchone()
            if row:
                self.conn.execute("UPDATE facts SET last_used = ? WHERE id = ?", (now_iso(), row["id"]))
            else:
                self.conn.execute(
                    "INSERT INTO facts (text, tags, created_at, last_used) VALUES (?, ?, ?, ?)",
                    (text, tags.strip(), now_iso(), now_iso()),
                )

    def _fts_query(self, query: str) -> str:
        tokens = re.findall(r"[\wÀ-ÿ]+", query, re.UNICODE)
        return " ".join('"' + token.replace('"', "") + '"' for token in tokens)

    def recall(self, query: str = "", limit: int = 5) -> list[dict]:
        with self.lock:
            if query.strip():
                if self.fts:
                    match = self._fts_query(query)
                    if match:
                        rows = self.conn.execute(
                            "SELECT f.id, f.text, f.tags, f.last_used FROM facts_fts "
                            "JOIN facts f ON f.id = facts_fts.rowid "
                            "WHERE facts_fts MATCH ? ORDER BY rank LIMIT ?",
                            (match, limit),
                        ).fetchall()
                    else:
                        rows = []
                else:
                    like = "%" + query.strip() + "%"
                    rows = self.conn.execute(
                        "SELECT id, text, tags, last_used FROM facts WHERE text LIKE ? ORDER BY id DESC LIMIT ?",
                        (like, limit),
                    ).fetchall()
            else:
                rows = self.conn.execute(
                    "SELECT id, text, tags, last_used FROM facts ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(row) for row in rows]

    def recent_facts(self, limit: int = 5) -> list[str]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT text FROM facts ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [str(row["text"]) for row in rows]

    def forget(self, query: str) -> int:
        query = query.strip()
        if not query:
            return 0
        with self.lock, self.conn:
            if self.fts:
                match = self._fts_query(query)
                if not match:
                    return 0
                rows = self.conn.execute(
                    "SELECT rowid FROM facts_fts WHERE facts_fts MATCH ?", (match,)
                ).fetchall()
                ids = [row["rowid"] for row in rows]
            else:
                like = "%" + query + "%"
                rows = self.conn.execute("SELECT id FROM facts WHERE text LIKE ?", (like,)).fetchall()
                ids = [row["id"] for row in rows]
            for fact_id in ids:
                self.conn.execute("DELETE FROM facts WHERE id = ?", (fact_id,))
        return len(ids)

    def forget_all(self) -> None:
        with self.lock, self.conn:
            self.conn.execute("DELETE FROM facts")
            self.conn.execute("DELETE FROM turns")
            self.conn.execute("DELETE FROM events")
            self.conn.execute("DELETE FROM sessions")
        self.session_id = self.new_session()

    def delete_fact(self, fact_id: int) -> int:
        try:
            fact_id = int(fact_id)
        except (TypeError, ValueError):
            return 0
        with self.lock, self.conn:
            cursor = self.conn.execute("DELETE FROM facts WHERE id = ?", (fact_id,))
        return int(cursor.rowcount or 0)

    def add_turn(
        self,
        role: str,
        text: str,
        lang: str = "",
        stt_ms: int = 0,
        ttft_ms: int = 0,
        total_ms: int = 0,
        usage: dict | None = None,
        cost: float | None = None,
        provider: str = "",
        model: str = "",
    ) -> None:
        usage = usage or {}
        with self.lock, self.conn:
            self.conn.execute(
                """
                INSERT INTO turns (
                    session_id, role, text, lang, stt_ms, ttft_ms, total_ms,
                    input_tokens, output_tokens, cache_read, cache_write,
                    cost_usd, provider, model, ts
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.session_id, role, text, lang, int(stt_ms), int(ttft_ms),
                    int(total_ms), int(usage.get("input_tokens") or 0),
                    int(usage.get("output_tokens") or 0),
                    int(usage.get("cache_read_input_tokens") or 0),
                    int(usage.get("cache_creation_input_tokens") or 0),
                    cost, provider, model, now_iso(),
                ),
            )
            self.conn.execute(
                "UPDATE sessions SET turns = turns + 1, cost_usd = cost_usd + ? WHERE id = ?",
                (float(cost or 0), self.session_id),
            )

    def last_turns(self, limit: int = 4) -> list[tuple[str, str]]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT role, text FROM turns WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (self.session_id, limit),
            ).fetchall()
        return [(str(row["role"]), str(row["text"])) for row in reversed(rows)]

    def session_cost(self) -> float:
        with self.lock:
            row = self.conn.execute(
                "SELECT cost_usd FROM sessions WHERE id = ?", (self.session_id,)
            ).fetchone()
        return float(row["cost_usd"] or 0) if row else 0.0

    def session_turns(self) -> int:
        with self.lock:
            row = self.conn.execute(
                "SELECT COUNT(*) AS n FROM turns WHERE session_id = ? AND role = 'assistant'",
                (self.session_id,),
            ).fetchone()
        return int(row["n"] or 0) if row else 0

    def facts_count(self) -> int:
        with self.lock:
            row = self.conn.execute("SELECT COUNT(*) AS n FROM facts").fetchone()
        return int(row["n"] or 0)

    def db_size(self) -> int:
        try:
            return self.path.stat().st_size
        except OSError:
            return 0

    @staticmethod
    def _clamp_int(value, default: int, low: int, high: int) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = default
        return max(low, min(high, number))

    @staticmethod
    def _turn_dict(row: sqlite3.Row) -> dict:
        return {
            "role": str(row["role"]),
            "text": str(row["text"]),
            "lang": row["lang"] or "",
            "stt_ms": int(row["stt_ms"] or 0),
            "ttft_ms": int(row["ttft_ms"] or 0),
            "total_ms": int(row["total_ms"] or 0),
            "input_tokens": int(row["input_tokens"] or 0),
            "output_tokens": int(row["output_tokens"] or 0),
            "cost_usd": float(row["cost_usd"] or 0),
            "provider": row["provider"] or "",
            "model": row["model"] or "",
            "ts": str(row["ts"]),
        }

    _TURN_COLUMNS = (
        "role, text, lang, stt_ms, ttft_ms, total_ms, input_tokens, output_tokens, "
        "cost_usd, provider, model, ts"
    )

    def history(self, limit: int = 50, all_sessions: bool = False) -> list[dict]:
        limit = self._clamp_int(limit, 50, 1, 200)
        with self.lock:
            if all_sessions:
                rows = self.conn.execute(
                    f"SELECT {self._TURN_COLUMNS} FROM turns ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            else:
                rows = self.conn.execute(
                    f"SELECT {self._TURN_COLUMNS} FROM turns WHERE session_id = ? "
                    "ORDER BY id DESC LIMIT ?",
                    (self.session_id, limit),
                ).fetchall()
        return [self._turn_dict(row) for row in reversed(rows)]

    def all_turns(self) -> list[dict]:
        with self.lock:
            rows = self.conn.execute(
                f"SELECT {self._TURN_COLUMNS} FROM turns ORDER BY id ASC"
            ).fetchall()
        return [self._turn_dict(row) for row in rows]

    def export_sessions(self) -> list[dict]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT id, started_at, ended_at, turns, cost_usd FROM sessions ORDER BY started_at ASC"
            ).fetchall()
        return [dict(row) for row in rows]

    def cost_by_day(self, days: int = 7) -> list[dict]:
        days = self._clamp_int(days, 7, 1, 90)
        today = date.today()
        start = today - timedelta(days=days - 1)
        with self.lock:
            rows = self.conn.execute(
                "SELECT date(ts, 'localtime') AS day, COALESCE(SUM(cost_usd), 0) AS cost, "
                "COUNT(*) AS n FROM turns WHERE role = 'assistant' "
                "AND date(ts, 'localtime') >= ? GROUP BY day",
                (start.isoformat(),),
            ).fetchall()
        buckets = {
            str(row["day"]): (float(row["cost"] or 0), int(row["n"] or 0))
            for row in rows
        }
        out = []
        for offset in range(days):
            day = (start + timedelta(days=offset)).isoformat()
            cost, turns = buckets.get(day, (0.0, 0))
            out.append({"date": day, "cost_usd": round(cost, 8), "turns": turns})
        return out

    def per_turn_costs(self, limit: int = 20) -> list[dict]:
        limit = self._clamp_int(limit, 20, 1, 100)
        with self.lock:
            rows = self.conn.execute(
                "SELECT ts, role, cost_usd, total_ms, input_tokens, output_tokens, provider, model "
                "FROM turns WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (self.session_id, limit),
            ).fetchall()
        return [
            {
                "ts": str(row["ts"]),
                "role": str(row["role"]),
                "cost_usd": float(row["cost_usd"] or 0),
                "total_ms": int(row["total_ms"] or 0),
                "input_tokens": int(row["input_tokens"] or 0),
                "output_tokens": int(row["output_tokens"] or 0),
                "provider": row["provider"] or "",
                "model": row["model"] or "",
            }
            for row in rows
        ]

    def spend_today(self) -> float:
        with self.lock:
            row = self.conn.execute(
                "SELECT COALESCE(SUM(cost_usd), 0) AS cost FROM turns "
                "WHERE role = 'assistant' AND date(ts, 'localtime') = date('now', 'localtime')"
            ).fetchone()
        return float(row["cost"] or 0) if row else 0.0

    def last_assistant_cost(self) -> float:
        with self.lock:
            row = self.conn.execute(
                "SELECT cost_usd FROM turns WHERE session_id = ? AND role = 'assistant' "
                "ORDER BY id DESC LIMIT 1",
                (self.session_id,),
            ).fetchone()
        return float(row["cost_usd"] or 0) if row else 0.0

    def event(self, level: str, event: str, detail: str = "") -> None:
        with self.lock, self.conn:
            self.conn.execute(
                "INSERT INTO events (level, event, detail, ts) VALUES (?, ?, ?, ?)",
                (level, event, detail[:2000], now_iso()),
            )
            self.conn.execute(
                "DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY id DESC LIMIT 200)"
            )

    def events(self, limit: int = 20) -> list[dict]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT level, event, detail, ts FROM events ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def close(self) -> None:
        with self.lock:
            self.conn.close()


class Route:
    def __init__(self, reply: str | None = None, action: str = "", lang: str = "en"):
        self.reply = reply
        self.action = action
        self.lang = lang


class Router:
    """Small local intents. Everything else goes to the brain."""

    def route(self, text: str, lang: str, store: Store) -> Route:
        raw = text.strip()
        low = raw.lower()

        if re.search(r"\b(stop|pause|silence|tais[- ]toi|arrête|arrete)\b", low):
            return Route("D'accord, j'arrête." if lang == "fr" else "Okay, stopping.", "stop", lang)

        if re.search(r"\b(goodbye|bye|au revoir|à plus|a plus)\b", low):
            return Route("Au revoir." if lang == "fr" else "Goodbye.", "end", lang)

        remember = re.match(
            r"^(?:please\s+)?(?:remember(?:\s+that)?|retiens(?:\s+que)?|souviens[- ]toi(?:\s+que)?)\s+(.+)$",
            raw,
            re.IGNORECASE,
        )
        if remember:
            fact = remember.group(1).strip()
            store.remember(fact)
            reply = "Je m'en souviendrai." if lang == "fr" else "I'll remember that."
            return Route(reply, "", lang)

        forget = re.match(
            r"^(?:please\s+)?(?:forget(?:\s+that)?|oublie)\s+(.+)$",
            raw,
            re.IGNORECASE,
        )
        if forget:
            count = store.forget(forget.group(1))
            if count:
                reply = "J'ai oublié ça." if lang == "fr" else "I forgot that."
            else:
                reply = "Je n'ai rien trouvé à oublier." if lang == "fr" else "I didn't find that to forget."
            return Route(reply, "", lang)

        if re.search(r"\b(what do you remember|what do you know|qu'est[- ]ce que tu (?:sais|te rappelles)|tu te rappelles quoi)\b", low):
            facts = store.recall("", 5)
            if facts:
                joined = "; ".join(fact["text"] for fact in facts)
                reply = "Je me souviens de ceci : " + joined if lang == "fr" else "I remember this: " + joined
            else:
                reply = "Je n'ai rien en mémoire pour l'instant." if lang == "fr" else "I don't have anything in memory yet."
            return Route(reply, "", lang)

        if re.search(r"\b(what time|quelle heure|the time)\b", low):
            now = datetime.now()
            if lang == "fr":
                reply = f"Il est {now.hour} h {now.minute:02d}."
            else:
                reply = now.strftime("It's %I:%M %p.").replace(" 0", " ")
            return Route(reply, "", lang)

        if re.search(r"\b(what date|what day|quelle date|quel jour)\b", low):
            now = datetime.now()
            if lang == "fr":
                reply = f"Nous sommes le {now.day} {now.strftime('%B %Y')}."
            else:
                reply = now.strftime("Today is %A, %d %B %Y.")
            return Route(reply, "", lang)

        if re.match(r"^(hi|hello|hey|bonjour|salut|bonsoir)[.!]?$", low):
            return Route("Bonjour. Je t'écoute." if lang == "fr" else "Hi. I'm listening.", "", lang)

        return Route(None, "", lang)


class BrainError(RuntimeError):
    pass


class BrainResult:
    def __init__(self, text: str, provider: str, model: str, usage: dict, cost: float | None, ttft_ms: int, session_id: str = ""):
        self.text = text
        self.provider = provider
        self.model = model
        self.usage = usage
        self.cost = cost
        self.ttft_ms = ttft_ms
        self.session_id = session_id


class Brain:
    def __init__(self, core: "Core"):
        self.core = core

    def candidates(self) -> list[tuple[str, str]]:
        config = self.core.brain_config
        out = [(config.get("provider", ""), config.get("model", ""))]
        for item in config.get("fallback", []):
            if ":" in item:
                provider, model = item.split(":", 1)
            else:
                provider, model = item, config.get("model", "")
            if provider:
                out.append((provider, model))
        seen = set()
        unique = []
        for pair in out:
            if pair not in seen:
                seen.add(pair)
                unique.append(pair)
        return unique

    def build_prompt(self, text: str, lang: str) -> str:
        store = self.core.store
        facts = store.recent_facts(6)
        turns = store.last_turns(4)
        parts = []
        if facts or turns:
            parts.append("[context]")
            if facts:
                parts.append("Known facts:")
                parts.extend("- " + fact for fact in facts)
            if turns:
                parts.append("Recent turns:")
                for role, line in turns:
                    label = "User" if role == "user" else "Jarvis"
                    parts.append(f"{label}: {line}")
            parts.append("[/context]")
        parts.append(f"User: {text}")
        parts.append("Reply in French." if lang == "fr" else "Reply in English.")
        parts.append("Jarvis:")
        return "\n".join(parts)

    def complete(self, text: str, lang: str, on_delta=None, on_sentence=None) -> BrainResult:
        prompt = self.build_prompt(text, lang)
        errors = []
        for provider, model in self.candidates():
            emitted = {"value": False}

            def delta(chunk: str) -> None:
                emitted["value"] = True
                if on_delta:
                    on_delta(chunk)

            def sentence(chunk: str) -> None:
                emitted["value"] = True
                if on_sentence:
                    on_sentence(chunk)

            try:
                return self.run_jcode(provider, model, prompt, delta, sentence)
            except Exception as exc:
                if emitted["value"]:
                    raise
                errors.append(f"{provider}/{model}: {exc}")
                self.core.store.event("warn", "brain_fallback", errors[-1])
        raise BrainError("; ".join(errors[-3:]) or "brain unavailable")

    def run_jcode(self, provider: str, model: str, prompt: str, on_delta, on_sentence) -> BrainResult:
        if self.core.brain_config.get("backend", "jcode") == "mock":
            text = "This is a mock reply."
            if on_delta:
                on_delta(text)
            if on_sentence:
                on_sentence(text)
            return BrainResult(text, "mock", "mock", {}, 0.0, 0)

        cmd = ["jcode", "run", "--ndjson", "--disable-base-tools", "--no-update", "--quiet"]
        if provider:
            cmd += ["-p", provider]
        if model:
            cmd += ["-m", model]
        cmd.append(prompt)
        env = os.environ.copy()
        env.setdefault("JCODE_NO_TELEMETRY", "1")
        env.setdefault("DO_NOT_TRACK", "1")
        started = time.time()
        ttft_ms = 0
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=str(self.core.persona_dir),
            env=env,
        )
        timeout = max(5, int(self.core.brain_config.get("timeout_ms", 30000)) / 1000)
        killed = {"value": False}

        def kill() -> None:
            killed["value"] = True
            try:
                proc.kill()
            except Exception:
                pass

        timer = threading.Timer(timeout, kill)
        timer.daemon = True
        timer.start()
        parts: list[str] = []
        usage: dict = {}
        session_id = ""
        used_provider = provider
        used_model = model
        buffer = SentenceBuffer()
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                if self.core.cancel_event.is_set():
                    kill()
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                kind = event.get("type")
                if kind == "start":
                    session_id = event.get("session_id", "")
                    used_provider = event.get("provider", provider)
                    used_model = event.get("model", model)
                elif kind == "text_delta":
                    delta = event.get("text", "")
                    if delta:
                        if not parts:
                            ttft_ms = int((time.time() - started) * 1000)
                        parts.append(delta)
                        if on_delta:
                            on_delta(delta)
                        for sentence in buffer.feed(delta):
                            if on_sentence:
                                on_sentence(sentence)
                elif kind == "tokens":
                    usage = {
                        "input_tokens": event.get("input", event.get("input_tokens", 0)),
                        "output_tokens": event.get("output", event.get("output_tokens", 0)),
                        "cache_read_input_tokens": event.get("cache_read", 0),
                        "cache_creation_input_tokens": event.get("cache_creation_input", 0),
                    }
                elif kind == "done":
                    if event.get("text") and not parts:
                        parts.append(event["text"])
                    usage = event.get("usage") or usage
                elif kind == "error":
                    raise BrainError(event.get("message") or "brain error")
            proc.wait(timeout=5)
        finally:
            timer.cancel()
            if proc.poll() is None:
                kill()
            if proc.poll() is None:
                proc.wait(timeout=2)

        for sentence in buffer.flush():
            if on_sentence:
                on_sentence(sentence)
        text = "".join(parts).strip()
        if not text:
            stderr = ""
            try:
                assert proc.stderr is not None
                stderr = proc.stderr.read()[-500:]
            except Exception:
                pass
            raise BrainError(("timeout" if killed["value"] else "empty reply") + (": " + stderr if stderr else ""))
        cost = compute_cost(self.core.pricing, used_provider, used_model, usage)
        return BrainResult(text, used_provider, used_model, usage, cost, ttft_ms, session_id)


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


class Core:
    def __init__(self, args: argparse.Namespace):
        self.args = args
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
        self.voices = self.voice_names
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
            if route.reply is not None:
                reply = route.reply
                self.emit(emit, {"type": "sentence", "text": reply})
            else:
                def on_delta(delta: str) -> None:
                    self.emit(emit, {"type": "delta", "text": delta})

                def on_sentence(sentence: str) -> None:
                    self.emit(emit, {"type": "sentence", "text": sentence})

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


def check_http(url: str, timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            response.read(64)
        return True
    except Exception:
        return False


def check_port(url: str, timeout: float = 0.5) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


class Handler(BaseHTTPRequestHandler):
    core: Core
    server_version = "Jarvis/" + VERSION

    def log_message(self, fmt: str, *args) -> None:
        if not os.environ.get("JARVIS_QUIET"):
            sys.stderr.write("jarvis: " + (fmt % args) + "\n")

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path in ("/", "/index.html"):
            try:
                body = (ROOT / "index.html").read_bytes()
            except OSError:
                self._send_json(500, {"error": "index.html missing"})
                return
            self._send_bytes(200, body, "text/html; charset=utf-8")
            return
        if not self._auth_ok():
            return
        if path == "/api/health":
            strict = urllib.parse.parse_qs(parsed.query).get("strict", ["0"])[0] in ("1", "true")
            health = self.core.health()
            self._send_json(200 if (not strict or health["ok"]) else 503, health)
        elif path == "/api/status":
            self._send_json(200, self.core.status())
        elif path == "/api/history":
            query = urllib.parse.parse_qs(parsed.query)
            limit = self._query_int(query, "limit", 50)
            all_sessions = query.get("all", ["0"])[0] in ("1", "true", "yes")
            self._send_json(200, {"turns": self.core.store.history(limit, all_sessions)})
        elif path == "/api/cost":
            query = urllib.parse.parse_qs(parsed.query)
            days = self._query_int(query, "days", 7)
            self._send_json(200, {
                "days": self.core.store.cost_by_day(days),
                "today": round(self.core.store.spend_today(), 8),
                "session": round(self.core.store.session_cost(), 8),
                "last": round(self.core.store.last_assistant_cost(), 8),
            })
        elif path == "/api/settings":
            self._send_json(200, self.core.settings_dict())
        elif path == "/api/export":
            self._handle_export(parsed)
        elif path == "/api/brain":
            provider = urllib.parse.parse_qs(parsed.query).get("provider", [None])[0]
            self._send_json(200, self._brain_info(provider))
        elif path == "/api/events":
            self._send_json(200, {"events": self.core.store.events(30)})
        elif path == "/api/facts":
            self._send_json(200, {"facts": self.core.store.recall("", 30)})
        elif path == "/api/usage":
            self._send_json(200, self.core.machine_usage() or {})
        else:
            self._send_json(404, {"error": "not found"})

    @staticmethod
    def _query_int(query: dict, name: str, default: int) -> int:
        try:
            return int(query.get(name, [str(default)])[0])
        except (TypeError, ValueError):
            return default

    def _handle_export(self, parsed) -> None:
        what = urllib.parse.parse_qs(parsed.query).get("what", ["all"])[0]
        if what not in ("all", "facts", "turns"):
            self._send_json(400, {"error": "what must be all, facts, or turns"})
            return
        payload = {}
        if what in ("all", "facts"):
            payload["facts"] = self.core.store.recall("", 100000)
        if what in ("all", "turns"):
            payload["turns"] = self.core.store.all_turns()
        if what == "all":
            payload["sessions"] = self.core.store.export_sessions()
            payload["settings"] = self.core.settings_dict()
        self._send_bytes(
            200,
            json.dumps(payload).encode("utf-8"),
            "application/json; charset=utf-8",
            {"Content-Disposition": 'attachment; filename="jarvis-export.json"'},
        )

    def do_POST(self) -> None:
        if not self._auth_ok():
            return
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/session":
                data = self._read_json()
                self.core.set_session(bool(data.get("enabled")))
                self._send_json(200, {"ok": True, "state": self.core.state})
            elif path == "/api/brain":
                data = self._read_json()
                self._save_brain(data)
                self._send_json(200, {"ok": True, "brain": self.core.brain_config})
            elif path == "/api/brain/test":
                data = self._read_json()
                self._send_json(200, self._test_brain(data))
            elif path == "/api/chat":
                data = self._read_json()
                result = self.core.turn(text=data.get("text", ""), lang=data.get("lang", "auto"))
                self._send_json(200, result)
            elif path == "/api/settings":
                try:
                    data = self._read_json()
                except Exception:
                    self._send_json(400, {"error": "invalid JSON body"})
                    return
                if not isinstance(data, dict):
                    self._send_json(400, {"error": "body must be a JSON object"})
                    return
                self.core.settings.merge(data)
                self.core.apply_settings()
                self._send_json(200, self.core.settings_dict())
            elif path == "/api/tts":
                if not self.core.settings.get("tts", True):
                    self._send_json(409, {"error": "TTS is disabled in settings"})
                    return
                data = self._read_json()
                lang = str(data.get("lang") or "auto").lower()
                if lang not in ("en", "fr"):
                    configured = self.core.settings.get("lang", "auto")
                    lang = configured if configured in ("en", "fr") else "en"
                audio = self.core.speech.synthesize(data.get("text", ""), lang)
                self._send_bytes(200, audio, "audio/wav")
            elif path == "/api/facts":
                try:
                    data = self._read_json()
                except Exception:
                    self._send_json(400, {"error": "invalid JSON body"})
                    return
                if not isinstance(data, dict):
                    self._send_json(400, {"error": "body must be a JSON object"})
                    return
                text = str(data.get("text") or "").strip()
                if not text:
                    self._send_json(400, {"error": "text is required"})
                    return
                self.core.store.remember(text, str(data.get("tags") or ""))
                self._send_json(200, {"ok": True, "facts": self.core.store.recall("", 30)})
            elif path == "/api/facts/forget":
                try:
                    data = self._read_json()
                except Exception:
                    self._send_json(400, {"error": "invalid JSON body"})
                    return
                if not isinstance(data, dict):
                    self._send_json(400, {"error": "body must be a JSON object"})
                    return
                deleted = self.core.store.delete_fact(data.get("id"))
                self._send_json(200, {
                    "ok": True,
                    "deleted": deleted,
                    "facts_count": self.core.store.facts_count(),
                })
            elif path == "/api/forget":
                data = self._read_json()
                if data.get("all"):
                    self.core.store.forget_all()
                else:
                    self.core.store.forget(str(data.get("query", "")))
                self._send_json(200, {"ok": True, "facts": self.core.store.facts_count()})
            elif path == "/api/cancel":
                self.core.cancel_event.set()
                self._send_json(200, {"ok": True})
            elif path == "/api/turn":
                self._handle_turn(parsed)
            else:
                self._send_json(404, {"error": "not found"})
        except BusyError:
            self._send_json(409, {"error": "a turn is already running"})
        except BodyTooLarge:
            self._send_json(413, {"error": "request too large"})
        except SpeechError as exc:
            self._send_json(503, {"error": str(exc)})
        except BrokenPipeError:
            pass
        except Exception as exc:
            self.core.store.event("error", "request", str(exc))
            self._send_json(500, {"error": str(exc)})

    def _handle_turn(self, parsed) -> None:
        query = urllib.parse.parse_qs(parsed.query)
        stream = query.get("stream", ["0"])[0] in ("1", "true", "yes") or "text/event-stream" in self.headers.get("Accept", "")
        content_type = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        lang = self.headers.get("X-Lang", "auto")
        text = None
        pcm = None
        if content_type == "application/json":
            data = self._read_json()
            text = data.get("text")
            lang = data.get("lang", lang)
        elif content_type in ("application/octet-stream", "audio/wav", "audio/x-wav", "application/x-www-form-urlencoded"):
            pcm = self._read_body()
        elif content_type == "audio/webm":
            self._send_json(415, {"error": "send 16 kHz mono PCM, not webm"})
            return
        else:
            data = self._read_json()
            text = data.get("text")

        if not stream:
            result = self.core.turn(text=text, pcm=pcm, lang=lang)
            self._send_json(200, result)
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        self.close_connection = True

        def emit(event: dict) -> None:
            if event.get("type") == "transcript":
                self._turn_lang = event.get("lang") or self._turn_lang
            if event.get("type") == "sentence" and self.core.settings.get("tts", True):
                try:
                    audio = self.core.speech.synthesize(event.get("text", ""), event.get("lang") or self._turn_lang)
                    if audio:
                        event["audio"] = base64.b64encode(audio).decode("ascii")
                except Exception as exc:
                    self.core.store.event("warn", "tts", str(exc))
            self.wfile.write(("data: " + json.dumps(event) + "\n\n").encode("utf-8"))
            self.wfile.flush()

        self._turn_lang = lang
        try:
            self.core.turn(text=text, pcm=pcm, lang=lang, emit=emit)
        except Exception as exc:
            try:
                emit({"type": "error", "message": str(exc)})
            except (BrokenPipeError, ConnectionResetError):
                pass

    _turn_lang = "auto"

    def _brain_info(self, provider: str | None = None) -> dict:
        providers = run_lines(["jcode", "provider", "list"])
        provider = provider or self.core.brain_config.get("provider", "")
        models = run_lines(["jcode", "model", "list", "-p", provider]) if provider else []
        return {
            "config": self.core.brain_config,
            "providers": providers,
            "models": models,
        }

    def _save_brain(self, data: dict) -> None:
        def clean(value: str) -> str:
            return re.sub(r"[^A-Za-z0-9._:/-]", "", str(value or ""))[:120]

        provider = clean(data.get("provider"))
        model = clean(data.get("model"))
        if not provider or not model:
            raise ValueError("provider and model are required")
        fallback = data.get("fallback", self.core.brain_config.get("fallback", []))
        if isinstance(fallback, str):
            fallback = [part.strip() for part in fallback.split(",") if part.strip()]
        self.core.brain_config = {
            "backend": self.core.brain_config.get("backend", "jcode"),
            "provider": provider,
            "model": model,
            "fallback": [clean(item) for item in fallback if clean(item)],
            "timeout_ms": self.core.brain_config.get("timeout_ms", 30000),
        }
        save_brain(self.core.brain_path, self.core.brain_config)
        self.core.store.event("info", "brain", f"{provider}/{model}")

    def _test_brain(self, data: dict) -> dict:
        provider = data.get("provider") or self.core.brain_config.get("provider")
        model = data.get("model") or self.core.brain_config.get("model")
        try:
            result = subprocess.run(
                ["jcode", "run", "--json", "--disable-base-tools", "--no-update", "-p", str(provider), "-m", str(model), "Reply with exactly OK"],
                capture_output=True, text=True, timeout=25, cwd=str(self.core.persona_dir),
                env={**os.environ, "JCODE_NO_TELEMETRY": "1", "DO_NOT_TRACK": "1"},
            )
            if result.returncode != 0:
                return {"ok": False, "error": (result.stderr or result.stdout)[-500:]}
            payload = json.loads(result.stdout)
            return {"ok": True, "text": payload.get("text", ""), "provider": payload.get("provider"), "model": payload.get("model")}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _auth_ok(self) -> bool:
        token = os.environ.get("JARVIS_TOKEN", "")
        if not token:
            return True
        provided = self.headers.get("Authorization", "")
        if provided.lower().startswith("bearer "):
            provided = provided[7:]
        provided = provided or self.headers.get("X-Jarvis-Token", "")
        if provided == token:
            return True
        self._send_json(401, {"error": "unauthorized"})
        return False

    def _read_body(self, limit: int = MAX_BODY) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        if length > limit:
            self.close_connection = True
            raise BodyTooLarge()
        return self.rfile.read(length)

    def _read_json(self) -> dict:
        body = self._read_body()
        if not body:
            return {}
        return json.loads(body.decode("utf-8"))

    def _send_json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self._send_bytes(code, body, "application/json; charset=utf-8")

    def _send_bytes(self, code: int, body: bytes, content_type: str, headers: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        try:
            self.wfile.write(body)
        except BrokenPipeError:
            pass


def run_lines(cmd: list[str], timeout: float = 6.0) -> list[str]:
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "JCODE_NO_TELEMETRY": "1", "DO_NOT_TRACK": "1"},
        )
        if result.returncode != 0:
            return []
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except Exception:
        return []


class Supervisor:
    def __init__(self, core: Core, enabled: bool):
        self.core = core
        self.enabled = enabled
        self.specs: list[tuple[str, list[str], subprocess.Popen]] = []
        self.failures: dict[str, int] = {}
        self.started: dict[str, float] = {}
        self.stop = threading.Event()

    def _spawn(self, name: str, cmd: list[str]) -> subprocess.Popen:
        # inherit output so loader and model errors reach the container log
        proc = subprocess.Popen(cmd)
        self.started[name] = time.time()
        return proc

    def _start_child(self, name: str, cmd: list[str]) -> None:
        self.core.store.event("info", "supervisor", "starting " + name)
        self.specs.append((name, cmd, self._spawn(name, cmd)))

    def start(self) -> None:
        if not self.enabled:
            return
        whisper_bin = os.environ.get("JARVIS_WHISPER_BIN", "/opt/whisper/whisper-server")
        if Path(whisper_bin).exists() and not check_port(self.core.whisper_url):
            model = self.core.whisper_model
            threads = os.environ.get("JARVIS_WHISPER_THREADS", "4")
            cmd = [whisper_bin, "-m", model, "--host", "127.0.0.1", "--port", "8178", "-t", threads]
            self._start_child("whisper", cmd)
        if not check_http(self.core.piper_url.rstrip("/") + "/info"):
            voices = os.environ.get("JARVIS_PIPER_VOICES", "/opt/piper/voices")
            voice = self.core.voice_paths.get("en", "")
            cmd = [
                sys.executable, "-m", "piper.http_server",
                "-m", voice, "--data-dir", voices,
                "--host", "127.0.0.1", "--port", "5000",
            ]
            self._start_child("piper", cmd)
        thread = threading.Thread(target=self._watch, daemon=True)
        thread.start()
        guard = time.time() + 20
        while time.time() < guard:
            if check_port(self.core.whisper_url) and check_http(self.core.piper_url.rstrip("/") + "/info"):
                break
            time.sleep(0.5)

    def _watch(self) -> None:
        while not self.stop.wait(5):
            for spec in list(self.specs):
                name, cmd, proc = spec
                if proc.poll() is None:
                    self.failures.pop(name, None)
                    continue
                self.core.store.event("warn", "supervisor", f"{name} exited {proc.returncode}")
                if time.time() - self.started.get(name, 0) > 10:
                    self.failures[name] = 1
                else:
                    self.failures[name] = self.failures.get(name, 0) + 1
                if self.failures[name] >= 3:
                    self.specs.remove(spec)
                    self.core.store.event("error", "supervisor", f"{name} failed 3 times, not restarting")
                    continue
                if self.stop.wait(2):
                    return
                try:
                    self.specs[self.specs.index(spec)] = (name, cmd, self._spawn(name, cmd))
                    self.core.store.event("info", "supervisor", "restarted " + name)
                except Exception as exc:
                    self.core.store.event("error", "supervisor", f"{name} restart failed: {exc}")

    def close(self) -> None:
        self.stop.set()
        for _name, _cmd, proc in self.specs:
            try:
                proc.terminate()
            except Exception:
                pass
        for _name, _cmd, proc in self.specs:
            try:
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        self.specs.clear()


def device_loop(core: Core, lang: str) -> None:
    if not shutil.which("arecord"):
        raise SystemExit("arecord is not installed")
    core.set_session(True)
    print("Jarvis device mode. Speak. Ctrl+C to stop.")
    proc = subprocess.Popen(
        ["arecord", "-q", "-f", "S16_LE", "-r", "16000", "-c", "1", "-t", "raw"],
        stdout=subprocess.PIPE,
    )
    chunk = 3200
    speaking = False
    silence = 0
    frames: list[bytes] = []
    try:
        assert proc.stdout is not None
        while True:
            data = proc.stdout.read(chunk)
            if not data:
                break
            level = rms_s16(data)
            if level > 500:
                speaking = True
                silence = 0
                frames.append(data)
            elif speaking:
                silence += 1
                frames.append(data)
                if silence >= 8:
                    pcm = b"".join(frames)
                    frames = []
                    speaking = False
                    silence = 0
                    if len(pcm) > 3200:
                        try:
                            result = core.turn(pcm=pcm, lang=lang)
                            print("You:", result.get("transcript", ""))
                            print("Jarvis:", result.get("reply", ""))
                            if core.settings.get("tts", True):
                                audio = core.speech.synthesize(result.get("reply", ""), result.get("lang", lang))
                                if audio:
                                    with tempfile.NamedTemporaryFile(suffix=".wav") as handle:
                                        handle.write(audio)
                                        handle.flush()
                                        subprocess.run(["aplay", "-q", handle.name], check=False)
                        except Exception as exc:
                            print("Error:", exc)
    finally:
        proc.terminate()
        core.set_session(False)


def selftest() -> int:
    failures = 0

    def check(name: str, condition: bool, detail: str = "") -> None:
        nonlocal failures
        if condition:
            print(f"ok   {name}")
        else:
            failures += 1
            print(f"FAIL {name} {detail}")

    check("lang fr", detect_lang("Bonjour, quelle heure est-il ?") == "fr")
    check("lang en", detect_lang("Hello, what time is it?") == "en")
    check("lang forced", detect_lang("Hello", "fr") == "fr")
    check("sentences", split_sentences("One. Two! Three?") == ["One.", "Two!", "Three?"])
    buffer = SentenceBuffer()
    out = buffer.feed("Hello there. How ") + buffer.feed("are you?")
    check("stream sentences", out == ["Hello there.", "How are you?"], str(out))
    check("wav header", pcm_to_wav(b"\x00\x00" * 160).startswith(b"RIFF"))
    pricing = {"deepseek": {"m": {"input": 1.0, "output": 2.0, "cache_read": 0.1}}}
    cost = compute_cost(pricing, "deepseek", "m", {"input_tokens": 1000, "output_tokens": 100, "cache_read_input_tokens": 500})
    check("cost math", abs((cost or 0) - 0.00075) < 1e-9, str(cost))
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(Path(tmp) / "test.db")
        store.remember("my sister is Ana")
        check("memory count", store.facts_count() == 1)
        check("memory recall", any("Ana" in fact["text"] for fact in store.recall("sister")))
        check("memory forget", store.forget("sister") == 1 and store.facts_count() == 0)
        router = Router()
        check("router time", router.route("what time is it", "en", store).reply is not None)
        check("router remember", router.route("remember that I like tea", "en", store).reply is not None)
        check("router recall", router.route("what do you remember", "en", store).reply is not None)
        check("router goodbye", router.route("goodbye", "en", store).action == "end")
        store.close()
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "brain.toml"
        os.environ.pop("JARVIS_BRAIN_PROVIDER", None)
        os.environ.pop("JARVIS_BRAIN_MODEL", None)
        save_brain(path, {"provider": "deepseek", "model": "m", "fallback": ["openai:gpt"], "timeout_ms": 1000})
        loaded = load_brain(path)
        check("brain roundtrip", loaded["provider"] == "deepseek" and loaded["model"] == "m" and loaded["fallback"] == ["openai:gpt"])
    print("selftest:", "PASS" if failures == 0 else f"{failures} FAILED")
    return 0 if failures == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Jarvis voice companion")
    parser.add_argument("--host", default=os.environ.get("JARVIS_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("JARVIS_PORT", "8765")))
    parser.add_argument("--data-dir", default=os.environ.get("JARVIS_DATA", "/data"))
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--no-supervise", action="store_true")
    parser.add_argument("--device", action="store_true")
    parser.add_argument("--lang", default="auto", choices=["auto", "en", "fr"])
    args = parser.parse_args()

    if args.selftest:
        return selftest()

    core = Core(args)
    supervisor = Supervisor(core, enabled=not args.no_supervise)
    supervisor.start()
    try:
        if args.device:
            device_loop(core, args.lang)
            return 0
        Handler.core = core
        server = ThreadingHTTPServer((args.host, args.port), Handler)
        server.daemon_threads = True
        print(f"Jarvis listening on http://{args.host}:{args.port}  data={core.data_dir}")
        print(f"brain={core.brain_config.get('provider')}/{core.brain_config.get('model')}  profile={core.profile}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
    finally:
        supervisor.close()
        core.store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
