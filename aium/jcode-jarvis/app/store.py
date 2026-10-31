"""SQLite storage for turns, facts, sessions, and events."""
from __future__ import annotations

import re
import sqlite3
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

from app.config import now_iso

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
            # FTS5 is optional; fall back to LIKE on builds without it.
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
        # Only one session is open; opening a new one closes the previous.
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
            # Copy totals onto the session row so cost reads stay one query.
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
        # Newest last, so the panel appends without reversing.
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
        # Bucket by the host's local date; stored timestamps keep their offset.
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


