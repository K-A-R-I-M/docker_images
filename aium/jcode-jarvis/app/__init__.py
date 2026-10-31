"""Jarvis application package.

jarvis.py parses args, builds Core, starts Supervisor, then calls api.serve.

  config      paths, defaults, persisted settings
  store       SQLite: sessions, turns, facts, events
  cost        token pricing
  language    FR/EN detection
  router      local intents handled before the cloud
  brain       jcode calls, prompt, provider fallback
  speech      whisper STT, Piper TTS, sentence streaming
  device      arecord/aplay loop for headless hardware
  supervisor  starts and restarts whisper and Piper
  api         HTTP endpoints and static files
  core        shared state that wires the modules above

Dependencies run one way: api -> core -> the rest. Modules must not import api.
"""
