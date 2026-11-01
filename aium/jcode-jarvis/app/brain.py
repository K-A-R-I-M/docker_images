"""Cloud brain: run jcode, stream deltas, track usage and cost."""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from typing import TYPE_CHECKING

from app.cost import compute_cost
from app.speech import SentenceBuffer

if TYPE_CHECKING:
    from app.core import Core


class BrainError(RuntimeError):
    pass


class BrainResult:
    """One completed reply with usage, cost, and timing."""

    def __init__(self, text: str, provider: str, model: str, usage: dict, cost: float | None, ttft_ms: int):
        self.text = text
        self.provider = provider
        self.model = model
        self.usage = usage
        self.cost = cost
        self.ttft_ms = ttft_ms


class Brain:
    """Run jcode with the fallback chain and stream its output."""

    def __init__(self, core: "Core"):
        self.core = core

    def candidates(self) -> list[tuple[str, str]]:
        """Return configured provider/model pairs, de-duplicated."""
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
        """Compose facts, recent turns, and the language instruction."""
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
        if self.core.brain_config.get("skills"):
            # Only the skill loader is exposed; other tools stay disabled.
            parts.append("Skills are available: load one with skill_manage when the user names it.")
        return "\n".join(parts)

    def complete(self, text: str, lang: str, on_delta=None, on_sentence=None) -> BrainResult:
        """Try candidates until one emits a token, otherwise raise BrainError."""
        prompt = self.build_prompt(text, lang)
        errors = []
        # Only fall back before the first token; a partial reply must not be retried.
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
        """Stream jcode NDJSON, emitting text deltas and speakable sentences."""
        if self.core.brain_config.get("backend", "jcode") == "mock":
            text = "This is a mock reply."
            if on_delta:
                on_delta(text)
            if on_sentence:
                on_sentence(text)
            return BrainResult(text, "mock", "mock", {}, 0.0, 0)

        cmd = ["jcode", "run", "--ndjson", "--disable-base-tools", "--no-update", "--quiet"]
        # Skills are instructions only: expose skill_manage and nothing else.
        if self.core.brain_config.get("skills"):
            cmd += ["--tools", "skill_manage"]
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
        return BrainResult(text, used_provider, used_model, usage, cost, ttft_ms)


