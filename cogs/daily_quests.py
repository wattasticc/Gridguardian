import sqlite3
import random
from datetime import datetime, timezone, timedelta
from typing import Optional

import discord
from discord.ext import commands


DB_PATH = "gridguardian.db"

# How much XP each quest awards.
QUEST_XP = {
    "practice": 50,
    "coach": 75,
    "setup": 100,
    "upvote": 50,
    "challenge": 75,
}

DAILY_COMPLETION_BONUS = 150

# Quest definitions.
QUEST_POOL = [
    {
        "type": "practice",
        "name": "Grid Practice",
        "description": "Complete 1 Wattson practice session.",
        "target": 1,
        "xp": QUEST_XP["practice"],
    },
    {
        "type": "coach",
        "name": "Coach's Apprentice",
        "description": "Complete 1 Apex Coach drill.",
        "target": 1,
        "xp": QUEST_XP["coach"],
    },
    {
        "type": "setup",
        "name": "Grid Architect",
        "description": "Submit 1 Wattson setup.",
        "target": 1,
        "xp": QUEST_XP["setup"],
    },
    {
        "type": "upvote",
        "name": "Share the Knowledge",
        "description": "Receive 1 upvote on one of your Wattson setups.",
        "target": 1,
        "xp": QUEST_XP["upvote"],
    },
    {
        "type": "challenge",
        "name": "Challenge Accepted",
        "description": "Complete 1 daily or weekly challenge.",
        "target": 1,
        "xp": QUEST_XP["challenge"],
    },
]


class DailyQuestView(discord.ui.View):
    """Buttons for the daily quest panel."""

    def __init__(self, cog):
        super().__init__(timeout=300)
        self.cog = cog

    @discord.ui.button(
        label="Refresh",
        style=discord.ButtonStyle.primary,
        emoji="🔄",
    )
    async def refresh(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ This can only be used inside a server.",
                ephemeral=True,
            )
            return

        embed = self.cog.build_daily_embed(
            interaction.guild.id,
            interaction.user.id,
        )

        await interaction.response.edit_message(
            embed=embed,
            view=DailyQuestView(self.cog),
        )

    @discord.ui.button(
        label="Claim",
        style=discord.ButtonStyle.success,
        emoji="🎁",
    )
    async def claim(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ This can only be used inside a server.",
                ephemeral=True,
            )
            return

        result = self.cog.claim_daily_quests(
            interaction.guild.id,
            interaction.user.id,
        )

        await interaction.response.send_message(
            result,
            ephemeral=True,
        )


class DailyQuests(commands.Cog):
    """Daily quest and reward system for Grid Guardian."""

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
            CREATE TABLE IF NOT EXISTS daily_quests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                quest_date TEXT NOT NULL,
                quest_type TEXT NOT NULL,
                quest_name TEXT NOT NULL,
                quest_description TEXT NOT NULL,
                target INTEGER NOT NULL DEFAULT 1,
                progress INTEGER NOT NULL DEFAULT 0,
                xp_reward INTEGER NOT NULL DEFAULT 0,
                claimed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                UNIQUE (
                    guild_id,
                    user_id,
                    quest_date,
                    quest_type
                )
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_quest_stats (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                current_streak INTEGER NOT NULL DEFAULT 0,
                longest_streak INTEGER NOT NULL DEFAULT 0,
                last_completed_date TEXT,
                total_days_completed INTEGER NOT NULL DEFAULT 0,
                total_xp_earned INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )
            """
        )

        conn.commit()
        conn.close()

    # ============================================================
    # DATE HELPERS
    # ============================================================

    def today(self) -> str:
        """
        Returns the current UTC date.

        Using UTC keeps quest resets consistent regardless
        of where members live.
        """
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # ============================================================
    # QUEST GENERATION
    # ============================================================

    def ensure_daily_quests(
        self,
        guild_id: int,
        user_id: int,
    ):
        today = self.today()

        conn = self.db_connect()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM daily_quests
            WHERE guild_id = ?
              AND user_id = ?
              AND quest_date = ?
            """,
            (
                guild_id,
                user_id,
                today,
            ),
        )

        count = cursor.fetchone()[0]

        if count >= 3:
            conn.close()
            return

        # Pick three different quest types.
        selected = random.sample(
            QUEST_POOL,
            3,
        )

        now = datetime.now(timezone.utc).isoformat()

        for quest in selected:
            try:
                cursor.execute(
                    """
                    INSERT INTO daily_quests (
                        guild_id,
                        user_id,
                        quest_date,
                        quest_type,
                        quest_name,
                        quest_description,
                        target,
                        progress,
                        xp_reward,
                        claimed,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, 0, ?)
                    """,
                    (
                        guild_id,
                        user_id,
                        today,
                        quest["type"],
                        quest["name"],
                        quest["description"],
                        quest["target"],
                        quest["xp"],
                        now,
                    ),
                )

            except sqlite3.IntegrityError:
                continue

        conn.commit()
        conn.close()

    # ============================================================
    # QUEST RETRIEVAL
    # ============================================================

    def get_daily_quests(
        self,
        guild_id: int,
        user_id: int,
    ):
        self.ensure_daily_quests(
            guild_id,
            user_id,
        )

        conn = self.db_connect()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM daily_quests
            WHERE guild_id = ?
              AND user_id = ?
              AND quest_date = ?
            ORDER BY id ASC
            """,
            (
                guild_id,
                user_id,
                self.today(),
            ),
        )

        rows = cursor.fetchall()
        conn.close()

        return rows

    # ============================================================
    # PROGRESS
    # ============================================================

    def update_quest_progress(
        self,
        guild_id: int,
        user_id: int,
        quest_type: str,
        amount: int = 1,
    ):
        if amount <= 0:
            return

        self.ensure_daily_quests(
            guild_id,
            user_id,
        )

        conn = self.db_connect()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE daily_quests
            SET progress = MIN(target, progress + ?)
            WHERE guild_id = ?
              AND user_id = ?
              AND quest_date = ?
              AND quest_type = ?
              AND claimed = 0
            """,
            (
                amount,
                guild_id,
                user_id,
                self.today(),
                quest_type,
            ),
        )

        conn.commit()
        conn.close()

    # ============================================================
    # XP REWARDS
    # ============================================================

    def add_daily_xp(
        self,
        guild_id: int,
        user_id: int,
        amount: int,
    ):
        """
        Adds daily quest XP to the challenge_rewards table.

        This intentionally does not modify the main leveling
        system because your existing economy/level systems use
        their own schemas.
        """

        conn = self.db_connect()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_quest_rewards (
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    xp INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (guild_id, user_id)
                )
                """
            )

            cursor.execute(
                """
                INSERT INTO daily_quest_rewards (
                    guild_id,
                    user_id,
                    xp
                )
                VALUES (?, ?, ?)
                ON CONFLICT(guild_id, user_id)
                DO UPDATE SET
                    xp = xp + excluded.xp
                """,
                (
                    guild_id,
                    user_id,
                    amount,
                ),
            )

            conn.commit()

        finally:
            conn.close()

    # ============================================================
    # STATS
    # ============================================================

    def get_stats(
        self,
        guild_id: int,
        user_id: int,
    ):
        conn = self.db_connect()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM daily_quest_stats
            WHERE guild_id = ?
              AND user_id = ?
            """,
            (
                guild_id,
                user_id,
            ),
        )

        row = cursor.fetchone()
        conn.close()

        return row

    def ensure_stats(
        self,
        guild_id: int,
        user_id: int,
    ):
        conn = self.db_connect()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR IGNORE INTO daily_quest_stats (
                guild_id,
                user_id
            )
            VALUES (?, ?)
            """,
            (
                guild_id,
                user_id,
            ),
        )

        conn.commit()
        conn.close()

    # ============================================================
    # CLAIM
    # ============================================================

    def claim_daily_quests(
        self,
        guild_id: int,
        user_id: int,
    ) -> str:
        quests = self.get_daily_quests(
            guild_id,
            user_id,
        )

        if not quests:
            return "❌ You don't have any daily quests."

        incomplete = [
            quest
            for quest in quests
            if quest["progress"] < quest["target"]
        ]

        if incomplete:
            remaining = "\n".join(
                f"• **{quest['quest_name']}** — "
                f"{quest['progress']}/{quest['target']}"
                for quest in incomplete
            )

            return (
                "❌ You haven't completed all of today's quests yet.\n\n"
                f"{remaining}"
            )

        already_claimed = all(
            quest["claimed"] == 1
            for quest in quests
        )

        if already_claimed:
            return (
                "🎁 You've already claimed today's rewards."
            )

        total_xp = sum(
            quest["xp_reward"]
            for quest in quests
        )

        total_xp += DAILY_COMPLETION_BONUS

        conn = self.db_connect()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE daily_quests
            SET claimed = 1
            WHERE guild_id = ?
              AND user_id = ?
              AND quest_date = ?
            """,
            (
                guild_id,
                user_id,
                self.today(),
            ),
        )

        # --------------------------------------------------------
        # STREAK
        # --------------------------------------------------------

        self.ensure_stats(
            guild_id,
            user_id,
        )

        cursor.execute(
            """
            SELECT *
            FROM daily_quest_stats
            WHERE guild_id = ?
              AND user_id = ?
            """,
            (
                guild_id,
                user_id,
            ),
        )

        stats = cursor.fetchone()

        current_streak = stats["current_streak"]
        longest_streak = stats["longest_streak"]
        last_completed = stats["last_completed_date"]
        total_days = stats["total_days_completed"]
        total_earned = stats["total_xp_earned"]

        today = datetime.now(
            timezone.utc
        ).date()

        if last_completed:
            try:
                last_date = datetime.strptime(
                    last_completed,
                    "%Y-%m-%d",
                ).date()

                difference = (
                    today - last_date
                ).days

                if difference == 1:
                    current_streak += 1
                elif difference == 0:
                    pass
                else:
                    current_streak = 1

            except ValueError:
                current_streak = 1

        else:
            current_streak = 1

        longest_streak = max(
            longest_streak,
            current_streak,
        )

        if last_completed != self.today():
            total_days += 1

        total_earned += total_xp

        cursor.execute(
            """
            UPDATE daily_quest_stats
            SET current_streak = ?,
                longest_streak = ?,
                last_completed_date = ?,
                total_days_completed = ?,
                total_xp_earned = ?
            WHERE guild_id = ?
              AND user_id = ?
            """,
            (
                current_streak,
                longest_streak,
                self.today(),
                total_days,
                total_earned,
                guild_id,
                user_id,
            ),
        )

        conn.commit()
        conn.close()

        self.add_daily_xp(
            guild_id,
            user_id,
            total_xp,
        )

        return (
            "🎉 **Daily quests completed!**\n\n"
            f"💰 Quest XP: **{total_xp - DAILY_COMPLETION_BONUS}**\n"
            f"🎁 Completion Bonus: **{DAILY_COMPLETION_BONUS} XP**\n"
            f"⚡ Total Earned: **{total_xp} XP**\n\n"
            f"🔥 Daily Streak: **{current_streak} day(s)**"
        )

    # ============================================================
    # EMBED
    # ============================================================

    def build_daily_embed(
        self,
        guild_id: int,
        user_id: int,
    ):
        quests = self.get_daily_quests(
            guild_id,
            user_id,
        )

        stats = self.get_stats(
            guild_id,
            user_id,
        )

        embed = discord.Embed(
            title="⚡ The Power Grid — Daily Quests",
            description=(
                "Complete all three quests to earn your rewards "
                "and maintain your daily streak."
            ),
            color=discord.Color.blurple(),
        )

        total_progress = 0
        total_target = 0
        total_xp = 0

        for index, quest in enumerate(quests, start=1):
            progress = quest["progress"]
            target = quest["target"]

            total_progress += min(
                progress,
                target,
            )

            total_target += target
            total_xp += quest["xp_reward"]

            if quest["claimed"]:
                status = "🎁 Claimed"
            elif progress >= target:
                status = "✅ Complete"
            else:
                status = "🔲 In Progress"

            embed.add_field(
                name=(
                    f"{index}. {quest['quest_name']} "
                    f"— {status}"
                ),
                value=(
                    f"{quest['quest_description']}\n"
                    f"Progress: **{progress}/{target}**\n"
                    f"Reward: **{quest['xp_reward']} XP**"
                ),
                inline=False,
            )

        if stats:
            streak = stats["current_streak"]
        else:
            streak = 0

        embed.add_field(
            name="📊 Today's Progress",
            value=(
                f"**{total_progress}/{total_target}** objectives\n"
                f"Quest XP: **{total_xp}**\n"
                f"Completion Bonus: **{DAILY_COMPLETION_BONUS} XP**"
            ),
            inline=True,
        )

        embed.add_field(
            name="🔥 Streak",
            value=f"**{streak} day(s)**",
            inline=True,
        )

        embed.set_footer(
            text=(
                f"Quest date: {self.today()} • "
                "Resets at 00:00 UTC"
            )
        )

        return embed

    # ============================================================
    # COMMAND: !dailyquest
    # ============================================================

    @commands.command(
        name="dailyquest",
        aliases=[
            "dailyquests",
            "dq",
        ],
    )
    @commands.guild_only()
    async def dailyquest(
        self,
        ctx: commands.Context,
    ):
        """Show today's daily quests."""

        embed = self.build_daily_embed(
            ctx.guild.id,
            ctx.author.id,
        )

        await ctx.send(
            embed=embed,
            view=DailyQuestView(self),
        )

    # ============================================================
    # COMMAND: !dailyquest claim
    # ============================================================

    @commands.command(
        name="dailyclaim",
        aliases=[
            "claimdaily",
        ],
    )
    @commands.guild_only()
    async def dailyclaim(
        self,
        ctx: commands.Context,
    ):
        """Claim completed daily quest rewards."""

        result = self.claim_daily_quests(
            ctx.guild.id,
            ctx.author.id,
        )

        await ctx.send(result)

    # ============================================================
    # COMMAND: !dailyquest stats
    # ============================================================

    @commands.command(
        name="dailystats",
        aliases=[
            "dailyqueststats",
        ],
    )
    @commands.guild_only()
    async def dailystats(
        self,
        ctx: commands.Context,
    ):
        """Show daily quest statistics."""

        self.ensure_stats(
            ctx.guild.id,
            ctx.author.id,
        )

        stats = self.get_stats(
            ctx.guild.id,
            ctx.author.id,
        )

        embed = discord.Embed(
            title=f"🔥 {ctx.author.display_name}'s Daily Stats",
            color=discord.Color.blurple(),
        )

        embed.set_thumbnail(
            url=ctx.author.display_avatar.url
        )

        embed.add_field(
            name="Current Streak",
            value=f"🔥 **{stats['current_streak']} days**",
            inline=True,
        )

        embed.add_field(
            name="Longest Streak",
            value=f"🏆 **{stats['longest_streak']} days**",
            inline=True,
        )

        embed.add_field(
            name="Days Completed",
            value=f"📅 **{stats['total_days_completed']}**",
            inline=True,
        )

        embed.add_field(
            name="Quest XP Earned",
            value=f"⚡ **{stats['total_xp_earned']} XP**",
            inline=True,
        )

        if stats["last_completed_date"]:
            embed.add_field(
                name="Last Completion",
                value=stats["last_completed_date"],
                inline=True,
            )
        else:
            embed.add_field(
                name="Last Completion",
                value="Never",
                inline=True,
            )

        await ctx.send(embed=embed)

    # ============================================================
    # COMMAND: !dailyquest reset
    # ============================================================

    @commands.command(
        name="dailyreset",
    )
    @commands.guild_only()
    @commands.has_guild_permissions(
        manage_guild=True
    )
    async def dailyreset(
        self,
        ctx: commands.Context,
        member: Optional[discord.Member] = None,
    ):
        """
        Admin-only testing command.

        Deletes today's quests for a member so they can
        be regenerated.
        """

        member = member or ctx.author

        conn = self.db_connect()
        cursor = conn.cursor()

        cursor.execute(
            """
            DELETE FROM daily_quests
            WHERE guild_id = ?
              AND user_id = ?
              AND quest_date = ?
            """,
            (
                ctx.guild.id,
                member.id,
                self.today(),
            ),
        )

        conn.commit()
        conn.close()

        await ctx.send(
            f"✅ Reset today's daily quests for "
            f"{member.mention}."
        )

    # ============================================================
    # COMMAND: !dailyhelp
    # ============================================================

    @commands.command(
        name="dailyhelp",
    )
    @commands.guild_only()
    async def dailyhelp(
        self,
        ctx: commands.Context,
    ):
        """Show daily quest help."""

        embed = discord.Embed(
            title="⚡ Daily Quest Help",
            description=(
                "`!dailyquest` — View today's quests\n"
                "`!dailyclaim` — Claim completed rewards\n"
                "`!dailystats` — View your streak and stats\n"
                "`!dailyhelp` — Show this help"
            ),
            color=discord.Color.blurple(),
        )

        embed.add_field(
            name="🎁 Rewards",
            value=(
                "Complete all 3 daily quests to receive "
                f"your quest XP plus a **{DAILY_COMPLETION_BONUS} XP** "
                "completion bonus."
            ),
            inline=False,
        )

        embed.add_field(
            name="🔥 Streaks",
            value=(
                "Complete your daily quests on consecutive days "
                "to build your streak."
            ),
            inline=False,
        )

        await ctx.send(embed=embed)

    # ============================================================
    # COMMAND ERRORS
    # ============================================================

    @dailyreset.error
    async def dailyreset_error(
        self,
        ctx: commands.Context,
        error,
    ):
        if isinstance(
            error,
            commands.MissingPermissions,
        ):
            await ctx.send(
                "❌ You need **Manage Server** permission "
                "to use this command."
            )
            return

        if isinstance(
            error,
            commands.BadArgument,
        ):
            await ctx.send(
                "❌ I couldn't find that member."
            )
            return

        raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(
        DailyQuests(bot)
    )