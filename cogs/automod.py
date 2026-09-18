"""
Grid Guardian - AutoMod

Features:
    !automod
    !automod enable
    !automod disable
    !automod settings

    !automod spam on/off
    !automod links on/off
    !automod caps on/off
    !automod mentions on/off
    !automod duplicate on/off
    !automod words on/off

    !automod word add <word>
    !automod word remove <word>
    !automod word list

    !automod exempt channel
    !automod exempt role @role

Automatic detection:
    - Spam
    - Duplicate messages
    - Excessive caps
    - Mention spam
    - Discord invite links
    - Custom blocked words

Automatic action:
    - Delete violating message
    - Record violation
    - Optional automatic timeout
"""

import sqlite3
import time
from datetime import timedelta

import discord
from discord.ext import commands


# ==========================================================
# CONFIGURATION
# ==========================================================

DB_PATH = "gridguardian.db"

EMBED_COLOR = discord.Color.from_rgb(
    80,
    220,
    255
)


# ==========================================================
# DEFAULT SETTINGS
# ==========================================================

DEFAULT_SETTINGS = {
    "enabled": 0,
    "spam_enabled": 1,
    "links_enabled": 0,
    "caps_enabled": 0,
    "mentions_enabled": 1,
    "duplicate_enabled": 1,
    "bad_words_enabled": 0,
    "warning_threshold": 3,
    "timeout_minutes": 10,
}


# ==========================================================
# DATABASE
# ==========================================================

def get_db():

    connection = sqlite3.connect(
        DB_PATH,
        timeout=30,
        check_same_thread=False
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA busy_timeout = 30000"
    )

    connection.execute(
        "PRAGMA journal_mode = WAL"
    )

    connection.execute(
        "PRAGMA synchronous = NORMAL"
    )

    return connection


def initialize_database():

    db = get_db()

    try:

        cursor = db.cursor()

        # --------------------------------------------------
        # AutoMod settings
        # --------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS automod_settings (
                guild_id INTEGER PRIMARY KEY,
                enabled INTEGER DEFAULT 0,
                spam_enabled INTEGER DEFAULT 1,
                links_enabled INTEGER DEFAULT 0,
                caps_enabled INTEGER DEFAULT 0,
                mentions_enabled INTEGER DEFAULT 1,
                duplicate_enabled INTEGER DEFAULT 1,
                bad_words_enabled INTEGER DEFAULT 0,
                warning_threshold INTEGER DEFAULT 3,
                timeout_minutes INTEGER DEFAULT 10
            )
        """)

        # --------------------------------------------------
        # Custom blocked words
        # --------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS automod_words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                word TEXT NOT NULL
            )
        """)

        # --------------------------------------------------
        # Exempt channels
        # --------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS automod_exempt_channels (
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                PRIMARY KEY (guild_id, channel_id)
            )
        """)

        # --------------------------------------------------
        # Exempt roles
        # --------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS automod_exempt_roles (
                guild_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL,
                PRIMARY KEY (guild_id, role_id)
            )
        """)

        # --------------------------------------------------
        # Violation history
        # --------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS automod_violations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                rule TEXT NOT NULL,
                message TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        db.commit()

    finally:

        db.close()


initialize_database()


# ==========================================================
# DATABASE HELPERS
# ==========================================================

def ensure_guild_settings(
    guild_id: int
):

    db = get_db()

    try:

        cursor = db.cursor()

        cursor.execute(
            """
            INSERT OR IGNORE INTO automod_settings (
                guild_id,
                enabled,
                spam_enabled,
                links_enabled,
                caps_enabled,
                mentions_enabled,
                duplicate_enabled,
                bad_words_enabled,
                warning_threshold,
                timeout_minutes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                guild_id,
                DEFAULT_SETTINGS["enabled"],
                DEFAULT_SETTINGS["spam_enabled"],
                DEFAULT_SETTINGS["links_enabled"],
                DEFAULT_SETTINGS["caps_enabled"],
                DEFAULT_SETTINGS["mentions_enabled"],
                DEFAULT_SETTINGS["duplicate_enabled"],
                DEFAULT_SETTINGS["bad_words_enabled"],
                DEFAULT_SETTINGS["warning_threshold"],
                DEFAULT_SETTINGS["timeout_minutes"],
            )
        )

        db.commit()

    finally:

        db.close()


def get_settings(
    guild_id: int
):

    ensure_guild_settings(
        guild_id
    )

    db = get_db()

    try:

        cursor = db.cursor()

        cursor.execute(
            """
            SELECT
                enabled,
                spam_enabled,
                links_enabled,
                caps_enabled,
                mentions_enabled,
                duplicate_enabled,
                bad_words_enabled,
                warning_threshold,
                timeout_minutes
            FROM automod_settings
            WHERE guild_id = ?
            """,
            (
                guild_id,
            )
        )

        result = cursor.fetchone()

        if result is None:
            return None

        return {
            "enabled": bool(result["enabled"]),
            "spam_enabled": bool(
                result["spam_enabled"]
            ),
            "links_enabled": bool(
                result["links_enabled"]
            ),
            "caps_enabled": bool(
                result["caps_enabled"]
            ),
            "mentions_enabled": bool(
                result["mentions_enabled"]
            ),
            "duplicate_enabled": bool(
                result["duplicate_enabled"]
            ),
            "bad_words_enabled": bool(
                result["bad_words_enabled"]
            ),
            "warning_threshold": int(
                result["warning_threshold"]
            ),
            "timeout_minutes": int(
                result["timeout_minutes"]
            ),
        }

    finally:

        db.close()


def update_setting(
    guild_id: int,
    setting: str,
    value
):

    allowed_settings = {
        "enabled",
        "spam_enabled",
        "links_enabled",
        "caps_enabled",
        "mentions_enabled",
        "duplicate_enabled",
        "bad_words_enabled",
        "warning_threshold",
        "timeout_minutes",
    }

    if setting not in allowed_settings:
        return False

    ensure_guild_settings(
        guild_id
    )

    db = get_db()

    try:

        cursor = db.cursor()

        cursor.execute(
            f"""
            UPDATE automod_settings
            SET {setting} = ?
            WHERE guild_id = ?
            """,
            (
                value,
                guild_id
            )
        )

        db.commit()

        return cursor.rowcount > 0

    finally:

        db.close()


def get_words(
    guild_id: int
):

    db = get_db()

    try:

        cursor = db.cursor()

        cursor.execute(
            """
            SELECT word
            FROM automod_words
            WHERE guild_id = ?
            ORDER BY word ASC
            """,
            (
                guild_id,
            )
        )

        return [
            row["word"].lower()
            for row in cursor.fetchall()
        ]

    finally:

        db.close()


def record_violation(
    guild_id: int,
    user_id: int,
    rule: str,
    message_content: str
):

    db = get_db()

    try:

        cursor = db.cursor()

        cursor.execute(
            """
            INSERT INTO automod_violations (
                guild_id,
                user_id,
                rule,
                message
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                guild_id,
                user_id,
                rule,
                message_content[:1000]
            )
        )

        db.commit()

    finally:

        db.close()


def get_violation_count(
    guild_id: int,
    user_id: int
):

    db = get_db()

    try:

        cursor = db.cursor()

        cursor.execute(
            """
            SELECT COUNT(*) AS count
            FROM automod_violations
            WHERE guild_id = ?
            AND user_id = ?
            """,
            (
                guild_id,
                user_id
            )
        )

        result = cursor.fetchone()

        return int(
            result["count"]
        )

    finally:

        db.close()


# ==========================================================
# AUTOMOD COG
# ==========================================================

class AutoMod(commands.Cog):

    def __init__(
        self,
        bot
    ):

        self.bot = bot

        # --------------------------------------------------
        # User ID -> recent message timestamps
        # --------------------------------------------------

        self.message_history = {}

        # --------------------------------------------------
        # User ID -> last message content
        # --------------------------------------------------

        self.last_messages = {}

        # --------------------------------------------------
        # User ID -> timestamp of last duplicate warning
        # --------------------------------------------------

        self.last_duplicate_trigger = {}


    # ======================================================
    # CLEAN MEMORY
    # ======================================================

    def cleanup_user(
        self,
        user_id: int
    ):

        now = time.time()

        timestamps = self.message_history.get(
            user_id,
            []
        )

        timestamps = [
            timestamp
            for timestamp in timestamps
            if now - timestamp <= 5
        ]

        if timestamps:

            self.message_history[
                user_id
            ] = timestamps

        else:

            self.message_history.pop(
                user_id,
                None
            )


        # --------------------------------------------------
        # Remove stale duplicate trigger data.
        # --------------------------------------------------

        last_trigger = self.last_duplicate_trigger.get(
            user_id
        )

        if (
            last_trigger is not None
            and now - last_trigger > 30
        ):

            self.last_duplicate_trigger.pop(
                user_id,
                None
            )


    # ======================================================
    # CHECK SPAM
    # ======================================================

    def check_spam(
        self,
        message: discord.Message
    ):

        user_id = message.author.id

        now = time.time()

        timestamps = self.message_history.setdefault(
            user_id,
            []
        )

        timestamps.append(
            now
        )

        timestamps[:] = [
            timestamp
            for timestamp in timestamps
            if now - timestamp <= 5
        ]

        # --------------------------------------------------
        # 5 messages in 5 seconds.
        # --------------------------------------------------

        return len(timestamps) >= 5


    # ======================================================
    # CHECK DUPLICATE
    # ======================================================

    def check_duplicate(
        self,
        message: discord.Message
    ):

        user_id = message.author.id

        content = message.content.strip().lower()

        if not content:

            return False


        previous = self.last_messages.get(
            user_id
        )

        self.last_messages[
            user_id
        ] = content


        if not previous:

            return False


        if previous != content:

            return False


        now = time.time()

        last_trigger = self.last_duplicate_trigger.get(
            user_id,
            0
        )


        # --------------------------------------------------
        # Prevent repeated duplicate triggers from
        # firing constantly.
        # --------------------------------------------------

        if now - last_trigger < 10:

            return False


        self.last_duplicate_trigger[
            user_id
        ] = now

        return True


    # ======================================================
    # CHECK CAPS
    # ======================================================

    def check_caps(
        self,
        message: discord.Message
    ):

        content = message.content

        letters = [
            character
            for character in content
            if character.isalpha()
        ]

        # --------------------------------------------------
        # Ignore very short messages.
        # --------------------------------------------------

        if len(letters) < 10:

            return False


        uppercase = [
            character
            for character in letters
            if character.isupper()
        ]


        percentage = (
            len(uppercase)
            / len(letters)
        )


        return percentage >= 0.80


    # ======================================================
    # CHECK MENTIONS
    # ======================================================

    def check_mentions(
        self,
        message: discord.Message
    ):

        # --------------------------------------------------
        # @everyone / @here
        # --------------------------------------------------

        if message.mention_everyone:

            return True


        # --------------------------------------------------
        # Excessive user mentions.
        # --------------------------------------------------

        if len(message.mentions) >= 6:

            return True


        return False


    # ======================================================
    # CHECK INVITE LINKS
    # ======================================================

    def check_links(
        self,
        message: discord.Message
    ):

        content = message.content.lower()

        patterns = [
            "discord.gg/",
            "discord.com/invite/",
            "discordapp.com/invite/",
        ]


        return any(
            pattern in content
            for pattern in patterns
        )


    # ======================================================
    # CHECK BLOCKED WORDS
    # ======================================================

    def check_bad_words(
        self,
        message: discord.Message
    ):

        content = message.content.lower()

        words = get_words(
            message.guild.id
        )


        for word in words:

            if word in content:

                return True


        return False


    # ======================================================
    # CHECK EXEMPTION
    # ======================================================

    def is_exempt(
        self,
        message: discord.Message
    ):

        guild_id = message.guild.id


        db = get_db()

        try:

            cursor = db.cursor()


            # --------------------------------------------------
            # Channel exemption
            # --------------------------------------------------

            cursor.execute(
                """
                SELECT 1
                FROM automod_exempt_channels
                WHERE guild_id = ?
                AND channel_id = ?
                LIMIT 1
                """,
                (
                    guild_id,
                    message.channel.id
                )
            )


            if cursor.fetchone():

                return True


            # --------------------------------------------------
            # Role exemption
            # --------------------------------------------------

            if isinstance(
                message.author,
                discord.Member
            ):

                role_ids = [
                    role.id
                    for role in message.author.roles
                ]


                if role_ids:

                    placeholders = ",".join(
                        "?"
                        for _ in role_ids
                    )


                    cursor.execute(
                        f"""
                        SELECT 1
                        FROM automod_exempt_roles
                        WHERE guild_id = ?
                        AND role_id IN ({placeholders})
                        LIMIT 1
                        """,
                        [
                            guild_id,
                            *role_ids
                        ]
                    )


                    if cursor.fetchone():

                        return True


            return False

        finally:

            db.close()


    # ======================================================
    # HANDLE VIOLATION
    # ======================================================

    async def handle_violation(
        self,
        message: discord.Message,
        rule: str
    ):

        guild = message.guild

        member = message.author


        # --------------------------------------------------
        # Record violation.
        # --------------------------------------------------

        record_violation(
            guild.id,
            member.id,
            rule,
            message.content
        )


        # --------------------------------------------------
        # Delete offending message.
        # --------------------------------------------------

        try:

            await message.delete()

        except (
            discord.Forbidden,
            discord.NotFound,
            discord.HTTPException
        ):

            pass


        settings = get_settings(
            guild.id
        )


        violation_count = get_violation_count(
            guild.id,
            member.id
        )


        # --------------------------------------------------
        # Send temporary warning.
        # --------------------------------------------------

        try:

            warning_message = await message.channel.send(
                f"⚠️ {member.mention}, your message was removed "
                f"because it triggered **{rule}**."
            )


            await warning_message.delete(
                delay=5
            )

        except (
            discord.Forbidden,
            discord.HTTPException
        ):

            pass


        # ==================================================
        # AUTOMATIC TIMEOUT
        # ==================================================

        threshold = settings[
            "warning_threshold"
        ]

        timeout_minutes = settings[
            "timeout_minutes"
        ]


        if (
            threshold > 0
            and violation_count >= threshold
            and violation_count % threshold == 0
        ):

            # --------------------------------------------------
            # Don't automatically timeout staff/admins.
            # --------------------------------------------------

            if (
                member.guild_permissions.moderate_members
                or member.guild_permissions.administrator
            ):

                return


            # --------------------------------------------------
            # Bot hierarchy protection.
            # --------------------------------------------------

            if (
                guild.me is None
                or member.top_role >= guild.me.top_role
            ):

                return


            try:

                duration = timedelta(
                    minutes=timeout_minutes
                )


                await member.timeout(
                    duration,
                    reason=(
                        f"Grid Guardian AutoMod: {rule}"
                    )
                )


                try:

                    timeout_message = await message.channel.send(
                        f"⏱️ {member.mention} has been "
                        f"timed out for **{timeout_minutes} "
                        f"minutes** due to repeated "
                        f"AutoMod violations."
                    )


                    await timeout_message.delete(
                        delay=8
                    )

                except (
                    discord.Forbidden,
                    discord.HTTPException
                ):

                    pass


            except (
                discord.Forbidden,
                discord.HTTPException
            ):

                pass


    # ======================================================
    # MESSAGE LISTENER
    # ======================================================

    @commands.Cog.listener()
    async def on_message(
        self,
        message: discord.Message
    ):

        # --------------------------------------------------
        # Ignore bots.
        # --------------------------------------------------

        if message.author.bot:

            return


        # --------------------------------------------------
        # Ignore DMs.
        # --------------------------------------------------

        if message.guild is None:

            return


        # --------------------------------------------------
        # Clean temporary memory.
        # --------------------------------------------------

        self.cleanup_user(
            message.author.id
        )


        # --------------------------------------------------
        # Get settings.
        # --------------------------------------------------

        settings = get_settings(
            message.guild.id
        )


        # --------------------------------------------------
        # AutoMod disabled.
        # --------------------------------------------------

        if not settings["enabled"]:

            return


        # --------------------------------------------------
        # Exempt channel/role.
        # --------------------------------------------------

        if self.is_exempt(message):

            return


        violation = None


        # ==================================================
        # MENTION SPAM
        # ==================================================

        if (
            settings["mentions_enabled"]
            and self.check_mentions(message)
        ):

            violation = "Mention Spam"


        # ==================================================
        # SPAM
        # ==================================================

        elif (
            settings["spam_enabled"]
            and self.check_spam(message)
        ):

            violation = "Spam"


        # ==================================================
        # DUPLICATE
        # ==================================================

        elif (
            settings["duplicate_enabled"]
            and self.check_duplicate(message)
        ):

            violation = "Duplicate Message"


        # ==================================================
        # CAPS
        # ==================================================

        elif (
            settings["caps_enabled"]
            and self.check_caps(message)
        ):

            violation = "Excessive Caps"


        # ==================================================
        # DISCORD INVITE
        # ==================================================

        elif (
            settings["links_enabled"]
            and self.check_links(message)
        ):

            violation = "Discord Invite Link"


        # ==================================================
        # BLOCKED WORD
        # ==================================================

        elif (
            settings["bad_words_enabled"]
            and self.check_bad_words(message)
        ):

            violation = "Blocked Word"


        # ==================================================
        # HANDLE
        # ==================================================

        if violation:

            await self.handle_violation(
                message,
                violation
            )


    # ======================================================
    # !AUTOMOD
    # ======================================================

    @commands.group(
        invoke_without_command=True
    )
    @commands.has_permissions(
        manage_guild=True
    )
    async def automod(
        self,
        ctx
    ):

        embed = discord.Embed(
            title="🛡️ Grid Guardian AutoMod",
            description=(
                "Configure automatic protection for your server."
            ),
            color=EMBED_COLOR
        )


        embed.add_field(
            name="🟢 Main",
            value=(
                "`!automod enable`\n"
                "`!automod disable`\n"
                "`!automod settings`"
            ),
            inline=False
        )


        embed.add_field(
            name="🛡️ Detection",
            value=(
                "`!automod spam on/off`\n"
                "`!automod links on/off`\n"
                "`!automod caps on/off`\n"
                "`!automod mentions on/off`\n"
                "`!automod duplicate on/off`\n"
                "`!automod words on/off`"
            ),
            inline=False
        )


        embed.add_field(
            name="🚫 Blocked Words",
            value=(
                "`!automod word add <word>`\n"
                "`!automod word remove <word>`\n"
                "`!automod word list`"
            ),
            inline=False
        )


        embed.add_field(
            name="🛡️ Exemptions",
            value=(
                "`!automod exempt channel`\n"
                "`!automod exempt role @role`"
            ),
            inline=False
        )


        embed.set_footer(
            text="Grid Guardian • AutoMod"
        )


        await ctx.send(
            embed=embed
        )


    # ======================================================
    # ENABLE
    # ======================================================

    @automod.command()
    async def enable(
        self,
        ctx
    ):

        update_setting(
            ctx.guild.id,
            "enabled",
            1
        )


        await ctx.send(
            "🛡️ **Grid Guardian AutoMod is now enabled.**"
        )


    # ======================================================
    # DISABLE
    # ======================================================

    @automod.command()
    async def disable(
        self,
        ctx
    ):

        update_setting(
            ctx.guild.id,
            "enabled",
            0
        )


        await ctx.send(
            "🛡️ **Grid Guardian AutoMod is now disabled.**"
        )


    # ======================================================
    # SETTINGS
    # ======================================================

    @automod.command()
    async def settings(
        self,
        ctx
    ):

        settings = get_settings(
            ctx.guild.id
        )


        def status(value):

            if value:

                return "🟢 ON"

            return "🔴 OFF"


        embed = discord.Embed(
            title="🛡️ AutoMod Settings",
            color=EMBED_COLOR
        )


        embed.add_field(
            name="AutoMod",
            value=status(
                settings["enabled"]
            ),
            inline=True
        )


        embed.add_field(
            name="Spam",
            value=status(
                settings["spam_enabled"]
            ),
            inline=True
        )


        embed.add_field(
            name="Invite Links",
            value=status(
                settings["links_enabled"]
            ),
            inline=True
        )


        embed.add_field(
            name="Excessive Caps",
            value=status(
                settings["caps_enabled"]
            ),
            inline=True
        )


        embed.add_field(
            name="Mention Spam",
            value=status(
                settings["mentions_enabled"]
            ),
            inline=True
        )


        embed.add_field(
            name="Duplicate Messages",
            value=status(
                settings["duplicate_enabled"]
            ),
            inline=True
        )


        embed.add_field(
            name="Blocked Words",
            value=status(
                settings["bad_words_enabled"]
            ),
            inline=True
        )


        embed.add_field(
            name="Timeout Threshold",
            value=(
                f"{settings['warning_threshold']} "
                f"violations"
            ),
            inline=True
        )


        embed.add_field(
            name="Timeout Length",
            value=(
                f"{settings['timeout_minutes']} "
                f"minutes"
            ),
            inline=True
        )


        await ctx.send(
            embed=embed
        )


    # ======================================================
    # GENERIC FEATURE TOGGLE
    # ======================================================

    async def toggle_feature(
        self,
        ctx,
        setting_name: str,
        enabled: str
    ):

        value = enabled.lower()


        if value not in (
            "on",
            "off"
        ):

            return await ctx.send(
                "❌ Use `on` or `off`."
            )


        update_setting(
            ctx.guild.id,
            setting_name,
            1 if value == "on" else 0
        )


        status = (
            "enabled"
            if value == "on"
            else "disabled"
        )


        await ctx.send(
            f"🛡️ `{setting_name}` has been "
            f"**{status}**."
        )


    # ======================================================
    # SPAM TOGGLE
    # ======================================================

    @automod.command()
    async def spam(
        self,
        ctx,
        enabled: str
    ):

        await self.toggle_feature(
            ctx,
            "spam_enabled",
            enabled
        )


    # ======================================================
    # LINKS TOGGLE
    # ======================================================

    @automod.command()
    async def links(
        self,
        ctx,
        enabled: str
    ):

        await self.toggle_feature(
            ctx,
            "links_enabled",
            enabled
        )


    # ======================================================
    # CAPS TOGGLE
    # ======================================================

    @automod.command()
    async def caps(
        self,
        ctx,
        enabled: str
    ):

        await self.toggle_feature(
            ctx,
            "caps_enabled",
            enabled
        )


    # ======================================================
    # MENTIONS TOGGLE
    # ======================================================

    @automod.command()
    async def mentions(
        self,
        ctx,
        enabled: str
    ):

        await self.toggle_feature(
            ctx,
            "mentions_enabled",
            enabled
        )


    # ======================================================
    # DUPLICATE TOGGLE
    # ======================================================

    @automod.command()
    async def duplicate(
        self,
        ctx,
        enabled: str
    ):

        await self.toggle_feature(
            ctx,
            "duplicate_enabled",
            enabled
        )


    # ======================================================
    # WORDS TOGGLE
    # ======================================================

    @automod.command()
    async def words(
        self,
        ctx,
        enabled: str
    ):

        await self.toggle_feature(
            ctx,
            "bad_words_enabled",
            enabled
        )


    # ======================================================
    # WORD GROUP
    # ======================================================

    @automod.group(
        name="word",
        invoke_without_command=True
    )
    async def word(
        self,
        ctx
    ):

        await ctx.send(
            "Use `!automod word add <word>`, "
            "`remove <word>`, or `list`."
        )


    # ======================================================
    # ADD WORD
    # ======================================================

    @word.command(
        name="add"
    )
    async def word_add(
        self,
        ctx,
        *,
        word: str
    ):

        word = word.strip().lower()


        if not word:

            return await ctx.send(
                "❌ Enter a word or phrase."
            )


        db = get_db()

        try:

            cursor = db.cursor()


            cursor.execute(
                """
                SELECT 1
                FROM automod_words
                WHERE guild_id = ?
                AND word = ?
                LIMIT 1
                """,
                (
                    ctx.guild.id,
                    word
                )
            )


            if cursor.fetchone():

                return await ctx.send(
                    "❌ That word is already blocked."
                )


            cursor.execute(
                """
                INSERT INTO automod_words (
                    guild_id,
                    word
                )
                VALUES (?, ?)
                """,
                (
                    ctx.guild.id,
                    word
                )
            )


            db.commit()

        finally:

            db.close()


        await ctx.send(
            f"🛡️ Added `{word}` to the AutoMod "
            f"blocked-word list."
        )


    # ======================================================
    # REMOVE WORD
    # ======================================================

    @word.command(
        name="remove"
    )
    async def word_remove(
        self,
        ctx,
        *,
        word: str
    ):

        word = word.strip().lower()


        db = get_db()

        try:

            cursor = db.cursor()


            cursor.execute(
                """
                DELETE FROM automod_words
                WHERE guild_id = ?
                AND word = ?
                """,
                (
                    ctx.guild.id,
                    word
                )
            )


            removed = cursor.rowcount > 0

            db.commit()

        finally:

            db.close()


        if removed:

            await ctx.send(
                f"🗑️ Removed `{word}` from the "
                f"AutoMod blocked-word list."
            )

        else:

            await ctx.send(
                f"❌ `{word}` wasn't in the blocked-word list."
            )


    # ======================================================
    # LIST WORDS
    # ======================================================

    @word.command(
        name="list"
    )
    async def word_list(
        self,
        ctx
    ):

        words = get_words(
            ctx.guild.id
        )


        if not words:

            return await ctx.send(
                "📭 No custom AutoMod words have been added."
            )


        display = "\n".join(
            f"• `{word}`"
            for word in words[:50]
        )


        embed = discord.Embed(
            title="🛡️ Blocked Words",
            description=display,
            color=EMBED_COLOR
        )


        if len(words) > 50:

            embed.set_footer(
                text=(
                    f"Showing 50 of "
                    f"{len(words)} words."
                )
            )


        await ctx.send(
            embed=embed
        )


    # ======================================================
    # EXEMPT GROUP
    # ======================================================

    @automod.group(
        name="exempt",
        invoke_without_command=True
    )
    async def exempt(
        self,
        ctx
    ):

        await ctx.send(
            "Use `!automod exempt channel` or "
            "`!automod exempt role @role`."
        )


    # ======================================================
    # EXEMPT CHANNEL
    # ======================================================

    @exempt.command(
        name="channel"
    )
    async def exempt_channel(
        self,
        ctx
    ):

        db = get_db()

        try:

            cursor = db.cursor()


            cursor.execute(
                """
                SELECT 1
                FROM automod_exempt_channels
                WHERE guild_id = ?
                AND channel_id = ?
                LIMIT 1
                """,
                (
                    ctx.guild.id,
                    ctx.channel.id
                )
            )


            exists = cursor.fetchone() is not None


            if exists:

                cursor.execute(
                    """
                    DELETE FROM automod_exempt_channels
                    WHERE guild_id = ?
                    AND channel_id = ?
                    """,
                    (
                        ctx.guild.id,
                        ctx.channel.id
                    )
                )

                db.commit()

                return await ctx.send(
                    f"🛡️ AutoMod is **no longer exempt** "
                    f"in {ctx.channel.mention}."
                )


            cursor.execute(
                """
                INSERT INTO automod_exempt_channels (
                    guild_id,
                    channel_id
                )
                VALUES (?, ?)
                """,
                (
                    ctx.guild.id,
                    ctx.channel.id
                )
            )


            db.commit()

        finally:

            db.close()


        await ctx.send(
            f"🛡️ AutoMod is now **exempt** "
            f"in {ctx.channel.mention}."
        )


    # ======================================================
    # EXEMPT ROLE
    # ======================================================

    @exempt.command(
        name="role"
    )
    async def exempt_role(
        self,
        ctx,
        role: discord.Role
    ):

        # --------------------------------------------------
        # Never exempt @everyone.
        # --------------------------------------------------

        if role == ctx.guild.default_role:

            return await ctx.send(
                "❌ You can't exempt the @everyone role."
            )


        db = get_db()

        try:

            cursor = db.cursor()


            cursor.execute(
                """
                SELECT 1
                FROM automod_exempt_roles
                WHERE guild_id = ?
                AND role_id = ?
                LIMIT 1
                """,
                (
                    ctx.guild.id,
                    role.id
                )
            )


            exists = cursor.fetchone() is not None


            if exists:

                cursor.execute(
                    """
                    DELETE FROM automod_exempt_roles
                    WHERE guild_id = ?
                    AND role_id = ?
                    """,
                    (
                        ctx.guild.id,
                        role.id
                    )
                )


                db.commit()


                return await ctx.send(
                    f"🛡️ AutoMod is **no longer exempt** "
                    f"for {role.mention}."
                )


            cursor.execute(
                """
                INSERT INTO automod_exempt_roles (
                    guild_id,
                    role_id
                )
                VALUES (?, ?)
                """,
                (
                    ctx.guild.id,
                    role.id
                )
            )


            db.commit()

        finally:

            db.close()


        await ctx.send(
            f"🛡️ AutoMod is now **exempt** "
            f"for {role.mention}."
        )


    # ======================================================
    # ERROR HANDLER
    # ======================================================

    @automod.error
    async def automod_error(
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
                "to configure AutoMod."
            )

            return


        if isinstance(
            error,
            commands.MissingRequiredArgument
        ):

            await ctx.send(
                "❌ You're missing a required argument."
            )

            return


        if isinstance(
            error,
            commands.RoleNotFound
        ):

            await ctx.send(
                "❌ I couldn't find that role."
            )

            return


        raise error


# ==========================================================
# SETUP
# ==========================================================

async def setup(
    bot
):

    await bot.add_cog(
        AutoMod(bot)
    )