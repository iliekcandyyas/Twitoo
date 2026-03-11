import sqlite3
import os
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "guardian.db")

class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS flagged_users (
                user_id TEXT PRIMARY KEY,
                reason TEXT NOT NULL,
                confidence INTEGER DEFAULT 5,
                reported_by_guild TEXT,
                reported_by_user TEXT,
                flagged_at TEXT,
                status TEXT DEFAULT 'pending'
            );

            CREATE TABLE IF NOT EXISTS review_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                guild_id TEXT NOT NULL,
                submitted_by TEXT NOT NULL,
                evidence TEXT,
                submitted_at TEXT,
                status TEXT DEFAULT 'pending'
            );

            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id TEXT PRIMARY KEY,
                alert_channel TEXT,
                auto_ban_threshold INTEGER DEFAULT 9,
                auto_kick_threshold INTEGER DEFAULT 7
            );
        """)
        self.conn.commit()

    # --- Flagged Users ---

    def flag_user(self, user_id: str, reason: str, confidence: int,
                  reported_by_guild: str, reported_by_user: str):
        self.conn.execute("""
            INSERT INTO flagged_users (user_id, reason, confidence, reported_by_guild, reported_by_user, flagged_at, status)
            VALUES (?, ?, ?, ?, ?, ?, 'pending')
            ON CONFLICT(user_id) DO UPDATE SET
                reason = excluded.reason,
                confidence = excluded.confidence,
                reported_by_guild = excluded.reported_by_guild,
                reported_by_user = excluded.reported_by_user,
                flagged_at = excluded.flagged_at
        """, (user_id, reason, confidence, reported_by_guild, reported_by_user, datetime.utcnow().isoformat()))
        self.conn.commit()

    def get_flag(self, user_id: str):
        row = self.conn.execute(
            "SELECT * FROM flagged_users WHERE user_id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else None

    def unflag_user(self, user_id: str):
        self.conn.execute("DELETE FROM flagged_users WHERE user_id = ?", (user_id,))
        self.conn.commit()

    def get_all_flags(self, status: str = None):
        if status:
            rows = self.conn.execute(
                "SELECT * FROM flagged_users WHERE status = ? ORDER BY flagged_at DESC", (status,)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM flagged_users ORDER BY flagged_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def update_flag_status(self, user_id: str, status: str):
        self.conn.execute(
            "UPDATE flagged_users SET status = ? WHERE user_id = ?", (status, user_id)
        )
        self.conn.commit()

    # --- Review Queue ---

    def add_to_review(self, user_id: str, guild_id: str, submitted_by: str, evidence: str):
        self.conn.execute("""
            INSERT INTO review_queue (user_id, guild_id, submitted_by, evidence, submitted_at, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
        """, (user_id, guild_id, submitted_by, evidence, datetime.utcnow().isoformat()))
        self.conn.commit()

    def get_review_queue(self, status: str = "pending"):
        rows = self.conn.execute(
            "SELECT * FROM review_queue WHERE status = ? ORDER BY submitted_at ASC", (status,)
        ).fetchall()
        return [dict(r) for r in rows]

    def update_review_status(self, review_id: int, status: str):
        self.conn.execute(
            "UPDATE review_queue SET status = ? WHERE id = ?", (status, review_id)
        )
        self.conn.commit()

    # --- Guild Settings ---

    def get_guild_settings(self, guild_id: str):
        row = self.conn.execute(
            "SELECT * FROM guild_settings WHERE guild_id = ?", (guild_id,)
        ).fetchone()
        if not row:
            self.conn.execute(
                "INSERT INTO guild_settings (guild_id) VALUES (?)", (guild_id,)
            )
            self.conn.commit()
            return {"guild_id": guild_id, "alert_channel": None,
                    "auto_ban_threshold": 9, "auto_kick_threshold": 7}
        return dict(row)

    def set_alert_channel(self, guild_id: str, channel_name: str):
        self.conn.execute("""
            INSERT INTO guild_settings (guild_id, alert_channel)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET alert_channel = excluded.alert_channel
        """, (guild_id, channel_name))
        self.conn.commit()