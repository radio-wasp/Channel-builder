import sqlite3
import json
from pathlib import Path
from app.config import DB_PATH

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Settings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        
        # Channels table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                number INTEGER UNIQUE NOT NULL,
                logo_url TEXT,
                content_type TEXT NOT NULL DEFAULT 'tv', -- 'tv' or 'movie'
                selected_items TEXT NOT NULL DEFAULT '[]', -- JSON list of Jellyfin series/movie IDs
                commercial_source_type TEXT NOT NULL DEFAULT 'youtube', -- 'youtube' or 'local'
                commercial_source_value TEXT NOT NULL DEFAULT '', -- URL or folder path
                break_duration_seconds INTEGER NOT NULL DEFAULT 120, -- target 2 mins commercial break
                shuffle_mode BOOLEAN NOT NULL DEFAULT 1
            )
        """)
        
        # Commercial clips cache table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS commercial_clips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER,
                title TEXT,
                source_type TEXT,
                source_identifier TEXT, -- video_id or filename
                file_path TEXT NOT NULL,
                duration_seconds REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(channel_id) REFERENCES channels(id) ON DELETE CASCADE
            )
        """)
        
        # Schedules table (caches generated 24h/48h schedules)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schedules (
                channel_id INTEGER PRIMARY KEY,
                schedule_data TEXT NOT NULL, -- JSON array of scheduled slots
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(channel_id) REFERENCES channels(id) ON DELETE CASCADE
            )
        """)
        
        conn.commit()

# Settings helpers
def set_setting(key: str, value: str):
    with get_db() as conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        conn.commit()

def get_setting(key: str, default: str = "") -> str:
    with get_db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

def get_all_settings() -> dict:
    with get_db() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}

# Channel helpers
def create_channel(name: str, number: int, logo_url: str, content_type: str, selected_items: list, commercial_source_type: str, commercial_source_value: str, break_duration_seconds: int = 120, shuffle_mode: bool = True):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO channels (name, number, logo_url, content_type, selected_items, commercial_source_type, commercial_source_value, break_duration_seconds, shuffle_mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, number, logo_url, content_type, json.dumps(selected_items), commercial_source_type, commercial_source_value, break_duration_seconds, 1 if shuffle_mode else 0))
        conn.commit()
        return cursor.lastrowid

def update_channel(channel_id: int, name: str, number: int, logo_url: str, content_type: str, selected_items: list, commercial_source_type: str, commercial_source_value: str, break_duration_seconds: int = 120, shuffle_mode: bool = True):
    with get_db() as conn:
        conn.execute("""
            UPDATE channels
            SET name = ?, number = ?, logo_url = ?, content_type = ?, selected_items = ?, commercial_source_type = ?, commercial_source_value = ?, break_duration_seconds = ?, shuffle_mode = ?
            WHERE id = ?
        """, (name, number, logo_url, content_type, json.dumps(selected_items), commercial_source_type, commercial_source_value, break_duration_seconds, 1 if shuffle_mode else 0, channel_id))
        conn.commit()

def delete_channel(channel_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM channels WHERE id = ?", (channel_id,))
        conn.execute("DELETE FROM commercial_clips WHERE channel_id = ?", (channel_id,))
        conn.execute("DELETE FROM schedules WHERE channel_id = ?", (channel_id,))
        conn.commit()

def get_channels():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM channels ORDER BY number ASC").fetchall()
        channels = []
        for r in rows:
            c = dict(r)
            c["selected_items"] = json.loads(c["selected_items"])
            channels.append(c)
        return channels

def get_channel(channel_id: int):
    with get_db() as conn:
        r = conn.execute("SELECT * FROM channels WHERE id = ?", (channel_id,)).fetchone()
        if not r:
            return None
        c = dict(r)
        c["selected_items"] = json.loads(c["selected_items"])
        return c
