import os
import sqlite3
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
            check_same_thread=False
        )

        db.execute("PRAGMA busy_timeout = 30000")
        db.execute("PRAGMA journal_mode = WAL")
        db.execute("PRAGMA synchronous = NORMAL")

        return db

    def _init_database(self):
        db = self._get_db()
        cursor = db.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS apex_map_notifications (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER NOT NULL,
                pubs_code TEXT,
                ranked_code TEXT
            )
        """)

        db.commit()
        db.close()

    def _get_settings(self, guild_id: int):
        db = self._get_db()
        cursor = db.cursor()

        cursor.execute("""
            SELECT channel_id, pubs_code, ranked_code
            FROM apex_map_notifications
            WHERE guild_id = ?
        """, (guild_id,))

        row = cursor.fetchone()

        db.close()

        return row

    def _set_settings(
        self,
        guild_id: int,
        channel_id: int,
        pubs_code: Optional[str],
        ranked_code: Optional[str]
    ):
        db = self._get_db()
        cursor = db.cursor()

        cursor.execute("""
            INSERT INTO apex_map_notifications
                (guild_id, channel_id, pubs_code, ranked_code)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id)
            DO UPDATE SET
                channel_id = excluded.channel_id,
                pubs_code = excluded.pubs_code,
                ranked_code = excluded.ranked_code
        """, (
            guild_id,
            channel_id,
            pubs_code,
            ranked_code
        ))

        db.commit()
        db.close()

    def _disable_settings(self, guild_id: int):
        db = self._get_db()
        cursor = db.cursor()

        cursor.execute("""
            DELETE FROM apex_map_notifications
            WHERE guild_id = ?
        """, (guild_id,))

        db.commit()
        db.close()

    # =========================================================
    # API
    # =========================================================

    async def _get_rotation(self):
        if not self.api_key:
            return None

        headers = {
            "Authorization": self.api_key,
            "User-Agent": "GridGuardian/1.0"
        }

        params = {
            "version": "2"
        }

        try:
            timeout = aiohttp.ClientTimeout(total=15)

            async with aiohttp.ClientSession(
                timeout=timeout
            ) as session:

                async with session.get(
                    API_URL,
                    params=params,
                    headers=headers
                ) as response:

                    if response.status != 200:
                        print(
                            f"[ApexMapNotify] API returned "
                            f"HTTP {response.status}"
                        )
                        return None

                    return await response.json()

        except aiohttp.ClientError as e:
            print(f"[ApexMapNotify] API request failed: {e}")
            return None

        except Exception as e:
            print(f"[ApexMapNotify] Unexpected API error: {e}")
            return None

    # =========================================================
    # HELPERS
    # =========================================================

    @staticmethod
    def _get_current(rotation, mode_name):
        mode_data = rotation.get(mode_name)

        if not isinstance(mode_data, dict):
            return None

        current = mode_data.get("current")

        if not isinstance(current, dict):
            return None

        return current

    @staticmethod
    def _get_next(rotation, mode_name):
        mode_data = rotation.get(mode_name)

        if not isinstance(mode_data, dict):
            return None

        next_map = mode_data.get("next")

        if not isinstance(next_map, dict):
            return None

        return next_map

    @staticmethod
    def _map_name(data):
        if not data:
            return "Unknown"

        return data.get("map") or data.get("mapName") or "Unknown"

    @staticmethod
    def _map_code(data):
        if not data:
            return None

        return (
            data.get("code")
            or data.get("map")
            or data.get("mapName")
        )

    @staticmethod
    def _remaining_time(data):
        if not data:
            return "Unknown"

        timer = data.get("remainingTimer")

        if timer:
            return timer

        remaining = data.get("remainingSecs")

        if remaining is not None:
            try:
                remaining = int(remaining)

                hours = remaining // 3600
                minutes = (remaining % 3600) // 60
                seconds = remaining % 60

                if hours > 0:
                    return f"{hours}h {minutes}m"

                if minutes > 0:
                    return f"{minutes}m {seconds}s"

                return f"{seconds}s"

            except (ValueError, TypeError):
                pass

        return "Unknown"

    # =========================================================
    # EMBEDS
    # =========================================================

    def _create_map_embed(
        self,
        mode_name: str,
        current,
        next_map
    ):
        mode_display = {
            "battle_royale": "Pubs",
            "ranked": "Ranked"
        }.get(mode_name, mode_name.title())

        current_map = self._map_name(current)
        next_name = self._map_name(next_map)

        embed = discord.Embed(
            title=f"🗺️ Apex {mode_display} Rotation Changed",
            description=(
                f"**Current Map:** {current_map}\n"
                f"**Next Map:** {next_name}"
            ),
            color=discord.Color.blue()
        )

        remaining = self._remaining_time(current)

        embed.add_field(
            name="⏱️ Time Remaining",
            value=remaining,
            inline=False
        )

        embed.set_footer(
            text="Data provided by Apex Legends Status"
        )

        return embed

    # =========================================================
    # BACKGROUND LOOP
    # =========================================================

    @tasks.loop(seconds=60)
    async def map_check_loop(self):
        if not self.api_key:
            return

        rotation = await self._get_rotation()

        if not rotation:
            return

        db = self._get_db()
        cursor = db.cursor()

        cursor.execute("""
            SELECT guild_id, channel_id, pubs_code, ranked_code
            FROM apex_map_notifications
        """)

        settings = cursor.fetchall()

        db.close()

        for (
            guild_id,
            channel_id,
            stored_pubs_code,
            stored_ranked_code
        ) in settings:

            guild = self.bot.get_guild(guild_id)

            if guild is None:
                continue

            channel = guild.get_channel(channel_id)

            if channel is None:
                continue

            new_pubs_code = stored_pubs_code
            new_ranked_code = stored_ranked_code

            # -------------------------------------------------
            # PUBS
            # -------------------------------------------------

            pubs_current = self._get_current(
                rotation,
                "battle_royale"
            )

            pubs_next = self._get_next(
                rotation,
                "battle_royale"
            )

            if pubs_current:
                current_pubs_code = self._map_code(pubs_current)

                if current_pubs_code:

                    if stored_pubs_code is None:
                        new_pubs_code = current_pubs_code

                    elif current_pubs_code != stored_pubs_code:

                        embed = self._create_map_embed(
                            "battle_royale",
                            pubs_current,
                            pubs_next
                        )

                        try:
                            await channel.send(embed=embed)
                        except discord.Forbidden:
                            print(
                                f"[ApexMapNotify] Missing permission "
                                f"to send in #{channel.name} "
                                f"({guild.name})"
                            )
                        except discord.HTTPException as e:
                            print(
                                f"[ApexMapNotify] Discord error: {e}"
                            )

                        new_pubs_code = current_pubs_code

            # -------------------------------------------------
            # RANKED
            # -------------------------------------------------

            ranked_current = self._get_current(
                rotation,
                "ranked"
            )

            ranked_next = self._get_next(
                rotation,
                "ranked"
            )

            if ranked_current:
                current_ranked_code = self._map_code(
                    ranked_current
                )

                if current_ranked_code:

                    if stored_ranked_code is None:
                        new_ranked_code = current_ranked_code

                    elif current_ranked_code != stored_ranked_code:

                        embed = self._create_map_embed(
                            "ranked",
                            ranked_current,
                            ranked_next
                        )

                        try:
                            await channel.send(embed=embed)
                        except discord.Forbidden:
                            print(
                                f"[ApexMapNotify] Missing permission "
                                f"to send in #{channel.name} "
                                f"({guild.name})"
                            )
                        except discord.HTTPException as e:
                            print(
                                f"[ApexMapNotify] Discord error: {e}"
                            )

                        new_ranked_code = current_ranked_code

            # -------------------------------------------------
            # SAVE UPDATED STATE
            # -------------------------------------------------

            if (
                new_pubs_code != stored_pubs_code
                or new_ranked_code != stored_ranked_code
            ):
                self._set_settings(
                    guild_id,
                    channel_id,
                    new_pubs_code,
                    new_ranked_code
                )

    @map_check_loop.before_loop
    async def before_map_check_loop(self):
        await self.bot.wait_until_ready()

    # =========================================================
    # COMMANDS
    # =========================================================

    @commands.command(name="setmapnotify")
    @commands.has_guild_permissions(manage_guild=True)
    @commands.bot_has_permissions(send_messages=True)
    async def set_map_notify(
        self,
        ctx,
        channel: discord.TextChannel
    ):
        """Set the channel for automatic Apex map notifications."""

        if not self.api_key:
            await ctx.send(
                "❌ `APEX_API_KEY` is not configured on the bot."
            )
            return

        rotation = await self._get_rotation()

        if not rotation:
            await ctx.send(
                "❌ I couldn't reach the Apex rotation API right now."
            )
            return

        pubs_current = self._get_current(
            rotation,
            "battle_royale"
        )

        ranked_current = self._get_current(
            rotation,
            "ranked"
        )

        pubs_code = self._map_code(pubs_current)
        ranked_code = self._map_code(ranked_current)

        self._set_settings(
            ctx.guild.id,
            channel.id,
            pubs_code,
            ranked_code
        )

        embed = discord.Embed(
            title="🗺️ Apex Map Notifications Enabled",
            description=(
                f"Map changes will now be posted in {channel.mention}.\n\n"
                "I'll notify the server when the **Pubs** or "
                "**Ranked** rotation changes."
            ),
            color=discord.Color.green()
        )

        await ctx.send(embed=embed)

    @commands.command(name="mapnotifystatus")
    async def map_notify_status(self, ctx):
        """Show Apex map notification settings."""

        settings = self._get_settings(ctx.guild.id)

        if not settings:
            await ctx.send(
                "🗺️ Apex map notifications are **disabled** "
                "in this server."
            )
            return

        channel_id, pubs_code, ranked_code = settings

        channel = ctx.guild.get_channel(channel_id)

        channel_text = (
            channel.mention
            if channel
            else f"<#{channel_id}>"
        )

        embed = discord.Embed(
            title="🗺️ Apex Map Notification Status",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="Status",
            value="🟢 Enabled",
            inline=True
        )

        embed.add_field(
            name="Channel",
            value=channel_text,
            inline=True
        )

        embed.add_field(
            name="Pubs Tracked",
            value=pubs_code or "Not initialized",
            inline=False
        )

        embed.add_field(
            name="Ranked Tracked",
            value=ranked_code or "Not initialized",
            inline=False
        )

        await ctx.send(embed=embed)

    @commands.command(name="disablemapnotify")
    @commands.has_guild_permissions(manage_guild=True)
    async def disable_map_notify(self, ctx):
        """Disable Apex map notifications."""

        settings = self._get_settings(ctx.guild.id)

        if not settings:
            await ctx.send(
                "🗺️ Apex map notifications are already disabled."
            )
            return

        self._disable_settings(ctx.guild.id)

        embed = discord.Embed(
            title="🗺️ Apex Map Notifications Disabled",
            description=(
                "Automatic map rotation notifications have been "
                "disabled for this server."
            ),
            color=discord.Color.red()
        )

        await ctx.send(embed=embed)

    # =========================================================
    # ERROR HANDLING
    # =========================================================

    @set_map_notify.error
    async def set_map_notify_error(self, ctx, error):

        if isinstance(error, commands.MissingPermissions):
            await ctx.send(
                "❌ You need **Manage Server** permission "
                "to configure map notifications."
            )

        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send(
                "❌ I need permission to send messages in "
                "that channel."
            )

        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                "Usage: `!setmapnotify #channel`"
            )

        elif isinstance(error, commands.BadArgument):
            await ctx.send(
                "❌ I couldn't find that channel.\n"
                "Use: `!setmapnotify #channel`"
            )

        else:
            raise error

    @disable_map_notify.error
    async def disable_map_notify_error(self, ctx, error):

        if isinstance(error, commands.MissingPermissions):
            await ctx.send(
                "❌ You need **Manage Server** permission "
                "to disable map notifications."
            )

        else:
            raise error

    # =========================================================
    # CLEANUP
    # =========================================================

    def cog_unload(self):
        self.map_check_loop.cancel()


async def setup(bot):
    await bot.add_cog(ApexMapNotify(bot))
    print("🗺️ Apex Map Notify cog loaded")