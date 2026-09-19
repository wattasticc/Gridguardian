import random
import sqlite3
import time

import discord
from discord.ext import commands

DB_PATH = "gridguardian.db"

XP_COOLDOWN = 60
XP_MIN = 5
XP_MAX = 15

# Current progression:
# Level 1 -> 2: 100 XP
# Level 2 -> 3: 125 XP
# Level 3 -> 4: 150 XP
BASE_XP_REQUIRED = 100
XP_INCREASE_PER_LEVEL = 25

LEVEL_ACHIEVEMENTS = {
    5: "Level 5",
    10: "Level 10",
    25: "Level 25",
    50: "Level 50",
    100: "Level 100",
}


def xp_required_for_level(level: int) -> int:
    level = max(1, int(level))
    return BASE_XP_REQUIRED + ((level - 1) * XP_INCREASE_PER_LEVEL)


def level_from_total_xp(total_xp: int) -> int:
    total_xp = max(0, int(total_xp))
    level = 1
    remaining = total_xp

    while remaining >= xp_required_for_level(level):
        remaining -= xp_required_for_level(level)
        level += 1

    return level


def progress_from_total_xp(total_xp: int) -> tuple[int, int]:
    total_xp = max(0, int(total_xp))
    level = 1
    remaining = total_xp

    while remaining >= xp_required_for_level(level):
        remaining -= xp_required_for_level(level)
        level += 1

    return remaining, xp_required_for_level(level)


def legacy_total_xp_from_level(level: int, xp: int) -> int:
    """Convert the previous level*100 progression into cumulative XP.

    The previous live leveling file used:
        Level 1 -> 100 XP
        Level 2 -> 200 XP
        Level 3 -> 300 XP
        ...

    Therefore the XP required to reach a level was the sum of all
    previous level thresholds, not simply (level - 1) * 100.
    """
    level = max(1, int(level))
    xp = max(0, int(xp))
    completed_levels = level - 1
    cumulative = 100 * completed_levels * (completed_levels + 1) // 2
    return cumulative + xp


class Leveling(commands.Cog):
    """XP, levels, ranks, achievements, and level roles."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.xp_cooldowns: dict[int, float] = {}
        self.init_database()

    def init_database(self):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS levels (
                    user_id INTEGER PRIMARY KEY,
                    xp INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1,
                    total_xp INTEGER DEFAULT 0
                )
                """
            )

            cursor.execute("PRAGMA table_info(levels)")
            columns = {row[1] for row in cursor.fetchall()}

            if "total_xp" not in columns:
                cursor.execute(
                    "ALTER TABLE levels ADD COLUMN total_xp INTEGER DEFAULT 0"
                )

            # One-time migration for rows created by the old level*100 system.
            # Do not touch rows that already have authoritative total_xp.
            cursor.execute(
                "SELECT user_id, xp, level, total_xp FROM levels"
            )

            for user_id, old_xp, old_level, stored_total_xp in cursor.fetchall():
                old_xp = max(0, int(old_xp or 0))
                old_level = max(1, int(old_level or 1))
                stored_total_xp = int(stored_total_xp or 0)

                if stored_total_xp == 0 and (old_level > 1 or old_xp > 0):
                    migrated_total_xp = legacy_total_xp_from_level(
                        old_level,
                        old_xp,
                    )
                    cursor.execute(
                        "UPDATE levels SET total_xp = ? WHERE user_id = ?",
                        (migrated_total_xp, user_id),
                    )

            conn.commit()

    def get_user_data(self, user_id: int):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT xp, level, total_xp FROM levels WHERE user_id = ?",
                (user_id,),
            )
            row = cursor.fetchone()

            if row is None:
                return None

            old_xp, stored_level, total_xp = row
            total_xp = max(0, int(total_xp or 0))

            # total_xp is the single source of truth from here on.
            level = level_from_total_xp(total_xp)
            current_xp, required_xp = progress_from_total_xp(total_xp)

            if (
                int(old_xp or 0) != current_xp
                or int(stored_level or 1) != level
            ):
                cursor.execute(
                    """
                    UPDATE levels
                    SET xp = ?, level = ?, total_xp = ?
                    WHERE user_id = ?
                    """,
                    (current_xp, level, total_xp, user_id),
                )
                conn.commit()

            return {
                "xp": current_xp,
                "level": level,
                "total_xp": total_xp,
                "required": required_xp,
            }

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return

        user_id = message.author.id
        now = time.time()

        if now - self.xp_cooldowns.get(user_id, 0) < XP_COOLDOWN:
            return

        xp_gain = random.randint(XP_MIN, XP_MAX)

        try:
            with sqlite3.connect(DB_PATH, timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute("BEGIN IMMEDIATE")

                cursor.execute(
                    "SELECT xp, level, total_xp FROM levels WHERE user_id = ?",
                    (user_id,),
                )
                row = cursor.fetchone()

                if row is None:
                    old_level = 1
                    total_xp = xp_gain
                else:
                    old_xp, stored_level, stored_total_xp = row
                    old_xp = max(0, int(old_xp or 0))
                    stored_level = max(1, int(stored_level or 1))
                    stored_total_xp = int(stored_total_xp or 0)

                    # Safety migration for any old row that has not yet been
                    # migrated. This uses the previous level*100 system.
                    if stored_total_xp == 0 and (stored_level > 1 or old_xp > 0):
                        stored_total_xp = legacy_total_xp_from_level(
                            stored_level,
                            old_xp,
                        )

                    total_xp = max(0, stored_total_xp)
                    old_level = level_from_total_xp(total_xp)
                    total_xp += xp_gain

                new_level = level_from_total_xp(total_xp)
                current_xp, _ = progress_from_total_xp(total_xp)

                if row is None:
                    cursor.execute(
                        """
                        INSERT INTO levels (user_id, xp, level, total_xp)
                        VALUES (?, ?, ?, ?)
                        """,
                        (user_id, current_xp, new_level, total_xp),
                    )
                else:
                    cursor.execute(
                        """
                        UPDATE levels
                        SET xp = ?, level = ?, total_xp = ?
                        WHERE user_id = ?
                        """,
                        (current_xp, new_level, total_xp, user_id),
                    )

                conn.commit()
        except sqlite3.Error as error:
            # Only consume the cooldown after a successful database write.
            print(f"[LEVELING] Database error for {user_id}: {error}")
            return

        self.xp_cooldowns[user_id] = now

        if new_level > old_level:
            await self.handle_level_up(message, old_level, new_level, total_xp)

    async def handle_level_up(self, message, old_level, new_level, total_xp):
        achievement = LEVEL_ACHIEVEMENTS.get(new_level)

        if achievement:
            try:
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS achievements (
                            user_id INTEGER NOT NULL,
                            achievement TEXT NOT NULL,
                            unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            PRIMARY KEY (user_id, achievement)
                        )
                        """
                    )
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO achievements (user_id, achievement)
                        VALUES (?, ?)
                        """,
                        (message.author.id, achievement),
                    )
                    conn.commit()
            except sqlite3.Error as error:
                print(f"[LEVELING] Achievement error: {error}")

        await self.sync_level_roles(message.author, message.guild, new_level)

        current_xp, required_xp = progress_from_total_xp(total_xp)

        embed = discord.Embed(
            title="🎉 Level Up!",
            description=f"{message.author.mention} reached **Level {new_level}**!",
            color=discord.Color.blurple(),
        )
        embed.set_thumbnail(url=message.author.display_avatar.url)
        embed.add_field(name="Previous Level", value=f"Level {old_level}", inline=True)
        embed.add_field(name="New Level", value=f"Level {new_level}", inline=True)
        embed.add_field(name="Total XP", value=f"{total_xp:,}", inline=True)
        embed.add_field(
            name="Next Level",
            value=f"{current_xp:,} / {required_xp:,} XP",
            inline=False,
        )
        embed.set_footer(text="Keep chatting to earn more XP!")

        try:
            await message.channel.send(embed=embed)
        except discord.HTTPException:
            pass

    async def sync_level_roles(self, member, guild, level):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS level_roles (
                    guild_id INTEGER NOT NULL,
                    level INTEGER NOT NULL,
                    role_id INTEGER NOT NULL,
                    PRIMARY KEY (guild_id, level)
                )
                """
            )
            cursor.execute(
                """
                SELECT level, role_id FROM level_roles
                WHERE guild_id = ? ORDER BY level ASC
                """,
                (guild.id,),
            )
            rows = cursor.fetchall()

        if not rows:
            return

        earned_roles = []
        role_levels = {}

        for role_level, role_id in rows:
            role_levels[role_id] = role_level
            if level >= role_level:
                role = guild.get_role(role_id)
                if role is not None:
                    earned_roles.append(role)

        if not earned_roles:
            return

        highest_role = max(earned_roles, key=lambda role: role_levels.get(role.id, 0))
        roles_to_remove = [
            role for role in earned_roles
            if role.id != highest_role.id and role in member.roles
        ]

        try:
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove, reason="Level role progression")
            if highest_role not in member.roles:
                await member.add_roles(highest_role, reason="Level role progression")
        except discord.HTTPException as error:
            print(f"[LEVELING] Could not update roles for {member}: {error}")

    @commands.command(name="rank")
    @commands.guild_only()
    async def rank(self, ctx: commands.Context):
        data = self.get_user_data(ctx.author.id)

        if data is None:
            data = {
                "xp": 0,
                "level": 1,
                "total_xp": 0,
                "required": BASE_XP_REQUIRED,
            }

        current_xp = data["xp"]
        level = data["level"]
        total_xp = data["total_xp"]
        required_xp = data["required"]

        percent = (current_xp / required_xp) * 100 if required_xp else 0
        bar_length = 15
        filled = min(
            bar_length,
            int((current_xp / required_xp) * bar_length) if required_xp else 0,
        )
        progress_bar = "█" * filled + "░" * (bar_length - filled)

        embed = discord.Embed(
            title=f"⚡ {ctx.author.display_name}'s Rank",
            color=discord.Color.blurple(),
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.add_field(name="Level", value=f"**{level}**", inline=True)
        embed.add_field(name="Total XP", value=f"**{total_xp:,}**", inline=True)
        embed.add_field(
            name="Progress",
            value=(
                f"`{progress_bar}`\n"
                f"**{current_xp:,} / {required_xp:,} XP** ({percent:.1f}%)"
            ),
            inline=False,
        )
        await ctx.send(embed=embed)

    @commands.command(name="setlevelrole")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def set_level_role(self, ctx: commands.Context, level: int, role: discord.Role):
        if level < 1:
            return await ctx.send("❌ Level must be 1 or higher.")

        if role == ctx.guild.default_role:
            return await ctx.send("❌ You can't use the @everyone role.")

        if ctx.guild.me and role >= ctx.guild.me.top_role:
            return await ctx.send(
                "❌ I can't manage that role because it is higher than or equal to my highest role."
            )

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS level_roles (
                    guild_id INTEGER NOT NULL,
                    level INTEGER NOT NULL,
                    role_id INTEGER NOT NULL,
                    PRIMARY KEY (guild_id, level)
                )
                """
            )
            conn.execute(
                """
                INSERT INTO level_roles (guild_id, level, role_id)
                VALUES (?, ?, ?)
                ON CONFLICT(guild_id, level)
                DO UPDATE SET role_id = excluded.role_id
                """,
                (ctx.guild.id, level, role.id),
            )
            conn.commit()

        await ctx.send(f"✅ **Level {level}** will now give {role.mention}.")

    @set_level_role.error
    async def set_level_role_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            return await ctx.send("❌ You need Administrator permission to use this command.")
        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send("❌ Usage: `!setlevelrole <level> @role`")
        if isinstance(error, commands.BadArgument):
            return await ctx.send("❌ Make sure the level is a number and you mention a valid Discord role.")
        raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(Leveling(bot))
