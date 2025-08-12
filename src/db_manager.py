import sqlite3
import threading
import json
from datetime import datetime

class DBManager:
    def __init__(self, path="query_logs.db"):
        self.path = path
        self._lock = threading.Lock()
        self._ensure_table()

    def _ensure_table(self):
        with sqlite3.connect(self.path) as con:
            con.execute("""
            CREATE TABLE IF NOT EXISTS query_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT,
                session_id TEXT,
                user_input TEXT,
                intent TEXT,
                entities TEXT,
                nlp_result TEXT,
                odoo_success INTEGER,
                odoo_error TEXT,
                processing_time_ms INTEGER
            )
            """)
            con.commit()

    def log_query(self, session_id, user_input, intent, entities, nlp_result,
                  odoo_success, odoo_error, processing_time_ms):
        with self._lock, sqlite3.connect(self.path) as con:
            con.execute("""
                INSERT INTO query_logs
                (ts, session_id, user_input, intent, entities,
                 nlp_result, odoo_success, odoo_error, processing_time_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.utcnow().isoformat(),
                session_id,
                user_input,
                intent,
                json.dumps(entities),
                json.dumps(nlp_result),
                1 if odoo_success else 0,
                odoo_error or None,
                processing_time_ms
            ))
            con.commit()
