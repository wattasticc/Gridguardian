import sqlite3
from datetime import datetime, timezone

import discord
from discord.ext import commands


EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)


# =========================================================
# DATABASE
# =========================================================

db = sqlite3.connect("gridguardian.db")
cursor = db.cursor()

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

cursor.execute("""
CREATE TABLE IF NOT EXISTS automod_words (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    word TEXT NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS automod_exempt_channels (
    guild_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    PRIMARY KEY (guild_id, channel_id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS automod_exempt_roles (
    guild_id INTEGER NOT NULL,
    role_id INTEGER NOT NULL,
    PRIMARY KEY (guild_id, role_id)
)
""")

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


# =========================================================
# DEFAULT SETTINGS
# =========================================================

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


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def ensure_guild_settings(guild_id: int):
    cursor.execute("""
    SELECT guild_id
    FROM automod_settings
    WHERE guild_id=?
    """, (guild_id,))

    if cursor.fetchone():
        return

    cursor.execute("""
    INSERT INTO automod_settings (
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
    """, (
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
    ))

    db.commit()


def get_settings(guild_id: int):
    ensure_guild_settings(guild_id)

    cursor.execute("""
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
    WHERE guild_id=?
    """, (guild_id,))

    result = cursor.fetchone()

    if not result:
        return None

    return {
        "enabled": bool(result[0]),
        "spam_enabled": bool(result[1]),
        "links_enabled": bool(result[2]),
        "caps_enabled": bool(result[3]),
        "mentions_enabled": bool(result[4]),
        "duplicate_enabled": bool(result[5]),
        "bad_words_enabled": bool(result[6]),
        "warning_threshold": result[7],
        "timeout_minutes": result[8],
    }


def update_setting(guild_id: int, setting: str, value):
    ensure_guild_settings(guild_id)

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

    cursor.execute(
        f"""
        UPDATE automod_settings
        SET {setting}=?
        WHERE guild_id=?
        """,
        (value, guild_id)
    )

    db.commit()

    return True


def get_violation_count(guild_id: int, user_id: int):
    cursor.execute("""
    SELECT COUNT(*)
    FROM automod_violations
    WHERE guild_id=?
    AND user_id=?
    """, (
        guild_id,
        user_id
    ))

    return cursor.fetchone()[0]


def record_violation(
    guild_id: int,
    user_id: int,
    rule: str,
    message: str
):
    cursor.execute("""
    INSERT INTO automod_violations (
        guild_id,
        user_id,
        rule,
        message
    )
    VALUES (?, ?, ?, ?)
    """, (
        guild_id,
        user_id,
        rule,
        message[:1000]
    ))

    db.commit()


def get_words(guild_id: int):
    cursor.execute("""
    SELECT word
    FROM automod_words
    WHERE guild_id=?
    ORDER BY word ASC
    """, (guild_id,))

    return [row[0].lower() for row in cursor.fetchall()]


def is_exempt(message: discord.Message):
    guild_id = message.guild.id

    # Exempt channel
    cursor.execute("""
    SELECT 1
    FROM automod_exempt_channels
    WHERE guild_id=?
    AND channel_id=?
    """, (
        guild_id,
        message.channel.id
    ))

    if cursor.fetchone():
        return True

    # Exempt role
    if isinstance(message.author, discord.Member):

        role_ids = [role.id for role in message.author.roles]

        if role_ids:
            placeholders = ",".join("?" for _ in role_ids)

            cursor.execute(
                f"""
                SELECT 1
                FROM automod_exempt_roles
                WHERE guild_id=?
                AND role_id IN ({placeholders})
                LIMIT 1
                """,
                [guild_id, *role_ids]
            )

            if cursor.fetchone():
                return True

    return False


# =========================================================
# AUTOMOD COG
# =========================================================

class AutoMod(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        # user_id -> list of recent message timestamps
        self.message_history = {}

        # user_id -> last message content
        self.last_messages = {}


    # =====================================================
    # CHECK SPAM
    # =====================================================

    def check_spam(self, message: discord.Message):

        now = datetime.now(timezone.utc)

        user_id = message.author.id

        if user_id not in self.message_history:
            self.message_history[user_id] = []

        timestamps = self.message_history[user_id]

        timestamps.append(now)

        # Keep only messages from the last 5 seconds.
        timestamps[:] = [
            timestamp
            for timestamp in timestamps
            if (now - timestamp).total_seconds() <= 5
        ]

        # 5 messages within 5 seconds = spam.
        if len(timestamps) >= 5:
            return True

        return False


    # =====================================================
    # CHECK DUPLICATE MESSAGE
    # =====================================================

    def check_duplicate(self, message: discord.Message):

        user_id = message.author.id

        content = message.content.strip().lower()

        if not content:
            return False

        previous = self.last_messages.get(user_id)

        self.last_messages[user_id] = content

        if previous and previous == content:
            return True

        return False


    # =====================================================
    # CHECK CAPS
    # =====================================================

    def check_caps(self, message: discord.Message):

        content = message.content

        letters = [
            character
            for character in content
            if character.isalpha()
        ]

        if len(letters) < 10:
            return False

        uppercase = [
            character
            for character in letters
            if character.isupper()
        ]

        percentage = len(uppercase) / len(letters)

        return percentage >= 0.80


    # =====================================================
    # CHECK MENTIONS
    # =====================================================

    def check_mentions(self, message: discord.Message):

        # Everyone/here mention
        if message.mention_everyone:
            return True

        # Excessive individual mentions
        if len(message.mentions) >= 6:
            return True

        return False


    # =====================================================
    # CHECK LINKS
    # =====================================================

    def check_links(self, message: discord.Message):

        content = message.content.lower()

        blocked_patterns = [
            "discord.gg/",
            "discord.com/invite/",
            "discordapp.com/invite/",
        ]

        return any(
            pattern in content
            for pattern in blocked_patterns
        )


    # =====================================================
    # CHECK CUSTOM WORDS
    # =====================================================

    def check_bad_words(self, message: discord.Message):

        content = message.content.lower()

        words = get_words(message.guild.id)

        for word in words:

            if word in content:
                return True

        return False


    # =====================================================
    # AUTOMOD ACTION
    # =====================================================

    async def handle_violation(
        self,
        message: discord.Message,
        rule: str
    ):

        guild = message.guild
        member = message.author

        record_violation(
            guild.id,
            member.id,
            rule,
            message.content
        )

        # Delete the offending message.
        try:
            await message.delete()
        except (
            discord.Forbidden,
            discord.NotFound,
            discord.HTTPException
        ):
            pass

        settings = get_settings(guild.id)

        violation_count = get_violation_count(
            guild.id,
            member.id
        )

        threshold = settings["warning_threshold"]

        # Inform the member.
        try:

            warning_message = await message.channel.send(
                f"⚠️ {member.mention}, your message was removed "
                f"because it triggered **{rule}**."
            )

            await warning_message.delete(delay=5)

        except (
            discord.Forbidden,
            discord.HTTPException
        ):
            pass

        # Automatic timeout after threshold.
        if (
            threshold > 0
            and violation_count % threshold == 0
        ):

            if (
                member.guild_permissions.moderate_members
                or member.guild_permissions.administrator
            ):
                return

            try:

                duration = settings["timeout_minutes"]

                until = (
                    discord.utils.utcnow()
                    + discord.utils.timedelta(
                        minutes=duration
                    )
                )

                await member.timeout(
                    until,
                    reason=f"Grid Guardian AutoMod: {rule}"
                )

            except (
                discord.Forbidden,
                discord.HTTPException
            ):
                pass


    # =====================================================
    # MESSAGE LISTENER
    # =====================================================

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):

        if message.author.bot:
            return

        if not message.guild:
            return

        settings = get_settings(
            message.guild.id
        )

        if not settings["enabled"]:
            return

        if is_exempt(message):
            return

        violation = None

        # -----------------------------
        # MENTION SPAM
        # -----------------------------

        if (
            settings["mentions_enabled"]
            and self.check_mentions(message)
        ):
            violation = "Mention Spam"

        # -----------------------------
        # SPAM
        # -----------------------------

        elif (
            settings["spam_enabled"]
            and self.check_spam(message)
        ):
            violation = "Spam"

        # -----------------------------
        # DUPLICATE MESSAGES
        # -----------------------------

        elif (
            settings["duplicate_enabled"]
            and self.check_duplicate(message)
        ):
            violation = "Duplicate Message"

        # -----------------------------
        # CAPS
        # -----------------------------

        elif (
            settings["caps_enabled"]
            and self.check_caps(message)
        ):
            violation = "Excessive Caps"

        # -----------------------------
        # INVITE LINKS
        # -----------------------------

        elif (
            settings["links_enabled"]
            and self.check_links(message)
        ):
            violation = "Discord Invite Link"

        # -----------------------------
        # CUSTOM WORDS
        # -----------------------------

        elif (
            settings["bad_words_enabled"]
            and self.check_bad_words(message)
        ):
            violation = "Blocked Word"

        if violation:
            await self.handle_violation(
                message,
                violation
            )


    # =====================================================
    # !AUTOMOD
    # =====================================================

    @commands.group(
        invoke_without_command=True
    )
    @commands.has_permissions(manage_guild=True)
    async def automod(self, ctx):

        embed = discord.Embed(
            title="🛡️ Grid Guardian AutoMod",
            description=(
                "Use the commands below to configure AutoMod."
            ),
            color=EMBED_COLOR
        )

        embed.add_field(
            name="Enable",
            value="`!automod enable`",
            inline=True
        )

        embed.add_field(
            name="Disable",
            value="`!automod disable`",
            inline=True
        )

        embed.add_field(
            name="Settings",
            value="`!automod settings`",
            inline=True
        )

        embed.add_field(
            name="Feature Controls",
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
            name="Custom Words",
            value=(
                "`!automod word add <word>`\n"
                "`!automod word remove <word>`\n"
                "`!automod word list`"
            ),
            inline=False
        )

        embed.add_field(
            name="Exemptions",
            value=(
                "`!automod exempt channel`\n"
                "`!automod exempt role`"
            ),
            inline=False
        )

        await ctx.send(embed=embed)


    # =====================================================
    # ENABLE
    # =====================================================

    @automod.command()
    async def enable(self, ctx):

        update_setting(
            ctx.guild.id,
            "enabled",
            1
        )

        await ctx.send(
            "🛡️ **Grid Guardian AutoMod is now enabled.**"
        )


    # =====================================================
    # DISABLE
    # =====================================================

    @automod.command()
    async def disable(self, ctx):

        update_setting(
            ctx.guild.id,
            "enabled",
            0
        )

        await ctx.send(
            "🛡️ **Grid Guardian AutoMod is now disabled.**"
        )


    # =====================================================
    # SETTINGS
    # =====================================================

    @automod.command()
    async def settings(self, ctx):

        settings = get_settings(
            ctx.guild.id
        )

        def status(value):
            return "🟢 ON" if value else "🔴 OFF"

        embed = discord.Embed(
            title="🛡️ AutoMod Settings",
            color=EMBED_COLOR
        )

        embed.add_field(
            name="AutoMod",
            value=status(settings["enabled"]),
            inline=True
        )

        embed.add_field(
            name="Spam",
            value=status(settings["spam_enabled"]),
            inline=True
        )

        embed.add_field(
            name="Invite Links",
            value=status(settings["links_enabled"]),
            inline=True
        )

        embed.add_field(
            name="Excessive Caps",
            value=status(settings["caps_enabled"]),
            inline=True
        )

        embed.add_field(
            name="Mention Spam",
            value=status(settings["mentions_enabled"]),
            inline=True
        )

        embed.add_field(
            name="Duplicate Messages",
            value=status(settings["duplicate_enabled"]),
            inline=True
        )

        embed.add_field(
            name="Blocked Words",
            value=status(settings["bad_words_enabled"]),
            inline=True
        )

        embed.add_field(
            name="Timeout Threshold",
            value=(
                f"{settings['warning_threshold']} violations"
            ),
            inline=True
        )

        embed.add_field(
            name="Timeout Length",
            value=(
                f"{settings['timeout_minutes']} minutes"
            ),
            inline=True
        )

        await ctx.send(embed=embed)


    # =====================================================
    # FEATURE TOGGLE
    # =====================================================

    async def toggle_feature(
        self,
        ctx,
        setting_name,
        enabled
    ):

        value = enabled.lower()

        if value not in ("on", "off"):

            return await ctx.send(
                "❌ Use `on` or `off`."
            )

        update_setting(
            ctx.guild.id,
            setting_name,
            1 if value == "on" else 0
        )

        status = "enabled" if value == "on" else "disabled"

        await ctx.send(
            f"🛡️ AutoMod feature `{setting_name}` "
            f"has been **{status}**."
        )


    @automod.command()
    async def spam(self, ctx, enabled: str):
        await self.toggle_feature(
            ctx,
            "spam_enabled",
            enabled
        )


    @automod.command()
    async def links(self, ctx, enabled: str):
        await self.toggle_feature(
            ctx,
            "links_enabled",
            enabled
        )


    @automod.command()
    async def caps(self, ctx, enabled: str):
        await self.toggle_feature(
            ctx,
            "caps_enabled",
            enabled
        )


    @automod.command()
    async def mentions(self, ctx, enabled: str):
        await self.toggle_feature(
            ctx,
            "mentions_enabled",
            enabled
        )


    @automod.command()
    async def duplicate(self, ctx, enabled: str):
        await self.toggle_feature(
            ctx,
            "duplicate_enabled",
            enabled
        )


    @automod.command()
    async def words(self, ctx, enabled: str):
        await self.toggle_feature(
            ctx,
            "bad_words_enabled",
            enabled
        )


    # =====================================================
    # CUSTOM WORDS
    # =====================================================

    @automod.group(
        name="word",
        invoke_without_command=True
    )
    async def word(self, ctx):

        await ctx.send(
            "Use `!automod word add`, "
            "`remove`, or `list`."
        )


    @word.command(name="add")
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

        cursor.execute("""
        SELECT 1
        FROM automod_words
        WHERE guild_id=?
        AND word=?
        """, (
            ctx.guild.id,
            word
        ))

        if cursor.fetchone():

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

        await ctx.send(
            f"🛡️ Added `{word}` to the AutoMod word filter."
        )


    @word.command(name="remove")
    async def word_remove(
        self,
        ctx,
        *,
        word: str
    ):

        word = word.strip().lower()

        cursor.execute("""
        DELETE FROM automod_words
        WHERE guild_id=?
        AND word=?
        """, (
            ctx.guild.id,
            word
        ))

        db.commit()

        await ctx.send(
            f"🗑️ Removed `{word}` from the AutoMod word filter."
        )


    @word.command(name="list")
    async def word_list(self, ctx):

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
                text=f"Showing 50 of {len(words)} words."
            )

        await ctx.send(embed=embed)


    # =====================================================
    # EXEMPT CHANNEL
    # =====================================================

    @automod.group(
        name="exempt",
        invoke_without_command=True
    )
    async def exempt(self, ctx):

        await ctx.send(
            "Use `!automod exempt channel` "
            "or `!automod exempt role`."
        )


    @exempt.command(name="channel")
    async def exempt_channel(self, ctx):

        cursor.execute("""
        SELECT 1
        FROM automod_exempt_channels
        WHERE guild_id=?
        AND channel_id=?
        """, (
            ctx.guild.id,
            ctx.channel.id
        ))

        if cursor.fetchone():

            cursor.execute("""
            DELETE FROM automod_exempt_channels
            WHERE guild_id=?
            AND channel_id=?
            """, (
                ctx.guild.id,
                ctx.channel.id
            ))

            db.commit()

            return await ctx.send(
                f"🛡️ AutoMod is no longer exempt in "
                f"{ctx.channel.mention}."
            )

        cursor.execute("""
        INSERT INTO automod_exempt_channels (
            guild_id,
            channel_id
        )
        VALUES (?, ?)
        """, (
            ctx.guild.id,
            ctx.channel.id
        ))

        db.commit()

        await ctx.send(
            f"🛡️ AutoMod is now exempt in "
            f"{ctx.channel.mention}."
        )


    # =====================================================
    # EXEMPT ROLE
    # =====================================================

    @exempt.command(name="role")
    async def exempt_role(
        self,
        ctx,
        role: discord.Role
    ):

        cursor.execute("""
        SELECT 1
        FROM automod_exempt_roles
        WHERE guild_id=?
        AND role_id=?
        """, (
            ctx.guild.id,
            role.id
        ))

        if cursor.fetchone():

            cursor.execute("""
            DELETE FROM automod_exempt_roles
            WHERE guild_id=?
            AND role_id=?
            """, (
                ctx.guild.id,
                role.id
            ))

            db.commit()

            return await ctx.send(
                f"🛡️ AutoMod is no longer exempt for "
                f"{role.mention}."
            )

        cursor.execute("""
        INSERT INTO automod_exempt_roles (
            guild_id,
            role_id
        )
        VALUES (?, ?)
        """, (
            ctx.guild.id,
            role.id
        ))

        db.commit()

        await ctx.send(
            f"🛡️ AutoMod is now exempt for "
            f"{role.mention}."
        )


    # =====================================================
    # ERROR HANDLER
    # =====================================================

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
            commands.CommandNotFound
        ):
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


# =========================================================
# SETUP
# =========================================================

async def setup(bot):

    await bot.add_cog(
        AutoMod(bot)
    )