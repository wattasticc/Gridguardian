import re
import time
import sqlite3

from collections import defaultdict, deque

import discord
from discord.ext import commands


EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)


# =========================================================
# DATABASE
# =========================================================

db = sqlite3.connect("gridguardian.db")
cursor = db.cursor()


# ---------------------------------------------------------
# CUSTOM BLACKLISTED WORDS
# ---------------------------------------------------------

cursor.execute("""
CREATE TABLE IF NOT EXISTS automod_words (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    word TEXT NOT NULL COLLATE NOCASE
)
""")


# ---------------------------------------------------------
# AUTOMOD SETTINGS
# ---------------------------------------------------------

cursor.execute("""
CREATE TABLE IF NOT EXISTS automod_settings (
    guild_id INTEGER PRIMARY KEY,
    block_invites INTEGER DEFAULT 1,
    block_links INTEGER DEFAULT 0,
    message_limit INTEGER DEFAULT 5,
    time_window INTEGER DEFAULT 5,
    duplicate_limit INTEGER DEFAULT 3,
    duplicate_window INTEGER DEFAULT 15,
    timeout_after INTEGER DEFAULT 3,
    timeout_minutes INTEGER DEFAULT 10
)
""")


db.commit()


# =========================================================
# AUTOMOD COG
# =========================================================

class AutoMod(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        # -------------------------------------------------
        # MESSAGE HISTORY
        # -------------------------------------------------

        self.message_times = defaultdict(deque)
        self.recent_messages = defaultdict(deque)

        # Prevent repeated warning messages.
        self.warning_cooldowns = {}

        self.warning_cooldown = 5

        # -------------------------------------------------
        # PATTERNS
        # -------------------------------------------------

        self.invite_pattern = re.compile(
            r"(discord\.gg/\S+|discord(?:app)?\.com/invite/\S+)",
            re.IGNORECASE
        )

        self.link_pattern = re.compile(
            r"(https?://\S+|www\.\S+)",
            re.IGNORECASE
        )


    # =====================================================
    # DATABASE HELPERS
    # =====================================================

    def get_settings(self, guild_id):

        cursor.execute("""
        INSERT OR IGNORE INTO automod_settings (
            guild_id
        )
        VALUES (?)
        """, (
            guild_id,
        ))

        db.commit()

        cursor.execute("""
        SELECT
            block_invites,
            block_links,
            message_limit,
            time_window,
            duplicate_limit,
            duplicate_window,
            timeout_after,
            timeout_minutes
        FROM automod_settings
        WHERE guild_id=?
        """, (
            guild_id,
        ))

        return cursor.fetchone()


    def get_blacklisted_words(self, guild_id):

        cursor.execute("""
        SELECT word
        FROM automod_words
        WHERE guild_id=?
        """, (
            guild_id,
        ))

        results = cursor.fetchall()

        return [
            word[0].lower()
            for word in results
        ]


    def get_warning_count(
        self,
        guild_id,
        user_id
    ):

        cursor.execute("""
        SELECT COUNT(*)
        FROM warnings
        WHERE user_id=?
        """, (
            user_id,
        ))

        result = cursor.fetchone()

        return result[0] if result else 0


    def add_warning(
        self,
        guild_id,
        user_id,
        reason
    ):

        cursor.execute("""
        INSERT INTO warnings (
            user_id,
            moderator_id,
            reason
        )
        VALUES (?, ?, ?)
        """, (
            user_id,
            self.bot.user.id,
            f"[AutoMod] {reason}"
        ))

        db.commit()


    # =====================================================
    # WARNING COOLDOWN
    # =====================================================

    def can_warn(self, user_id):

        current_time = time.time()

        last_warning = self.warning_cooldowns.get(
            user_id,
            0
        )

        if (
            current_time - last_warning
            < self.warning_cooldown
        ):

            return False

        self.warning_cooldowns[
            user_id
        ] = current_time

        return True


    # =====================================================
    # SEND LOG
    # =====================================================

    async def send_log(
        self,
        message,
        reason,
        warning_count
    ):

        # Try to find the configured log channel
        # from your existing settings table.

        try:

            cursor.execute("""
            SELECT log_channel_id
            FROM settings
            WHERE guild_id=?
            """, (
                message.guild.id,
            ))

            result = cursor.fetchone()

        except sqlite3.Error:

            result = None


        if not result or not result[0]:
            return


        log_channel = message.guild.get_channel(
            result[0]
        )


        if not isinstance(
            log_channel,
            discord.TextChannel
        ):
            return


        embed = discord.Embed(
            title="🛡️ AutoMod Action",
            color=discord.Color.orange()
        )


        embed.add_field(
            name="👤 User",
            value=(
                f"{message.author.mention}\n"
                f"`{message.author.id}`"
            ),
            inline=True
        )


        embed.add_field(
            name="📍 Channel",
            value=message.channel.mention,
            inline=True
        )


        embed.add_field(
            name="⚠️ Reason",
            value=reason,
            inline=False
        )


        embed.add_field(
            name="📊 Total Warnings",
            value=str(warning_count),
            inline=True
        )


        if message.content:

            content = message.content[:1000]

            embed.add_field(
                name="💬 Message",
                value=(
                    f"```{content}```"
                ),
                inline=False
            )


        try:

            await log_channel.send(
                embed=embed
            )

        except (
            discord.Forbidden,
            discord.HTTPException
        ):

            pass


    # =====================================================
    # SEND WARNING
    # =====================================================

    async def send_warning(
        self,
        message,
        reason,
        warning_count
    ):

        if not self.can_warn(
            message.author.id
        ):
            return


        embed = discord.Embed(
            title="⚠️ AutoMod Warning",
            description=(
                f"{message.author.mention}\n\n"
                f"**Reason:** {reason}\n"
                f"**Warnings:** {warning_count}"
            ),
            color=discord.Color.orange()
        )


        embed.set_footer(
            text="Please follow the server rules."
        )


        try:

            warning_message = (
                await message.channel.send(
                    embed=embed
                )
            )

            await warning_message.delete(
                delay=8
            )

        except (
            discord.Forbidden,
            discord.HTTPException
        ):

            pass


    # =====================================================
    # TIMEOUT USER
    # =====================================================

    async def timeout_user(
        self,
        member,
        minutes,
        reason
    ):

        try:

            until = discord.utils.utcnow()

            until += discord.utils.timedelta(
                minutes=minutes
            )

            await member.timeout(
                until,
                reason=f"AutoMod: {reason}"
            )

            return True

        except AttributeError:

            # Fallback for Python datetime
            from datetime import timedelta

            try:

                until = discord.utils.utcnow()

                until += timedelta(
                    minutes=minutes
                )

                await member.timeout(
                    until,
                    reason=f"AutoMod: {reason}"
                )

                return True

            except (
                discord.Forbidden,
                discord.HTTPException
            ):

                return False


        except (
            discord.Forbidden,
            discord.HTTPException
        ):

            return False


    # =====================================================
    # DELETE VIOLATION
    # =====================================================

    async def handle_violation(
        self,
        message,
        reason,
        settings
    ):

        # -------------------------------------------------
        # DELETE MESSAGE
        # -------------------------------------------------

        try:

            await message.delete()

        except (
            discord.Forbidden,
            discord.HTTPException
        ):

            pass


        # -------------------------------------------------
        # ADD WARNING
        # -------------------------------------------------

        self.add_warning(
            message.guild.id,
            message.author.id,
            reason
        )


        warning_count = self.get_warning_count(
            message.guild.id,
            message.author.id
        )


        # -------------------------------------------------
        # SEND WARNING
        # -------------------------------------------------

        await self.send_warning(
            message,
            reason,
            warning_count
        )


        # -------------------------------------------------
        # SEND LOG
        # -------------------------------------------------

        await self.send_log(
            message,
            reason,
            warning_count
        )


        # -------------------------------------------------
        # TIMEOUT SETTINGS
        # -------------------------------------------------

        timeout_after = settings[6]
        timeout_minutes = settings[7]


        # -------------------------------------------------
        # TIMEOUT USER
        # -------------------------------------------------

        if warning_count >= timeout_after:

            success = await self.timeout_user(
                message.author,
                timeout_minutes,
                reason
            )


            if success:

                try:

                    embed = discord.Embed(
                        title="🔇 AutoMod Timeout",
                        description=(
                            f"{message.author.mention} "
                            f"has been timed out for "
                            f"**{timeout_minutes} minutes** "
                            f"after receiving "
                            f"**{warning_count} warnings**."
                        ),
                        color=discord.Color.red()
                    )

                    timeout_message = (
                        await message.channel.send(
                            embed=embed
                        )
                    )

                    await timeout_message.delete(
                        delay=10
                    )

                except (
                    discord.Forbidden,
                    discord.HTTPException
                ):

                    pass


    # =====================================================
    # AUTOMOD MESSAGE LISTENER
    # =====================================================

    @commands.Cog.listener()
    async def on_message(self, message):

        # -------------------------------------------------
        # IGNORE BOTS
        # -------------------------------------------------

        if message.author.bot:
            return


        # -------------------------------------------------
        # IGNORE DMS
        # -------------------------------------------------

        if message.guild is None:
            return


        # -------------------------------------------------
        # ADMIN / MOD BYPASS
        # -------------------------------------------------

        if (
            message.author.guild_permissions.administrator
            or message.author.guild_permissions.manage_messages
        ):

            return


        settings = self.get_settings(
            message.guild.id
        )


        (
            block_invites,
            block_links,
            message_limit,
            time_window,
            duplicate_limit,
            duplicate_window,
            timeout_after,
            timeout_minutes
        ) = settings


        user_id = message.author.id

        current_time = time.time()

        normalized_content = (
            message.content
            .lower()
            .strip()
        )


        # =================================================
        # INVITE FILTER
        # =================================================

        if block_invites:

            if self.invite_pattern.search(
                message.content
            ):

                await self.handle_violation(
                    message,
                    "Discord invite links are not allowed.",
                    settings
                )

                return


        # =================================================
        # LINK FILTER
        # =================================================

        if block_links:

            if self.link_pattern.search(
                message.content
            ):

                await self.handle_violation(
                    message,
                    "Links are not allowed.",
                    settings
                )

                return


        # =================================================
        # BLACKLISTED WORD FILTER
        # =================================================

        blacklisted_words = (
            self.get_blacklisted_words(
                message.guild.id
            )
        )


        for word in blacklisted_words:

            pattern = (
                r"(?<!\w)"
                + re.escape(word)
                + r"(?!\w)"
            )


            if re.search(
                pattern,
                normalized_content,
                re.IGNORECASE
            ):

                await self.handle_violation(
                    message,
                    "That word is not allowed in this server.",
                    settings
                )

                return


        # =================================================
        # MESSAGE FLOOD DETECTION
        # =================================================

        timestamps = self.message_times[
            user_id
        ]


        while (
            timestamps
            and current_time - timestamps[0]
            > time_window
        ):

            timestamps.popleft()


        timestamps.append(
            current_time
        )


        if len(timestamps) > message_limit:

            timestamps.clear()

            await self.handle_violation(
                message,
                "You are sending messages too quickly.",
                settings
            )

            return


        # =================================================
        # DUPLICATE MESSAGE DETECTION
        # =================================================

        if normalized_content:

            content_history = (
                self.recent_messages[
                    user_id
                ]
            )


            while (
                content_history
                and current_time
                - content_history[0][1]
                > duplicate_window
            ):

                content_history.popleft()


            duplicate_count = sum(
                1
                for content, timestamp
                in content_history
                if content == normalized_content
            )


            content_history.append(
                (
                    normalized_content,
                    current_time
                )
            )


            if duplicate_count >= duplicate_limit:

                content_history.clear()

                await self.handle_violation(
                    message,
                    "Please do not repeatedly send the same message.",
                    settings
                )

                return


    # =====================================================
    # ADD BLACKLISTED WORD
    # =====================================================

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def addbadword(
        self,
        ctx,
        *,
        word: str
    ):

        word = word.lower().strip()


        if not word:

            return await ctx.send(
                "❌ Please provide a word."
            )


        cursor.execute("""
        SELECT id
        FROM automod_words
        WHERE guild_id=?
        AND word=?
        """, (
            ctx.guild.id,
            word
        ))


        existing = cursor.fetchone()


        if existing:

            return await ctx.send(
                "❌ That word is already blocked."
            )


        cursor.execute("""
        INSERT INTO automod_words (
            guild_id,
            word
        )
        VALUES (?, ?)
        """, (
            ctx.guild.id,
            word
        ))


        db.commit()


        embed = discord.Embed(
            title="🚫 Word Added",
            description=(
                f"`{word}` has been added to "
                f"the AutoMod blacklist."
            ),
            color=discord.Color.red()
        )


        await ctx.send(
            embed=embed
        )


    # =====================================================
    # REMOVE BLACKLISTED WORD
    # =====================================================

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def removebadword(
        self,
        ctx,
        *,
        word: str
    ):

        word = word.lower().strip()


        cursor.execute("""
        DELETE FROM automod_words
        WHERE guild_id=?
        AND word=?
        """, (
            ctx.guild.id,
            word
        ))


        if cursor.rowcount == 0:

            return await ctx.send(
                "❌ That word isn't currently blocked."
            )


        db.commit()


        embed = discord.Embed(
            title="✅ Word Removed",
            description=(
                f"`{word}` has been removed from "
                f"the AutoMod blacklist."
            ),
            color=discord.Color.green()
        )


        await ctx.send(
            embed=embed
        )


    # =====================================================
    # VIEW BLACKLIST
    # =====================================================

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def badwords(self, ctx):

        words = self.get_blacklisted_words(
            ctx.guild.id
        )


        if not words:

            return await ctx.send(
                "🛡️ There are currently no custom "
                "blocked words."
            )


        # Discord embeds have limits.

        display_words = words[:50]


        embed = discord.Embed(
            title="🚫 AutoMod Blocked Words",
            description=(
                "\n".join(
                    f"• `{word}`"
                    for word in display_words
                )
            ),
            color=discord.Color.red()
        )


        if len(words) > 50:

            embed.set_footer(
                text=(
                    f"Showing 50 of {len(words)} "
                    f"blocked words."
                )
            )


        await ctx.send(
            embed=embed
        )


    # =====================================================
    # TOGGLE INVITE FILTER
    # =====================================================

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def automodinvites(
        self,
        ctx,
        enabled: str
    ):

        enabled = enabled.lower()


        if enabled not in (
            "on",
            "off"
        ):

            return await ctx.send(
                "❌ Use `on` or `off`."
            )


        value = (
            1
            if enabled == "on"
            else 0
        )


        cursor.execute("""
        INSERT OR IGNORE INTO automod_settings (
            guild_id
        )
        VALUES (?)
        """, (
            ctx.guild.id,
        ))


        cursor.execute("""
        UPDATE automod_settings
        SET block_invites=?
        WHERE guild_id=?
        """, (
            value,
            ctx.guild.id
        ))


        db.commit()


        await ctx.send(
            f"✅ Discord invite filtering is now "
            f"**{enabled.upper()}**."
        )


    # =====================================================
    # TOGGLE LINK FILTER
    # =====================================================

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def automodlinks(
        self,
        ctx,
        enabled: str
    ):

        enabled = enabled.lower()


        if enabled not in (
            "on",
            "off"
        ):

            return await ctx.send(
                "❌ Use `on` or `off`."
            )


        value = (
            1
            if enabled == "on"
            else 0
        )


        cursor.execute("""
        INSERT OR IGNORE INTO automod_settings (
            guild_id
        )
        VALUES (?)
        """, (
            ctx.guild.id,
        ))


        cursor.execute("""
        UPDATE automod_settings
        SET block_links=?
        WHERE guild_id=?
        """, (
            value,
            ctx.guild.id
        ))


        db.commit()


        await ctx.send(
            f"✅ Link filtering is now "
            f"**{enabled.upper()}**."
        )


    # =====================================================
    # VIEW AUTOMOD SETTINGS
    # =====================================================

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def automod(self, ctx):

        settings = self.get_settings(
            ctx.guild.id
        )


        (
            block_invites,
            block_links,
            message_limit,
            time_window,
            duplicate_limit,
            duplicate_window,
            timeout_after,
            timeout_minutes
        ) = settings


        embed = discord.Embed(
            title="🛡️ AutoMod Settings",
            color=EMBED_COLOR
        )


        embed.add_field(
            name="📨 Invite Filter",
            value=(
                "ON"
                if block_invites
                else "OFF"
            ),
            inline=True
        )


        embed.add_field(
            name="🔗 Link Filter",
            value=(
                "ON"
                if block_links
                else "OFF"
            ),
            inline=True
        )


        embed.add_field(
            name="💬 Spam Limit",
            value=(
                f"{message_limit} messages "
                f"in {time_window} seconds"
            ),
            inline=False
        )


        embed.add_field(
            name="🔁 Duplicate Limit",
            value=(
                f"{duplicate_limit + 1} duplicate "
                f"messages in {duplicate_window} seconds"
            ),
            inline=False
        )


        embed.add_field(
            name="🔇 Automatic Timeout",
            value=(
                f"After {timeout_after} warnings\n"
                f"Timeout: {timeout_minutes} minutes"
            ),
            inline=False
        )


        words = self.get_blacklisted_words(
            ctx.guild.id
        )


        embed.add_field(
            name="🚫 Custom Blocked Words",
            value=str(
                len(words)
            ),
            inline=True
        )


        embed.set_footer(
            text="Grid Guardian AutoMod"
        )


        await ctx.send(
            embed=embed
        )


# =========================================================
# SETUP
# =========================================================

async def setup(bot):

    await bot.add_cog(
        AutoMod(bot)
    )