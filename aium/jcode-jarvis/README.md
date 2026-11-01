# jcode-jarvis

A voice-first companion with a control panel: local speech, local memory, and
a modular cloud brain. Audio never leaves the container.

- Local STT: whisper.cpp `base` (default) or `tiny` (`JARVIS_PROFILE=low`).
- Local TTS: Piper, one English and one French voice; can be switched off.
- Local router and SQLite memory for small intents, facts, and the last turns.
- Cloud brain: jcode with any configured provider/model. DeepSeek by default.
- Browser and device audio adapters from the same core.
- Panel: live transcript, turn timings, health, events, memory, cost, logs.

## Build

```sh
podman build -t localhost/jcode-jarvis ./aium/jcode-jarvis
```

Multi-arch:

```sh
podman build --platform linux/amd64,linux/arm64 \
  -t localhost/jcode-jarvis ./aium/jcode-jarvis
```

Build inputs are pinned: jcode `v0.99.1`, whisper.cpp `v1.9.5`, Piper
`1.8.0`, and SHA-256 checksums for the Whisper and Piper models.

## Run, browser mode

```sh
podman volume create jcode-jarvis-data

podman run --rm -it --name jcode-jarvis \
  -p 127.0.0.1:8765:8765 \
  -v jcode-jarvis-data:/data \
  -e DEEPSEEK_API_KEY="your-key" \
  localhost/jcode-jarvis
```

Open <http://localhost:8765>. Press Start or `Space` to start a session. Press
again, or say "goodbye", to end it. The microphone requires `localhost` or
HTTPS. For a phone or another machine, put the container behind HTTPS or a
Tailscale address, and set `JARVIS_TOKEN`:

```sh
-e JARVIS_TOKEN="a-long-random-value" -p 0.0.0.0:8765:8765
```

The panel keeps Now and Live on screen: transcript, per-turn timings, health,
and events. Tabs cover Brain (provider/model), Voice (language, voices, mic
device, browser mic diagnostics), Memory (facts, add, forget, export), Cost
(today, session, last turn, 7-day chart, recent turns), System (versions,
uptime, database size, token, export), and Logs (filterable events). The token
is saved in System.

Diagrams: when the user explicitly asks for a schema or a diagram, Jarvis may
reply with one fenced mermaid block. The transcript renders it locally with the
vendored `web/vendor/mermaid.min.js`, fetched only when a diagram appears; nothing
is fetched from the internet, and the block is never spoken. Each rendered
diagram has a Copy source button that copies the original mermaid text. All
other replies stay plain text.

## Run, device mode

Linux host with `/dev/snd`:

```sh
podman run --rm -it --name jcode-jarvis \
  --device /dev/snd --group-add keep-groups \
  -v jcode-jarvis-data:/data \
  -e DEEPSEEK_API_KEY="your-key" \
  localhost/jcode-jarvis \
  python3 /opt/jarvis/jarvis.py --device --lang auto
```

`arecord` starts listening when the process starts. `Ctrl+C` ends it. On
Windows and macOS, use browser mode; Podman there does not pass host audio.

## Brain

The brain is a provider/model pair, not a fixed DeepSeek call. The image ships
`config/brain.toml` with DeepSeek as the default. The Brain tab lists providers and
models from jcode, and can Apply or Test a switch. The same values can be set by
environment:

```sh
-e JARVIS_BRAIN_PROVIDER=deepseek
-e JARVIS_BRAIN_MODEL=deepseek-v4-flash
```

The Brain tab can also allow skills. That exposes jcode's skill loader only, so
the assistant can load a skill's instructions when you name one; it still has no
shell, browser, or file tools. Off by default.

The selected pair is written to `/data/brain.toml`. A fallback list is
supported:

```toml
[brain]
backend = "jcode"
provider = "deepseek"
model = "deepseek-v4-flash"
fallback = ["openrouter:some-model", "ollama:qwen2.5:1.5b"]
timeout_ms = 30000
```

Provider credentials come from environment variables or Podman secrets. For
OpenAI-compatible endpoints, add a jcode provider profile:

```sh
podman exec -it jcode-jarvis jcode provider add
```

The core always calls jcode with `--disable-base-tools`, so voice input cannot
run commands.

## Privacy

- Audio stays in the container. Only text, persona, and selected memory facts go
  to the configured provider.
- Telemetry and auto-update are disabled.
- The data volume is `0700`. Use host disk encryption for data at rest.
- `Forget all` in the Info drawer deletes facts, turns, and events.
- When the cloud is unavailable, local intents and memory still work. An
  open-ended turn reports "cloud unavailable" instead of failing silently.

## Cost

The Cost tab shows:

- last turn and session cost, computed from tokens and `config/pricing.json`;
- today, month, all-time local spend and provider balance from
  `jcode usage --json`.

Edit `config/pricing.json` inside the image or bake your own rates. Unknown models show
tokens without a dollar amount. Local speech is free.

## Profiles and tuning

| Variable | Default | Meaning |
|---|---|---|
| `JARVIS_PROFILE` | `standard` | `standard` uses whisper `base`; `low` uses `tiny` |
| `JARVIS_WHISPER_THREADS` | `4` | whisper.cpp threads |
| `JARVIS_SPEECH_TIMEOUT` | `35` | seconds for STT/TTS requests |
| `JARVIS_TOKEN` | empty | require a bearer token on the API |
| `JARVIS_BRAIN_PROVIDER` | `deepseek` | override provider |
| `JARVIS_BRAIN_MODEL` | `deepseek-v4-flash` | override model |
| `JARVIS_HOST` / `JARVIS_PORT` | `127.0.0.1` / `8765` | bind address |

## API

Read-only data for the panel, all authenticated when `JARVIS_TOKEN` is set:

| Route | Purpose |
|---|---|
| `GET /api/status` | state, session, turns, facts, cost, spend today, uptime, version, arch |
| `GET /api/health` | whisper, piper, jcode, db, brain |
| `GET /api/history?limit=50&all=0` | recent turns with timings, tokens, cost |
| `GET /api/cost?days=7` | per-day cost, today, session, last turn |
| `GET /api/events` | recent supervisor and request events |
| `GET /api/facts?limit=50` | stored facts plus the total `count` |
| `GET/POST /api/settings` | `tts`, `lang`, `voice_en`, `voice_fr`, `silence_ms` (persisted to `/data/settings.json`) |
| `GET /api/export?what=all\|facts\|turns` | JSON download |
| `POST /api/facts`, `POST /api/facts/forget` | add a fact, delete one by id |
| `POST /api/turn?stream=1` | SSE turn: transcript, stage, delta, sentence, done |

Speech settings apply to the next turn. `tts: false` keeps text replies and
silences server synthesis. `silence_ms` is how long the browser waits after you
stop talking before it ends the turn; it applies immediately and is clamped to
600-4000 ms.

## Tests

```sh
cd aium/jcode-jarvis
python3 -m pip install -r requirements-dev.txt
python3 -m pytest
```

The suite covers language detection, the FR/EN router, SQLite memory and cost
queries, settings, sentence streaming, WAV framing, cost calculation, the voice
path, and the mermaid speech filter. It does not need a microphone, Piper,
Whisper, or network.

## Limits

- The cloud brain is required for open-ended conversation. Local mode covers
  intents and memory only.
- Browser microphone access needs `localhost` or HTTPS.
- The first run downloads nothing at runtime; models are baked into the image.
- The image does not yet wire into `run.ps1` or CI. That is outside this
  directory's v1 scope.

## Files

```
Dockerfile           multi-arch image build
jarvis.py            entrypoint: args, core, supervisor, server
app/                 Python package; app/__init__.py lists every module by role
web/                 browser client
web/index.html       panel markup
web/styles.css       panel styles
web/js/app.js        entry module: tabs, wiring, polling
web/js/core.js       shared state, DOM helpers, formatting, API client
web/js/ui.js         status chip, banner, stage timer
web/js/audio.js      microphone, VAD, playback, speech fallback
web/js/transcript.js messages, rich text, breakdown
web/js/diagrams.js   lazy mermaid renderer
web/js/turn.js       SSE turn and cancellation
web/js/panels-system.js status, health, events, logs, history
web/js/panels-config.js brain, voice, memory, cost, microphones
web/vendor/          vendored mermaid build for local diagram rendering
persona/AGENTS.md    companion persona (also installed as /root/AGENTS.md)
config/config.toml   minimal jcode provider config
config/brain.toml    default provider/model/fallback
config/pricing.json  editable per-model rates
tests/               pytest suite
pyproject.toml       pytest settings
requirements-dev.txt test dependency
NOTICE               bundled licenses
```
