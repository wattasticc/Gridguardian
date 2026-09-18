import sqlite3
from typing import Optional

import discord
from discord.ext import commands


DB_PATH = "gridguardian.db"
EMBED_COLOR = discord.Color.blurple()


class Profile(commands.Cog):
    """Grid Guardian member profile system."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ============================================================
    # DATABASE
    # ============================================================

    def db_connect(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    # ============================================================
    # DATABASE HELPERS
    # ============================================================

    def get_level_data(
        self,
        user_id: int
    ):
        conn = self.db_connect()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT xp, level
                FROM levels
                WHERE user_id = ?
                """,
                (user_id,)
            )

            row = cursor.fetchone()

        except sqlite3.OperationalError:
            row = None

        conn.close()

        return row

    def get_mastery_data(
        self,
        guild_id: int,
        user_id: int
    ):
        conn = self.db_connect()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT xp, level
                FROM wattson_mastery
                WHERE guild_id = ?
                  AND user_id = ?
                """,
                (
                    guild_id,
                    user_id
                )
            )

            row = cursor.fetchone()

        except sqlite3.OperationalError:
            row = None

        conn.close()

        return row

    def get_setup_data(
        self,
        guild_id: int,
        user_id: int
    ):
        conn = self.db_connect()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT
                    COUNT(*) AS setup_count,
                    COALESCE(SUM(upvotes), 0) AS upvotes
                FROM wattson_setups
                WHERE guild_id = ?
                  AND user_id = ?
                """,
                (
                    guild_id,
                    user_id
                )
            )

            row = cursor.fetchone()

        except sqlite3.OperationalError:
            row = None

        conn.close()

        return row

    def get_challenge_xp(
        self,
        guild_id: int,
        user_id: int
    ):
        conn = self.db_connect()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT total_xp
                FROM challenge_rewards
                WHERE guild_id = ?
                  AND user_id = ?
                """,
                (
                    guild_id,
                    user_id
                )
            )

            row = cursor.fetchone()

        except sqlite3.OperationalError:
            row = None

        conn.close()

        if not row:
            return 0

        return row["total_xp"]

    def get_achievement_count(
        self,
        user_id: int
    ):
        conn = self.db_connect()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT COUNT(*) AS count
                FROM achievements
                WHERE user_id = ?
                """,
                (user_id,)
            )

            row = cursor.fetchone()

        except sqlite3.OperationalError:
            row = None

        conn.close()

        if not row:
            return 0

        return row["count"]

    # ============================================================
    # RANK HELPERS
    # ============================================================

    def get_level_rank(
        self,
        user_id: int
    ):
        conn = self.db_connect()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT user_id
                FROM levels
                ORDER BY level DESC, xp DESC
                """
            )

            rows = cursor.fetchall()

        except sqlite3.OperationalError:
            conn.close()
            return None

        conn.close()

        for index, row in enumerate(rows, start=1):
            if row["user_id"] == user_id:
                return index

        return None

    def get_mastery_rank(
        self,
        guild_id: int,
        user_id: int
    ):
        conn = self.db_connect()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT user_id
                FROM wattson_mastery
                WHERE guild_id = ?
                ORDER BY level DESC, xp DESC
                """,
                (guild_id,)
            )

            rows = cursor.fetchall()

        except sqlite3.OperationalError:
            conn.close()
            return None

        conn.close()

        for index, row in enumerate(rows, start=1):
            if row["user_id"] == user_id:
                return index

        return None

    def get_setup_rank(
        self,
        guild_id: int,
        user_id: int
    ):
        conn = self.db_connect()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT user_id
                FROM wattson_setups
                WHERE guild_id = ?
                GROUP BY user_id
                ORDER BY
                    COALESCE(SUM(upvotes), 0) DESC,
                    COUNT(*) DESC
                """,
                (guild_id,)
            )

            rows = cursor.fetchall()

        except sqlite3.OperationalError:
            conn.close()
            return None

        conn.close()

        for index, row in enumerate(rows, start=1):
            if row["user_id"] == user_id:
                return index

        return None

    # ============================================================
    # TITLES
    # ============================================================

    def get_mastery_title(
        self,
        level: int
    ):
        titles = [
            (100, "⚡ Master of the Grid"),
            (75, "⚡ Grid Legend"),
            (50, "⚡ Power Grid Master"),
            (30, "⚡ Electrical Expert"),
            (20, "⚡ Grid Commander"),
            (10, "⚡ Fence Specialist"),
            (5, "⚡ Junior Engineer"),
            (1, "⚡ Grid Recruit"),
        ]

        for required_level, title in titles:
            if level >= required_level:
                return title

        return "⚡ Grid Recruit"

    # ============================================================
    # PROFILE EMBED
    # ============================================================

    def build_profile_embed(
        self,
        member: discord.Member,
        level_data,
        mastery_data,
        setup_data,
        challenge_xp,
        achievement_count,
        level_rank,
        mastery_rank,
        setup_rank
    ):
        level = (
            level_data["level"]
            if level_data
            else 1
        )

        level_xp = (
            level_data["xp"]
            if level_data
            else 0
        )

        mastery_level = (
            mastery_data["level"]
            if mastery_data
            else 1
        )

        mastery_xp = (
            mastery_data["xp"]
            if mastery_data
            else 0
        )

        setup_count = (
            setup_data["setup_count"]
            if setup_data
            else 0
        )

        upvotes = (
            setup_data["upvotes"]
            if setup_data
            else 0
        )

        mastery_title = self.get_mastery_title(
            mastery_level
        )

        embed = discord.Embed(
            title=f"⚡ {member.display_name}",
            description=mastery_title,
            color=EMBED_COLOR
        )

        embed.set_thumbnail(
            url=member.display_avatar.url
        )

        # --------------------------------------------------------
        # LEVEL
        # --------------------------------------------------------

        level_rank_text = (
            f"#{level_rank}"
            if level_rank
            else "Unranked"
        )

        embed.add_field(
            name="📈 Server Level",
            value=(
                f"**Level:** {level}\n"
                f"**XP:** {level_xp:,}\n"
                f"**Rank:** {level_rank_text}"
            ),
            inline=True
        )

        # --------------------------------------------------------
        # WATTSON MASTERY
        # --------------------------------------------------------

        mastery_rank_text = (
            f"#{mastery_rank}"
            if mastery_rank
            else "Unranked"
        )

        embed.add_field(
            name="⚡ Wattson Mastery",
            value=(
                f"**Level:** {mastery_level}\n"
                f"**XP:** {mastery_xp:,}\n"
                f"**Rank:** {mastery_rank_text}"
            ),
            inline=True
        )

        # --------------------------------------------------------
        # SETUPS
        # --------------------------------------------------------

        setup_rank_text = (
            f"#{setup_rank}"
            if setup_rank
            else "Unranked"
        )

        embed.add_field(
            name="🧠 Setup Library",
            value=(
                f"**Setups:** {setup_count:,}\n"
                f"**Upvotes:** {upvotes:,}\n"
                f"**Rank:** {setup_rank_text}"
            ),
            inline=True
        )

        # --------------------------------------------------------
        # ACHIEVEMENTS
        # --------------------------------------------------------

        embed.add_field(
            name="🏆 Achievements",
            value=(
                f"**Unlocked:** "
                f"{achievement_count:,}"
            ),
            inline=True
        )

        # --------------------------------------------------------
        # CHALLENGES
        # --------------------------------------------------------

        embed.add_field(
            name="🎯 Challenge XP",
            value=(
                f"**Earned:** "
                f"{challenge_xp:,} XP"
            ),
            inline=True
        )

        # --------------------------------------------------------
        # MEMBER
        # --------------------------------------------------------

        joined_text = (
            discord.utils.format_dt(
                member.joined_at,
                style="D"
            )
            if member.joined_at
            else "Unknown"
        )

        embed.add_field(
            name="👤 Member",
            value=(
                f"**Joined:** {joined_text}\n"
                f"**ID:** `{member.id}`"
            ),
            inline=True
        )

        embed.set_footer(
            text="Grid Guardian • Member Profile"
        )

        return embed

    # ============================================================
    # PROFILE COMMAND
    # ============================================================

    @commands.command(
        name="profile",
        aliases=[
            "p",
            "me",
            "card"
        ]
    )
    @commands.guild_only()
    async def profile(
        self,
        ctx: commands.Context,
        member: Optional[discord.Member] = None
    ):
        """Display a Grid Guardian profile."""

        member = member or ctx.author

        user_id = member.id
        guild_id = ctx.guild.id

        level_data = self.get_level_data(
            user_id
        )

        mastery_data = self.get_mastery_data(
            guild_id,
            user_id
        )

        setup_data = self.get_setup_data(
            guild_id,
            user_id
        )

        challenge_xp = self.get_challenge_xp(
            guild_id,
            user_id
        )

        achievement_count = self.get_achievement_count(
            user_id
        )

        level_rank = self.get_level_rank(
            user_id
        )

        mastery_rank = self.get_mastery_rank(
            guild_id,
            user_id
        )

        setup_rank = self.get_setup_rank(
            guild_id,
            user_id
        )

        embed = self.build_profile_embed(
            member,
            level_data,
            mastery_data,
            setup_data,
            challenge_xp,
            achievement_count,
            level_rank,
            mastery_rank,
            setup_rank
        )

        await ctx.send(
            embed=embed
        )

    # ============================================================
    # PROFILE HELP
    # ============================================================

    @commands.command(
        name="profilehelp"
    )
    @commands.guild_only()
    async def profile_help(
        self,
        ctx: commands.Context
    ):
        embed = discord.Embed(
            title="⚡ Profile Commands",
            description=(
                "`!profile` — View your profile\n"
                "`!profile @user` — View another member's profile\n"
                "`!p` — Profile shortcut\n"
                "`!me` — Profile shortcut\n"
                "`!card` — Profile shortcut"
            ),
            color=EMBED_COLOR
        )

        embed.add_field(
            name="Profile Includes",
            value=(
                "📈 Server Level\n"
                "⚡ Wattson Mastery\n"
                "🧠 Setup Library stats\n"
                "🎯 Challenge XP\n"
                "🏆 Achievements\n"
                "📊 Server ranks"
            ),
            inline=False
        )

        await ctx.send(
            embed=embed
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Profile(bot))