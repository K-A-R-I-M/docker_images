"""Unit tests for the Jarvis modules. Run with `python3 -m pytest`."""
from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.brain import BrainResult
from app.config import SETTINGS_DEFAULTS, Settings, load_brain, now_iso, save_brain
from app.core import Core
from app.cost import compute_cost
from app.language import detect_lang
from app.router import Router
from app.speech import SentenceBuffer, SpeechFence, pcm_to_wav, rms_s16
from app.store import Store


def test_language():
    assert detect_lang("Bonjour, quelle heure est-il ?") == "fr"
    assert detect_lang("Hello, what time is it?") == "en"
    assert detect_lang("Hello", "fr") == "fr"


def test_sentences():
    buffer = SentenceBuffer()
    assert buffer.feed("Hello there. How ") == ["Hello there."]
    assert buffer.feed("are you?") == ["How are you?"]
    assert buffer.flush() == []


def test_wav():
    audio = pcm_to_wav(b"\x00\x00" * 160)
    assert audio.startswith(b"RIFF")
    assert b"WAVE" in audio[:16]


def test_cost():
    pricing = {"deepseek": {"m": {"input": 1.0, "output": 2.0, "cache_read": 0.1}}}
    cost = compute_cost(
        pricing, "deepseek", "m",
        {"input_tokens": 1000, "output_tokens": 100, "cache_read_input_tokens": 500},
    )
    assert cost == pytest.approx(0.00075, abs=1e-9)
    assert compute_cost(pricing, "missing", "m", {"input_tokens": 1}) is None


def test_memory(tmp_path):
    store = Store(tmp_path / "test.db")
    store.remember("my sister is Ana")
    store.remember("my sister is Ana")
    assert store.facts_count() == 1
    assert any("Ana" in fact["text"] for fact in store.recall("sister"))
    assert store.forget("sister") == 1
    assert store.facts_count() == 0
    store.close()


def test_router(tmp_path):
    store = Store(tmp_path / "test.db")
    router = Router()
    assert router.route("what time is it", "en", store).reply is not None
    assert router.route("quelle heure est-il", "fr", store).reply is not None
    assert router.route("remember that I like tea", "en", store).reply is not None
    assert router.route("souviens-toi que j'aime le thé", "fr", store).reply is not None
    assert router.route("goodbye", "en", store).action == "end"
    assert router.route("tell me a story", "en", store).reply is None
    store.close()


def test_brain_config(tmp_path, monkeypatch):
    monkeypatch.delenv("JARVIS_BRAIN_PROVIDER", raising=False)
    monkeypatch.delenv("JARVIS_BRAIN_MODEL", raising=False)
    path = tmp_path / "brain.toml"
    save_brain(
        path,
        {"provider": "deepseek", "model": "m", "fallback": ["openai:gpt"], "timeout_ms": 1000},
    )
    loaded = load_brain(path)
    assert loaded["provider"] == "deepseek"
    assert loaded["model"] == "m"
    assert loaded["fallback"] == ["openai:gpt"]
    assert loaded["timeout_ms"] == 1000


def test_rms():
    assert rms_s16(b"") == 0.0
    assert rms_s16(b"\xff\x7f" * 10) > 1000


def test_history(tmp_path):
    store = Store(tmp_path / "test.db")
    store.add_turn("user", "hello", "en", stt_ms=120, total_ms=120)
    store.add_turn(
        "assistant", "hi there", "en", ttft_ms=80, total_ms=900,
        usage={"input_tokens": 10, "output_tokens": 5}, cost=0.0001,
        provider="deepseek", model="m",
    )
    turns = store.history()
    assert [turn["role"] for turn in turns] == ["user", "assistant"]
    last = turns[-1]
    assert last["text"] == "hi there"
    assert last["lang"] == "en"
    assert last["ttft_ms"] == 80
    assert last["total_ms"] == 900
    assert last["input_tokens"] == 10
    assert last["output_tokens"] == 5
    assert last["cost_usd"] == pytest.approx(0.0001)
    assert last["provider"] == "deepseek"
    assert last["model"] == "m"
    assert last["ts"]
    for key in (
        "role", "text", "lang", "stt_ms", "ttft_ms", "total_ms",
        "input_tokens", "output_tokens", "cost_usd", "provider", "model", "ts",
    ):
        assert key in last

    for index in range(4):
        store.add_turn("user", f"turn {index}")
    limited = store.history(2)
    assert len(limited) == 2
    assert [turn["text"] for turn in limited] == ["turn 2", "turn 3"]
    assert len(store.history(0)) == 1

    second = "s_test_second"
    with store.lock, store.conn:
        store.conn.execute(
            "INSERT INTO sessions (id, started_at) VALUES (?, ?)",
            (second, now_iso()),
        )
    store.session_id = second
    store.add_turn("user", "other session")
    current = store.history(50, all_sessions=False)
    assert [turn["text"] for turn in current] == ["other session"]
    everything = store.history(50, all_sessions=True)
    assert len(everything) == 7
    assert everything[-1]["text"] == "other session"
    store.close()


def test_cost_by_day(tmp_path):
    store = Store(tmp_path / "test.db")
    empty = store.cost_by_day(7)
    assert len(empty) == 7
    assert empty[-1]["date"] == date.today().isoformat()
    assert empty[0]["date"] == (date.today() - timedelta(days=6)).isoformat()
    assert all(day["cost_usd"] == 0 and day["turns"] == 0 for day in empty)
    assert store.spend_today() == 0.0
    assert store.last_assistant_cost() == 0.0

    store.add_turn("assistant", "reply", "en", cost=0.25)
    days = store.cost_by_day(7)
    assert len(days) == 7
    assert days[-1]["date"] == date.today().isoformat()
    assert days[-1]["cost_usd"] == pytest.approx(0.25)
    assert days[-1]["turns"] == 1
    assert all(day["cost_usd"] == 0 for day in days[:-1])
    assert store.spend_today() == pytest.approx(0.25)
    assert store.last_assistant_cost() == pytest.approx(0.25)
    assert len(store.cost_by_day(0)) == 1
    assert len(store.cost_by_day(500)) == 90
    store.close()


def test_settings(tmp_path):
    path = tmp_path / "settings.json"
    settings = Settings(path)
    assert settings.as_dict() == SETTINGS_DEFAULTS

    settings.merge({"tts": False, "lang": "fr"})
    assert settings.get("tts") is False
    assert settings.get("lang") == "fr"
    assert settings.get("silence_ms") == 1200

    settings.merge({"silence_ms": 3000})
    assert settings.get("silence_ms") == 3000
    settings.merge({"silence_ms": 100})
    assert settings.get("silence_ms") == 600
    settings.merge({"silence_ms": "2000"})
    assert settings.get("silence_ms") == 600

    reloaded = Settings(path)
    assert reloaded.get("tts") is False
    assert reloaded.get("lang") == "fr"
    assert reloaded.get("voice_en") == ""

    reloaded.merge({"voice_en": " my-voice "})
    assert reloaded.get("voice_en") == "my-voice"
    assert reloaded.get("tts") is False

    before = reloaded.as_dict()
    reloaded.merge({"tts": "yes", "lang": "de", "voice_fr": 5, "unknown": True})
    assert reloaded.as_dict() == before

    path.write_text("{not valid json", encoding="utf-8")
    corrupt = Settings(path)
    assert corrupt.as_dict() == SETTINGS_DEFAULTS


def test_core_settings_and_status(tmp_path, monkeypatch):
    monkeypatch.delenv("JARVIS_PIPER_VOICES", raising=False)
    core = Core(argparse.Namespace(data_dir=str(tmp_path)))
    assert core.settings_dict()["lang"] == "auto"
    assert core.settings_dict()["silence_ms"] == 1200
    core.settings.merge({"lang": "fr", "voice_en": "custom-voice"})
    core.apply_settings()
    assert core.voice_names["en"] == "custom-voice"
    assert core.voice_paths["en"] == "/opt/piper/voices/custom-voice.onnx"
    assert core.settings_dict()["voice_en"] == "custom-voice"
    status = core.status()
    assert status["version"] == "2.0"
    assert status["lang"] == "fr"
    assert "arch" in status
    assert "uptime_s" in status
    assert "spend_today" in status
    core.store.close()


def test_delete_fact_by_id(tmp_path):
    store = Store(tmp_path / "test.db")
    store.remember("my sister is Ana")
    store.remember("my sister is Anna")
    facts = store.recall("", 30)
    assert len(facts) == 2
    target = next(fact for fact in facts if fact["text"] == "my sister is Ana")
    assert store.delete_fact(target["id"]) == 1
    remaining = store.recall("", 30)
    assert len(remaining) == 1
    assert remaining[0]["text"] == "my sister is Anna"
    assert store.delete_fact(target["id"]) == 0
    assert store.delete_fact("not-an-id") == 0
    assert store.facts_count() == 1
    store.close()


def test_cost_by_day_buckets(tmp_path):
    store = Store(tmp_path / "test.db")
    store.add_turn("user", "question", "en")
    store.add_turn("assistant", "paid reply", "en", cost=0.5)
    with store.lock, store.conn:
        store.conn.execute(
            "UPDATE turns SET ts = ? WHERE role = 'assistant'",
            ((date.today() - timedelta(days=2)).isoformat() + "T12:00:00+00:00",),
        )
    days = store.cost_by_day(3)
    assert [day["cost_usd"] for day in days] == [0.5, 0.0, 0.0]
    assert [day["turns"] for day in days] == [1, 0, 0]
    assert store.spend_today() == 0.0
    assert store.last_assistant_cost() == 0.5
    store.close()


def test_voice_setting_cannot_escape_voice_dir(tmp_path):
    core = Core(argparse.Namespace(data_dir=str(tmp_path)))
    core.settings.merge({"voice_en": "../../etc/passwd"})
    core.apply_settings()
    assert "/" not in core.voice_names["en"]
    assert Path(core.voice_paths["en"]).parent == Path("/opt/piper/voices")
    assert core.voice_paths["en"].endswith(".onnx")
    core.settings.merge({"voice_en": ""})
    core.apply_settings()
    assert core.voice_names["en"] == core.default_voice_names["en"]
    assert core.voice_paths["en"] == core.default_voice_paths["en"]
    core.store.close()


def test_empty_turn_raises_and_releases_lock(tmp_path):
    core = Core(argparse.Namespace(data_dir=str(tmp_path)))
    for _ in range(2):
        with pytest.raises(ValueError):
            core.turn(text="")
    core.store.close()


def test_speech_fence():
    fence = SpeechFence()
    assert fence.feed("Hello.") == ["Hello."]
    assert fence.feed("```mermaid") == []
    assert fence.feed("graph TD; A-->B") == []
    assert fence.feed("```") == []
    assert fence.feed("Done.") == ["Done."]
    inline = SpeechFence()
    assert inline.feed("Before. ```mermaid\nA-->B\n``` After.") == ["Before.", "After."]
    assert inline.feed("Plain.") == ["Plain."]


def test_health_checks():
    import http.server
    import socket
    import threading

    from app.supervisor import check_http, check_port

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]
    assert check_port(f"http://127.0.0.1:{port}") is True
    listener.close()
    assert check_port("http://127.0.0.1:1") is False

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = b"ok"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        assert check_http(f"http://127.0.0.1:{server.server_address[1]}/info") is True
    finally:
        server.shutdown()
        server.server_close()


def test_turn_filters_fenced_speech(tmp_path):
    class FakeBrain:
        def complete(self, text, lang, on_delta, on_sentence):
            on_delta("Here. ```mermaid\n")
            on_sentence("Here. ```mermaid")
            on_sentence("graph TD")
            on_sentence("``` Done.")
            return BrainResult("Here. ```mermaid\ngraph TD\n``` Done.", "p", "m", {}, None, 1)

    core = Core(argparse.Namespace(data_dir=str(tmp_path)))
    core.brain = FakeBrain()
    events = []
    core.turn(text="draw it", lang="en", emit=events.append)
    sentences = [event["text"] for event in events if event["type"] == "sentence"]
    assert " ".join(sentences) == "Here. Done."
    assert not any("graph" in sentence for sentence in sentences)
    done = events[-1]
    assert done["type"] == "done"
    assert "```mermaid" in done["reply"]
    core.store.close()
