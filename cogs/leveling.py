import random
import sqlite3
import time

import discord
from discord.ext import commands

DB_PATH = "gridguardian.db"

# XP settings
XP_COOLDOWN = 60
XP_MIN = 5
XP_MAX = 15

# Progressive leveling:
# Level 1 -> 2 = 100 XP
# Level 2 -> 3 = 125 XP
# Level 3 -> 4 = 150 XP
# Every level requires 25 more XP than the previous level.
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
    """XP needed to move from this level to the next level."""
    level = max(1, int(level))
    return BASE_XP_REQUIRED + ((level - 1) * XP_INCREASE_PER_LEVEL)


def total_xp_required_for_level(level: int) -> int:
    """Cumulative XP required to reach the beginning of a level."""
    level = max(1, int(level))
    completed_levels = level - 1
    return (
        BASE_XP_REQUIRED * completed_levels
        + XP_INCREASE_PER_LEVEL * completed_levels * (completed_levels - 1) // 2
    )


def level_from_total_xp(total_xp: int) -> int:
    """Calculate a level from permanent cumulative XP."""
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
    """Return current-level XP and XP needed for the next level."""
    total_xp = max(0, int(total_xp))
    level = level_from_total_xp(total_xp)
    current_xp = total_xp - total_xp_required_for_level(level)
    return current_xp, xp_required_for_level(level)


def total_xp_from_level_and_progress(level: int, xp: int) -> int:
    """Build a valid cumulative XP value from an existing level/progress pair."""
    level = max(1, int(level))
    xp = max(0, int(xp))
    required = xp_required_for_level(level)
    xp = min(xp, max(0, required - 1))
    return total_xp_required_for_level(level) + xp


class Leveling(commands.Cog):
    """XP, progressive levels, ranks, achievements, and level roles."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.xp_cooldowns: dict[int, float] = {}
        self.init_database()

    def init_database(self):
        """Create/migrate the leveling tables without ever lowering an existing level."""
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS levels (
                    user_id INTEGER PRIMARY KEY,
                    xp INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1,
                    total_xp INTEGER DEFAULT 0,
                    highest_level INTEGER DEFAULT 1,
                    highest_total_xp INTEGER DEFAULT 0
                )
                """
            )

            cursor.execute("PRAGMA table_info(levels)")
            columns = {row[1] for row in cursor.fetchall()}

            if "total_xp" not in columns:
                cursor.execute("ALTER TABLE levels ADD COLUMN total_xp INTEGER DEFAULT 0")
            if "highest_level" not in columns:
                cursor.execute("ALTER TABLE levels ADD COLUMN highest_level INTEGER DEFAULT 1")
            if "highest_total_xp" not in columns:
                cursor.execute("ALTER TABLE levels ADD COLUMN highest_total_xp INTEGER DEFAULT 0")

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS level_history (
                    user_id INTEGER PRIMARY KEY,
                    highest_level INTEGER NOT NULL DEFAULT 1,
                    highest_total_xp INTEGER NOT NULL DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            cursor.execute(
                """
                SELECT user_id, xp, level, total_xp, highest_level, highest_total_xp
                FROM levels
                """
            )

            rows = cursor.fetchall()
            for user_id, xp, stored_level, stored_total, highest_level, highest_total in rows:
                stored_level = max(1, int(stored_level or 1))
                xp = max(0, int(xp or 0))
                stored_total = max(0, int(stored_total or 0))
                highest_level = max(1, int(highest_level or 1))
                highest_total = max(0, int(highest_total or 0))

                # If total_xp was never initialized, convert the existing level/xp pair.
                if stored_total <= 0 and (stored_level > 1 or xp > 0):
                    stored_total = total_xp_from_level_and_progress(stored_level, xp)

                # The stored level is authoritative during migration. This prevents
                # an old/inconsistent total_xp value from dropping someone a level.
                calculated_level = level_from_total_xp(stored_total)
                final_level = max(stored_level, highest_level, calculated_level)

                # If an old row says Level 15 but total_xp only calculates to Level 14,
                # rebuild total_xp from the Level 15 + current XP instead of downgrading.
                if final_level > calculated_level:
                    progress_xp = xp
                    required = xp_required_for_level(final_level)
                    progress_xp = min(progress_xp, required - 1)
                    stored_total = total_xp_required_for_level(final_level) + progress_xp

                final_level = max(final_level, level_from_total_xp(stored_total))
                current_xp, _ = progress_from_total_xp(stored_total)
                highest_level = max(highest_level, final_level)
                highest_total = max(highest_total, stored_total)

                cursor.execute(
                    """
                    UPDATE levels
                    SET xp = ?, level = ?, total_xp = ?,
                        highest_level = ?, highest_total_xp = ?
                    WHERE user_id = ?
                    """,
                    (
                        current_xp,
                        final_level,
                        stored_total,
                        highest_level,
                        highest_total,
                        user_id,
                    ),
                )

                cursor.execute(
                    """
                    INSERT INTO level_history (user_id, highest_level, highest_total_xp)
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        highest_level = MAX(level_history.highest_level, excluded.highest_level),
                        highest_total_xp = MAX(level_history.highest_total_xp, excluded.highest_total_xp),
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (user_id, highest_level, highest_total),
                )

            conn.commit()

    def get_user_data(self, user_id: int):
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT xp, level, total_xp, highest_level, highest_total_xp
                FROM levels
                WHERE user_id = ?
                """,
                (user_id,),
            )
            row = cursor.fetchone()

            if row is None:
                return None

            xp, stored_level, stored_total, highest_level, highest_total = row
            stored_level = max(1, int(stored_level or 1))
            stored_total = max(0, int(stored_total or 0))
            highest_level = max(1, int(highest_level or 1))
            highest_total = max(0, int(highest_total or 0))

            # Never calculate a lower level from an inconsistent old total.
            level = max(stored_level, highest_level, level_from_total_xp(stored_total))

            if level > level_from_total_xp(stored_total):
                stored_total = max(
                    stored_total,
                    total_xp_from_level_and_progress(level, int(xp or 0)),
                    total_xp_required_for_level(level),
                )

            current_xp, required_xp = progress_from_total_xp(stored_total)
            highest_total = max(highest_total, stored_total)
            highest_level = max(highest_level, level)

            cursor.execute(
                """
                UPDATE levels
                SET xp = ?, level = ?, total_xp = ?,
                    highest_level = ?, highest_total_xp = ?
                WHERE user_id = ?
                """,
                (
                    current_xp,
                    level,
                    stored_total,
                    highest_level,
                    highest_total,
                    user_id,
                ),
            )
            cursor.execute(
                """
                INSERT INTO level_history (user_id, highest_level, highest_total_xp)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    highest_level = MAX(level_history.highest_level, excluded.highest_level),
                    highest_total_xp = MAX(level_history.highest_total_xp, excluded.highest_total_xp),
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user_id, highest_level, highest_total),
            )
            conn.commit()

            return {
                "xp": current_xp,
                "level": level,
                "total_xp": stored_total,
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
                    """
                    SELECT xp, level, total_xp, highest_level, highest_total_xp
                    FROM levels
                    WHERE user_id = ?
                    """,
                    (user_id,),
                )
                row = cursor.fetchone()

                if row is None:
                    old_level = 1
                    old_total_xp = 0
                    total_xp = xp_gain
                    new_level = level_from_total_xp(total_xp)
                    current_xp, _ = progress_from_total_xp(total_xp)
                    highest_level = new_level
                    highest_total_xp = total_xp

                    cursor.execute(
                        """
                        INSERT INTO levels
                            (user_id, xp, level, total_xp, highest_level, highest_total_xp)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            user_id,
                            current_xp,
                            new_level,
                            total_xp,
                            highest_level,
                            highest_total_xp,
                        ),
                    )
                else:
                    old_xp, stored_level, stored_total, highest_level, highest_total = row
                    stored_level = max(1, int(stored_level or 1))
                    stored_total = max(0, int(stored_total or 0))
                    highest_level = max(1, int(highest_level or 1))
                    highest_total = max(0, int(highest_total or 0))

                    calculated_level = level_from_total_xp(stored_total)
                    old_level = max(stored_level, highest_level, calculated_level)

                    # Repair an inconsistent row before adding new XP.
                    if old_level > calculated_level:
                        stored_total = max(
                            stored_total,
                            total_xp_from_level_and_progress(old_level, int(old_xp or 0)),
                            total_xp_required_for_level(old_level),
                        )

                    old_level = max(old_level, level_from_total_xp(stored_total))
                    old_total_xp = stored_total
                    total_xp = old_total_xp + xp_gain
                    new_level = max(old_level, level_from_total_xp(total_xp))
                    current_xp, _ = progress_from_total_xp(total_xp)

                    highest_level = max(highest_level, new_level)
                    highest_total_xp = max(highest_total, total_xp)

                    cursor.execute(
                        """
                        UPDATE levels
                        SET xp = ?, level = ?, total_xp = ?,
                            highest_level = ?, highest_total_xp = ?
                        WHERE user_id = ?
                        """,
                        (
                            current_xp,
                            new_level,
                            total_xp,
                            highest_level,
                            highest_total_xp,
                            user_id,
                        ),
                    )

                cursor.execute(
                    """
                    INSERT INTO level_history (user_id, highest_level, highest_total_xp)
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        highest_level = MAX(level_history.highest_level, excluded.highest_level),
                        highest_total_xp = MAX(level_history.highest_total_xp, excluded.highest_total_xp),
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (user_id, highest_level, highest_total_xp),
                )
                conn.commit()

        except sqlite3.Error as error:
            print(f"[LEVELING] Database error for {user_id}: {error}")
            return

        self.xp_cooldowns[user_id] = now

        if new_level > old_level:
            await self.handle_level_up(message, old_level, new_level, total_xp)

    async def handle_level_up(self, message, old_level, new_level, total_xp):
        milestones = [
            (level, achievement)
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
                    for _, achievement in milestones:
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

    @commands.command(name="setlevel")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def set_level(self, ctx: commands.Context, member: discord.Member, level: int):
        """Administrator repair tool. It can raise a level but never lowers one."""
        if level < 1:
            return await ctx.send("❌ Level must be 1 or higher.")

        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute(
                """
                SELECT xp, level, total_xp, highest_level, highest_total_xp
                FROM levels WHERE user_id = ?
                """,
                (member.id,),
            )
            row = cursor.fetchone()

            if row:
                old_xp, current_level, current_total, highest_level, highest_total = row
                current_level = max(1, int(current_level or 1))
                current_total = max(0, int(current_total or 0))
                highest_level = max(1, int(highest_level or 1))
                highest_total = max(0, int(highest_total or 0))
            else:
                old_xp = 0
                current_level = 1
                current_total = 0
                highest_level = 1
                highest_total = 0

            target_level = max(int(level), current_level, highest_level)
            target_total = max(
                current_total,
                highest_total,
                total_xp_required_for_level(target_level),
            )
            current_xp, _ = progress_from_total_xp(target_total)

            cursor.execute(
                """
                INSERT INTO levels
                    (user_id, xp, level, total_xp, highest_level, highest_total_xp)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    xp = excluded.xp,
                    level = excluded.level,
                    total_xp = excluded.total_xp,
                    highest_level = excluded.highest_level,
                    highest_total_xp = excluded.highest_total_xp
                """,
                (
                    member.id,
                    current_xp,
                    target_level,
                    target_total,
                    target_level,
                    target_total,
                ),
            )
            cursor.execute(
                """
                INSERT INTO level_history (user_id, highest_level, highest_total_xp)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    highest_level = MAX(level_history.highest_level, excluded.highest_level),
                    highest_total_xp = MAX(level_history.highest_total_xp, excluded.highest_total_xp),
                    updated_at = CURRENT_TIMESTAMP
                """,
                (member.id, target_level, target_total),
            )
            conn.commit()

        await self.sync_level_roles(member, ctx.guild, target_level)
        await ctx.send(
            f"✅ {member.mention} is now protected at **Level {target_level}** with **{target_total:,} total XP**."
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
                ON CONFLICT(guild_id, level)
                DO UPDATE SET role_id = excluded.role_id
                """,
                (ctx.guild.id, level, role.id),
            )
            conn.commit()

        await ctx.send(f"✅ Level **{level}** will now use {role.mention}.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Leveling(bot))
