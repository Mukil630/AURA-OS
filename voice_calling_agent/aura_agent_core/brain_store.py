"""
AURA Persistent SQLite FTS5 Brain Store
File: aura/memory/brain_store.py
Reverse-engineered from Google Antigravity (AGY) conversation_summaries.db:
- Preserves complete multi-session conversation history across CLI restarts.
- Uses SQLite FTS5 (Full-Text Search) with BM25 ranking for sub-millisecond context retrieval.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import os
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

DB_PATH = Path(__file__).resolve().parent / "aura_brain.db"


class BrainStore:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initializes tables and FTS5 full-text index."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Sessions Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                title TEXT DEFAULT 'Untitled Session',
                turn_count INTEGER DEFAULT 0
            );
            """)

            # 2. Conversational Turns Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            );
            """)

            # 3. FTS5 Virtual Table for Instant Search
            cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS brain_fts USING fts5(
                session_id,
                role,
                content,
                tokenize='unicode61'
            );
            """)
            conn.commit()

    def log_turn(self, session_id: str, role: str, content: str):
        """Logs a single conversation turn and indexes it into FTS5."""
        if not content.strip():
            return

        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Ensure session exists
            cursor.execute("""
            INSERT OR IGNORE INTO sessions (session_id, title) VALUES (?, ?);
            """, [session_id, f"Session {datetime.now().strftime('%d %b %H:%M')}"])

            # Insert turn
            cursor.execute("""
            INSERT INTO turns (session_id, role, content) VALUES (?, ?, ?);
            """, [session_id, role, content])

            # Increment turn count
            cursor.execute("""
            UPDATE sessions SET turn_count = turn_count + 1 WHERE session_id = ?;
            """, [session_id])

            # Index into FTS5
            cursor.execute("""
            INSERT INTO brain_fts (session_id, role, content) VALUES (?, ?, ?);
            """, [session_id, role, content])

            conn.commit()

    def search_brain(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Searches past memory using SQLite FTS5 BM25 relevance ranking."""
        clean_q = query.replace('"', '').replace("'", "").strip()
        if not clean_q:
            return []

        results = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                # FTS5 match query
                cursor.execute("""
                SELECT session_id, role, content, rank
                FROM brain_fts
                WHERE brain_fts MATCH ?
                ORDER BY rank
                LIMIT ?;
                """, [f'"{clean_q}"', limit])

                for row in cursor.fetchall():
                    results.append({
                        "session_id": row["session_id"],
                        "role": row["role"],
                        "content": row["content"],
                        "score": round(row["rank"], 4)
                    })
            except sqlite3.OperationalError:
                # Fallback to standard LIKE if query syntax fails
                cursor.execute("""
                SELECT session_id, role, content
                FROM turns
                WHERE content LIKE ?
                ORDER BY id DESC
                LIMIT ?;
                """, [f"%{clean_q}%", limit])
                for row in cursor.fetchall():
                    results.append({
                        "session_id": row["session_id"],
                        "role": row["role"],
                        "content": row["content"],
                        "score": 0.0
                    })
        return results

    def get_recent_turns(self, session_id: str, limit: int = 8) -> List[Dict[str, Any]]:
        """Retrieves latest turns for the current active session."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT role, content, created_at
            FROM turns
            WHERE session_id = ?
            ORDER BY id DESC
            LIMIT ?;
            """, [session_id, limit])
            rows = cursor.fetchall()
            return [{"role": r["role"], "content": r["content"], "created_at": r["created_at"]} for r in reversed(rows)]


# Global Brain Store Singleton
brain_store = BrainStore()
