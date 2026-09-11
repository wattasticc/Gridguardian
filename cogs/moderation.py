import sqlite3
from datetime import timedelta

import discord
from discord.ext import commands


EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)


# =========================================================
# DATABASE
# =========================================================

db = sqlite3.connect("gridguardian.db")
cursor = db.cursor()


# Warnings
cursor.execute("""
CREATE TABLE IF NOT EXISTS warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    moderator_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")


# Moderation cases
cursor.execute("""
CREATE TABLE IF NOT EXISTS cases (
    case_id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    moderator_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    reason TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")


# Server settings
cursor.execute("""
CREATE TABLE IF NOT EXISTS settings (
    guild_id INTEGER PRIMARY KEY,
    log_channel_id INTEGER,
    welcome_channel_id INTEGER,
    autorole_id INTEGER
)
""")


db.commit()


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def parse_time(time_string: str):
    """
    Converts:

    10s -> 10 seconds
    5m  -> 5 minutes
    2h  -> 2 hours
    3d  -> 3 days
    """

    time_string = time_string.lower().strip()

    if len(time_string) < 2:
        return None

    try:
        amount = int(time_string[:-1])
    except ValueError:
        return None

    unit = time_string[-1]

    if amount <= 0:
        return None

    if unit == "s":
        return timedelta(seconds=amount)

    if unit == "m":
        return timedelta(minutes=amount)

    if unit == "h":
        return timedelta(hours=amount)

    if unit == "d":
        return timedelta(days=amount)

    return None


# =========================================================
# MODERATION COG
# =========================================================

class Moderation(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # =====================================================
    # CREATE CASE
    # =====================================================

    def create_case(
        self,
        guild_id,
        user_id,
        moderator_id,
        action,
        reason
    ):
        """
        Creates a moderation case and returns the case ID.
        """

        cursor.execute("""
        INSERT INTO cases (
            guild_id,
            user_id,
            moderator_id,
            action,
            reason
        )
        VALUES (?, ?, ?, ?, ?)
        """, (
            guild_id,
            user_id,
            moderator_id,
            action,
            reason
        ))

        db.commit()

        return cursor.lastrowid

    # =====================================================
    # SEND MODERATION LOG
    # =====================================================

    async def send_mod_log(
        self,
        guild,
        action,
        moderator,
        member=None,
        reason=None,
        color=discord.Color.orange(),
        case_id=None
    ):

        try:

            cursor.execute("""
            SELECT log_channel_id
            FROM settings
            WHERE guild_id=?
            """, (
                guild.id,
            ))

            result = cursor.fetchone()

        except sqlite3.Error:
            return

        if not result or not result[0]:
            return

        log_channel = guild.get_channel(
            result[0]
        )

        if not isinstance(
            log_channel,
            discord.TextChannel
        ):
            return

        embed = discord.Embed(
            title=f"🛡️ Moderation: {action}",
            color=color
        )

        if case_id is not None:

            embed.add_field(
                name="📁 Case",
                value=f"`#{case_id}`",
                inline=True
            )

        if member:

            embed.add_field(
                name="👤 User",
                value=(
                    f"{member.mention}\n"
                    f"`{member.id}`"
                ),
                inline=True
            )

        if moderator:

            embed.add_field(
                name="🛡️ Moderator",
                value=moderator.mention,
                inline=True
            )

        if reason:

            embed.add_field(
                name="📝 Reason",
                value=reason[:1000],
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
    # WARN
    # =====================================================

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def warn(
        self,
        ctx,
        member: discord.Member,
        *,
        reason: str = "No reason provided."
    ):

        if member.bot:

            return await ctx.send(
                "❌ You cannot warn a bot."
            )

        if member == ctx.author:

            return await ctx.send(
                "❌ You cannot warn yourself."
            )

        if (
            member.top_role >= ctx.author.top_role
            and ctx.author != ctx.guild.owner
        ):

            return await ctx.send(
                "❌ You cannot warn someone with an equal or higher role."
            )

        cursor.execute("""
        INSERT INTO warnings (
            user_id,
            moderator_id,
            reason
        )
        VALUES (?, ?, ?)
        """, (
            member.id,
            ctx.author.id,
            reason
        ))

        db.commit()

        warning_id = cursor.lastrowid

        cursor.execute("""
        SELECT COUNT(*)
        FROM warnings
        WHERE user_id=?
        """, (
            member.id,
        ))

        warning_count = cursor.fetchone()[0]

        # Create moderation case
        case_id = self.create_case(
            ctx.guild.id,
            member.id,
            ctx.author.id,
            "WARN",
            reason
        )

        embed = discord.Embed(
            title="⚠️ Member Warned",
            description=(
                f"{member.mention} has received a warning."
            ),
            color=discord.Color.orange()
        )

        embed.add_field(
            name="📝 Reason",
            value=reason,
            inline=False
        )

        embed.add_field(
            name="📊 Total Warnings",
            value=str(warning_count),
            inline=True
        )

        embed.add_field(
            name="🆔 Warning ID",
            value=f"#{warning_id}",
            inline=True
        )

        embed.add_field(
            name="📁 Case",
            value=f"#{case_id}",
            inline=True
        )

        embed.set_footer(
            text=f"Moderator: {ctx.author}"
        )

        await ctx.send(
            embed=embed
        )

        await self.send_mod_log(
            ctx.guild,
            "Warning",
            ctx.author,
            member,
            reason,
            discord.Color.orange(),
            case_id
        )

    # =====================================================
    # VIEW WARNINGS
    # =====================================================

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def warnings(
        self,
        ctx,
        member: discord.Member
    ):

        cursor.execute("""
        SELECT
            id,
            moderator_id,
            reason,
            timestamp
        FROM warnings
        WHERE user_id=?
        ORDER BY id DESC
        """, (
            member.id,
        ))

        results = cursor.fetchall()

        if not results:

            return await ctx.send(
                f"✅ {member.mention} has no warnings."
            )

        embed = discord.Embed(
            title=f"⚠️ Warnings for {member}",
            description=(
                f"Total warnings: **{len(results)}**"
            ),
            color=discord.Color.orange()
        )

        for (
            warning_id,
            moderator_id,
            reason,
            timestamp
        ) in results[:10]:

            moderator = ctx.guild.get_member(
                moderator_id
            )

            moderator_name = (
                moderator.mention
                if moderator
                else f"User ID: {moderator_id}"
            )

            embed.add_field(
                name=f"Warning #{warning_id}",
                value=(
                    f"**Reason:** {reason}\n"
                    f"**Moderator:** {moderator_name}\n"
                    f"**Date:** {timestamp}"
                ),
                inline=False
            )

        if len(results) > 10:

            embed.set_footer(
                text=(
                    f"Showing the newest 10 "
                    f"of {len(results)} warnings."
                )
            )

        await ctx.send(
            embed=embed
        )

    # =====================================================
    # CLEAR WARNINGS
    # =====================================================

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def clearwarnings(
        self,
        ctx,
        member: discord.Member
    ):

        cursor.execute("""
        SELECT COUNT(*)
        FROM warnings
        WHERE user_id=?
        """, (
            member.id,
        ))

        warning_count = cursor.fetchone()[0]

        if warning_count == 0:

            return await ctx.send(
                "❌ That user has no warnings."
            )

        cursor.execute("""
        DELETE FROM warnings
        WHERE user_id=?
        """, (
            member.id,
        ))

        db.commit()

        case_id = self.create_case(
            ctx.guild.id,
            member.id,
            ctx.author.id,
            "CLEAR_WARNINGS",
            f"{warning_count} warning(s) removed."
        )

        embed = discord.Embed(
            title="🗑️ Warnings Cleared",
            description=(
                f"Removed **{warning_count} warning(s)** "
                f"from {member.mention}."
            ),
            color=discord.Color.green()
        )

        embed.add_field(
            name="📁 Case",
            value=f"#{case_id}",
            inline=True
        )

        await ctx.send(
            embed=embed
        )

        await self.send_mod_log(
            ctx.guild,
            "Warnings Cleared",
            ctx.author,
            member,
            f"{warning_count} warning(s) removed.",
            discord.Color.green(),
            case_id
        )

    # =====================================================
    # TIMEOUT
    # =====================================================

    @commands.command()
    @commands.has_permissions(moderate_members=True)
    async def timeout(
        self,
        ctx,
        member: discord.Member,
        duration: str,
        *,
        reason: str = "No reason provided."
    ):

        if member.bot:

            return await ctx.send(
                "❌ You cannot timeout a bot."
            )

        if member == ctx.author:

            return await ctx.send(
                "❌ You cannot timeout yourself."
            )

        if (
            member.top_role >= ctx.author.top_role
            and ctx.author != ctx.guild.owner
        ):

            return await ctx.send(
                "❌ You cannot timeout someone with an equal or higher role."
            )

        duration_delta = parse_time(
            duration
        )

        if duration_delta is None:

            return await ctx.send(
                "❌ Invalid time format.\n\n"
                "Examples: `10s`, `5m`, `2h`, `3d`"
            )

        if duration_delta > timedelta(days=28):

            return await ctx.send(
                "❌ Discord only allows timeouts up to 28 days."
            )

        until = (
            discord.utils.utcnow()
            + duration_delta
        )

        try:

            await member.timeout(
                until,
                reason=reason
            )

        except discord.Forbidden:

            return await ctx.send(
                "❌ I don't have permission to timeout that member."
            )

        except discord.HTTPException:

            return await ctx.send(
                "❌ Discord could not apply that timeout."
            )

        case_id = self.create_case(
            ctx.guild.id,
            member.id,
            ctx.author.id,
            "TIMEOUT",
            f"{duration} - {reason}"
        )

        embed = discord.Embed(
            title="🔇 Member Timed Out",
            description=member.mention,
            color=discord.Color.red()
        )

        embed.add_field(
            name="⏱️ Duration",
            value=duration,
            inline=True
        )

        embed.add_field(
            name="📁 Case",
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
            "Timeout",
            ctx.author,
            member,
            reason,
            discord.Color.red(),
            case_id
        )

    # =====================================================
    # REMOVE TIMEOUT
    # =====================================================

    @commands.command()
    @commands.has_permissions(moderate_members=True)
    async def untimeout(
        self,
        ctx,
        member: discord.Member
    ):

        try:

            await member.timeout(
                None,
                reason=(
                    f"Timeout removed by "
                    f"{ctx.author}"
                )
            )

        except discord.Forbidden:

            return await ctx.send(
                "❌ I don't have permission to remove that timeout."
            )

        case_id = self.create_case(
            ctx.guild.id,
            member.id,
            ctx.author.id,
            "UNTIMEOUT",
            "Timeout removed."
        )

        embed = discord.Embed(
            title="🔊 Timeout Removed",
            description=(
                f"{member.mention} can speak again."
            ),
            color=discord.Color.green()
        )

        embed.add_field(
            name="📁 Case",
            value=f"#{case_id}",
            inline=True
        )

        await ctx.send(
            embed=embed
        )

        await self.send_mod_log(
            ctx.guild,
            "Timeout Removed",
            ctx.author,
            member,
            None,
            discord.Color.green(),
            case_id
        )

    # =====================================================
    # KICK
    # =====================================================

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def kick(
        self,
        ctx,
        member: discord.Member,
        *,
        reason: str = "No reason provided."
    ):

        if member == ctx.author:

            return await ctx.send(
                "❌ You cannot kick yourself."
            )

        if member.bot:

            return await ctx.send(
                "❌ You cannot kick a bot."
            )

        if (
            member.top_role >= ctx.author.top_role
            and ctx.author != ctx.guild.owner
        ):

            return await ctx.send(
                "❌ You cannot kick someone with an equal or higher role."
            )

        try:

            await member.kick(
                reason=(
                    f"{reason} | "
                    f"Moderator: {ctx.author}"
                )
            )

        except discord.Forbidden:

            return await ctx.send(
                "❌ I don't have permission to kick that member."
            )

        case_id = self.create_case(
            ctx.guild.id,
            member.id,
            ctx.author.id,
            "KICK",
            reason
        )

        embed = discord.Embed(
            title="👢 Member Kicked",
            description=(
                f"**User:** {member}\n"
                f"**Reason:** {reason}"
            ),
            color=discord.Color.red()
        )

        embed.add_field(
            name="📁 Case",
            value=f"#{case_id}",
            inline=True
        )

        await ctx.send(
            embed=embed
        )

        await self.send_mod_log(
            ctx.guild,
            "Kick",
            ctx.author,
            member,
            reason,
            discord.Color.red(),
            case_id
        )

    # =====================================================
    # BAN
    # =====================================================

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def ban(
        self,
        ctx,
        member: discord.Member,
        *,
        reason: str = "No reason provided."
    ):

        if member == ctx.author:

            return await ctx.send(
                "❌ You cannot ban yourself."
            )

        if member.bot:

            return await ctx.send(
                "❌ You cannot ban a bot."
            )

        if (
            member.top_role >= ctx.author.top_role
            and ctx.author != ctx.guild.owner
        ):

            return await ctx.send(
                "❌ You cannot ban someone with an equal or higher role."
            )

        try:

            await member.ban(
                reason=(
                    f"{reason} | "
                    f"Moderator: {ctx.author}"
                )
            )

        except discord.Forbidden:

            return await ctx.send(
                "❌ I don't have permission to ban that member."
            )

        case_id = self.create_case(
            ctx.guild.id,
            member.id,
            ctx.author.id,
            "BAN",
            reason
        )

        embed = discord.Embed(
            title="🔨 Member Banned",
            description=(
                f"**User:** {member}\n"
                f"**Reason:** {reason}"
            ),
            color=discord.Color.red()
        )

        embed.add_field(
            name="📁 Case",
            value=f"#{case_id}",
            inline=True
        )

        await ctx.send(
            embed=embed
        )

        await self.send_mod_log(
            ctx.guild,
            "Ban",
            ctx.author,
            member,
            reason,
            discord.Color.red(),
            case_id
        )

    # =====================================================
    # UNBAN
    # =====================================================

    @commands.command()
    @commands.has_permissions(ban_members=True)
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
                "❌ I couldn't find that user."
            )

        try:

            await ctx.guild.unban(
                user,
                reason=(
                    f"Unbanned by {ctx.author}"
                )
            )

        except discord.NotFound:

            return await ctx.send(
                "❌ That user isn't banned."
            )

        except discord.Forbidden:

            return await ctx.send(
                "❌ I don't have permission to unban users."
            )

        case_id = self.create_case(
            ctx.guild.id,
            user.id,
            ctx.author.id,
            "UNBAN",
            "User unbanned."
        )

        embed = discord.Embed(
            title="🔓 User Unbanned",
            description=(
                f"**User:** {user}\n"
                f"**ID:** `{user.id}`"
            ),
            color=discord.Color.green()
        )

        embed.add_field(
            name="📁 Case",
            value=f"#{case_id}",
            inline=True
        )

        await ctx.send(
            embed=embed
        )

        await self.send_mod_log(
            ctx.guild,
            "Unban",
            ctx.author,
            None,
            f"User: {user} ({user.id})",
            discord.Color.green(),
            case_id
        )

    # =====================================================
    # PURGE MESSAGES
    # =====================================================

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def purge(
        self,
        ctx,
        amount: int
    ):

        if amount < 1:

            return await ctx.send(
                "❌ Please enter at least 1 message."
            )

        if amount > 100:

            return await ctx.send(
                "❌ You can delete a maximum of 100 messages at once."
            )

        try:

            deleted = await ctx.channel.purge(
                limit=amount + 1
            )

        except discord.Forbidden:

            return await ctx.send(
                "❌ I don't have permission to delete messages."
            )

        deleted_count = len(deleted) - 1

        case_id = self.create_case(
            ctx.guild.id,
            ctx.author.id,
            ctx.author.id,
            "PURGE",
            f"{deleted_count} messages deleted in {ctx.channel.mention}."
        )

        confirmation = await ctx.send(
            f"🧹 Deleted **{deleted_count}** messages.\n"
            f"📁 Case `#{case_id}`"
        )

        await confirmation.delete(
            delay=5
        )

        await self.send_mod_log(
            ctx.guild,
            "Message Purge",
            ctx.author,
            None,
            f"{deleted_count} messages deleted in {ctx.channel.mention}.",
            discord.Color.orange(),
            case_id
        )

    # =====================================================
    # CASE LOOKUP
    # =====================================================

    @commands.command(name="case")
    @commands.has_permissions(manage_guild=True)
    async def case(
        self,
        ctx,
        case_id: int
    ):

        cursor.execute("""
        SELECT
            guild_id,
            user_id,
            moderator_id,
            action,
            reason,
            timestamp
        FROM cases
        WHERE case_id=?
        """, (
            case_id,
        ))

        result = cursor.fetchone()

        if not result:

            return await ctx.send(
                f"❌ Case `#{case_id}` does not exist."
            )

        (
            guild_id,
            user_id,
            moderator_id,
            action,
            reason,
            timestamp
        ) = result

        if guild_id != ctx.guild.id:

            return await ctx.send(
                "❌ That case belongs to another server."
            )

        user = ctx.guild.get_member(
            user_id
        )

        moderator = ctx.guild.get_member(
            moderator_id
        )

        user_text = (
            user.mention
            if user
            else f"`{user_id}`"
        )

        moderator_text = (
            moderator.mention
            if moderator
            else f"`{moderator_id}`"
        )

        embed = discord.Embed(
            title=f"📁 Case #{case_id}",
            color=EMBED_COLOR
        )

        embed.add_field(
            name="👤 User",
            value=user_text,
            inline=True
        )

        embed.add_field(
            name="🛡️ Moderator",
            value=moderator_text,
            inline=True
        )

        embed.add_field(
            name="⚖️ Action",
            value=action,
            inline=True
        )

        embed.add_field(
            name="📝 Reason",
            value=reason[:1000],
            inline=False
        )

        embed.add_field(
            name="🕒 Date",
            value=timestamp,
            inline=False
        )

        await ctx.send(
            embed=embed
        )

    # =====================================================
    # USER CASE HISTORY
    # =====================================================

    @commands.command(name="cases")
    @commands.has_permissions(manage_guild=True)
    async def cases(
        self,
        ctx,
        member: discord.Member
    ):

        cursor.execute("""
        SELECT
            case_id,
            action,
            reason,
            moderator_id,
            timestamp
        FROM cases
        WHERE guild_id=?
        AND user_id=?
        ORDER BY case_id DESC
        """, (
            ctx.guild.id,
            member.id
        ))

        results = cursor.fetchall()

        if not results:

            return await ctx.send(
                f"✅ {member.mention} has no moderation cases."
            )

        embed = discord.Embed(
            title=f"📁 Case History — {member}",
            description=(
                f"Total cases: **{len(results)}**"
            ),
            color=EMBED_COLOR
        )

        for (
            case_id,
            action,
            reason,
            moderator_id,
            timestamp
        ) in results[:10]:

            moderator = ctx.guild.get_member(
                moderator_id
            )

            moderator_text = (
                moderator.mention
                if moderator
                else f"`{moderator_id}`"
            )

            embed.add_field(
                name=f"Case #{case_id} — {action}",
                value=(
                    f"**Reason:** {reason[:500]}\n"
                    f"**Moderator:** {moderator_text}\n"
                    f"**Date:** {timestamp}"
                ),
                inline=False
            )

        if len(results) > 10:

            embed.set_footer(
                text=(
                    f"Showing the newest 10 "
                    f"of {len(results)} cases."
                )
            )

        await ctx.send(
            embed=embed
        )

    # =====================================================
    # COMMAND ERROR HANDLER
    # =====================================================

    @warn.error
    @warnings.error
    @clearwarnings.error
    @timeout.error
    @untimeout.error
    @kick.error
    @ban.error
    @unban.error
    @purge.error
    @case.error
    @cases.error
    async def moderation_error(
        self,
        ctx,
        error
    ):

        if isinstance(
            error,
            commands.MissingPermissions
        ):

            await ctx.send(
                "❌ You don't have permission to use that command."
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
            commands.MemberNotFound
        ):

            await ctx.send(
                "❌ I couldn't find that member."
            )

            return

        if isinstance(
            error,
            commands.BadArgument
        ):

            await ctx.send(
                "❌ One of the arguments you entered is invalid."
            )

            return

        raise error


# =========================================================
# SETUP
# =========================================================

async def setup(bot):

    await bot.add_cog(
        Moderation(bot)
    )