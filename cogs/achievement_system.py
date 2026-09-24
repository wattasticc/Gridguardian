import sqlite3
from datetime import datetime, timezone
from typing import Optional

import discord
from discord.ext import commands


DB_PATH = "gridguardian.db"
EMBED_COLOR = discord.Color.blurple()


ACHIEVEMENTS = {
    "first_steps": {
        "name": "First Steps",
        "description": "Use the Wattson Mastery system for the first time.",
        "emoji": "⚡",
        "reward": 25,
    },
    "grid_recruit": {
        "name": "Grid Recruit",
        "description": "Reach Wattson Mastery Level 5.",
        "emoji": "🔌",
        "reward": 50,
    },
    "fence_specialist": {
        "name": "Fence Specialist",
        "description": "Reach Wattson Mastery Level 10.",
        "emoji": "⚡",
        "reward": 100,
    },
    "grid_commander": {
        "name": "Grid Commander",
        "description": "Reach Wattson Mastery Level 20.",
        "emoji": "🛡️",
        "reward": 200,
    },
    "electrical_expert": {
        "name": "Electrical Expert",
        "description": "Reach Wattson Mastery Level 30.",
        "emoji": "💡",
        "reward": 300,
    },
    "power_grid_master": {
        "name": "Power Grid Master",
        "description": "Reach Wattson Mastery Level 50.",
        "emoji": "⚡",
        "reward": 500,
    },
    "grid_legend": {
        "name": "Grid Legend",
        "description": "Reach Wattson Mastery Level 75.",
        "emoji": "🏆",
        "reward": 750,
    },
    "master_of_the_grid": {
        "name": "Master of the Grid",
        "description": "Reach Wattson Mastery Level 100.",
        "emoji": "👑",
        "reward": 1000,
    },
    "first_setup": {
        "name": "Grid Architect",
        "description": "Submit your first Wattson setup.",
        "emoji": "🧠",
        "reward": 50,
    },
    "five_setups": {
        "name": "Master Builder",
        "description": "Submit 5 Wattson setups.",
        "emoji": "🏗️",
        "reward": 150,
    },
    "ten_setups": {
        "name": "Fortress Engineer",
        "description": "Submit 10 Wattson setups.",
        "emoji": "🏰",
        "reward": 300,
    },
    "first_upvote": {
        "name": "Community Favorite",
        "description": "Receive your first setup upvote.",
        "emoji": "⭐",
        "reward": 50,
    },
    "ten_upvotes": {
        "name": "Popular Engineer",
        "description": "Receive 10 setup upvotes.",
        "emoji": "🌟",
        "reward": 150,
    },
    "fifty_upvotes": {
        "name": "Grid Influencer",
        "description": "Receive 50 setup upvotes.",
        "emoji": "💫",
        "reward": 400,
    },
    "hundred_upvotes": {
        "name": "Power Grid Icon",
        "description": "Receive 100 setup upvotes.",
        "emoji": "👑",
        "reward": 750,
    },
    "mastery_25": {
        "name": "Wattson Mastery Level 25",
        "description": "Reach Wattson Mastery Level 25.",
        "emoji": "⚡",
        "reward": 250,
    },
    "level_5": {
        "name": "Level 5",
        "description": "Reach Grid Guardian Level 5.",
        "emoji": "📈",
        "reward": 25,
    },
    "level_10": {
        "name": "Level 10",
        "description": "Reach Grid Guardian Level 10.",
        "emoji": "📈",
        "reward": 50,
    },
    "level_25": {
        "name": "Level 25",
        "description": "Reach Grid Guardian Level 25.",
        "emoji": "📈",
        "reward": 100,
    },
    "level_50": {
        "name": "Level 50",
        "description": "Reach Grid Guardian Level 50.",
        "emoji": "📈",
        "reward": 250,
    },
    "level_100": {
        "name": "Level 100",
        "description": "Reach Grid Guardian Level 100.",
        "emoji": "📈",
        "reward": 500,
    },
}


# Older versions stored achievement names directly instead of the canonical IDs.
# Normalize those values when reading so existing unlocks are not lost.
LEGACY_ACHIEVEMENT_IDS = {
    "⚡ Wattson Mastery Level 5": "grid_recruit",
    "⚡ Wattson Mastery Level 10": "fence_specialist",
    "⚡ Wattson Mastery Level 25": "mastery_25",
    "⚡ Wattson Mastery Level 50": "power_grid_master",
    "👑 Wattson Mastery Level 100": "master_of_the_grid",
    "Level 5": "level_5",
    "Level 10": "level_10",
    "Level 25": "level_25",
    "Level 50": "level_50",
    "Level 100": "level_100",
}


class AchievementSystem(commands.Cog):
    """Advanced achievement tracking for Grid Guardian."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.initialize_database()

    # ============================================================
    # DATABASE
    # ============================================================

    def db_connect(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize_database(self):
        conn = self.db_connect()
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS achievement_rewards (
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                total_xp INTEGER DEFAULT 0,
                PRIMARY KEY(user_id, guild_id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS achievement_notifications (
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                achievement_id TEXT NOT NULL,
                PRIMARY KEY(user_id, guild_id, achievement_id)
            )
            """
        )

        conn.commit()
        conn.close()

    # ============================================================
    # ACHIEVEMENT HELPERS
    # ============================================================

    def get_unlocked(
        self,
        user_id: int
    ):
        conn = self.db_connect()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT achievement
                FROM achievements
                WHERE user_id = ?
                """,
                (user_id,)
            )

            rows = cursor.fetchall()

        except sqlite3.OperationalError:
            rows = []

        conn.close()

        return {
            LEGACY_ACHIEVEMENT_IDS.get(
                row["achievement"],
                row["achievement"],
            )
            for row in rows
        }

    def unlock(
        self,
        user_id: int,
        guild_id: int,
        achievement_id: str
    ):
        achievement_id = LEGACY_ACHIEVEMENT_IDS.get(
            achievement_id,
            achievement_id,
        )

        if achievement_id not in ACHIEVEMENTS:
            return False

        conn = self.db_connect()
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS achievements (
                user_id INTEGER NOT NULL,
                achievement TEXT NOT NULL,
                PRIMARY KEY(user_id, achievement)
            )
            """
        )

        cursor.execute(
            """
            SELECT 1
            FROM achievements
            WHERE user_id = ?
              AND achievement = ?
            """,
            (
                user_id,
                achievement_id
            )
        )

        if cursor.fetchone():
            conn.close()
            return False

        cursor.execute(
            """
            INSERT INTO achievements (
                user_id,
                achievement
            )
            VALUES (?, ?)
            """,
            (
                user_id,
                achievement_id
            )
        )

        reward = ACHIEVEMENTS[achievement_id]["reward"]

        cursor.execute(
            """
            INSERT INTO achievement_rewards (
                user_id,
                guild_id,
                total_xp
            )
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, guild_id)
            DO UPDATE SET total_xp =
                total_xp + excluded.total_xp
            """,
            (
                user_id,
                guild_id,
                reward
            )
        )

        conn.commit()
        conn.close()

        return True

    # ============================================================
    # AUTO CHECK
    # ============================================================

    def check_mastery(
        self,
        user_id: int,
        guild_id: int
    ):
        conn = self.db_connect()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT level
                FROM wattson_mastery
                WHERE user_id = ?
                  AND guild_id = ?
                """,
                (
                    user_id,
                    guild_id
                )
            )

            row = cursor.fetchone()

        except sqlite3.OperationalError:
            conn.close()
            return []

        conn.close()

        if not row:
            return []

        level = row["level"]

        unlocked = []

        level_requirements = {
            1: "first_steps",
            5: "grid_recruit",
            10: "fence_specialist",
            20: "grid_commander",
            30: "electrical_expert",
            50: "power_grid_master",
            75: "grid_legend",
            100: "master_of_the_grid",
        }

        for required_level, achievement_id in level_requirements.items():
            if level >= required_level:
                if self.unlock(
                    user_id,
                    guild_id,
                    achievement_id
                ):
                    unlocked.append(achievement_id)

        return unlocked

    def check_setups(
        self,
        user_id: int,
        guild_id: int
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
                WHERE user_id = ?
                  AND guild_id = ?
                """,
                (
                    user_id,
                    guild_id
                )
            )

            row = cursor.fetchone()

        except sqlite3.OperationalError:
            conn.close()
            return []

        conn.close()

        if not row:
            return []

        setup_count = row["setup_count"]
        upvotes = row["upvotes"]

        unlocked = []

        setup_requirements = {
            1: "first_setup",
            5: "five_setups",
            10: "ten_setups",
        }

        upvote_requirements = {
            1: "first_upvote",
            10: "ten_upvotes",
            50: "fifty_upvotes",
            100: "hundred_upvotes",
        }

        for amount, achievement_id in setup_requirements.items():
            if setup_count >= amount:
                if self.unlock(
                    user_id,
                    guild_id,
                    achievement_id
                ):
                    unlocked.append(achievement_id)

        for amount, achievement_id in upvote_requirements.items():
            if upvotes >= amount:
                if self.unlock(
                    user_id,
                    guild_id,
                    achievement_id
                ):
                    unlocked.append(achievement_id)

        return unlocked

    # ============================================================
    # NOTIFICATION
    # ============================================================

    async def send_unlock_notifications(
        self,
        ctx: commands.Context,
        achievement_ids
    ):
        for achievement_id in achievement_ids:
            achievement = ACHIEVEMENTS.get(
                achievement_id
            )

            if not achievement:
                continue

            embed = discord.Embed(
                title="🏆 Achievement Unlocked!",
                description=(
                    f"{achievement['emoji']} "
                    f"**{achievement['name']}**\n\n"
                    f"{achievement['description']}\n\n"
                    f"🎁 Reward: **"
                    f"{achievement['reward']} XP**"
                ),
                color=discord.Color.gold()
            )

            embed.set_footer(
                text="Grid Guardian • Achievement System"
            )

            await ctx.send(
                embed=embed
            )

    # ============================================================
    # COMMAND: ACHIEVEMENTS
    # ============================================================

    @commands.command(
        name="achievements",
        aliases=[
            "ach",
            "achievement"
        ]
    )
    @commands.guild_only()
    async def achievements(
        self,
        ctx: commands.Context,
        member: Optional[discord.Member] = None
    ):
        """Show a member's achievements."""

        member = member or ctx.author

        unlocked = self.get_unlocked(
            member.id
        )

        embed = discord.Embed(
            title=f"🏆 {member.display_name}'s Achievements",
            description=(
                f"**{len(unlocked)} / "
                f"{len(ACHIEVEMENTS)} unlocked**"
            ),
            color=EMBED_COLOR
        )

        embed.set_thumbnail(
            url=member.display_avatar.url
        )

        for achievement_id, achievement in ACHIEVEMENTS.items():
            if achievement_id in unlocked:
                status = "✅"
            else:
                status = "🔒"

            embed.add_field(
                name=(
                    f"{status} "
                    f"{achievement['emoji']} "
                    f"{achievement['name']}"
                ),
                value=(
                    f"{achievement['description']}\n"
                    f"Reward: "
                    f"**{achievement['reward']} XP**"
                ),
                inline=False
            )

        embed.set_footer(
            text="Grid Guardian • Achievements"
        )

        await ctx.send(
            embed=embed
        )

    # ============================================================
    # COMMAND: CHECK
    # ============================================================

    @commands.command(
        name="checkachievements",
        aliases=["checkach"]
    )
    @commands.guild_only()
    async def check_achievements(
        self,
        ctx: commands.Context
    ):
        """Check and unlock achievements."""

        unlocked = []

        unlocked.extend(
            self.check_mastery(
                ctx.author.id,
                ctx.guild.id
            )
        )

        unlocked.extend(
            self.check_setups(
                ctx.author.id,
                ctx.guild.id
            )
        )

        if not unlocked:
            await ctx.send(
                "🔍 No new achievements unlocked."
            )
            return

        await self.send_unlock_notifications(
            ctx,
            unlocked
        )

    # ============================================================
    # COMMAND: ACHIEVEMENT LIST
    # ============================================================

    @commands.command(
        name="achievementlist"
    )
    @commands.guild_only()
    async def achievement_list(
        self,
        ctx: commands.Context
    ):
        """Show every available achievement."""

        embed = discord.Embed(
            title="🏆 Grid Guardian Achievements",
            description=(
                f"There are **{len(ACHIEVEMENTS)}** "
                "achievements to unlock."
            ),
            color=EMBED_COLOR
        )

        for achievement_id, achievement in ACHIEVEMENTS.items():
            embed.add_field(
                name=(
                    f"{achievement['emoji']} "
                    f"{achievement['name']}"
                ),
                value=(
                    f"{achievement['description']}\n"
                    f"🎁 {achievement['reward']} XP"
                ),
                inline=False
            )

        await ctx.send(
            embed=embed
        )

    # ============================================================
    # COMMAND: ACHIEVEMENT INFO
    # ============================================================

    @commands.command(
        name="achievementinfo"
    )
    @commands.guild_only()
    async def achievement_info(
        self,
        ctx: commands.Context,
        achievement_id: str
    ):
        """Show information about one achievement."""

        achievement = ACHIEVEMENTS.get(
            achievement_id.lower()
        )

        if not achievement:
            await ctx.send(
                "❌ That achievement doesn't exist."
            )
            return

        unlocked = self.get_unlocked(
            ctx.author.id
        )

        is_unlocked = (
            achievement_id.lower()
            in unlocked
        )

        status = (
            "✅ Unlocked"
            if is_unlocked
            else "🔒 Locked"
        )

        embed = discord.Embed(
            title=(
                f"{achievement['emoji']} "
                f"{achievement['name']}"
            ),
            description=achievement["description"],
            color=(
                discord.Color.green()
                if is_unlocked
                else discord.Color.dark_grey()
            )
        )

        embed.add_field(
            name="Status",
            value=status,
            inline=True
        )

        embed.add_field(
            name="Reward",
            value=f"⭐ {achievement['reward']} XP",
            inline=True
        )

        await ctx.send(
            embed=embed
        )

    # ============================================================
    # HELP
    # ============================================================

    @commands.command(
        name="achievementhelp"
    )
    @commands.guild_only()
    async def achievement_help(
        self,
        ctx: commands.Context
    ):
        embed = discord.Embed(
            title="🏆 Achievement Commands",
            description=(
                "`!achievements` — View your achievements\n"
                "`!achievements @user` — View another member\n"
                "`!checkachievements` — Check for newly unlocked achievements\n"
                "`!achievementlist` — View all achievements\n"
                "`!achievementinfo <id>` — View an achievement\n"
                "`!achievementhelp` — Show this help"
            ),
            color=EMBED_COLOR
        )

        await ctx.send(
            embed=embed
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(AchievementSystem(bot))