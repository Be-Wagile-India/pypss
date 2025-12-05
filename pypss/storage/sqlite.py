import sqlite3
import json
import time
from typing import Dict, List, Any, Optional
from .base import StorageBackend


class SQLiteStorage(StorageBackend):
    CURRENT_VERSION = 1

    def __init__(self, db_path: str = "pypss_history.db", retention_days: int = 90):
        self.db_path = db_path
        self.retention_days = retention_days
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Meta table for versioning
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS _meta (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)

            # Check version
            cursor.execute("SELECT value FROM _meta WHERE key='version'")
            row = cursor.fetchone()
            db_version = int(row[0]) if row else 0

            if db_version == 0:
                # First run, create tables
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS pss_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp REAL,
                        pss REAL,
                        ts REAL,
                        ms REAL,
                        ev REAL,
                        be REAL,
                        cc REAL,
                        meta TEXT
                    )
                """)
                cursor.execute(
                    "INSERT OR REPLACE INTO _meta (key, value) VALUES ('version', ?)",
                    (self.CURRENT_VERSION,),
                )

            elif db_version < self.CURRENT_VERSION:
                self._migrate(conn, db_version)

            conn.commit()

    def _migrate(self, conn, current_ver):
        """Handle schema migrations."""
        pass

    def prune(self, days: Optional[int] = None):
        """Remove records older than 'days'."""
        _days_to_prune: int = days if days is not None else self.retention_days
        if not _days_to_prune:
            return

        cutoff = time.time() - (_days_to_prune * 86400)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM pss_history WHERE timestamp < ?", (cutoff,))
            conn.commit()

    def save(
        self, report: Dict[str, Any], meta: Optional[Dict[str, Any]] = None
    ) -> None:
        # Auto-prune on save (keep DB healthy)
        self.prune()

        timestamp = time.time()
        meta_json = json.dumps(meta or {})

        # Extract sub-scores safely
        breakdown = report.get("breakdown", {})

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO pss_history (timestamp, pss, ts, ms, ev, be, cc, meta)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    timestamp,
                    report.get("pss", 0.0),
                    breakdown.get("timing_stability", 0.0),
                    breakdown.get("memory_stability", 0.0),
                    breakdown.get("error_volatility", 0.0),
                    breakdown.get("branching_entropy", 0.0),
                    breakdown.get("concurrency_chaos", 0.0),
                    meta_json,
                ),
            )
            conn.commit()

    def get_history(
        self, limit: int = 10, days: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM pss_history"
        params = []

        if days:
            cutoff = time.time() - (days * 86400)
            query += " WHERE timestamp >= ?"
            params.append(cutoff)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()

            history = []
            for row in rows:
                item = dict(row)
                try:
                    item["meta"] = json.loads(item["meta"])
                except Exception:
                    item["meta"] = {}
                history.append(item)
            return history
