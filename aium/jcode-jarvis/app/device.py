"""Device audio loop using arecord and aplay."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from typing import TYPE_CHECKING

from app.speech import rms_s16

if TYPE_CHECKING:
    from app.core import Core


def device_loop(core: Core, lang: str) -> None:
    """Run a blocking arecord capture loop and speak replies with aplay."""
    if not shutil.which("arecord"):
        raise SystemExit("arecord is not installed")
    core.set_session(True)
    print("Jarvis device mode. Speak. Ctrl+C to stop.")
    proc = subprocess.Popen(
        ["arecord", "-q", "-f", "S16_LE", "-r", "16000", "-c", "1", "-t", "raw"],
        stdout=subprocess.PIPE,
    )
    # 3200 bytes is 100 ms of 16 kHz mono PCM; 8 silent chunks end an utterance.
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


