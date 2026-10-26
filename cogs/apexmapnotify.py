import asyncio
import os
import sqlite3
import traceback
from typing import Optional

import aiohttp
import discord
from discord.ext import commands, tasks


DB_PATH = "gridguardian.db"
API_URL = "https://api.apexlegendsstatus.com/maprotation"


class ApexMapNotify(commands.Cog):
    """Automatic Apex Legends map rotation notifications."""

    def __init__(self, bot):
        self.bot = bot
        self.api_key = os.getenv("APEX_API_KEY")
        self._init_database()
        self.map_check_loop.start()

    # =========================================================
    # DATABASE
    # =========================================================

    def _get_db(self):
        db = sqlite3.connect(
            DB_PATH,
            timeout=30,
            check_same_thread=False,
        )
        db.execute("PRAGMA busy_timeout = 30000")
        db.execute("PRAGMA journal_mode = WAL")
        db.execute("PRAGMA synchronous = NORMAL")
        return db

    def _init_database(self):
        with self._get_db() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS apex_map_notifications (
                    guild_id INTEGER PRIMARY KEY,
                    channel_id INTEGER NOT NULL,
                    pubs_code TEXT,
                    ranked_code TEXT
                )
            """)

    def _get_settings(self, guild_id: int):
        with self._get_db() as db:
            cursor = db.execute("""
                SELECT channel_id, pubs_code, ranked_code
                FROM apex_map_notifications
                WHERE guild_id = ?
            """, (guild_id,))
            return cursor.fetchone()

    def _set_settings(
        self,
        guild_id: int,
        channel_id: int,
        pubs_code: Optional[str],
        ranked_code: Optional[str],
    ):
        with self._get_db() as db:
            db.execute("""
                INSERT INTO apex_map_notifications
                    (guild_id, channel_id, pubs_code, ranked_code)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id)
                DO UPDATE SET
                    channel_id = excluded.channel_id,
                    pubs_code = excluded.pubs_code,
                    ranked_code = excluded.ranked_code
            """, (guild_id, channel_id, pubs_code, ranked_code))

    def _disable_settings(self, guild_id: int):
        with self._get_db() as db:
            db.execute(
                "DELETE FROM apex_map_notifications WHERE guild_id = ?",
                (guild_id,),
            )

    # =========================================================
    # API
    # =========================================================

    async def _get_rotation(self):
        if not self.api_key:
            print(
                "[ApexMapNotify] APEX_API_KEY is not configured. "
                "Set it in the host's private environment settings."
            )
            return None