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

# XP required for EACH level.
#
# Level 1 -> Level 2 = 100 XP
# Level 2 -> Level 3 = 100 XP
# Level 3 -> Level 4 = 100 XP
#
# Extra XP is carried over after a level-up.
XP_PER_LEVEL = 100


# ==========================================================
# DATABASE
# ==========================================================

DB_PATH = "gridguardian.db"


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


# ==========================================================
# INITIALIZE DATABASE
# ==========================================================

def initialize_database():

    db = get_db()

    try:

        cursor = db.cursor()

        # --------------------------------------------------
        # Levels
        # --------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS levels (
                user_id INTEGER PRIMARY KEY,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1
            )
        """)

        # --------------------------------------------------
        # Level roles
        # --------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS level_roles (
                guild_id INTEGER,
                level INTEGER,
                role_id INTEGER,
                PRIMARY KEY (guild_id, level)
            )
        """)

        db.commit()

    finally:

        db.close()


initialize_database()


# ==========================================================
# LEVELING COG
# ==========================================================

class Leveling(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        # --------------------------------------------------
        # User ID -> timestamp
        # --------------------------------------------------

        self.cooldowns = {}


    # ======================================================
    # XP REQUIRED
    # ======================================================

    @staticmethod
    def xp_required(level: int) -> int:
        """
        Return the XP required to move from the current
        level to the next level.

        Every level requires the same amount of XP.

        Examples:

        Level 1 -> Level 2 = 100 XP
        Level 2 -> Level 3 = 100 XP
        Level 7 -> Level 8 = 100 XP
        Level 8 -> Level 9 = 100 XP
        """

        return XP_PER_LEVEL


    # ======================================================
    # GET USER DATA
    # ======================================================

    @staticmethod
    def get_user_data(user_id: int):

        db = get_db()

        try:

            cursor = db.cursor()

            cursor.execute(
                """
                SELECT xp, level
                FROM levels
                WHERE user_id = ?
                """,
                (
                    user_id,
                )
            )

            return cursor.fetchone()

        finally:

            db.close()


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
        # Ignore DMs
        # --------------------------------------------------

        if message.guild is None:
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
        # Database
        # --------------------------------------------------

        db = get_db()

        try:

            cursor = db.cursor()


            # ==================================================
            # GET CURRENT DATA
            # ==================================================

            cursor.execute(
                """
                SELECT xp, level
                FROM levels
                WHERE user_id = ?
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

            xp = int(data["xp"])
            level = int(data["level"])


            # --------------------------------------------------
            # Add XP
            # --------------------------------------------------

            xp += xp_gain


            # --------------------------------------------------
            # Save original level
            # --------------------------------------------------

            old_level = level

            levels_gained = []


            # ==================================================
            # PROCESS LEVEL UPS
            # ==================================================

            while xp >= self.xp_required(level):

                required_xp = self.xp_required(level)

                # ----------------------------------------------
                # Subtract only the XP needed for this level.
                #
                # Any remaining XP is preserved.
                # ----------------------------------------------

                xp -= required_xp

                level += 1

                levels_gained.append(
                    level
                )


            # ==================================================
            # SAVE XP + LEVEL
            # ==================================================

            cursor.execute(
                """
                UPDATE levels
                SET
                    xp = ?,
                    level = ?
                WHERE user_id = ?
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
            # FIND HIGHEST LEVEL ROLE
            # ==================================================

            final_role = None

            cursor.execute(
                """
                SELECT role_id
                FROM level_roles
                WHERE guild_id = ?
                AND level <= ?
                ORDER BY level DESC
                LIMIT 1
                """,
                (
                    message.guild.id,
                    level
                )
            )

            role_result = cursor.fetchone()


            if role_result:

                final_role = message.guild.get_role(
                    role_result["role_id"]
                )


            # ==================================================
            # APPLY LEVEL ROLE
            # ==================================================

            if final_role:

                try:

                    # ------------------------------------------
                    # Find lower configured level roles.
                    # ------------------------------------------

                    cursor.execute(
                        """
                        SELECT role_id
                        FROM level_roles
                        WHERE guild_id = ?
                        AND level < ?
                        """,
                        (
                            message.guild.id,
                            level
                        )
                    )

                    old_role_rows = cursor.fetchall()

                    roles_to_remove = []


                    for row in old_role_rows:

                        old_role = message.guild.get_role(
                            row["role_id"]
                        )

                        if (
                            old_role
                            and old_role in message.author.roles
                            and old_role != final_role
                        ):

                            roles_to_remove.append(
                                old_role
                            )


                    # ------------------------------------------
                    # Remove old level roles.
                    # ------------------------------------------

                    if roles_to_remove:

                        await message.author.remove_roles(
                            *roles_to_remove,
                            reason=(
                                f"Level progression "
                                f"to Level {level}"
                            )
                        )


                    # ------------------------------------------
                    # Give new level role.
                    # ------------------------------------------

                    if final_role not in message.author.roles:

                        await message.author.add_roles(
                            final_role,
                            reason=(
                                f"Reached Level {level}"
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


            # ==================================================
            # ROLE INFORMATION
            # ==================================================

            if final_role:

                embed.add_field(
                    name="🏅 Level Role",
                    value=final_role.mention,
                    inline=True
                )


            # ==================================================
            # CURRENT XP
            # ==================================================

            xp_needed = self.xp_required(
                level
            )

            embed.add_field(
                name="⚡ XP",
                value=(
                    f"{xp}/{xp_needed}"
                ),
                inline=True
            )


            # ==================================================
            # SEND LEVEL-UP MESSAGE
            # ==================================================

            try:

                await message.channel.send(
                    embed=embed
                )

            except (
                discord.Forbidden,
                discord.HTTPException
            ):

                pass

        finally:

            db.close()


    # ======================================================
    # !RANK
    # ======================================================

    @commands.command()
    async def rank(
        self,
        ctx
    ):

        data = self.get_user_data(
            ctx.author.id
        )


        if data is None:

            return await ctx.send(
                "You don't have any XP yet."
            )


        xp = int(data["xp"])
        level = int(data["level"])


        xp_needed = self.xp_required(
            level
        )


        # --------------------------------------------------
        # Progress bar
        # --------------------------------------------------

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

    @commands.command()
    @commands.has_permissions(
        administrator=True
    )
    async def setlevelrole(
        self,
        ctx,
        level: int,
        role: discord.Role
    ):

        if ctx.guild is None:

            return await ctx.send(
                "❌ This command can only be used in a server."
            )


        if level < 1:

            return await ctx.send(
                "❌ Level must be 1 or higher."
            )


        # --------------------------------------------------
        # Bot role hierarchy check
        # --------------------------------------------------

        if role >= ctx.guild.me.top_role:

            return await ctx.send(
                "❌ I can't manage that role because it is "
                "higher than or equal to my highest role."
            )


        # --------------------------------------------------
        # Prevent @everyone
        # --------------------------------------------------

        if role == ctx.guild.default_role:

            return await ctx.send(
                "❌ You can't use the @everyone role."
            )


        db = get_db()

        try:

            cursor = db.cursor()

            cursor.execute(
                """
                INSERT OR REPLACE INTO level_roles (
                    guild_id,
                    level,
                    role_id
                )
                VALUES (?, ?, ?)
                """,
                (
                    ctx.guild.id,
                    level,
                    role.id
                )
            )

            db.commit()

        finally:

            db.close()


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
    # ERROR HANDLER - SET LEVEL ROLE
    # ======================================================

    @setlevelrole.error
    async def setlevelrole_error(
        self,
        ctx,
        error
    ):

        if isinstance(
            error,
            commands.MissingPermissions
        ):

            await ctx.send(
                "❌ You need Administrator permission "
                "to use this command."
            )

        elif isinstance(
            error,
            commands.MissingRequiredArgument
        ):

            await ctx.send(
                "❌ Usage: `!setlevelrole <level> @role`"
            )

        elif isinstance(
            error,
            commands.BadArgument
        ):

            await ctx.send(
                "❌ Make sure the level is a number and "
                "you mention a valid Discord role."
            )


# ==========================================================
# SETUP
# ==========================================================

async def setup(bot):

    await bot.add_cog(
        Leveling(bot)
    )