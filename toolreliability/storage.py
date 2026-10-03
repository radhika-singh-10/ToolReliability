from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import RunSummary


class RunStore:
    """Durable run history behind a small storage boundary."""

    def __init__(self, path: str | Path = "data/toolreliability.db"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self):
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS evaluation_runs (
                    run_id TEXT PRIMARY KEY, agent TEXT NOT NULL, domains TEXT NOT NULL,
                    pass_rate REAL NOT NULL, average_score REAL NOT NULL,
                    p95_latency_ms REAL NOT NULL, result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def save_run(self, summary: RunSummary, domains: list[str]):
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO evaluation_runs(run_id, agent, domains, pass_rate, average_score, p95_latency_ms, result_json) VALUES(?,?,?,?,?,?,?)",
                (summary.run_id, summary.agent, json.dumps(domains), summary.pass_rate,
                 summary.average_score, summary.p95_latency_ms, summary.model_dump_json()),
            )

    def list_runs(self, limit: int = 25) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT run_id, agent, domains, pass_rate, average_score, p95_latency_ms, created_at FROM evaluation_runs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [{**dict(row), "domains": json.loads(row["domains"])} for row in rows]

    def get_run(self, run_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute("SELECT result_json FROM evaluation_runs WHERE run_id = ?", (run_id,)).fetchone()
        return json.loads(row["result_json"]) if row else None
