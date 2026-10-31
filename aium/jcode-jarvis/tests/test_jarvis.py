import argparse
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import jarvis  # noqa: E402


class JarvisTests(unittest.TestCase):
    def test_language(self):
        self.assertEqual(jarvis.detect_lang("Bonjour, quelle heure est-il ?"), "fr")
        self.assertEqual(jarvis.detect_lang("Hello, what time is it?"), "en")
        self.assertEqual(jarvis.detect_lang("Hello", "fr"), "fr")

    def test_sentences(self):
        self.assertEqual(jarvis.split_sentences("One. Two! Three?"), ["One.", "Two!", "Three?"])
        buffer = jarvis.SentenceBuffer()
        self.assertEqual(buffer.feed("Hello there. How "), ["Hello there."])
        self.assertEqual(buffer.feed("are you?"), ["How are you?"])
        self.assertEqual(buffer.flush(), [])

    def test_wav(self):
        audio = jarvis.pcm_to_wav(b"\x00\x00" * 160)
        self.assertTrue(audio.startswith(b"RIFF"))
        self.assertIn(b"WAVE", audio[:16])

    def test_cost(self):
        pricing = {"deepseek": {"m": {"input": 1.0, "output": 2.0, "cache_read": 0.1}}}
        cost = jarvis.compute_cost(
            pricing, "deepseek", "m",
            {"input_tokens": 1000, "output_tokens": 100, "cache_read_input_tokens": 500},
        )
        self.assertAlmostEqual(cost, 0.00075, places=9)
        self.assertIsNone(jarvis.compute_cost(pricing, "missing", "m", {"input_tokens": 1}))

    def test_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = jarvis.Store(Path(tmp) / "test.db")
            store.remember("my sister is Ana")
            store.remember("my sister is Ana")
            self.assertEqual(store.facts_count(), 1)
            self.assertTrue(any("Ana" in fact["text"] for fact in store.recall("sister")))
            self.assertEqual(store.forget("sister"), 1)
            self.assertEqual(store.facts_count(), 0)
            store.close()

    def test_router(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = jarvis.Store(Path(tmp) / "test.db")
            router = jarvis.Router()
            self.assertIsNotNone(router.route("what time is it", "en", store).reply)
            self.assertIsNotNone(router.route("quelle heure est-il", "fr", store).reply)
            self.assertIsNotNone(router.route("remember that I like tea", "en", store).reply)
            self.assertIsNotNone(router.route("souviens-toi que j'aime le thé", "fr", store).reply)
            self.assertEqual(router.route("goodbye", "en", store).action, "end")
            self.assertIsNone(router.route("tell me a story", "en", store).reply)
            store.close()

    def test_brain_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "brain.toml"
            os.environ.pop("JARVIS_BRAIN_PROVIDER", None)
            os.environ.pop("JARVIS_BRAIN_MODEL", None)
            jarvis.save_brain(
                path,
                {"provider": "deepseek", "model": "m", "fallback": ["openai:gpt"], "timeout_ms": 1000},
            )
            loaded = jarvis.load_brain(path)
            self.assertEqual(loaded["provider"], "deepseek")
            self.assertEqual(loaded["model"], "m")
            self.assertEqual(loaded["fallback"], ["openai:gpt"])
            self.assertEqual(loaded["timeout_ms"], 1000)

    def test_rms(self):
        self.assertEqual(jarvis.rms_s16(b""), 0.0)
        self.assertGreater(jarvis.rms_s16(b"\xff\x7f" * 10), 1000)

    def test_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = jarvis.Store(Path(tmp) / "test.db")
            store.add_turn("user", "hello", "en", stt_ms=120, total_ms=120)
            store.add_turn(
                "assistant", "hi there", "en", ttft_ms=80, total_ms=900,
                usage={"input_tokens": 10, "output_tokens": 5}, cost=0.0001,
                provider="deepseek", model="m",
            )
            turns = store.history()
            self.assertEqual([turn["role"] for turn in turns], ["user", "assistant"])
            last = turns[-1]
            self.assertEqual(last["text"], "hi there")
            self.assertEqual(last["lang"], "en")
            self.assertEqual(last["ttft_ms"], 80)
            self.assertEqual(last["total_ms"], 900)
            self.assertEqual(last["input_tokens"], 10)
            self.assertEqual(last["output_tokens"], 5)
            self.assertAlmostEqual(last["cost_usd"], 0.0001)
            self.assertEqual(last["provider"], "deepseek")
            self.assertEqual(last["model"], "m")
            self.assertTrue(last["ts"])
            for key in (
                "role", "text", "lang", "stt_ms", "ttft_ms", "total_ms",
                "input_tokens", "output_tokens", "cost_usd", "provider", "model", "ts",
            ):
                self.assertIn(key, last)

            for index in range(4):
                store.add_turn("user", f"turn {index}")
            limited = store.history(2)
            self.assertEqual(len(limited), 2)
            self.assertEqual([turn["text"] for turn in limited], ["turn 2", "turn 3"])
            self.assertEqual(len(store.history(0)), 1)

            second = "s_test_second"
            with store.lock, store.conn:
                store.conn.execute(
                    "INSERT INTO sessions (id, started_at) VALUES (?, ?)",
                    (second, jarvis.now_iso()),
                )
            store.session_id = second
            store.add_turn("user", "other session")
            current = store.history(50, all_sessions=False)
            self.assertEqual([turn["text"] for turn in current], ["other session"])
            everything = store.history(50, all_sessions=True)
            self.assertEqual(len(everything), 7)
            self.assertEqual(everything[-1]["text"], "other session")
            store.close()

    def test_cost_by_day(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = jarvis.Store(Path(tmp) / "test.db")
            empty = store.cost_by_day(7)
            self.assertEqual(len(empty), 7)
            self.assertEqual(empty[-1]["date"], date.today().isoformat())
            self.assertEqual(empty[0]["date"], (date.today() - timedelta(days=6)).isoformat())
            self.assertTrue(all(day["cost_usd"] == 0 and day["turns"] == 0 for day in empty))
            self.assertEqual(store.spend_today(), 0.0)
            self.assertEqual(store.last_assistant_cost(), 0.0)

            store.add_turn("assistant", "reply", "en", cost=0.25)
            days = store.cost_by_day(7)
            self.assertEqual(len(days), 7)
            self.assertEqual(days[-1]["date"], date.today().isoformat())
            self.assertAlmostEqual(days[-1]["cost_usd"], 0.25)
            self.assertEqual(days[-1]["turns"], 1)
            self.assertTrue(all(day["cost_usd"] == 0 for day in days[:-1]))
            self.assertAlmostEqual(store.spend_today(), 0.25)
            self.assertAlmostEqual(store.last_assistant_cost(), 0.25)
            self.assertEqual(len(store.cost_by_day(0)), 1)
            self.assertEqual(len(store.cost_by_day(500)), 90)
            store.close()

    def test_per_turn_costs(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = jarvis.Store(Path(tmp) / "test.db")
            store.add_turn("assistant", "first", "en", total_ms=100, cost=0.01,
                           usage={"input_tokens": 1, "output_tokens": 2},
                           provider="p", model="m")
            store.add_turn("assistant", "second", "en", total_ms=200, cost=0.02,
                           usage={"input_tokens": 3, "output_tokens": 4},
                           provider="p", model="m")
            costs = store.per_turn_costs(10)
            self.assertEqual(len(costs), 2)
            self.assertAlmostEqual(costs[0]["cost_usd"], 0.02)
            self.assertAlmostEqual(costs[1]["cost_usd"], 0.01)
            self.assertEqual(costs[0]["total_ms"], 200)
            self.assertEqual(costs[0]["input_tokens"], 3)
            self.assertEqual(costs[0]["output_tokens"], 4)
            self.assertEqual(costs[0]["role"], "assistant")
            for key in (
                "ts", "role", "cost_usd", "total_ms", "input_tokens",
                "output_tokens", "provider", "model",
            ):
                self.assertIn(key, costs[0])
            self.assertEqual(len(store.per_turn_costs(0)), 1)
            self.assertLessEqual(len(store.per_turn_costs(500)), 100)
            store.close()

    def test_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            settings = jarvis.Settings(path)
            self.assertEqual(settings.as_dict(), jarvis.SETTINGS_DEFAULTS)

            settings.merge({"tts": False, "lang": "fr"})
            self.assertFalse(settings.get("tts"))
            self.assertEqual(settings.get("lang"), "fr")

            reloaded = jarvis.Settings(path)
            self.assertFalse(reloaded.get("tts"))
            self.assertEqual(reloaded.get("lang"), "fr")
            self.assertEqual(reloaded.get("voice_en"), "")

            reloaded.merge({"voice_en": " my-voice "})
            self.assertEqual(reloaded.get("voice_en"), "my-voice")
            self.assertFalse(reloaded.get("tts"))

            before = reloaded.as_dict()
            reloaded.merge({"tts": "yes", "lang": "de", "voice_fr": 5, "unknown": True})
            self.assertEqual(reloaded.as_dict(), before)

            path.write_text("{not valid json", encoding="utf-8")
            corrupt = jarvis.Settings(path)
            self.assertEqual(corrupt.as_dict(), jarvis.SETTINGS_DEFAULTS)

    def test_core_settings_and_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            core = jarvis.Core(argparse.Namespace(data_dir=tmp))
            self.assertEqual(core.settings_dict()["lang"], "auto")
            core.settings.merge({"lang": "fr", "voice_en": "custom-voice"})
            core.apply_settings()
            self.assertEqual(core.voice_names["en"], "custom-voice")
            self.assertEqual(core.voice_paths["en"], "/opt/piper/voices/custom-voice.onnx")
            self.assertEqual(core.settings_dict()["voice_en"], "custom-voice")
            status = core.status()
            self.assertEqual(status["version"], "2.0")
            self.assertEqual(status["lang"], "fr")
            self.assertIn("arch", status)
            self.assertIn("uptime_s", status)
            self.assertIn("spend_today", status)
            core.store.close()

    def test_delete_fact_by_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = jarvis.Store(Path(tmp) / "test.db")
            store.remember("my sister is Ana")
            store.remember("my sister is Anna")
            facts = store.recall("", 30)
            self.assertEqual(len(facts), 2)
            target = next(fact for fact in facts if fact["text"] == "my sister is Ana")
            self.assertEqual(store.delete_fact(target["id"]), 1)
            remaining = store.recall("", 30)
            self.assertEqual(len(remaining), 1)
            self.assertEqual(remaining[0]["text"], "my sister is Anna")
            self.assertEqual(store.delete_fact(target["id"]), 0)
            self.assertEqual(store.delete_fact("not-an-id"), 0)
            self.assertEqual(store.facts_count(), 1)
            store.close()

    def test_cost_by_day_buckets(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = jarvis.Store(Path(tmp) / "test.db")
            store.add_turn("user", "question", "en")
            store.add_turn("assistant", "paid reply", "en", cost=0.5)
            with store.lock, store.conn:
                store.conn.execute(
                    "UPDATE turns SET ts = ? WHERE role = 'assistant'",
                    ((date.today() - timedelta(days=2)).isoformat() + "T12:00:00+00:00",),
                )
            days = store.cost_by_day(3)
            self.assertEqual([day["cost_usd"] for day in days], [0.5, 0.0, 0.0])
            self.assertEqual([day["turns"] for day in days], [1, 0, 0])
            self.assertEqual(store.spend_today(), 0.0)
            self.assertEqual(store.last_assistant_cost(), 0.5)
            store.close()

    def test_voice_setting_cannot_escape_voice_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            core = jarvis.Core(argparse.Namespace(data_dir=tmp))
            core.settings.merge({"voice_en": "../../etc/passwd"})
            core.apply_settings()
            self.assertNotIn("/", core.voice_names["en"])
            self.assertEqual(Path(core.voice_paths["en"]).parent, Path("/opt/piper/voices"))
            self.assertTrue(core.voice_paths["en"].endswith(".onnx"))
            core.settings.merge({"voice_en": ""})
            core.apply_settings()
            self.assertEqual(core.voice_names["en"], core.default_voice_names["en"])
            self.assertEqual(core.voice_paths["en"], core.default_voice_paths["en"])
            core.store.close()

    def test_empty_turn_raises_and_releases_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            core = jarvis.Core(argparse.Namespace(data_dir=tmp))
            for _ in range(2):
                with self.assertRaises(ValueError):
                    core.turn(text="")
            core.store.close()

    def test_speech_fence(self):
        fence = jarvis.SpeechFence()
        self.assertEqual(fence.feed("Hello."), ["Hello."])
        self.assertEqual(fence.feed("```mermaid"), [])
        self.assertEqual(fence.feed("graph TD; A-->B"), [])
        self.assertEqual(fence.feed("```"), [])
        self.assertEqual(fence.feed("Done."), ["Done."])
        inline = jarvis.SpeechFence()
        self.assertEqual(inline.feed("Before. ```mermaid\nA-->B\n``` After."), ["Before.", "After."])
        self.assertEqual(inline.feed("Plain."), ["Plain."])

    def test_turn_filters_fenced_speech(self):
        class FakeBrain:
            def complete(self, text, lang, on_delta, on_sentence):
                on_delta("Here. ```mermaid\n")
                on_sentence("Here. ```mermaid")
                on_sentence("graph TD")
                on_sentence("``` Done.")
                return jarvis.BrainResult(
                    "Here. ```mermaid\ngraph TD\n``` Done.", "p", "m", {}, None, 1
                )

        with tempfile.TemporaryDirectory() as tmp:
            core = jarvis.Core(argparse.Namespace(data_dir=tmp))
            core.brain = FakeBrain()
            events = []
            core.turn(text="draw it", lang="en", emit=events.append)
            sentences = [event["text"] for event in events if event["type"] == "sentence"]
            self.assertEqual(" ".join(sentences), "Here. Done.")
            self.assertFalse(any("graph" in sentence for sentence in sentences))
            done = events[-1]
            self.assertEqual(done["type"], "done")
            self.assertIn("```mermaid", done["reply"])
            core.store.close()


if __name__ == "__main__":
    unittest.main()
