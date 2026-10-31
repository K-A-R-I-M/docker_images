"""Local speech process supervision and health checks."""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core import Core

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


