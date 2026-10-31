"""HTTP API and static file serving on the standard library server."""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app.config import ROOT, VERSION, save_brain
from app.core import BusyError, Core
from app.speech import SpeechError
from app.supervisor import run_lines

MAX_BODY = 16 * 1024 * 1024

class BodyTooLarge(Exception):
    pass


def serve(core: Core, host: str, port: int) -> None:
    Handler.core = core
    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    print(f"Jarvis listening on http://{host}:{port}  data={core.data_dir}")
    print(f"brain={core.brain_config.get('provider')}/{core.brain_config.get('model')}  profile={core.profile}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


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
        if path == "/vendor/mermaid.min.js":
            try:
                body = (ROOT / "vendor" / "mermaid.min.js").read_bytes()
            except OSError:
                self._send_json(404, {"error": "not found"})
                return
            self._send_bytes(200, body, "text/javascript; charset=utf-8")
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
            query = urllib.parse.parse_qs(parsed.query)
            limit = max(1, min(200, self._query_int(query, "limit", 50)))
            self._send_json(200, {
                "facts": self.core.store.recall("", limit),
                "count": self.core.store.facts_count(),
            })
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
                enabled = data.get("enabled")
                if not isinstance(enabled, bool):
                    self._send_json(400, {"error": "enabled must be a boolean"})
                    return
                self.core.set_session(enabled)
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
                text = data.get("text")
                if not isinstance(text, str) or not text.strip():
                    self._send_json(400, {"error": "text must be a non-empty string"})
                    return
                result = self.core.turn(text=text, lang=data.get("lang", "auto"))
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
                text = data.get("text")
                if not isinstance(text, str) or not text.strip():
                    self._send_json(400, {"error": "text must be a non-empty string"})
                    return
                audio = self.core.speech.synthesize(text, lang)
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
                    self.core.last_turn = None
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
        except ValueError as exc:
            self._send_json(400, {"error": str(exc) or "invalid request"})
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

        if pcm is not None:
            if len(pcm) < 3200:
                self._send_json(400, {"error": "audio is too short"})
                return
        else:
            if not isinstance(text, str):
                self._send_json(400, {"error": "text must be a string"})
                return
            if not text.strip():
                self._send_json(400, {"error": "text is required"})
                return

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


