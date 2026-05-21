from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from runtime.taskframe import json_safe, utc_now

SCHEMA_VERSION = 2
DEFAULT_SQLITE_DB_PATH = Path("runtime_data") / "taskframe_runtime.db"

REQUIRED_TABLES = [
    "schema_meta",
    "taskframes",
    "events",
    "event_queue",
    "durable_event_queue",
    "run_ledger",
    "audit_events",
    "pending_actions",
    "executed_actions",
    "tool_calls",
    "llm_calls",
    "validations",
]

REQUIRED_INDEXES = [
    "idx_taskframes_manifest_state",
    "idx_taskframes_updated_at",
    "idx_events_type_status",
    "idx_events_linked_frame",
    "idx_event_queue_status",
    "idx_durable_queue_status",
    "idx_durable_queue_dedupe",
    "idx_durable_queue_event_id",
    "idx_run_ledger_frame",
    "idx_pending_actions_status",
    "idx_executed_actions_frame",
    "idx_audit_events_frame",
    "idx_tool_calls_frame",
    "idx_llm_calls_frame",
    "idx_validations_frame",
]

_SECRET_KEY_PARTS = (
    "token",
    "secret",
    "credential",
    "password",
    "oauth",
    "api_key",
    "apikey",
    "private_key",
    "confirmation_phrase",
    "confirm_phrase",
    "live_confirmation",
)


class _ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> bool:
        super().__exit__(exc_type, exc_value, traceback)
        self.close()
        return False


class SQLitePersistenceBackend:
    backend_name = "sqlite"

    def __init__(self, db_path: str | Path = DEFAULT_SQLITE_DB_PATH):
        self.db_path = Path(db_path)

    def init_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS schema_meta (
                  key TEXT PRIMARY KEY,
                  value TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS taskframes (
                  frame_id TEXT PRIMARY KEY,
                  manifest_id TEXT,
                  state TEXT,
                  created_at TEXT,
                  updated_at TEXT,
                  trigger_source TEXT,
                  trigger_event_type TEXT,
                  payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                  event_id TEXT PRIMARY KEY,
                  source TEXT,
                  event_type TEXT,
                  status TEXT,
                  received_at TEXT,
                  linked_frame_id TEXT,
                  payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS event_queue (
                  event_id TEXT PRIMARY KEY,
                  source TEXT,
                  event_type TEXT,
                  status TEXT,
                  received_at TEXT,
                  updated_at TEXT,
                  route_id TEXT,
                  manifest_id TEXT,
                  linked_frame_id TEXT,
                  duplicate INTEGER NOT NULL DEFAULT 0,
                  payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS run_ledger (
                  ledger_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  migration_key TEXT UNIQUE,
                  frame_id TEXT,
                  manifest_id TEXT,
                  state TEXT,
                  created_at TEXT,
                  updated_at TEXT,
                  recorded_at TEXT NOT NULL,
                  payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                  audit_id TEXT PRIMARY KEY,
                  frame_id TEXT,
                  event_type TEXT,
                  created_at TEXT,
                  payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS pending_actions (
                  action_id TEXT PRIMARY KEY,
                  frame_id TEXT,
                  tool TEXT,
                  status TEXT,
                  created_at TEXT,
                  updated_at TEXT,
                  payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS executed_actions (
                  action_id TEXT PRIMARY KEY,
                  frame_id TEXT,
                  tool TEXT,
                  status TEXT,
                  created_at TEXT,
                  updated_at TEXT,
                  payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tool_calls (
                  call_id TEXT PRIMARY KEY,
                  frame_id TEXT,
                  tool TEXT,
                  status TEXT,
                  created_at TEXT,
                  payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS llm_calls (
                  call_id TEXT PRIMARY KEY,
                  frame_id TEXT,
                  provider TEXT,
                  model TEXT,
                  status TEXT,
                  created_at TEXT,
                  payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS validations (
                  validation_id TEXT PRIMARY KEY,
                  frame_id TEXT,
                  validation_type TEXT,
                  ok INTEGER,
                  created_at TEXT,
                  payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_taskframes_manifest_state ON taskframes(manifest_id, state);
                CREATE INDEX IF NOT EXISTS idx_taskframes_updated_at ON taskframes(updated_at);
                CREATE INDEX IF NOT EXISTS idx_events_type_status ON events(event_type, status);
                CREATE INDEX IF NOT EXISTS idx_events_linked_frame ON events(linked_frame_id);
                CREATE INDEX IF NOT EXISTS idx_event_queue_status ON event_queue(status, updated_at);
                CREATE TABLE IF NOT EXISTS durable_event_queue (
                  queue_id TEXT PRIMARY KEY,
                  event_id TEXT,
                  source TEXT,
                  event_type TEXT,
                  status TEXT,
                  priority INTEGER NOT NULL DEFAULT 100,
                  attempt_count INTEGER NOT NULL DEFAULT 0,
                  max_attempts INTEGER NOT NULL DEFAULT 3,
                  available_at TEXT,
                  claimed_at TEXT,
                  claimed_by TEXT,
                  completed_at TEXT,
                  linked_frame_id TEXT,
                  dedupe_key TEXT,
                  last_error TEXT,
                  failure_category TEXT,
                  created_at TEXT,
                  updated_at TEXT,
                  payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_durable_queue_status ON durable_event_queue(status, priority, available_at);
                CREATE INDEX IF NOT EXISTS idx_durable_queue_dedupe ON durable_event_queue(dedupe_key, status);
                CREATE INDEX IF NOT EXISTS idx_durable_queue_event_id ON durable_event_queue(event_id);
                CREATE INDEX IF NOT EXISTS idx_run_ledger_frame ON run_ledger(frame_id, recorded_at);
                CREATE INDEX IF NOT EXISTS idx_pending_actions_status ON pending_actions(status, frame_id);
                CREATE INDEX IF NOT EXISTS idx_executed_actions_frame ON executed_actions(frame_id);
                CREATE INDEX IF NOT EXISTS idx_audit_events_frame ON audit_events(frame_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_tool_calls_frame ON tool_calls(frame_id);
                CREATE INDEX IF NOT EXISTS idx_llm_calls_frame ON llm_calls(frame_id);
                CREATE INDEX IF NOT EXISTS idx_validations_frame ON validations(frame_id);
                """
            )
            conn.execute(
                "INSERT OR REPLACE INTO schema_meta(key, value, updated_at) VALUES (?, ?, ?)",
                ("schema_version", str(SCHEMA_VERSION), utc_now()),
            )

    def save_taskframe(self, frame: dict[str, Any]) -> None:
        self.init_schema()
        clean = _sanitize_payload(frame)
        trigger = clean.get("trigger") if isinstance(clean.get("trigger"), dict) else {}
        frame_id = str(clean.get("frame_id", "") or "")
        if not frame_id:
            raise ValueError("frame_id is required.")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO taskframes(frame_id, manifest_id, state, created_at, updated_at, trigger_source, trigger_event_type, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(frame_id) DO UPDATE SET
                  manifest_id=excluded.manifest_id,
                  state=excluded.state,
                  created_at=excluded.created_at,
                  updated_at=excluded.updated_at,
                  trigger_source=excluded.trigger_source,
                  trigger_event_type=excluded.trigger_event_type,
                  payload_json=excluded.payload_json
                """,
                (
                    frame_id,
                    str(clean.get("manifest_id", "") or ""),
                    str(clean.get("state", "") or ""),
                    str(clean.get("created_at", "") or ""),
                    str(clean.get("updated_at", "") or ""),
                    str(trigger.get("source", "") or ""),
                    str(trigger.get("event_type", "") or ""),
                    _to_json(clean),
                ),
            )
            self._replace_frame_children(conn, frame_id, clean)

    def load_taskframe(self, frame_id: str) -> dict[str, Any] | None:
        self.init_schema()
        with self._connect() as conn:
            row = conn.execute("SELECT payload_json FROM taskframes WHERE frame_id = ?", (frame_id,)).fetchone()
        return _from_json(row["payload_json"]) if row else None

    def list_taskframes(self, limit: int = 100) -> list[dict[str, Any]]:
        self.init_schema()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM taskframes ORDER BY updated_at DESC, created_at DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [_from_json(row["payload_json"]) for row in rows]

    def append_event(self, event: dict[str, Any]) -> None:
        self.init_schema()
        clean = _sanitize_payload(event)
        event_id = str(clean.get("event_id", "") or "")
        if not event_id:
            return
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO events(event_id, source, event_type, status, received_at, linked_frame_id, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                  source=excluded.source,
                  event_type=excluded.event_type,
                  status=excluded.status,
                  received_at=excluded.received_at,
                  linked_frame_id=excluded.linked_frame_id,
                  payload_json=excluded.payload_json
                """,
                (
                    event_id,
                    str(clean.get("source", "") or ""),
                    str(clean.get("event_type", "") or ""),
                    str(clean.get("status", "") or ""),
                    str(clean.get("received_at", "") or ""),
                    clean.get("linked_frame_id"),
                    _to_json(clean),
                ),
            )

    def get_event(self, event_id: str) -> dict[str, Any] | None:
        self.init_schema()
        with self._connect() as conn:
            row = conn.execute("SELECT payload_json FROM events WHERE event_id = ?", (event_id,)).fetchone()
        return _from_json(row["payload_json"]) if row else None

    def list_events(self, limit: int = 100) -> list[dict[str, Any]]:
        self.init_schema()
        with self._connect() as conn:
            rows = conn.execute("SELECT payload_json FROM events ORDER BY received_at DESC LIMIT ?", (int(limit),)).fetchall()
        return [_from_json(row["payload_json"]) for row in rows]

    def save_queue_record(self, record: dict[str, Any]) -> None:
        self.init_schema()
        clean = _sanitize_payload(record)
        event_id = str(clean.get("event_id", "") or "")
        if not event_id:
            return
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO event_queue(event_id, source, event_type, status, received_at, updated_at, route_id, manifest_id, linked_frame_id, duplicate, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                  source=excluded.source,
                  event_type=excluded.event_type,
                  status=excluded.status,
                  received_at=excluded.received_at,
                  updated_at=excluded.updated_at,
                  route_id=excluded.route_id,
                  manifest_id=excluded.manifest_id,
                  linked_frame_id=excluded.linked_frame_id,
                  duplicate=excluded.duplicate,
                  payload_json=excluded.payload_json
                """,
                (
                    event_id,
                    str(clean.get("source", "") or ""),
                    str(clean.get("event_type", "") or ""),
                    str(clean.get("status", "") or ""),
                    str(clean.get("received_at", "") or ""),
                    str(clean.get("updated_at", "") or ""),
                    clean.get("route_id"),
                    clean.get("manifest_id"),
                    clean.get("linked_frame_id"),
                    1 if clean.get("duplicate") else 0,
                    _to_json(clean),
                ),
            )

    def get_queue_record(self, event_id: str) -> dict[str, Any] | None:
        self.init_schema()
        with self._connect() as conn:
            row = conn.execute("SELECT payload_json FROM event_queue WHERE event_id = ?", (event_id,)).fetchone()
        return _from_json(row["payload_json"]) if row else None

    def list_queue_records(self, limit: int = 100, **filters: Any) -> list[dict[str, Any]]:
        self.init_schema()
        where: list[str] = []
        params: list[Any] = []
        for key in ("status", "source", "event_type"):
            value = filters.get(key)
            if value:
                where.append(f"{key} = ?")
                params.append(value)
        sql = "SELECT payload_json FROM event_queue"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY received_at DESC, updated_at DESC LIMIT ?"
        params.append(int(limit))
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_from_json(row["payload_json"]) for row in rows]

    def save_durable_queue_record(self, record: dict[str, Any]) -> None:
        self.init_schema()
        clean = _sanitize_payload(record)
        queue_id = str(clean.get("queue_id", "") or "")
        if not queue_id:
            return
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO durable_event_queue(
                  queue_id, event_id, source, event_type, status, priority, attempt_count,
                  max_attempts, available_at, claimed_at, claimed_by, completed_at,
                  linked_frame_id, dedupe_key, last_error, failure_category,
                  created_at, updated_at, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(queue_id) DO UPDATE SET
                  event_id=excluded.event_id,
                  source=excluded.source,
                  event_type=excluded.event_type,
                  status=excluded.status,
                  priority=excluded.priority,
                  attempt_count=excluded.attempt_count,
                  max_attempts=excluded.max_attempts,
                  available_at=excluded.available_at,
                  claimed_at=excluded.claimed_at,
                  claimed_by=excluded.claimed_by,
                  completed_at=excluded.completed_at,
                  linked_frame_id=excluded.linked_frame_id,
                  dedupe_key=excluded.dedupe_key,
                  last_error=excluded.last_error,
                  failure_category=excluded.failure_category,
                  created_at=excluded.created_at,
                  updated_at=excluded.updated_at,
                  payload_json=excluded.payload_json
                """,
                (
                    queue_id,
                    str(clean.get("event_id", "") or ""),
                    str(clean.get("source", "") or ""),
                    str(clean.get("event_type", "") or ""),
                    str(clean.get("status", "") or ""),
                    int(clean.get("priority", 100) or 100),
                    int(clean.get("attempt_count", 0) or 0),
                    int(clean.get("max_attempts", 3) or 3),
                    str(clean.get("available_at", "") or ""),
                    str(clean.get("claimed_at", "") or ""),
                    str(clean.get("claimed_by", "") or ""),
                    str(clean.get("completed_at", "") or ""),
                    str(clean.get("linked_frame_id", "") or ""),
                    str(clean.get("dedupe_key", "") or ""),
                    str(clean.get("last_error", "") or ""),
                    str(clean.get("failure_category", "") or ""),
                    str(clean.get("created_at", "") or ""),
                    str(clean.get("updated_at", "") or ""),
                    _to_json(clean),
                ),
            )

    def get_durable_queue_record(self, queue_id: str) -> dict[str, Any] | None:
        self.init_schema()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM durable_event_queue WHERE queue_id = ?", (queue_id,)
            ).fetchone()
        return _from_json(row["payload_json"]) if row else None

    def list_durable_queue_records(self, limit: int = 100, **filters: Any) -> list[dict[str, Any]]:
        self.init_schema()
        where: list[str] = []
        params: list[Any] = []
        for key in ("status", "source", "event_type"):
            value = filters.get(key)
            if value:
                where.append(f"{key} = ?")
                params.append(value)
        sql = "SELECT payload_json FROM durable_event_queue"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY priority ASC, available_at ASC, created_at ASC LIMIT ?"
        params.append(int(limit))
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_from_json(row["payload_json"]) for row in rows]

    def append_run_ledger_record(self, record: dict[str, Any]) -> None:
        self.init_schema()
        clean = _sanitize_payload(record)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO run_ledger(frame_id, manifest_id, state, created_at, updated_at, recorded_at, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(clean.get("frame_id", "") or ""),
                    str(clean.get("manifest_id", "") or ""),
                    str(clean.get("state", "") or ""),
                    str(clean.get("created_at", "") or ""),
                    str(clean.get("updated_at", "") or ""),
                    utc_now(),
                    _to_json(clean),
                ),
            )

    def list_run_ledger_records(self, limit: int = 100) -> list[dict[str, Any]]:
        self.init_schema()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM run_ledger ORDER BY ledger_id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        records = [_from_json(row["payload_json"]) for row in rows]
        records.reverse()
        return records

    def health(self) -> dict[str, Any]:
        exists = self.db_path.is_file()
        if not exists:
            return {
                "ok": False,
                "backend": self.backend_name,
                "sqlite_path": str(self.db_path),
                "db_exists": False,
                "schema_version": None,
                "taskframe_count": 0,
                "event_count": 0,
                "run_ledger_count": 0,
                "last_write_timestamp": "",
            }
        self.init_schema()
        with self._connect() as conn:
            version = conn.execute("SELECT value FROM schema_meta WHERE key = 'schema_version'").fetchone()
            taskframes = conn.execute("SELECT COUNT(*) AS count FROM taskframes").fetchone()["count"]
            events = conn.execute("SELECT COUNT(*) AS count FROM events").fetchone()["count"]
            ledger = conn.execute("SELECT COUNT(*) AS count FROM run_ledger").fetchone()["count"]
            last = conn.execute(
                """
                SELECT MAX(ts) AS last_write FROM (
                  SELECT MAX(updated_at) AS ts FROM taskframes
                  UNION ALL SELECT MAX(received_at) AS ts FROM events
                  UNION ALL SELECT MAX(recorded_at) AS ts FROM run_ledger
                )
                """
            ).fetchone()["last_write"]
        return {
            "ok": True,
            "backend": self.backend_name,
            "sqlite_path": str(self.db_path),
            "db_exists": True,
            "schema_version": int(version["value"]) if version else None,
            "taskframe_count": int(taskframes),
            "event_count": int(events),
            "run_ledger_count": int(ledger),
            "last_write_timestamp": str(last or ""),
        }

    def verify_schema(self) -> dict[str, Any]:
        self.init_schema()
        with self._connect() as conn:
            tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}
            indexes = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'index'").fetchall()}
            version = conn.execute("SELECT value FROM schema_meta WHERE key = 'schema_version'").fetchone()
            malformed = 0
            for table in ("taskframes", "events", "event_queue", "durable_event_queue", "run_ledger"):
                for row in conn.execute(f"SELECT payload_json FROM {table}").fetchall():
                    try:
                        parsed = json.loads(row["payload_json"])
                        if not isinstance(parsed, dict):
                            malformed += 1
                    except json.JSONDecodeError:
                        malformed += 1
        missing_tables = [name for name in REQUIRED_TABLES if name not in tables]
        missing_indexes = [name for name in REQUIRED_INDEXES if name not in indexes]
        ok = not missing_tables and not missing_indexes and malformed == 0 and int(version["value"] if version else 0) == SCHEMA_VERSION
        return {
            "ok": ok,
            "schema_version": int(version["value"]) if version else None,
            "required_schema_version": SCHEMA_VERSION,
            "missing_tables": missing_tables,
            "missing_indexes": missing_indexes,
            "malformed_record_count": malformed,
        }

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), factory=_ClosingConnection)
        conn.row_factory = sqlite3.Row
        return conn

    def _replace_frame_children(self, conn: sqlite3.Connection, frame_id: str, frame: dict[str, Any]) -> None:
        for table in ("audit_events", "pending_actions", "executed_actions", "tool_calls", "llm_calls", "validations"):
            conn.execute(f"DELETE FROM {table} WHERE frame_id = ?", (frame_id,))
        now = str(frame.get("updated_at") or utc_now())
        for index, item in enumerate(list(frame.get("audit") or [])):
            if not isinstance(item, dict):
                continue
            audit_id = f"{frame_id}:audit:{index}"
            conn.execute(
                "INSERT INTO audit_events(audit_id, frame_id, event_type, created_at, payload_json) VALUES (?, ?, ?, ?, ?)",
                (audit_id, frame_id, str(item.get("event_type", "") or ""), str(item.get("timestamp", "") or now), _to_json(item)),
            )
        for table, items, key_name in (
            ("pending_actions", list(frame.get("pending_actions") or []), "action_id"),
            ("executed_actions", list(frame.get("executed_actions") or []), "action_id"),
        ):
            for index, item in enumerate(items):
                if not isinstance(item, dict):
                    continue
                action_id = str(item.get(key_name, "") or f"{frame_id}:{table}:{index}")
                conn.execute(
                    f"INSERT INTO {table}(action_id, frame_id, tool, status, created_at, updated_at, payload_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        action_id,
                        frame_id,
                        str(item.get("tool", "") or item.get("tool_key", "") or ""),
                        str(item.get("status", "") or ""),
                        str(item.get("created_at", "") or item.get("staged_at", "") or now),
                        str(item.get("updated_at", "") or item.get("executed_at", "") or now),
                        _to_json(item),
                    ),
                )
        for table, items, id_key in (
            ("tool_calls", list(frame.get("tool_calls") or []), "call_id"),
            ("llm_calls", list(frame.get("llm_calls") or []), "call_id"),
            ("validations", list(frame.get("validations") or []), "validation_id"),
        ):
            for index, item in enumerate(items):
                if not isinstance(item, dict):
                    continue
                row_id = str(item.get(id_key, "") or f"{frame_id}:{table}:{index}")
                if table == "tool_calls":
                    conn.execute(
                        "INSERT INTO tool_calls(call_id, frame_id, tool, status, created_at, payload_json) VALUES (?, ?, ?, ?, ?, ?)",
                        (row_id, frame_id, str(item.get("tool", "") or item.get("tool_key", "") or ""), str(item.get("status", "") or ""), str(item.get("created_at", "") or now), _to_json(item)),
                    )
                elif table == "llm_calls":
                    conn.execute(
                        "INSERT INTO llm_calls(call_id, frame_id, provider, model, status, created_at, payload_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (row_id, frame_id, str(item.get("provider", "") or ""), str(item.get("model", "") or ""), str(item.get("status", "") or ""), str(item.get("created_at", "") or now), _to_json(item)),
                    )
                else:
                    conn.execute(
                        "INSERT INTO validations(validation_id, frame_id, validation_type, ok, created_at, payload_json) VALUES (?, ?, ?, ?, ?, ?)",
                        (row_id, frame_id, str(item.get("validation_type", "") or item.get("type", "") or ""), 1 if item.get("ok") else 0, str(item.get("created_at", "") or now), _to_json(item)),
                    )


def _to_json(payload: Any) -> str:
    return json.dumps(json_safe(payload), ensure_ascii=False, sort_keys=True)


def _from_json(payload: str) -> dict[str, Any]:
    raw = json.loads(payload)
    return dict(raw) if isinstance(raw, dict) else {}


def _sanitize_payload(value: Any, key: str = "") -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            child_key = str(raw_key)
            lowered = child_key.lower()
            if any(part in lowered for part in _SECRET_KEY_PARTS):
                sanitized[child_key] = "[REDACTED]"
            elif lowered in {"browser_profile_path", "chrome_profile_path", "profile_path"}:
                sanitized[child_key] = "[SANITIZED_PATH_REF]"
            else:
                sanitized[child_key] = _sanitize_payload(raw_value, child_key)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_payload(item, key) for item in value]
    return json_safe(value)
