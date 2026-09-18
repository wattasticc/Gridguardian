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

# Every level requires the same amount of XP.
#
# Level 1 -> Level 2 = 100 XP
# Level 2 -> Level 3 = 100 XP
# Level 3 -> Level 4 = 100 XP
#
# Total XP is stored permanently.
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
        # Add total_xp if this is an existing database.
        # --------------------------------------------------

        cursor.execute(
            "PRAGMA table_info(levels)"
        )

        columns = {
            row["name"]
            for row in cursor.fetchall()
        }

        if "total_xp" not in columns:

            cursor.execute(
                """
                ALTER TABLE levels
                ADD COLUMN total_xp INTEGER DEFAULT 0
                """
            )

        # --------------------------------------------------
        # Migrate existing users.
        #
        # The old system stored:
        #
        #     level
        #     xp inside that level
        #
        # Example:
        #
        # Level 6 + 37 XP
        #
        # becomes:
        #
        # Total XP = 537
        #
        # This preserves their progress.
        # --------------------------------------------------

        cursor.execute(
            """
            SELECT
                user_id,
                xp,
                level,
                total_xp
            FROM levels
            """
        )

        existing_users = cursor.fetchall()

        for user in existing_users:

            user_id = int(user["user_id"])

            old_xp = max(
                0,
                int(user["xp"] or 0)
            )

            old_level = max(
                1,
                int(user["level"] or 1)
            )

            current_total = user["total_xp"]

            # ----------------------------------------------
            # Only migrate rows that don't already have a
            # meaningful total XP value.
            # ----------------------------------------------

            if current_total is None or int(current_total) <= 0:

                total_xp = (
                    (old_level - 1) * XP_PER_LEVEL
                    + old_xp
                )

                cursor.execute(
                    """
                    UPDATE levels
                    SET total_xp = ?
                    WHERE user_id = ?
                    """,
                    (
                        total_xp,
                        user_id
                    )
                )

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
        #
        # This is only a message XP cooldown.
        # It does NOT control level progression.
        # --------------------------------------------------

        self.cooldowns = {}


    # ======================================================
    # LEVEL FROM TOTAL XP
    # ======================================================

    @staticmethod
    def level_from_total_xp(total_xp: int) -> int:
        """
        Calculate a user's level from their permanent
        total XP value.

        Examples:

        0 XP   -> Level 1
        99 XP  -> Level 1
        100 XP -> Level 2
        199 XP -> Level 2
        200 XP -> Level 3
        500 XP -> Level 6
        600 XP -> Level 7

        The level can never go backward unless total XP
        itself is deliberately reduced.
        """

        total_xp = max(
            0,
            int(total_xp)
        )

        return (
            total_xp // XP_PER_LEVEL
        ) + 1


    # ======================================================
    # XP REQUIRED FOR NEXT LEVEL
    # ======================================================

    @staticmethod
    def xp_required(level: int) -> int:
        """
        XP required for the next level.

        Every level requires the same amount.
        """

        return XP_PER_LEVEL


    # ======================================================
    # XP INSIDE CURRENT LEVEL
    # ======================================================

    @staticmethod
    def current_level_xp(total_xp: int) -> int:
        """
        Return the XP progress inside the user's
        current level.
        """

        total_xp = max(
            0,
            int(total_xp)
        )

        return total_xp % XP_PER_LEVEL


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
                SELECT
                    user_id,
                    xp,
                    level,
                    total_xp
                FROM levels
                WHERE user_id = ?
                """,
                (
                    user_id,
                )
            )

            data = cursor.fetchone()

            if data is None:
                return None

            # ------------------------------------------------
            # Always derive the level from total XP.
            #
            # This protects against an old/inconsistent
            # level value sitting in the database.
            # ------------------------------------------------

            total_xp = max(
                0,
                int(data["total_xp"] or 0)
            )

            calculated_level = (
                Leveling.level_from_total_xp(
                    total_xp
                )
            )

            current_xp = (
                Leveling.current_level_xp(
                    total_xp
                )
            )

            # ------------------------------------------------
            # If the legacy columns are incorrect, repair
            # them while we're here.
            # ------------------------------------------------

            if (
                int(data["level"] or 1)
                != calculated_level
                or
                int(data["xp"] or 0)
                != current_xp
            ):

                cursor.execute(
                    """
                    UPDATE levels
                    SET
                        xp = ?,
                        level = ?,
                        total_xp = ?
                    WHERE user_id = ?
                    """,
                    (
                        current_xp,
                        calculated_level,
                        total_xp,
                        user_id
                    )
                )

                db.commit()

            return {
                "user_id": user_id,
                "xp": current_xp,
                "level": calculated_level,
                "total_xp": total_xp
            }

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


        # ==================================================
        # DATABASE
        # ==================================================

        db = get_db()

        try:

            cursor = db.cursor()

            # ------------------------------------------------
            # BEGIN IMMEDIATE
            #
            # This prevents two simultaneous XP updates from
            # reading the same old value and overwriting each
            # other.
            # ------------------------------------------------

            cursor.execute(
                "BEGIN IMMEDIATE"
            )


            # ==================================================
            # GET CURRENT DATA
            # ==================================================

            cursor.execute(
                """
                SELECT
                    user_id,
                    xp,
                    level,
                    total_xp
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

                total_xp = xp_gain

                level = (
                    self.level_from_total_xp(
                        total_xp
                    )
                )

                current_xp = (
                    self.current_level_xp(
                        total_xp
                    )
                )

                cursor.execute(
                    """
                    INSERT INTO levels (
                        user_id,
                        xp,
                        level,
                        total_xp
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        message.author.id,
                        current_xp,
                        level,
                        total_xp
                    )
                )

                db.commit()

                return


            # ==================================================
            # EXISTING USER
            # ==================================================

            stored_total_xp = data["total_xp"]

            # ------------------------------------------------
            # Safety fallback for an old row.
            # ------------------------------------------------

            if stored_total_xp is None:

                old_xp = max(
                    0,
                    int(data["xp"] or 0)
                )

                old_level = max(
                    1,
                    int(data["level"] or 1)
                )

                stored_total_xp = (
                    (old_level - 1) * XP_PER_LEVEL
                    + old_xp
                )

            else:

                stored_total_xp = max(
                    0,
                    int(stored_total_xp)
                )


            # ------------------------------------------------
            # Save the level BEFORE adding XP.
            # ------------------------------------------------

            old_level = (
                self.level_from_total_xp(
                    stored_total_xp
                )
            )


            # ------------------------------------------------
            # Add XP to permanent total.
            # ------------------------------------------------

            total_xp = (
                stored_total_xp
                + xp_gain
            )


            # ------------------------------------------------
            # Calculate the new level entirely from total XP.
            #
            # This is the important part:
            #
            # We NEVER manually subtract XP from the database
            # and then increment/decrement the level.
            #
            # The level is always derived from total XP.
            # ------------------------------------------------

            new_level = (
                self.level_from_total_xp(
                    total_xp
                )
            )


            # ------------------------------------------------
            # XP inside current level.
            # ------------------------------------------------

            current_xp = (
                self.current_level_xp(
                    total_xp
                )
            )


            # ------------------------------------------------
            # Safety check.
            #
            # A user's level is never allowed to decrease
            # from an XP gain.
            # ------------------------------------------------

            if new_level < old_level:

                new_level = old_level

                # This should never happen, but if it somehow
                # does, preserve the user's current level.
                current_xp = min(
                    current_xp,
                    XP_PER_LEVEL - 1
                )


            # ==================================================
            # DETERMINE LEVELS GAINED
            # ==================================================

            levels_gained = []

            if new_level > old_level:

                for reached_level in range(
                    old_level + 1,
                    new_level + 1
                ):

                    levels_gained.append(
                        reached_level
                    )


            # ==================================================
            # SAVE EVERYTHING
            # ==================================================

            cursor.execute(
                """
                UPDATE levels
                SET
                    xp = ?,
                    level = ?,
                    total_xp = ?
                WHERE user_id = ?
                """,
                (
                    current_xp,
                    new_level,
                    total_xp,
                    message.author.id
                )
            )


            # ==================================================
            # COMMIT
            # ==================================================

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
                    new_level
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
                            new_level
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
                                f"to Level {new_level}"
                            )
                        )


                    # ------------------------------------------
                    # Give new level role.
                    # ------------------------------------------

                    if final_role not in message.author.roles:

                        await message.author.add_roles(
                            final_role,
                            reason=(
                                f"Reached Level {new_level}"
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
                    f"Level {new_level}**"
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
                new_level
            )

            embed.add_field(
                name="⚡ XP",
                value=(
                    f"{current_xp}/{xp_needed}"
                ),
                inline=True
            )


            # ==================================================
            # TOTAL XP
            # ==================================================

            embed.add_field(
                name="📊 Total XP",
                value=f"{total_xp:,}",
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

        except sqlite3.Error:

            # ------------------------------------------------
            # If anything goes wrong with the transaction,
            # roll it back so partial XP/level changes cannot
            # remain in the database.
            # ------------------------------------------------

            try:
                db.rollback()
            except sqlite3.Error:
                pass

            raise

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
        total_xp = int(data["total_xp"])


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
            name="📊 Total XP",
            value=f"{total_xp:,}",
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