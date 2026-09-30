import random
import sqlite3
import time

import discord
from discord.ext import commands

DB_PATH = "gridguardian.db"
XP_COOLDOWN = 60
XP_MIN = 5
XP_MAX = 15

# Progressive leveling:
# 1 -> 2 = 100 XP
# 2 -> 3 = 125 XP
# 3 -> 4 = 150 XP
# Each level requires 25 more XP than the previous level.
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


def total_xp_required_for_level(level: int) -> int:
    """Total XP required to reach the beginning of a level."""
    level = max(1, int(level))
    n = level - 1
    return (BASE_XP_REQUIRED * n) + (XP_INCREASE_PER_LEVEL * n * (n - 1) // 2)


def level_from_total_xp(total_xp: int) -> int:
    """Calculate the user's level using total_xp as the single source of truth."""
    total_xp = max(0, int(total_xp))
    level = 1
    spent = 0

    while True:
        needed = xp_required_for_level(level)
        if spent + needed > total_xp:
            return level
        spent += needed
        level += 1


def progress_from_total_xp(total_xp: int) -> tuple[int, int]:
    level = level_from_total_xp(total_xp)
    current_xp = max(0, int(total_xp) - total_xp_required_for_level(level))
    return current_xp, xp_required_for_level(level)


def total_xp_from_level_and_progress(level: int, xp: int) -> int:
    """Convert an old level/xp pair into the new cumulative total XP format."""
    level = max(1, int(level))
    required = xp_required_for_level(level)
    xp = max(0, min(int(xp), required - 1))
    return total_xp_required_for_level(level) + xp


class Leveling(commands.Cog):
    """XP, progressive levels, ranks, achievements, and level roles."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.xp_cooldowns: dict[int, float] = {}
        self.init_database()

    def init_database(self):
        """Create the table and safely migrate old rows.

        total_xp is the only source of truth after migration. The level/xp columns
        are maintained as cached display values for compatibility with other cogs.
        """
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
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
                cursor.execute("ALTER TABLE levels ADD COLUMN total_xp INTEGER DEFAULT 0")

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS level_up_announcements (
                    user_id INTEGER NOT NULL,
                    level INTEGER NOT NULL,
                    announced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, level)
                )
                """
            )

            cursor.execute("SELECT user_id, xp, level, total_xp FROM levels")
            rows = cursor.fetchall()

            for user_id, xp, level, total_xp in rows:
                xp = max(0, int(xp or 0))
                level = max(1, int(level or 1))
                total_xp = max(0, int(total_xp or 0))

                # Existing total_xp is authoritative. Only reconstruct it when
                # migrating an old row that never had a total_xp value.
                if total_xp == 0 and (level > 1 or xp > 0):
                    total_xp = total_xp_from_level_and_progress(level, xp)

                actual_level = level_from_total_xp(total_xp)
                current_xp, _ = progress_from_total_xp(total_xp)

                cursor.execute(
                    """
                    UPDATE levels
                    SET xp = ?, level = ?, total_xp = ?
                    WHERE user_id = ?
                    """,
                    (current_xp, actual_level, total_xp, user_id),
                )

            conn.commit()

    def get_user_data(self, user_id: int):
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT xp, level, total_xp FROM levels WHERE user_id = ?",
                (user_id,),
            )
            row = cursor.fetchone()

            if row is None:
                return None

            _, _, total_xp = row
            total_xp = max(0, int(total_xp or 0))
            level = level_from_total_xp(total_xp)
            current_xp, required_xp = progress_from_total_xp(total_xp)

            # Keep compatibility/cache columns synchronized with the source of truth.
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
        old_level = 1
        new_level = 1
        total_xp = 0

        try:
            with sqlite3.connect(DB_PATH, timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute("BEGIN IMMEDIATE")
                cursor.execute(
                    "SELECT total_xp, xp, level FROM levels WHERE user_id = ?",
                    (user_id,),
                )
                row = cursor.fetchone()

                if row is None:
                    old_total_xp = 0
                else:
                    stored_total = max(0, int(row[0] or 0))
                    old_total_xp = stored_total

                    # Only old databases with no total_xp need reconstruction.
                    if stored_total == 0 and (int(row[1] or 0) > 0 or int(row[2] or 1) > 1):
                        old_total_xp = total_xp_from_level_and_progress(
                            int(row[2] or 1), int(row[1] or 0)
                        )

                old_level = level_from_total_xp(old_total_xp)
                total_xp = old_total_xp + xp_gain
                new_level = level_from_total_xp(total_xp)
                current_xp, _ = progress_from_total_xp(total_xp)

                cursor.execute(
                    """
                    INSERT INTO levels (user_id, xp, level, total_xp)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        xp = excluded.xp,
                        level = excluded.level,
                        total_xp = excluded.total_xp
                    """,
                    (user_id, current_xp, new_level, total_xp),
                )
                conn.commit()

        except sqlite3.Error as error:
            print(f"[LEVELING] Database error for {user_id}: {error}")
            return

        self.xp_cooldowns[user_id] = now

        if new_level > old_level:
            # Claim each newly reached level atomically. This prevents duplicate
            # announcements if multiple events/processes observe the same level.
            for reached_level in range(old_level + 1, new_level + 1):
                if await self.claim_level_announcement(message.author.id, reached_level):
                    await self.handle_level_up(
                        message, old_level, reached_level, total_xp
                    )

    def claim_level_announcement(self, user_id: int, level: int) -> bool:
        """Atomically claim a level-up announcement.

        Returns True only for the first process that claims this user's level.
        """
        try:
            with sqlite3.connect(DB_PATH, timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO level_up_announcements
                    (user_id, level)
                    VALUES (?, ?)
                    """,
                    (user_id, level),
                )
                conn.commit()
                return cursor.rowcount == 1
        except sqlite3.Error as error:
            print(f"[LEVELING] Announcement tracking error: {error}")
            # If tracking fails, do not send an announcement that could duplicate.
            return False

    async def handle_level_up(self, message, old_level, new_level, total_xp):
        milestones = [
            achievement
            for level, achievement in LEVEL_ACHIEVEMENTS.items()
            if old_level < level <= new_level
        ]

        if milestones:
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
                    for achievement in milestones:
                        conn.execute(
                            "INSERT OR IGNORE INTO achievements (user_id, achievement) VALUES (?, ?)",
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
                "SELECT level, role_id FROM level_roles WHERE guild_id = ? ORDER BY level ASC",
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
            data = {"xp": 0, "level": 1, "total_xp": 0, "required": BASE_XP_REQUIRED}

        current_xp = data["xp"]
        level = data["level"]
        total_xp = data["total_xp"]
        required_xp = data["required"]
        percent = (current_xp / required_xp) * 100 if required_xp else 0
        bar_length = 15
        filled = min(bar_length, int((current_xp / required_xp) * bar_length) if required_xp else 0)
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
            value=f"`{progress_bar}`\n**{current_xp:,} / {required_xp:,} XP** ({percent:.1f}%)",
            inline=False,
        )
        await ctx.send(embed=embed)

    @commands.command(name="setlevel")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def set_level(self, ctx: commands.Context, member: discord.Member, level: int):
        if level < 1:
            return await ctx.send("❌ Level must be 1 or higher.")

        target_total = total_xp_required_for_level(level)
        current = self.get_user_data(member.id)
        if current is not None and current["level"] > level:
            return await ctx.send(
                f"❌ {member.mention} is already Level **{current['level']}**. This command cannot lower levels."
            )

        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            current_xp, _ = progress_from_total_xp(target_total)
            conn.execute(
                """
                INSERT INTO levels (user_id, xp, level, total_xp)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    xp = excluded.xp,
                    level = excluded.level,
                    total_xp = excluded.total_xp
                """,
                (member.id, current_xp, level, target_total),
            )
            conn.commit()

        await self.sync_level_roles(member, ctx.guild, level)
        await ctx.send(
            f"✅ {member.mention} is now **Level {level}** with **{target_total:,} total XP**."
        )

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
                ON CONFLICT(guild_id, level) DO UPDATE SET role_id = excluded.role_id
                """,
                (ctx.guild.id, level, role.id),
            )
            conn.commit()

        await ctx.send(f"✅ Level **{level}** will now use {role.mention}.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Leveling(bot))
