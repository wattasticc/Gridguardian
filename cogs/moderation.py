"""
Grid Guardian - Advanced Moderation

Features:
    !warn @user <reason>
    !warnings @user
    !clearwarnings @user

    !kick @user <reason>
    !ban @user <reason>
    !unban <user_id>

    !timeout @user <minutes> <reason>
    !untimeout @user

    !case <case_id>
    !modlog #channel
    !modsettings
    !setpunishment <warning_count> <action>
    !moderationhelp

Features include:
    - Persistent warning history
    - Moderation case IDs
    - Moderation logs
    - Role hierarchy protection
    - Self-action protection
    - Bot protection
    - Warning escalation
    - SQLite persistence
"""

import sqlite3
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

DEFAULT_REASON = "No reason provided"


# ==========================================================
# DATABASE
# ==========================================================

def get_db():
    """
    Create a fresh SQLite connection.
    """

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
    """
    Create moderation tables.
    """

    db = get_db()

    try:

        cursor = db.cursor()

        # --------------------------------------------------
        # Moderation cases
        # --------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS moderation_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                moderator_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                reason TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # --------------------------------------------------
        # Warnings
        # --------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS moderation_warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                moderator_id INTEGER NOT NULL,
                reason TEXT NOT NULL,
                case_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # --------------------------------------------------
        # Moderation settings
        # --------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS moderation_settings (
                guild_id INTEGER PRIMARY KEY,
                log_channel_id INTEGER,
                timeout_warning_count INTEGER DEFAULT 0,
                kick_warning_count INTEGER DEFAULT 0,
                ban_warning_count INTEGER DEFAULT 0
            )
        """)

        db.commit()

    finally:

        db.close()


initialize_database()


# ==========================================================
# MODERATION COG
# ==========================================================

class Moderation(commands.Cog):

    def __init__(self, bot):

        self.bot = bot


    # ======================================================
    # DATABASE HELPERS
    # ======================================================

    @staticmethod
    def create_case(
        guild_id: int,
        user_id: int,
        moderator_id: int,
        action: str,
        reason: str
    ):

        db = get_db()

        try:

            cursor = db.cursor()

            cursor.execute(
                """
                INSERT INTO moderation_cases (
                    guild_id,
                    user_id,
                    moderator_id,
                    action,
                    reason
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    guild_id,
                    user_id,
                    moderator_id,
                    action,
                    reason
                )
            )

            case_id = cursor.lastrowid

            db.commit()

            return case_id

        finally:

            db.close()


    @staticmethod
    def create_warning(
        guild_id: int,
        user_id: int,
        moderator_id: int,
        reason: str,
        case_id: int
    ):

        db = get_db()

        try:

            cursor = db.cursor()

            cursor.execute(
                """
                INSERT INTO moderation_warnings (
                    guild_id,
                    user_id,
                    moderator_id,
                    reason,
                    case_id
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    guild_id,
                    user_id,
                    moderator_id,
                    reason,
                    case_id
                )
            )

            warning_id = cursor.lastrowid

            db.commit()

            return warning_id

        finally:

            db.close()


    @staticmethod
    def get_warning_count(
        guild_id: int,
        user_id: int
    ) -> int:

        db = get_db()

        try:

            cursor = db.cursor()

            cursor.execute(
                """
                SELECT COUNT(*) AS count
                FROM moderation_warnings
                WHERE guild_id = ?
                AND user_id = ?
                """,
                (
                    guild_id,
                    user_id
                )
            )

            result = cursor.fetchone()

            return int(result["count"])

        finally:

            db.close()


    @staticmethod
    def get_settings(
        guild_id: int
    ):

        db = get_db()

        try:

            cursor = db.cursor()

            cursor.execute(
                """
                INSERT OR IGNORE INTO moderation_settings (
                    guild_id
                )
                VALUES (?)
                """,
                (
                    guild_id,
                )
            )

            db.commit()

            cursor.execute(
                """
                SELECT *
                FROM moderation_settings
                WHERE guild_id = ?
                """,
                (
                    guild_id,
                )
            )

            return cursor.fetchone()

        finally:

            db.close()


    @staticmethod
    def update_setting(
        guild_id: int,
        column: str,
        value
    ):

        allowed_columns = {
            "log_channel_id",
            "timeout_warning_count",
            "kick_warning_count",
            "ban_warning_count"
        }

        if column not in allowed_columns:
            return

        db = get_db()

        try:

            cursor = db.cursor()

            cursor.execute(
                """
                INSERT OR IGNORE INTO moderation_settings (
                    guild_id
                )
                VALUES (?)
                """,
                (
                    guild_id,
                )
            )

            cursor.execute(
                f"""
                UPDATE moderation_settings
                SET {column} = ?
                WHERE guild_id = ?
                """,
                (
                    value,
                    guild_id
                )
            )

            db.commit()

        finally:

            db.close()


    # ======================================================
    # CASE LOOKUP
    # ======================================================

    @staticmethod
    def get_case(
        guild_id: int,
        case_id: int
    ):

        db = get_db()

        try:

            cursor = db.cursor()

            cursor.execute(
                """
                SELECT *
                FROM moderation_cases
                WHERE guild_id = ?
                AND id = ?
                """,
                (
                    guild_id,
                    case_id
                )
            )

            return cursor.fetchone()

        finally:

            db.close()


    # ======================================================
    # HIERARCHY CHECK
    # ======================================================

    @staticmethod
    def can_moderate(
        ctx,
        member: discord.Member
    ):
        """
        Check whether the moderator is allowed to act
        on the target.
        """

        if member == ctx.author:

            return False, (
                "❌ You cannot moderate yourself."
            )


        if member == ctx.guild.owner:

            return False, (
                "❌ You cannot moderate the server owner."
            )


        if member == ctx.guild.me:

            return False, (
                "❌ You cannot moderate me."
            )


        # --------------------------------------------------
        # Moderator hierarchy
        # --------------------------------------------------

        if (
            ctx.author != ctx.guild.owner
            and member.top_role >= ctx.author.top_role
        ):

            return False, (
                "❌ You cannot moderate someone with "
                "an equal or higher role."
            )


        # --------------------------------------------------
        # Bot hierarchy
        # --------------------------------------------------

        if member.top_role >= ctx.guild.me.top_role:

            return False, (
                "❌ I cannot moderate that member because "
                "their highest role is equal to or higher "
                "than mine."
            )


        return True, None


    # ======================================================
    # SEND MODERATION LOG
    # ======================================================

    async def send_mod_log(
        self,
        guild: discord.Guild,
        case_id: int,
        action: str,
        target_id: int,
        moderator: discord.Member,
        reason: str,
        color: discord.Color
    ):

        settings = self.get_settings(
            guild.id
        )

        channel_id = settings["log_channel_id"]

        if not channel_id:
            return


        channel = guild.get_channel(
            channel_id
        )

        if channel is None:
            return


        target = guild.get_member(
            target_id
        )

        target_text = (
            target.mention
            if target
            else f"<@{target_id}>"
        )


        embed = discord.Embed(
            title=f"🛡️ Moderation • {action}",
            color=color
        )

        embed.add_field(
            name="🆔 Case",
            value=f"#{case_id}",
            inline=True
        )

        embed.add_field(
            name="👤 User",
            value=target_text,
            inline=True
        )

        embed.add_field(
            name="👮 Moderator",
            value=moderator.mention,
            inline=True
        )

        embed.add_field(
            name="📝 Reason",
            value=reason,
            inline=False
        )

        embed.set_footer(
            text="Grid Guardian Moderation"
        )


        try:

            await channel.send(
                embed=embed
            )

        except (
            discord.Forbidden,
            discord.HTTPException
        ):

            pass


    # ======================================================
    # APPLY WARNING ESCALATION
    # ======================================================

    async def process_escalation(
        self,
        ctx,
        member: discord.Member,
        warning_count: int
    ):
        """
        Check configured warning thresholds.

        Priority:
            Ban
            Kick
            Timeout
        """

        settings = self.get_settings(
            ctx.guild.id
        )


        # --------------------------------------------------
        # BAN
        # --------------------------------------------------

        ban_threshold = int(
            settings["ban_warning_count"] or 0
        )

        if (
            ban_threshold > 0
            and warning_count >= ban_threshold
        ):

            try:

                case_id = self.create_case(
                    ctx.guild.id,
                    member.id,
                    ctx.author.id,
                    "Ban",
                    (
                        f"Automatic escalation after "
                        f"{warning_count} warnings."
                    )
                )

                await member.ban(
                    reason=(
                        f"Automatic escalation after "
                        f"{warning_count} warnings."
                    )
                )

                await self.send_mod_log(
                    ctx.guild,
                    case_id,
                    "Ban",
                    member.id,
                    ctx.author,
                    (
                        f"Automatic escalation after "
                        f"{warning_count} warnings."
                    ),
                    discord.Color.red()
                )

                return (
                    "🔨 Automatic escalation: "
                    "member banned."
                )

            except (
                discord.Forbidden,
                discord.HTTPException
            ):

                return (
                    "⚠️ The warning threshold was reached, "
                    "but I could not ban the member."
                )


        # --------------------------------------------------
        # KICK
        # --------------------------------------------------

        kick_threshold = int(
            settings["kick_warning_count"] or 0
        )

        if (
            kick_threshold > 0
            and warning_count >= kick_threshold
        ):

            try:

                case_id = self.create_case(
                    ctx.guild.id,
                    member.id,
                    ctx.author.id,
                    "Kick",
                    (
                        f"Automatic escalation after "
                        f"{warning_count} warnings."
                    )
                )

                await member.kick(
                    reason=(
                        f"Automatic escalation after "
                        f"{warning_count} warnings."
                    )
                )

                await self.send_mod_log(
                    ctx.guild,
                    case_id,
                    "Kick",
                    member.id,
                    ctx.author,
                    (
                        f"Automatic escalation after "
                        f"{warning_count} warnings."
                    ),
                    discord.Color.red()
                )

                return (
                    "👢 Automatic escalation: "
                    "member kicked."
                )

            except (
                discord.Forbidden,
                discord.HTTPException
            ):

                return (
                    "⚠️ The warning threshold was reached, "
                    "but I could not kick the member."
                )


        # --------------------------------------------------
        # TIMEOUT
        # --------------------------------------------------

        timeout_threshold = int(
            settings["timeout_warning_count"] or 0
        )

        if (
            timeout_threshold > 0
            and warning_count >= timeout_threshold
        ):

            try:

                duration = timedelta(
                    minutes=10
                )

                case_id = self.create_case(
                    ctx.guild.id,
                    member.id,
                    ctx.author.id,
                    "Timeout",
                    (
                        f"Automatic escalation after "
                        f"{warning_count} warnings."
                    )
                )

                await member.timeout(
                    duration,
                    reason=(
                        f"Automatic escalation after "
                        f"{warning_count} warnings."
                    )
                )

                await self.send_mod_log(
                    ctx.guild,
                    case_id,
                    "Timeout",
                    member.id,
                    ctx.author,
                    (
                        f"Automatic escalation after "
                        f"{warning_count} warnings."
                    ),
                    discord.Color.orange()
                )

                return (
                    "⏱️ Automatic escalation: "
                    "member timed out for 10 minutes."
                )

            except (
                discord.Forbidden,
                discord.HTTPException
            ):

                return (
                    "⚠️ The warning threshold was reached, "
                    "but I could not timeout the member."
                )


        return None


    # ======================================================
    # !WARN
    # ======================================================

    @commands.command()
    @commands.has_permissions(
        moderate_members=True
    )
    async def warn(
        self,
        ctx,
        member: discord.Member,
        *,
        reason: str = DEFAULT_REASON
    ):

        if ctx.guild is None:

            return await ctx.send(
                "❌ This command can only be used in a server."
            )


        allowed, error = self.can_moderate(
            ctx,
            member
        )

        if not allowed:

            return await ctx.send(
                error
            )


        # --------------------------------------------------
        # Create case
        # --------------------------------------------------

        case_id = self.create_case(
            ctx.guild.id,
            member.id,
            ctx.author.id,
            "Warning",
            reason
        )


        # --------------------------------------------------
        # Create warning
        # --------------------------------------------------

        warning_id = self.create_warning(
            ctx.guild.id,
            member.id,
            ctx.author.id,
            reason,
            case_id
        )


        warning_count = self.get_warning_count(
            ctx.guild.id,
            member.id
        )


        embed = discord.Embed(
            title="⚠️ Member Warned",
            description=(
                f"{member.mention} has received a warning."
            ),
            color=discord.Color.orange()
        )

        embed.add_field(
            name="🆔 Case",
            value=f"#{case_id}",
            inline=True
        )

        embed.add_field(
            name="⚠️ Warning",
            value=f"#{warning_id}",
            inline=True
        )

        embed.add_field(
            name="📊 Total Warnings",
            value=str(warning_count),
            inline=True
        )

        embed.add_field(
            name="📝 Reason",
            value=reason,
            inline=False
        )

        embed.set_footer(
            text=f"Moderator: {ctx.author}"
        )


        await ctx.send(
            embed=embed
        )


        await self.send_mod_log(
            ctx.guild,
            case_id,
            "Warning",
            member.id,
            ctx.author,
            reason,
            discord.Color.orange()
        )


        # --------------------------------------------------
        # Escalation
        # --------------------------------------------------

        escalation = await self.process_escalation(
            ctx,
            member,
            warning_count
        )

        if escalation:

            await ctx.send(
                escalation
            )


    # ======================================================
    # !WARNINGS
    # ======================================================

    @commands.command()
    @commands.has_permissions(
        moderate_members=True
    )
    async def warnings(
        self,
        ctx,
        member: discord.Member
    ):

        db = get_db()

        try:

            cursor = db.cursor()

            cursor.execute(
                """
                SELECT
                    id,
                    moderator_id,
                    reason,
                    case_id,
                    created_at
                FROM moderation_warnings
                WHERE guild_id = ?
                AND user_id = ?
                ORDER BY id DESC
                """,
                (
                    ctx.guild.id,
                    member.id
                )
            )

            results = cursor.fetchall()

        finally:

            db.close()


        if not results:

            return await ctx.send(
                f"✅ {member.mention} has no warnings."
            )


        embed = discord.Embed(
            title=f"⚠️ Warnings • {member.display_name}",
            description=(
                f"Total warnings: **{len(results)}**"
            ),
            color=discord.Color.orange()
        )


        for row in results[:10]:

            moderator = ctx.guild.get_member(
                row["moderator_id"]
            )

            moderator_text = (
                moderator.mention
                if moderator
                else f"<@{row['moderator_id']}>"
            )


            case_text = (
                f"#{row['case_id']}"
                if row["case_id"]
                else "N/A"
            )


            embed.add_field(
                name=f"⚠️ Warning #{row['id']}",
                value=(
                    f"**Case:** {case_text}\n"
                    f"**Reason:** {row['reason']}\n"
                    f"**Moderator:** {moderator_text}\n"
                    f"**Date:** {row['created_at']}"
                ),
                inline=False
            )


        if len(results) > 10:

            embed.set_footer(
                text=(
                    f"Showing the newest 10 of "
                    f"{len(results)} warnings."
                )
            )


        await ctx.send(
            embed=embed
        )


    # ======================================================
    # !CLEARWARNINGS
    # ======================================================

    @commands.command()
    @commands.has_permissions(
        manage_guild=True
    )
    async def clearwarnings(
        self,
        ctx,
        member: discord.Member
    ):

        warning_count = self.get_warning_count(
            ctx.guild.id,
            member.id
        )


        if warning_count == 0:

            return await ctx.send(
                f"✅ {member.mention} has no warnings."
            )


        db = get_db()

        try:

            cursor = db.cursor()

            cursor.execute(
                """
                DELETE FROM moderation_warnings
                WHERE guild_id = ?
                AND user_id = ?
                """,
                (
                    ctx.guild.id,
                    member.id
                )
            )

            db.commit()

        finally:

            db.close()


        case_id = self.create_case(
            ctx.guild.id,
            member.id,
            ctx.author.id,
            "Clear Warnings",
            (
                f"Cleared {warning_count} warning(s)."
            )
        )


        await ctx.send(
            f"✅ Cleared **{warning_count}** warning(s) "
            f"from {member.mention}. "
            f"Case **#{case_id}**."
        )


        await self.send_mod_log(
            ctx.guild,
            case_id,
            "Clear Warnings",
            member.id,
            ctx.author,
            f"Cleared {warning_count} warning(s).",
            discord.Color.green()
        )


    # ======================================================
    # !KICK
    # ======================================================

    @commands.command()
    @commands.has_permissions(
        kick_members=True
    )
    async def kick(
        self,
        ctx,
        member: discord.Member,
        *,
        reason: str = DEFAULT_REASON
    ):

        allowed, error = self.can_moderate(
            ctx,
            member
        )

        if not allowed:

            return await ctx.send(
                error
            )


        case_id = self.create_case(
            ctx.guild.id,
            member.id,
            ctx.author.id,
            "Kick",
            reason
        )


        try:

            await member.kick(
                reason=reason
            )

        except discord.Forbidden:

            return await ctx.send(
                "❌ I don't have permission to kick that member."
            )

        except discord.HTTPException:

            return await ctx.send(
                "❌ Discord rejected the kick request."
            )


        embed = discord.Embed(
            title="👢 Member Kicked",
            color=discord.Color.red()
        )

        embed.add_field(
            name="👤 Member",
            value=member.mention,
            inline=False
        )

        embed.add_field(
            name="👮 Moderator",
            value=ctx.author.mention,
            inline=False
        )

        embed.add_field(
            name="📝 Reason",
            value=reason,
            inline=False
        )

        embed.add_field(
            name="🆔 Case",
            value=f"#{case_id}",
            inline=True
        )


        await ctx.send(
            embed=embed
        )


        await self.send_mod_log(
            ctx.guild,
            case_id,
            "Kick",
            member.id,
            ctx.author,
            reason,
            discord.Color.red()
        )


    # ======================================================
    # !BAN
    # ======================================================

    @commands.command()
    @commands.has_permissions(
        ban_members=True
    )
    async def ban(
        self,
        ctx,
        member: discord.Member,
        *,
        reason: str = DEFAULT_REASON
    ):

        allowed, error = self.can_moderate(
            ctx,
            member
        )

        if not allowed:

            return await ctx.send(
                error
            )


        case_id = self.create_case(
            ctx.guild.id,
            member.id,
            ctx.author.id,
            "Ban",
            reason
        )


        try:

            await member.ban(
                reason=reason
            )

        except discord.Forbidden:

            return await ctx.send(
                "❌ I don't have permission to ban that member."
            )

        except discord.HTTPException:

            return await ctx.send(
                "❌ Discord rejected the ban request."
            )


        embed = discord.Embed(
            title="🔨 Member Banned",
            color=discord.Color.red()
        )

        embed.add_field(
            name="👤 Member",
            value=member.mention,
            inline=False
        )

        embed.add_field(
            name="👮 Moderator",
            value=ctx.author.mention,
            inline=False
        )

        embed.add_field(
            name="📝 Reason",
            value=reason,
            inline=False
        )

        embed.add_field(
            name="🆔 Case",
            value=f"#{case_id}",
            inline=True
        )


        await ctx.send(
            embed=embed
        )


        await self.send_mod_log(
            ctx.guild,
            case_id,
            "Ban",
            member.id,
            ctx.author,
            reason,
            discord.Color.red()
        )


    # ======================================================
    # !UNBAN
    # ======================================================

    @commands.command()
    @commands.has_permissions(
        ban_members=True
    )
    async def unban(
        self,
        ctx,
        user_id: int
    ):

        try:

            user = await self.bot.fetch_user(
                user_id
            )

        except discord.NotFound:

            return await ctx.send(
                "❌ I couldn't find that Discord user."
            )

        except discord.HTTPException:

            return await ctx.send(
                "❌ I couldn't retrieve that user."
            )


        try:

            await ctx.guild.unban(
                user,
                reason=f"Unbanned by {ctx.author}"
            )

        except discord.NotFound:

            return await ctx.send(
                "❌ That user isn't currently banned."
            )

        except discord.Forbidden:

            return await ctx.send(
                "❌ I don't have permission to unban users."
            )

        except discord.HTTPException:

            return await ctx.send(
                "❌ Discord rejected the unban request."
            )


        case_id = self.create_case(
            ctx.guild.id,
            user.id,
            ctx.author.id,
            "Unban",
            DEFAULT_REASON
        )


        embed = discord.Embed(
            title="🔓 User Unbanned",
            color=discord.Color.green()
        )

        embed.add_field(
            name="👤 User",
            value=f"{user} (`{user.id}`)",
            inline=False
        )

        embed.add_field(
            name="👮 Moderator",
            value=ctx.author.mention,
            inline=False
        )

        embed.add_field(
            name="🆔 Case",
            value=f"#{case_id}",
            inline=True
        )


        await ctx.send(
            embed=embed
        )


        await self.send_mod_log(
            ctx.guild,
            case_id,
            "Unban",
            user.id,
            ctx.author,
            DEFAULT_REASON,
            discord.Color.green()
        )


    # ======================================================
    # !TIMEOUT
    # ======================================================

    @commands.command()
    @commands.has_permissions(
        moderate_members=True
    )
    async def timeout(
        self,
        ctx,
        member: discord.Member,
        minutes: int,
        *,
        reason: str = DEFAULT_REASON
    ):

        if minutes < 1:

            return await ctx.send(
                "❌ Timeout duration must be at least 1 minute."
            )


        if minutes > 40320:

            return await ctx.send(
                "❌ Timeout duration cannot exceed 28 days."
            )


        allowed, error = self.can_moderate(
            ctx,
            member
        )

        if not allowed:

            return await ctx.send(
                error
            )


        duration = timedelta(
            minutes=minutes
        )


        case_id = self.create_case(
            ctx.guild.id,
            member.id,
            ctx.author.id,
            "Timeout",
            reason
        )


        try:

            await member.timeout(
                duration,
                reason=reason
            )

        except discord.Forbidden:

            return await ctx.send(
                "❌ I don't have permission to timeout that member."
            )

        except discord.HTTPException:

            return await ctx.send(
                "❌ Discord rejected the timeout request."
            )


        embed = discord.Embed(
            title="⏱️ Member Timed Out",
            color=discord.Color.orange()
        )

        embed.add_field(
            name="👤 Member",
            value=member.mention,
            inline=True
        )

        embed.add_field(
            name="⏱️ Duration",
            value=f"{minutes} minute(s)",
            inline=True
        )

        embed.add_field(
            name="🆔 Case",
            value=f"#{case_id}",
            inline=True
        )

        embed.add_field(
            name="📝 Reason",
            value=reason,
            inline=False
        )


        await ctx.send(
            embed=embed
        )


        await self.send_mod_log(
            ctx.guild,
            case_id,
            "Timeout",
            member.id,
            ctx.author,
            reason,
            discord.Color.orange()
        )


    # ======================================================
    # !UNTIMEOUT
    # ======================================================

    @commands.command()
    @commands.has_permissions(
        moderate_members=True
    )
    async def untimeout(
        self,
        ctx,
        member: discord.Member
    ):

        allowed, error = self.can_moderate(
            ctx,
            member
        )

        if not allowed:

            return await ctx.send(
                error
            )


        case_id = self.create_case(
            ctx.guild.id,
            member.id,
            ctx.author.id,
            "Remove Timeout",
            DEFAULT_REASON
        )


        try:

            await member.timeout(
                None,
                reason=f"Timeout removed by {ctx.author}"
            )

        except discord.Forbidden:

            return await ctx.send(
                "❌ I don't have permission to remove that timeout."
            )

        except discord.HTTPException:

            return await ctx.send(
                "❌ Discord rejected the request."
            )


        await ctx.send(
            f"✅ Removed the timeout from "
            f"{member.mention}. Case **#{case_id}**."
        )


        await self.send_mod_log(
            ctx.guild,
            case_id,
            "Remove Timeout",
            member.id,
            ctx.author,
            DEFAULT_REASON,
            discord.Color.green()
        )


    # ======================================================
    # !CASE
    # ======================================================

    @commands.command()
    @commands.has_permissions(
        moderate_members=True
    )
    async def case(
        self,
        ctx,
        case_id: int
    ):

        if case_id < 1:

            return await ctx.send(
                "❌ Case ID must be 1 or higher."
            )


        case_data = self.get_case(
            ctx.guild.id,
            case_id
        )


        if case_data is None:

            return await ctx.send(
                f"❌ Case **#{case_id}** doesn't exist "
                f"in this server."
            )


        user = ctx.guild.get_member(
            case_data["user_id"]
        )

        moderator = ctx.guild.get_member(
            case_data["moderator_id"]
        )


        user_text = (
            user.mention
            if user
            else f"<@{case_data['user_id']}>"
        )

        moderator_text = (
            moderator.mention
            if moderator
            else f"<@{case_data['moderator_id']}>"
        )


        embed = discord.Embed(
            title=f"🛡️ Moderation Case #{case_id}",
            color=EMBED_COLOR
        )


        embed.add_field(
            name="👤 User",
            value=user_text,
            inline=True
        )

        embed.add_field(
            name="🛡️ Action",
            value=case_data["action"],
            inline=True
        )

        embed.add_field(
            name="👮 Moderator",
            value=moderator_text,
            inline=True
        )

        embed.add_field(
            name="📝 Reason",
            value=case_data["reason"],
            inline=False
        )

        embed.add_field(
            name="📅 Date",
            value=str(case_data["created_at"]),
            inline=False
        )


        await ctx.send(
            embed=embed
        )


    # ======================================================
    # !MODLOG
    # ======================================================

    @commands.command()
    @commands.has_permissions(
        manage_guild=True
    )
    async def modlog(
        self,
        ctx,
        channel: discord.TextChannel
    ):

        self.update_setting(
            ctx.guild.id,
            "log_channel_id",
            channel.id
        )


        embed = discord.Embed(
            title="✅ Moderation Log Configured",
            description=(
                f"Moderation actions will now be logged in "
                f"{channel.mention}."
            ),
            color=discord.Color.green()
        )


        await ctx.send(
            embed=embed
        )


    # ======================================================
    # !MODSETTINGS
    # ======================================================

    @commands.command()
    @commands.has_permissions(
        manage_guild=True
    )
    async def modsettings(
        self,
        ctx
    ):

        settings = self.get_settings(
            ctx.guild.id
        )


        log_channel = None

        if settings["log_channel_id"]:

            log_channel = ctx.guild.get_channel(
                settings["log_channel_id"]
            )


        embed = discord.Embed(
            title="🛡️ Moderation Settings",
            color=EMBED_COLOR
        )


        embed.add_field(
            name="📜 Mod Log",
            value=(
                log_channel.mention
                if log_channel
                else "Not configured"
            ),
            inline=False
        )


        timeout_count = (
            settings["timeout_warning_count"]
            or 0
        )

        kick_count = (
            settings["kick_warning_count"]
            or 0
        )

        ban_count = (
            settings["ban_warning_count"]
            or 0
        )


        embed.add_field(
            name="⏱️ Timeout",
            value=(
                f"{timeout_count} warnings"
                if timeout_count
                else "Disabled"
            ),
            inline=True
        )


        embed.add_field(
            name="👢 Kick",
            value=(
                f"{kick_count} warnings"
                if kick_count
                else "Disabled"
            ),
            inline=True
        )


        embed.add_field(
            name="🔨 Ban",
            value=(
                f"{ban_count} warnings"
                if ban_count
                else "Disabled"
            ),
            inline=True
        )


        embed.add_field(
            name="⚙️ Configuration",
            value=(
                "`!modlog #channel`\n"
                "`!setpunishment <warnings> timeout`\n"
                "`!setpunishment <warnings> kick`\n"
                "`!setpunishment <warnings> ban`"
            ),
            inline=False
        )


        await ctx.send(
            embed=embed
        )


    # ======================================================
    # !SETPUNISHMENT
    # ======================================================

    @commands.command()
    @commands.has_permissions(
        administrator=True
    )
    async def setpunishment(
        self,
        ctx,
        warning_count: int,
        action: str
    ):

        if warning_count < 0:

            return await ctx.send(
                "❌ Warning count cannot be negative."
            )


        action = action.lower()


        allowed_actions = {
            "timeout",
            "kick",
            "ban"
        }


        if action not in allowed_actions:

            return await ctx.send(
                "❌ Action must be `timeout`, `kick`, or `ban`."
            )


        column_map = {
            "timeout": "timeout_warning_count",
            "kick": "kick_warning_count",
            "ban": "ban_warning_count"
        }


        self.update_setting(
            ctx.guild.id,
            column_map[action],
            warning_count
        )


        if warning_count == 0:

            return await ctx.send(
                f"✅ Automatic **{action}** escalation "
                f"has been disabled."
            )


        await ctx.send(
            f"✅ Members will automatically receive a "
            f"**{action}** after **{warning_count} warnings**."
        )


    # ======================================================
    # !MODERATIONHELP
    # ======================================================

    @commands.command(
        aliases=["modhelp"]
    )
    async def moderationhelp(
        self,
        ctx
    ):

        embed = discord.Embed(
            title="🛡️ Grid Guardian Moderation",
            description=(
                "Advanced server moderation commands."
            ),
            color=EMBED_COLOR
        )


        embed.add_field(
            name="⚠️ Warnings",
            value=(
                "`!warn @user <reason>`\n"
                "`!warnings @user`\n"
                "`!clearwarnings @user`"
            ),
            inline=False
        )


        embed.add_field(
            name="🔨 Moderation",
            value=(
                "`!kick @user <reason>`\n"
                "`!ban @user <reason>`\n"
                "`!unban <user_id>`\n"
                "`!timeout @user <minutes> <reason>`\n"
                "`!untimeout @user`"
            ),
            inline=False
        )


        embed.add_field(
            name="📋 Cases",
            value=(
                "`!case <case_id>`"
            ),
            inline=False
        )


        embed.add_field(
            name="⚙️ Configuration",
            value=(
                "`!modlog #channel`\n"
                "`!modsettings`\n"
                "`!setpunishment <warnings> <action>`"
            ),
            inline=False
        )


        embed.set_footer(
            text="Grid Guardian • Moderation"
        )


        await ctx.send(
            embed=embed
        )


    # ======================================================
    # COMMAND ERROR HANDLERS
    # ======================================================

    @warn.error
    async def warn_error(
        self,
        ctx,
        error
    ):

        if isinstance(
            error,
            commands.MissingPermissions
        ):

            await ctx.send(
                "❌ You need the **Moderate Members** "
                "permission to warn members."
            )

        elif isinstance(
            error,
            commands.MissingRequiredArgument
        ):

            await ctx.send(
                "❌ Usage: `!warn @user <reason>`"
            )

        elif isinstance(
            error,
            commands.MemberNotFound
        ):

            await ctx.send(
                "❌ I couldn't find that member."
            )


    @warnings.error
    async def warnings_error(
        self,
        ctx,
        error
    ):

        if isinstance(
            error,
            commands.MissingPermissions
        ):

            await ctx.send(
                "❌ You need the **Moderate Members** "
                "permission to view warnings."
            )

        elif isinstance(
            error,
            commands.MissingRequiredArgument
        ):

            await ctx.send(
                "❌ Usage: `!warnings @user`"
            )


    @clearwarnings.error
    async def clearwarnings_error(
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
                "to clear warnings."
            )


    @setpunishment.error
    async def setpunishment_error(
        self,
        ctx,
        error
    ):

        if isinstance(
            error,
            commands.MissingPermissions
        ):

            await ctx.send(
                "❌ You need **Administrator** permission "
                "to configure punishments."
            )

        elif isinstance(
            error,
            commands.MissingRequiredArgument
        ):

            await ctx.send(
                "❌ Usage: `!setpunishment <warnings> <action>`"
            )


# ==========================================================
# SETUP
# ==========================================================

async def setup(bot):

    await bot.add_cog(
        Moderation(bot)
    )