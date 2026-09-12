import random
import sqlite3
import time

import discord
from discord.ext import commands

from cogs.utils.achievement_manager import unlock


# ==========================================================
# CONFIGURATION
# ==========================================================

EMBED_COLOR = discord.Color.from_rgb(
    80,
    220,
    255
)

XP_COOLDOWN = 60

MIN_XP_GAIN = 5
MAX_XP_GAIN = 15

XP_PER_LEVEL_MULTIPLIER = 100


# ==========================================================
# DATABASE
# ==========================================================

db = sqlite3.connect(
    "gridguardian.db",
    timeout=30,
    check_same_thread=False
)

db.execute(
    "PRAGMA busy_timeout = 30000"
)

db.execute(
    "PRAGMA journal_mode = WAL"
)

db.execute(
    "PRAGMA synchronous = NORMAL"
)

cursor = db.cursor()


cursor.execute("""
CREATE TABLE IF NOT EXISTS levels (
    user_id INTEGER PRIMARY KEY,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1
)
""")


cursor.execute("""
CREATE TABLE IF NOT EXISTS level_roles (
    guild_id INTEGER,
    level INTEGER,
    role_id INTEGER,
    PRIMARY KEY (guild_id, level)
)
""")


db.commit()


# ==========================================================
# LEVELING COG
# ==========================================================

class Leveling(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        # User ID -> timestamp
        self.cooldowns = {}


    # ======================================================
    # XP REQUIRED
    # ======================================================

    @staticmethod
    def xp_required(level: int) -> int:
        """
        Return the XP required to go from the
        current level to the next level.

        Example:

        Level 1 -> 100 XP
        Level 2 -> 200 XP
        Level 3 -> 300 XP
        Level 4 -> 400 XP
        """

        return level * XP_PER_LEVEL_MULTIPLIER


    # ======================================================
    # MESSAGE LISTENER
    # ======================================================

    @commands.Cog.listener()
    async def on_message(
        self,
        message: discord.Message
    ):

        # --------------------------------------------------
        # Ignore bots
        # --------------------------------------------------

        if message.author.bot:
            return


        # --------------------------------------------------
        # XP cooldown
        # --------------------------------------------------

        now = time.time()

        last = self.cooldowns.get(
            message.author.id,
            0
        )

        if now - last < XP_COOLDOWN:
            return

        self.cooldowns[
            message.author.id
        ] = now


        # --------------------------------------------------
        # Random XP
        # --------------------------------------------------

        xp_gain = random.randint(
            MIN_XP_GAIN,
            MAX_XP_GAIN
        )


        # --------------------------------------------------
        # Get current level data
        # --------------------------------------------------

        cursor.execute(
            """
            SELECT xp, level
            FROM levels
            WHERE user_id=?
            """,
            (
                message.author.id,
            )
        )

        data = cursor.fetchone()


        # ==================================================
        # NEW USER
        # ==================================================

        if data is None:

            cursor.execute(
                """
                INSERT INTO levels (
                    user_id,
                    xp,
                    level
                )
                VALUES (?, ?, ?)
                """,
                (
                    message.author.id,
                    xp_gain,
                    1
                )
            )

            db.commit()

            return


        # ==================================================
        # EXISTING USER
        # ==================================================

        xp, level = data

        xp += xp_gain


        # --------------------------------------------------
        # Track every level crossed during this XP gain.
        # --------------------------------------------------

        old_level = level

        levels_gained = []


        # ==================================================
        # PROCESS LEVEL UPS
        # ==================================================

        while xp >= self.xp_required(level):

            required_xp = self.xp_required(level)

            xp -= required_xp

            level += 1

            levels_gained.append(
                level
            )


        # ==================================================
        # SAVE DATABASE IMMEDIATELY
        # ==================================================

        cursor.execute(
            """
            UPDATE levels
            SET
                xp=?,
                level=?
            WHERE user_id=?
            """,
            (
                xp,
                level,
                message.author.id
            )
        )

        db.commit()


        # ==================================================
        # NO LEVEL UP
        # ==================================================

        if not levels_gained:
            return


        # ==================================================
        # ACHIEVEMENTS
        # ==================================================

        for reached_level in levels_gained:

            if reached_level == 5:

                unlock(
                    message.author.id,
                    "⭐ Level 5"
                )

            elif reached_level == 10:

                unlock(
                    message.author.id,
                    "⭐ Level 10"
                )

            elif reached_level == 25:

                unlock(
                    message.author.id,
                    "⭐ Level 25"
                )

            elif reached_level == 50:

                unlock(
                    message.author.id,
                    "🌟 Level 50"
                )

            elif reached_level == 100:

                unlock(
                    message.author.id,
                    "👑 Level 100"
                )


        # ==================================================
        # LEVEL ROLE
        # ==================================================

        if message.guild is not None:

            # Give the role for the FINAL level reached.
            final_level = level

            cursor.execute(
                """
                SELECT role_id
                FROM level_roles
                WHERE guild_id=?
                AND level=?
                """,
                (
                    message.guild.id,
                    final_level
                )
            )

            result = cursor.fetchone()

            if result:

                role = message.guild.get_role(
                    result[0]
                )

                if role:

                    try:

                        # Only add if they don't already
                        # have the role.
                        if role not in message.author.roles:

                            await message.author.add_roles(
                                role,
                                reason=(
                                    f"Reached Level "
                                    f"{final_level}"
                                )
                            )

                    except (
                        discord.Forbidden,
                        discord.HTTPException
                    ):

                        pass


        # ==================================================
        # LEVEL-UP MESSAGE
        # ==================================================

        # If multiple levels were gained at once,
        # show the full range.

        if len(levels_gained) == 1:

            level_text = (
                f"**Level {levels_gained[0]}**"
            )

        else:

            level_text = (
                f"**Level {old_level} → "
                f"Level {level}**"
            )


        embed = discord.Embed(
            title="🎉 Level Up!",
            description=(
                f"{message.author.mention} reached "
                f"{level_text}!"
            ),
            color=discord.Color.gold()
        )


        # --------------------------------------------------
        # Role information
        # --------------------------------------------------

        if message.guild is not None:

            cursor.execute(
                """
                SELECT role_id
                FROM level_roles
                WHERE guild_id=?
                AND level=?
                """,
                (
                    message.guild.id,
                    level
                )
            )

            role_result = cursor.fetchone()

            if role_result:

                role = message.guild.get_role(
                    role_result[0]
                )

                if role:

                    embed.add_field(
                        name="🏅 New Role",
                        value=role.mention,
                        inline=True
                    )


        # --------------------------------------------------
        # Current XP
        # --------------------------------------------------

        xp_needed = self.xp_required(
            level
        )

        embed.add_field(
            name="⚡ XP",
            value=f"{xp}/{xp_needed}",
            inline=True
        )


        try:

            await message.channel.send(
                embed=embed
            )

        except (
            discord.Forbidden,
            discord.HTTPException
        ):

            pass


    # ======================================================
    # !RANK
    # ======================================================

    @commands.command()
    async def rank(
        self,
        ctx
    ):

        cursor.execute(
            """
            SELECT xp, level
            FROM levels
            WHERE user_id=?
            """,
            (
                ctx.author.id,
            )
        )

        data = cursor.fetchone()


        if data is None:

            return await ctx.send(
                "You don't have any XP yet."
            )


        xp, level = data

        xp_needed = self.xp_required(
            level
        )


        percent = min(
            int(
                (xp / xp_needed) * 10
            ),
            10
        )


        bar = (
            "█" * percent
            + "░" * (10 - percent)
        )


        embed = discord.Embed(
            title=(
                f"⭐ "
                f"{ctx.author.display_name}'s Rank"
            ),
            color=EMBED_COLOR
        )


        embed.set_thumbnail(
            url=ctx.author.display_avatar.url
        )


        embed.add_field(
            name="⭐ Level",
            value=level,
            inline=True
        )


        embed.add_field(
            name="⚡ XP",
            value=f"{xp}/{xp_needed}",
            inline=True
        )


        embed.add_field(
            name="📈 Progress",
            value=bar,
            inline=False
        )


        await ctx.send(
            embed=embed
        )


    # ======================================================
    # !SETLEVELROLE
    # ======================================================

    @commands.has_permissions(
        administrator=True
    )
    @commands.command()
    async def setlevelrole(
        self,
        ctx,
        level: int,
        role: discord.Role
    ):

        if level < 1:

            return await ctx.send(
                "❌ Level must be 1 or higher."
            )


        cursor.execute(
            """
            INSERT OR REPLACE INTO level_roles
            VALUES (?, ?, ?)
            """,
            (
                ctx.guild.id,
                level,
                role.id
            )
        )

        db.commit()


        embed = discord.Embed(
            title="✅ Level Role Added",
            description=(
                f"Members will receive "
                f"{role.mention}\n"
                f"when they reach **Level {level}**."
            ),
            color=discord.Color.green()
        )


        await ctx.send(
            embed=embed
        )


    # ======================================================
    # !LEADERBOARD
    # ======================================================

    @commands.command(
        aliases=["lb"]
    )
    async def leaderboard(
        self,
        ctx
    ):

        cursor.execute(
            """
            SELECT
                user_id,
                level,
                xp
            FROM levels
            ORDER BY
                level DESC,
                xp DESC
            LIMIT 10
            """
        )

        results = cursor.fetchall()


        if not results:

            return await ctx.send(
                "Nobody has earned XP yet."
            )


        medals = [
            "🥇",
            "🥈",
            "🥉"
        ]


        embed = discord.Embed(
            title="🏆 Grid Guardian Leaderboard",
            description=(
                "Top 10 members by level"
            ),
            color=EMBED_COLOR
        )


        displayed = 0


        for index, (
            user_id,
            level,
            xp
        ) in enumerate(results):

            member = ctx.guild.get_member(
                user_id
            )


            if member is None:
                continue


            if index < 3:

                place = medals[index]

            else:

                place = (
                    f"**{index + 1}.**"
                )


            embed.add_field(
                name=(
                    f"{place} "
                    f"{member.display_name}"
                ),
                value=(
                    f"⭐ Level **{level}**\n"
                    f"⚡ XP **{xp}/"
                    f"{self.xp_required(level)}**"
                ),
                inline=False
            )


            displayed += 1


        if displayed == 0:

            return await ctx.send(
                "Nobody has earned XP yet."
            )


        embed.set_footer(
            text=(
                f"Requested by "
                f"{ctx.author.display_name}"
            )
        )


        await ctx.send(
            embed=embed
        )


# ==========================================================
# SETUP
# ==========================================================

async def setup(bot):

    await bot.add_cog(
        Leveling(bot)
    )