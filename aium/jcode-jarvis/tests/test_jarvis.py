import os
import sys
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
