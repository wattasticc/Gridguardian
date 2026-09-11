import sqlite3
from datetime import timedelta

import discord
from discord.ext import commands


# =========================================================
# SETTINGS
# =========================================================

EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)
DB_PATH = "gridguardian.db"


# =========================================================
# DATABASE
# =========================================================

db = sqlite3.connect(DB_PATH)
db.row_factory = sqlite3.Row
cursor = db.cursor()


cursor.execute("""
CREATE TABLE IF NOT EXISTS warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    moderator_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
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

    Returns a timedelta or None.
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


def can_moderate(ctx, member: discord.Member):
    """
    Checks whether the command author is allowed to
    moderate the target member.

    Returns:
        True  -> allowed
        False -> not allowed
    """

    if member == ctx.author:
        return False

    if member == ctx.guild.owner:
        return False

    if (
        member.top_role >= ctx.author.top_role
        and ctx.author != ctx.guild.owner
    ):
        return False

    return True


def bot_can_moderate(guild, member: discord.Member):
    """
    Makes sure Grid Guardian's highest role is above
    the target member's highest role.
    """

    me = guild.me

    if me is None:
        return False

    if member == guild.owner:
        return False

    if member.top_role >= me.top_role:
        return False

    return True


# =========================================================
# MODERATION COG
# =========================================================

class Moderation(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # =====================================================
    # MODERATION LOGGING
    # =====================================================

    async def send_mod_log(
        self,
        guild,
        action,
        moderator,
        member=None,
        reason=None,
        color=None
    ):
        """
        Sends moderation actions to the configured
        moderation log channel.
        """

        if color is None:
            color = discord.Color.orange()

        try:
            cursor.execute("""
            SELECT log_channel_id
            FROM settings
            WHERE guild_id = ?
            """, (guild.id,))

            result = cursor.fetchone()

        except sqlite3.Error:
            return

        if not result:
            return

        log_channel_id = result["log_channel_id"]

        if not log_channel_id:
            return

        log_channel = guild.get_channel(log_channel_id)

        if log_channel is None:
            return

        embed = discord.Embed(
            title=f"🛡️ Moderation: {action}",
            color=color,
            timestamp=discord.utils.utcnow()
        )

        # -------------------------------------------------
        # USER
        # -------------------------------------------------

        if member:

            embed.add_field(
                name="👤 User",
                value=(
                    f"{member.mention}\n"
                    f"`{member.id}`"
                ),
                inline=True
            )

        # -------------------------------------------------
        # MODERATOR
        # -------------------------------------------------

        if moderator:

            embed.add_field(
                name="🛡️ Moderator",
                value=(
                    f"{moderator.mention}\n"
                    f"`{moderator.id}`"
                ),
                inline=True
            )

        # -------------------------------------------------
        # REASON
        # -------------------------------------------------

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

        if not can_moderate(ctx, member):

            return await ctx.send(
                "❌ You cannot warn someone with an equal "
                "or higher role than you."
            )

        if not bot_can_moderate(ctx.guild, member):

            return await ctx.send(
                "❌ My role is not high enough to moderate that member."
            )

        try:

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
            WHERE user_id = ?
            """, (member.id,))

            warning_count = cursor.fetchone()[0]

        except sqlite3.Error:

            return await ctx.send(
                "❌ I couldn't save the warning to the database."
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
            value=reason[:1000],
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
            discord.Color.orange()
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

        try:

            cursor.execute("""
            SELECT
                id,
                moderator_id,
                reason,
                timestamp
            FROM warnings
            WHERE user_id = ?
            ORDER BY id DESC
            """, (member.id,))

            results = cursor.fetchall()

        except sqlite3.Error:

            return await ctx.send(
                "❌ I couldn't read the warnings database."
            )

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

        # Show newest 10 warnings.

        for row in results[:10]:

            warning_id = row["id"]
            moderator_id = row["moderator_id"]
            reason = row["reason"]
            timestamp = row["timestamp"]

            moderator = ctx.guild.get_member(
                moderator_id
            )

            if moderator:

                moderator_name = moderator.mention

            else:

                moderator_name = (
                    f"`{moderator_id}`"
                )

            embed.add_field(
                name=f"Warning #{warning_id}",
                value=(
                    f"**Reason:** {reason[:500]}\n"
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

        if member.bot:

            return await ctx.send(
                "❌ Bots do not have warnings."
            )

        if not can_moderate(ctx, member):

            return await ctx.send(
                "❌ You cannot clear warnings for someone "
                "with an equal or higher role."
            )

        try:

            cursor.execute("""
            SELECT COUNT(*)
            FROM warnings
            WHERE user_id = ?
            """, (member.id,))

            warning_count = cursor.fetchone()[0]

        except sqlite3.Error:

            return await ctx.send(
                "❌ I couldn't read the warnings database."
            )

        if warning_count == 0:

            return await ctx.send(
                f"✅ {member.mention} has no warnings."
            )

        try:

            cursor.execute("""
            DELETE FROM warnings
            WHERE user_id = ?
            """, (member.id,))

            db.commit()

        except sqlite3.Error:

            return await ctx.send(
                "❌ I couldn't clear the warnings."
            )

        embed = discord.Embed(
            title="🗑️ Warnings Cleared",
            description=(
                f"Removed **{warning_count}** warning(s) "
                f"from {member.mention}."
            ),
            color=discord.Color.green()
        )

        embed.set_footer(
            text=f"Moderator: {ctx.author}"
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
            discord.Color.green()
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

        if not can_moderate(ctx, member):

            return await ctx.send(
                "❌ You cannot timeout someone with an "
                "equal or higher role than you."
            )

        if not bot_can_moderate(ctx.guild, member):

            return await ctx.send(
                "❌ My role is not high enough to timeout that member."
            )

        duration_delta = parse_time(duration)

        if duration_delta is None:

            return await ctx.send(
                "❌ Invalid time format.\n\n"
                "Use:\n"
                "`10s` = 10 seconds\n"
                "`5m` = 5 minutes\n"
                "`2h` = 2 hours\n"
                "`3d` = 3 days"
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
                "❌ Discord rejected the timeout request."
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
            name="📝 Reason",
            value=reason[:1000],
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
            "Timeout",
            ctx.author,
            member,
            reason,
            discord.Color.red()
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

        if not can_moderate(ctx, member):

            return await ctx.send(
                "❌ You cannot remove a timeout from "
                "someone with an equal or higher role."
            )

        if not bot_can_moderate(ctx.guild, member):

            return await ctx.send(
                "❌ My role is not high enough to manage that member."
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
                "❌ Discord rejected the timeout removal."
            )

        embed = discord.Embed(
            title="🔊 Timeout Removed",
            description=(
                f"{member.mention} can speak again."
            ),
            color=discord.Color.green()
        )

        embed.set_footer(
            text=f"Moderator: {ctx.author}"
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
            discord.Color.green()
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

        if member.bot:

            return await ctx.send(
                "❌ You cannot kick a bot."
            )

        if not can_moderate(ctx, member):

            return await ctx.send(
                "❌ You cannot kick someone with an "
                "equal or higher role than you."
            )

        if not bot_can_moderate(ctx.guild, member):

            return await ctx.send(
                "❌ My role is not high enough to kick that member."
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
            name="👤 User",
            value=(
                f"{member}\n"
                f"`{member.id}`"
            ),
            inline=True
        )

        embed.add_field(
            name="📝 Reason",
            value=reason[:1000],
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
            "Kick",
            ctx.author,
            member,
            reason,
            discord.Color.red()
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

        if member.bot:

            return await ctx.send(
                "❌ You cannot ban a bot."
            )

        if not can_moderate(ctx, member):

            return await ctx.send(
                "❌ You cannot ban someone with an "
                "equal or higher role than you."
            )

        if not bot_can_moderate(ctx.guild, member):

            return await ctx.send(
                "❌ My role is not high enough to ban that member."
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
            name="👤 User",
            value=(
                f"{member}\n"
                f"`{member.id}`"
            ),
            inline=True
        )

        embed.add_field(
            name="📝 Reason",
            value=reason[:1000],
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
            "Ban",
            ctx.author,
            member,
            reason,
            discord.Color.red()
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

        except discord.HTTPException:

            return await ctx.send(
                "❌ Discord couldn't retrieve that user."
            )

        try:

            await ctx.guild.unban(
                user,
                reason=f"Unbanned by {ctx.author}"
            )

        except discord.NotFound:

            return await ctx.send(
                "❌ That user isn't banned."
            )

        except discord.Forbidden:

            return await ctx.send(
                "❌ I don't have permission to unban users."
            )

        except discord.HTTPException:

            return await ctx.send(
                "❌ Discord rejected the unban request."
            )

        embed = discord.Embed(
            title="🔓 User Unbanned",
            color=discord.Color.green()
        )

        embed.add_field(
            name="👤 User",
            value=(
                f"{user}\n"
                f"`{user.id}`"
            ),
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
            "Unban",
            ctx.author,
            None,
            f"User: {user} ({user.id})",
            discord.Color.green()
        )

    # =====================================================
    # PURGE
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

        except discord.HTTPException:

            return await ctx.send(
                "❌ Discord rejected the purge request."
            )

        # The command itself is included in the purge.

        deleted_count = max(
            len(deleted) - 1,
            0
        )

        confirmation = await ctx.send(
            f"🧹 Deleted **{deleted_count}** messages."
        )

        try:

            await confirmation.delete(
                delay=5
            )

        except discord.HTTPException:
            pass

        await self.send_mod_log(
            ctx.guild,
            "Message Purge",
            ctx.author,
            None,
            (
                f"{deleted_count} messages deleted "
                f"in {ctx.channel.mention}."
            ),
            discord.Color.orange()
        )

    # =====================================================
    # MODERATION ERROR HANDLER
    # =====================================================

    async def handle_error(
        self,
        ctx,
        error
    ):

        # -------------------------------------------------
        # UNWRAP COMMAND INVOCATION ERROR
        # -------------------------------------------------

        if isinstance(
            error,
            commands.CommandInvokeError
        ):

            error = error.original

        # -------------------------------------------------
        # MISSING PERMISSIONS
        # -------------------------------------------------

        if isinstance(
            error,
            commands.MissingPermissions
        ):

            return await ctx.send(
                "❌ You don't have permission to use that command."
            )

        # -------------------------------------------------
        # MISSING ARGUMENT
        # -------------------------------------------------

        if isinstance(
            error,
            commands.MissingRequiredArgument
        ):

            return await ctx.send(
                "❌ You're missing a required argument.\n"
                f"Use `{ctx.prefix}help {ctx.command}` "
                "to see how to use this command."
            )

        # -------------------------------------------------
        # MEMBER NOT FOUND
        # -------------------------------------------------

        if isinstance(
            error,
            commands.MemberNotFound
        ):

            return await ctx.send(
                "❌ I couldn't find that member.\n"
                "Try mentioning them or using their exact ID."
            )

        # -------------------------------------------------
        # USER NOT FOUND
        # -------------------------------------------------

        if isinstance(
            error,
            commands.UserNotFound
        ):

            return await ctx.send(
                "❌ I couldn't find that user."
            )

        # -------------------------------------------------
        # INVALID INTEGER
        # -------------------------------------------------

        if isinstance(
            error,
            commands.BadArgument
        ):

            return await ctx.send(
                "❌ One of the arguments you entered is invalid."
            )

        # -------------------------------------------------
        # EVERYTHING ELSE
        # -------------------------------------------------

        raise error

    # =====================================================
    # INDIVIDUAL COMMAND ERROR HOOKS
    # =====================================================

    @warn.error
    async def warn_error(self, ctx, error):
        await self.handle_error(ctx, error)

    @warnings.error
    async def warnings_error(self, ctx, error):
        await self.handle_error(ctx, error)

    @clearwarnings.error
    async def clearwarnings_error(self, ctx, error):
        await self.handle_error(ctx, error)

    @timeout.error
    async def timeout_error(self, ctx, error):
        await self.handle_error(ctx, error)

    @untimeout.error
    async def untimeout_error(self, ctx, error):
        await self.handle_error(ctx, error)

    @kick.error
    async def kick_error(self, ctx, error):
        await self.handle_error(ctx, error)

    @ban.error
    async def ban_error(self, ctx, error):
        await self.handle_error(ctx, error)

    @unban.error
    async def unban_error(self, ctx, error):
        await self.handle_error(ctx, error)

    @purge.error
    async def purge_error(self, ctx, error):
        await self.handle_error(ctx, error)


# =========================================================
# SETUP
# =========================================================

async def setup(bot):

    await bot.add_cog(
        Moderation(bot)
    )