import asyncio
import re
import sqlite3
from html import unescape
from urllib.parse import urljoin

import aiohttp
import discord
from discord.ext import commands, tasks


DB_PATH = "gridguardian.db"

EA_GAME_UPDATES_URL = (
    "https://www.ea.com/games/apex-legends/"
    "apex-legends/news?page=1&type=game-updates"
)

EA_BASE_URL = "https://www.ea.com"

CHECK_INTERVAL = 10 * 60


class ApexPatch(commands.Cog):
    """Automatically monitors official Apex Legends patch notes."""

    def __init__(self, bot):
        self.bot = bot

        self._init_database()

        self.patch_check_loop.start()

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
            CREATE TABLE IF NOT EXISTS apex_patch_settings (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER NOT NULL,
                last_url TEXT,
                last_title TEXT
            )
        """)

        db.commit()
        db.close()

    def _get_settings(self, guild_id: int):
        db = self._get_db()
        cursor = db.cursor()

        cursor.execute("""
            SELECT channel_id, last_url, last_title
            FROM apex_patch_settings
            WHERE guild_id = ?
        """, (guild_id,))

        row = cursor.fetchone()

        db.close()

        return row

    def _get_all_settings(self):
        db = self._get_db()
        cursor = db.cursor()

        cursor.execute("""
            SELECT guild_id, channel_id, last_url, last_title
            FROM apex_patch_settings
        """)

        rows = cursor.fetchall()

        db.close()

        return rows

    def _save_settings(
        self,
        guild_id: int,
        channel_id: int,
        last_url: str | None,
        last_title: str | None
    ):
        db = self._get_db()
        cursor = db.cursor()

        cursor.execute("""
            INSERT INTO apex_patch_settings
                (guild_id, channel_id, last_url, last_title)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id)
            DO UPDATE SET
                channel_id = excluded.channel_id,
                last_url = excluded.last_url,
                last_title = excluded.last_title
        """, (
            guild_id,
            channel_id,
            last_url,
            last_title
        ))

        db.commit()
        db.close()

    def _disable_settings(self, guild_id: int):
        db = self._get_db()
        cursor = db.cursor()

        cursor.execute("""
            DELETE FROM apex_patch_settings
            WHERE guild_id = ?
        """, (guild_id,))

        db.commit()
        db.close()

    # =========================================================
    # EA WEBSITE
    # =========================================================

    async def _fetch_latest_patch(self):
        """
        Fetch the newest article from EA's official
        Apex Legends Game Updates page.
        """

        headers = {
            "User-Agent": (
                "Mozilla/5.0 "
                "(compatible; GridGuardian/1.0)"
            )
        }

        timeout = aiohttp.ClientTimeout(total=20)

        try:
            async with aiohttp.ClientSession(
                timeout=timeout,
                headers=headers
            ) as session:

                async with session.get(
                    EA_GAME_UPDATES_URL
                ) as response:

                    if response.status != 200:
                        print(
                            "[ApexPatch] EA returned "
                            f"HTTP {response.status}"
                        )
                        return None

                    html = await response.text()

        except aiohttp.ClientError as e:
            print(f"[ApexPatch] EA request failed: {e}")
            return None

        except asyncio.TimeoutError:
            print("[ApexPatch] EA request timed out")
            return None

        except Exception as e:
            print(f"[ApexPatch] Unexpected error: {e}")
            return None

        # -----------------------------------------------------
        # Find Apex Game Update article links
        # -----------------------------------------------------

        pattern = re.compile(
            r'href=["\']([^"\']*?/games/apex-legends/'
            r'apex-legends/news/[^"\']+)["\']',
            re.IGNORECASE
        )

        matches = pattern.findall(html)

        if not matches:
            print(
                "[ApexPatch] Could not find any Game Update "
                "articles on EA's page."
            )
            return None

        # Remove duplicates while keeping original order.
        article_urls = []

        for url in matches:
            full_url = urljoin(EA_BASE_URL, unescape(url))

            if full_url not in article_urls:
                article_urls.append(full_url)

        if not article_urls:
            return None

        # -----------------------------------------------------
        # Get the first article that actually loads.
        # -----------------------------------------------------

        for article_url in article_urls[:10]:

            article = await self._fetch_article(
                session_headers=headers,
                url=article_url
            )

            if article:
                return article

        return None

    async def _fetch_article(self, session_headers, url):
        timeout = aiohttp.ClientTimeout(total=20)

        try:
            async with aiohttp.ClientSession(
                timeout=timeout,
                headers=session_headers
            ) as session:

                async with session.get(url) as response:

                    if response.status != 200:
                        return None

                    html = await response.text()

        except Exception:
            return None

        # -----------------------------------------------------
        # Extract title
        # -----------------------------------------------------

        title = None

        title_match = re.search(
            r"<h1[^>]*>(.*?)</h1>",
            html,
            re.IGNORECASE | re.DOTALL
        )

        if title_match:
            title = self._clean_html(
                title_match.group(1)
            )

        # Fall back to page title.
        if not title:
            title_match = re.search(
                r"<title[^>]*>(.*?)</title>",
                html,
                re.IGNORECASE | re.DOTALL
            )

            if title_match:
                title = self._clean_html(
                    title_match.group(1)
                )

        if not title:
            title = "Apex Legends Game Update"

        # -----------------------------------------------------
        # Extract date
        # -----------------------------------------------------

        date_text = None

        date_match = re.search(
            r"""
            (?:
                January|February|March|April|May|June|
                July|August|September|October|November|December
            )
            \s+\d{1,2},\s+\d{4}
            """,
            html,
            re.IGNORECASE | re.VERBOSE
        )

        if date_match:
            date_text = date_match.group(0)

        return {
            "title": title,
            "url": url,
            "date": date_text
        }

    @staticmethod
    def _clean_html(value):
        value = re.sub(
            r"<[^>]+>",
            " ",
            value
        )

        value = unescape(value)

        value = re.sub(
            r"\s+",
            " ",
            value
        )

        return value.strip()

    # =========================================================
    # EMBED
    # =========================================================

    @staticmethod
    def _create_patch_embed(patch):
        embed = discord.Embed(
            title="🔴 New Apex Patch Notes",
            description=(
                f"**{patch['title']}**\n\n"
                "EA has released a new Apex Legends "
                "Game Update."
            ),
            url=patch["url"],
            color=discord.Color.red()
        )

        if patch.get("date"):
            embed.add_field(
                name="📅 Published",
                value=patch["date"],
                inline=True
            )

        embed.add_field(
            name="📖 Read the Patch Notes",
            value=f"[Open the official EA article]({patch['url']})",
            inline=False
        )

        embed.set_footer(
            text="Official Apex Legends Game Update • EA"
        )

        return embed

    # =========================================================
    # BACKGROUND LOOP
    # =========================================================

    @tasks.loop(seconds=CHECK_INTERVAL)
    async def patch_check_loop(self):
        latest_patch = await self._fetch_latest_patch()

        if not latest_patch:
            return

        settings = self._get_all_settings()

        for (
            guild_id,
            channel_id,
            stored_url,
            stored_title
        ) in settings:

            guild = self.bot.get_guild(guild_id)

            if guild is None:
                continue

            channel = guild.get_channel(channel_id)

            if channel is None:
                continue

            # -------------------------------------------------
            # First run / initialization
            # -------------------------------------------------

            if not stored_url:
                self._save_settings(
                    guild_id,
                    channel_id,
                    latest_patch["url"],
                    latest_patch["title"]
                )

                continue

            # -------------------------------------------------
            # New patch detected
            # -------------------------------------------------

            if latest_patch["url"] != stored_url:

                embed = self._create_patch_embed(
                    latest_patch
                )

                try:
                    await channel.send(embed=embed)

                except discord.Forbidden:
                    print(
                        "[ApexPatch] Missing permission to "
                        f"send in #{channel.name} "
                        f"({guild.name})"
                    )

                except discord.HTTPException as e:
                    print(
                        f"[ApexPatch] Discord error: {e}"
                    )

                # Save even if Discord sending failed so the
                # bot doesn't repeatedly spam the channel.
                self._save_settings(
                    guild_id,
                    channel_id,
                    latest_patch["url"],
                    latest_patch["title"]
                )

    @patch_check_loop.before_loop
    async def before_patch_check_loop(self):
        await self.bot.wait_until_ready()

    # =========================================================
    # COMMANDS
    # =========================================================

    @commands.command(name="setapexpatch")
    @commands.has_guild_permissions(
        manage_guild=True
    )
    @commands.bot_has_permissions(
        send_messages=True,
        embed_links=True
    )
    async def set_apex_patch(
        self,
        ctx,
        channel: discord.TextChannel
    ):
        """
        Set the channel for automatic Apex patch notes.
        """

        latest_patch = await self._fetch_latest_patch()

        if not latest_patch:
            await ctx.send(
                "❌ I couldn't access EA's Apex Game Updates "
                "page right now. Try again in a little while."
            )
            return

        self._save_settings(
            ctx.guild.id,
            channel.id,
            latest_patch["url"],
            latest_patch["title"]
        )

        embed = discord.Embed(
            title="🔴 Apex Patch Notifications Enabled",
            description=(
                f"New official Apex Game Updates will now "
                f"be posted in {channel.mention}.\n\n"
                "The current patch has been recorded, so I "
                "won't immediately post an old update."
            ),
            color=discord.Color.green()
        )

        embed.add_field(
            name="Currently Tracking",
            value=latest_patch["title"],
            inline=False
        )

        await ctx.send(embed=embed)

    @commands.command(name="apexpatchstatus")
    async def apex_patch_status(self, ctx):
        """Show Apex patch notification settings."""

        settings = self._get_settings(
            ctx.guild.id
        )

        if not settings:
            await ctx.send(
                "🔴 Apex patch notifications are "
                "**disabled** in this server."
            )
            return

        channel_id, last_url, last_title = settings

        channel = ctx.guild.get_channel(
            channel_id
        )

        channel_text = (
            channel.mention
            if channel
            else f"<#{channel_id}>"
        )

        embed = discord.Embed(
            title="🔴 Apex Patch Notification Status",
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
            name="Last Recorded Update",
            value=last_title or "None",
            inline=False
        )

        if last_url:
            embed.add_field(
                name="Article",
                value=f"[Open on EA]({last_url})",
                inline=False
            )

        embed.set_footer(
            text="Checking EA Game Updates automatically"
        )

        await ctx.send(embed=embed)

    @commands.command(name="disableapexpatch")
    @commands.has_guild_permissions(
        manage_guild=True
    )
    async def disable_apex_patch(self, ctx):
        """Disable automatic Apex patch notifications."""

        settings = self._get_settings(
            ctx.guild.id
        )

        if not settings:
            await ctx.send(
                "🔴 Apex patch notifications are "
                "already disabled."
            )
            return

        self._disable_settings(
            ctx.guild.id
        )

        embed = discord.Embed(
            title="🔴 Apex Patch Notifications Disabled",
            description=(
                "Automatic Apex Game Update notifications "
                "have been disabled for this server."
            ),
            color=discord.Color.red()
        )

        await ctx.send(embed=embed)

    # =========================================================
    # COMMAND ERROR HANDLING
    # =========================================================

    @set_apex_patch.error
    async def set_apex_patch_error(
        self,
        ctx,
        error
    ):
        if isinstance(
            error,
            commands.MissingPermissions
        ):
            await ctx.send(
                "❌ You need **Manage Server** permission "
                "to configure Apex patch notifications."
            )

        elif isinstance(
            error,
            commands.BotMissingPermissions
        ):
            await ctx.send(
                "❌ I need permission to send messages "
                "and embed links in that channel."
            )

        elif isinstance(
            error,
            commands.MissingRequiredArgument
        ):
            await ctx.send(
                "Usage: `!setapexpatch #channel`"
            )

        elif isinstance(
            error,
            commands.BadArgument
        ):
            await ctx.send(
                "❌ I couldn't find that channel.\n"
                "Use: `!setapexpatch #channel`"
            )

        else:
            raise error

    @disable_apex_patch.error
    async def disable_apex_patch_error(
        self,
        ctx,
        error
    ):
        if isinstance(
            error,
            commands.MissingPermissions
        ):
            await ctx.send(
                "❌ You need **Manage Server** permission "
                "to disable Apex patch notifications."
            )

        else:
            raise error

    # =========================================================
    # CLEANUP
    # =========================================================

    def cog_unload(self):
        self.patch_check_loop.cancel()


async def setup(bot):
    await bot.add_cog(
        ApexPatch(bot)
    )

    print("🔴 Apex Patch cog loaded")