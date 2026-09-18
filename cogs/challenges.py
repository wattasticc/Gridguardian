import random
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord.ext import commands


DB_PATH = "gridguardian.db"
EMBED_COLOR = discord.Color.blurple()


CHALLENGES = [
    {
        "id": "practice_1",
        "name": "Power Practice",
        "description": "Use `!wattson practice` once.",
        "type": "practice",
        "target": 1,
        "reward": 50,
        "difficulty": "Easy",
    },
    {
        "id": "practice_3",
        "name": "Grid Training",
        "description": "Complete 3 Wattson practice sessions.",
        "type": "practice",
        "target": 3,
        "reward": 125,
        "difficulty": "Medium",
    },
    {
        "id": "setups_1",
        "name": "Grid Architect",
        "description": "Create 1 Wattson setup in the Setup Library.",
        "type": "setups",
        "target": 1,
        "reward": 100,
        "difficulty": "Easy",
    },
    {
        "id": "setups_3",
        "name": "Fortify the Grid",
        "description": "Create 3 Wattson setups.",
        "type": "setups",
        "target": 3,
        "reward": 250,
        "difficulty": "Hard",
    },
    {
        "id": "upvotes_5",
        "name": "Community Power",
        "description": "Receive 5 upvotes on your Wattson setups.",
        "type": "upvotes",
        "target": 5,
        "reward": 150,
        "difficulty": "Medium",
    },
    {
        "id": "upvotes_10",
        "name": "Power Grid Expert",
        "description": "Receive 10 upvotes on your Wattson setups.",
        "type": "upvotes",
        "target": 10,
        "reward": 300,
        "difficulty": "Hard",
    },
    {
        "id": "coach_1",
        "name": "Study the Grid",
        "description": "Complete 1 Apex Coach lesson.",
        "type": "coach",
        "target": 1,
        "reward": 75,
        "difficulty": "Easy",
    },
    {
        "id": "coach_3",
        "name": "Wattson Student",
        "description": "Complete 3 Apex Coach lessons.",
        "type": "coach",
        "target": 3,
        "reward": 175,
        "difficulty": "Medium",
    },
]


class ChallengeView(discord.ui.View):
    def __init__(self, cog, ctx):
        super().__init__(timeout=180)

        self.cog = cog
        self.ctx = ctx

    async def interaction_check(
        self,
        interaction: discord.Interaction
    ) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "❌ Only the person who opened this menu can use these buttons.",
                ephemeral=True
            )
            return False

        return True

    @discord.ui.button(
        label="Refresh",
        emoji="🔄",
        style=discord.ButtonStyle.secondary
    )
    async def refresh_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        embed = await self.cog.build_challenges_embed(
            self.ctx
        )

        await interaction.response.edit_message(
            embed=embed,
            view=self
        )


class Challenges(commands.Cog):
    """Daily and weekly challenge system."""

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
            CREATE TABLE IF NOT EXISTS challenges (
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                challenge_id TEXT NOT NULL,
                period TEXT NOT NULL,
                progress INTEGER DEFAULT 0,
                completed INTEGER DEFAULT 0,
                claimed INTEGER DEFAULT 0,
                assigned_at TEXT NOT NULL,
                completed_at TEXT,
                PRIMARY KEY (
                    user_id,
                    guild_id,
                    challenge_id,
                    period
                )
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_challenges_user
            ON challenges(user_id, guild_id, period)
            """
        )

        conn.commit()
        conn.close()

    # ============================================================
    # TIME HELPERS
    # ============================================================

    def now(self):
        return datetime.now(timezone.utc)

    def current_daily_period(self):
        return self.now().strftime("%Y-%m-%d")

    def current_weekly_period(self):
        current = self.now()

        monday = current - timedelta(
            days=current.weekday()
        )

        return monday.strftime("%Y-%m-%d")

    # ============================================================
    # CHALLENGE HELPERS
    # ============================================================

    def get_challenge(self, challenge_id: str):
        for challenge in CHALLENGES:
            if challenge["id"] == challenge_id:
                return challenge

        return None

    def get_period_challenges(
        self,
        user_id: int,
        guild_id: int,
        period_type: str
    ):
        period = (
            self.current_daily_period()
            if period_type == "daily"
            else self.current_weekly_period()
        )

        conn = self.db_connect()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM challenges
            WHERE user_id = ?
              AND guild_id = ?
              AND period = ?
            ORDER BY challenge_id
            """,
            (
                user_id,
                guild_id,
                f"{period_type}:{period}"
            )
        )

        rows = cursor.fetchall()
        conn.close()

        return rows

    def ensure_challenges(
        self,
        user_id: int,
        guild_id: int
    ):
        daily_period = (
            f"daily:{self.current_daily_period()}"
        )

        weekly_period = (
            f"weekly:{self.current_weekly_period()}"
        )

        conn = self.db_connect()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT challenge_id
            FROM challenges
            WHERE user_id = ?
              AND guild_id = ?
              AND period = ?
            """,
            (
                user_id,
                guild_id,
                daily_period
            )
        )

        daily_existing = {
            row["challenge_id"]
            for row in cursor.fetchall()
        }

        cursor.execute(
            """
            SELECT challenge_id
            FROM challenges
            WHERE user_id = ?
              AND guild_id = ?
              AND period = ?
            """,
            (
                user_id,
                guild_id,
                weekly_period
            )
        )

        weekly_existing = {
            row["challenge_id"]
            for row in cursor.fetchall()
        }

        # Two daily challenges.
        if len(daily_existing) < 2:
            available = [
                challenge
                for challenge in CHALLENGES
                if challenge["id"] not in daily_existing
            ]

            needed = 2 - len(daily_existing)

            selected = random.sample(
                available,
                min(needed, len(available))
            )

            for challenge in selected:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO challenges (
                        user_id,
                        guild_id,
                        challenge_id,
                        period,
                        progress,
                        completed,
                        claimed,
                        assigned_at
                    )
                    VALUES (?, ?, ?, ?, 0, 0, 0, ?)
                    """,
                    (
                        user_id,
                        guild_id,
                        challenge["id"],
                        daily_period,
                        self.now().isoformat()
                    )
                )

        # Three weekly challenges.
        if len(weekly_existing) < 3:
            available = [
                challenge
                for challenge in CHALLENGES
                if challenge["id"] not in weekly_existing
            ]

            needed = 3 - len(weekly_existing)

            selected = random.sample(
                available,
                min(needed, len(available))
            )

            for challenge in selected:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO challenges (
                        user_id,
                        guild_id,
                        challenge_id,
                        period,
                        progress,
                        completed,
                        claimed,
                        assigned_at
                    )
                    VALUES (?, ?, ?, ?, 0, 0, 0, ?)
                    """,
                    (
                        user_id,
                        guild_id,
                        challenge["id"],
                        weekly_period,
                        self.now().isoformat()
                    )
                )

        conn.commit()
        conn.close()

    # ============================================================
    # PROGRESS
    # ============================================================

    def update_progress(
        self,
        user_id: int,
        guild_id: int,
        challenge_type: str,
        amount: int = 1
    ):
        self.ensure_challenges(
            user_id,
            guild_id
        )

        daily_period = (
            f"daily:{self.current_daily_period()}"
        )

        weekly_period = (
            f"weekly:{self.current_weekly_period()}"
        )

        conn = self.db_connect()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM challenges
            WHERE user_id = ?
              AND guild_id = ?
              AND period IN (?, ?)
              AND completed = 0
            """,
            (
                user_id,
                guild_id,
                daily_period,
                weekly_period
            )
        )

        rows = cursor.fetchall()

        for row in rows:
            challenge = self.get_challenge(
                row["challenge_id"]
            )

            if not challenge:
                continue

            if challenge["type"] != challenge_type:
                continue

            new_progress = min(
                row["progress"] + amount,
                challenge["target"]
            )

            completed = (
                1
                if new_progress >= challenge["target"]
                else 0
            )

            completed_at = (
                self.now().isoformat()
                if completed
                else None
            )

            cursor.execute(
                """
                UPDATE challenges
                SET progress = ?,
                    completed = ?,
                    completed_at = ?
                WHERE user_id = ?
                  AND guild_id = ?
                  AND challenge_id = ?
                  AND period = ?
                """,
                (
                    new_progress,
                    completed,
                    completed_at,
                    user_id,
                    guild_id,
                    row["challenge_id"],
                    row["period"]
                )
            )

        conn.commit()
        conn.close()

    # ============================================================
    # CLAIM REWARD
    # ============================================================

    def claim_challenge(
        self,
        user_id: int,
        guild_id: int,
        challenge_id: str
    ):
        daily_period = (
            f"daily:{self.current_daily_period()}"
        )

        weekly_period = (
            f"weekly:{self.current_weekly_period()}"
        )

        conn = self.db_connect()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM challenges
            WHERE user_id = ?
              AND guild_id = ?
              AND challenge_id = ?
              AND period IN (?, ?)
            """,
            (
                user_id,
                guild_id,
                challenge_id,
                daily_period,
                weekly_period
            )
        )

        row = cursor.fetchone()

        if not row:
            conn.close()
            return None, "not_found"

        if row["claimed"]:
            conn.close()
            return None, "already_claimed"

        if not row["completed"]:
            conn.close()
            return None, "not_completed"

        challenge = self.get_challenge(
            challenge_id
        )

        if not challenge:
            conn.close()
            return None, "not_found"

        cursor.execute(
            """
            UPDATE challenges
            SET claimed = 1
            WHERE user_id = ?
              AND guild_id = ?
              AND challenge_id = ?
              AND period = ?
            """,
            (
                user_id,
                guild_id,
                challenge_id,
                row["period"]
            )
        )

        conn.commit()
        conn.close()

        return challenge, "success"

    # ============================================================
    # REWARD
    # ============================================================

    def award_xp(
        self,
        user_id: int,
        guild_id: int,
        amount: int
    ):
        conn = self.db_connect()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS challenge_rewards (
                    user_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    total_xp INTEGER DEFAULT 0,
                    PRIMARY KEY(user_id, guild_id)
                )
                """
            )

            cursor.execute(
                """
                INSERT INTO challenge_rewards (
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
                    amount
                )
            )

            conn.commit()

        finally:
            conn.close()

    # ============================================================
    # EMBED
    # ============================================================

    async def build_challenges_embed(
        self,
        ctx: commands.Context
    ):
        self.ensure_challenges(
            ctx.author.id,
            ctx.guild.id
        )

        daily = self.get_period_challenges(
            ctx.author.id,
            ctx.guild.id,
            "daily"
        )

        weekly = self.get_period_challenges(
            ctx.author.id,
            ctx.guild.id,
            "weekly"
        )

        embed = discord.Embed(
            title="⚡ Wattson Challenges",
            description=(
                "Complete challenges to earn rewards and "
                "progress your Grid Guardian profile."
            ),
            color=EMBED_COLOR
        )

        embed.set_thumbnail(
            url=ctx.author.display_avatar.url
        )

        daily_lines = []

        for row in daily:
            challenge = self.get_challenge(
                row["challenge_id"]
            )

            if not challenge:
                continue

            progress = row["progress"]
            target = challenge["target"]

            if row["claimed"]:
                status = "✅ Claimed"
            elif row["completed"]:
                status = "🎁 Ready to claim"
            else:
                status = f"**{progress}/{target}**"

            daily_lines.append(
                f"**{challenge['name']}**\n"
                f"{challenge['description']}\n"
                f"Progress: {status} • "
                f"⭐ {challenge['reward']} XP"
            )

        weekly_lines = []

        for row in weekly:
            challenge = self.get_challenge(
                row["challenge_id"]
            )

            if not challenge:
                continue

            progress = row["progress"]
            target = challenge["target"]

            if row["claimed"]:
                status = "✅ Claimed"
            elif row["completed"]:
                status = "🎁 Ready to claim"
            else:
                status = f"**{progress}/{target}**"

            weekly_lines.append(
                f"**{challenge['name']}**\n"
                f"{challenge['description']}\n"
                f"Progress: {status} • "
                f"⭐ {challenge['reward']} XP"
            )

        embed.add_field(
            name="☀️ Daily Challenges",
            value="\n\n".join(daily_lines)
            if daily_lines
            else "No daily challenges.",
            inline=False
        )

        embed.add_field(
            name="📅 Weekly Challenges",
            value="\n\n".join(weekly_lines)
            if weekly_lines
            else "No weekly challenges.",
            inline=False
        )

        embed.add_field(
            name="🎁 Claiming Rewards",
            value=(
                "Use `!challenge claim <challenge_id>` "
                "after completing a challenge."
            ),
            inline=False
        )

        embed.set_footer(
            text="Grid Guardian • Challenges"
        )

        return embed

    # ============================================================
    # COMMAND GROUP
    # ============================================================

    @commands.group(
        name="challenge",
        aliases=["challenges"],
        invoke_without_command=True
    )
    @commands.guild_only()
    async def challenge(
        self,
        ctx: commands.Context
    ):
        """Display your active challenges."""

        embed = await self.build_challenges_embed(ctx)

        view = ChallengeView(
            self,
            ctx
        )

        await ctx.send(
            embed=embed,
            view=view
        )

    # ============================================================
    # LIST
    # ============================================================

    @challenge.command(name="list")
    @commands.guild_only()
    async def challenge_list(
        self,
        ctx: commands.Context
    ):
        embed = await self.build_challenges_embed(ctx)

        view = ChallengeView(
            self,
            ctx
        )

        await ctx.send(
            embed=embed,
            view=view
        )

    # ============================================================
    # CLAIM
    # ============================================================

    @challenge.command(name="claim")
    @commands.guild_only()
    async def challenge_claim(
        self,
        ctx: commands.Context,
        challenge_id: str
    ):
        challenge, status = self.claim_challenge(
            ctx.author.id,
            ctx.guild.id,
            challenge_id.lower()
        )

        if status == "not_found":
            await ctx.send(
                "❌ I couldn't find that active challenge."
            )
            return

        if status == "already_claimed":
            await ctx.send(
                "❌ You already claimed that challenge."
            )
            return

        if status == "not_completed":
            await ctx.send(
                "❌ You haven't completed that challenge yet."
            )
            return

        self.award_xp(
            ctx.author.id,
            ctx.guild.id,
            challenge["reward"]
        )

        embed = discord.Embed(
            title="🎉 Challenge Complete!",
            description=(
                f"You claimed **{challenge['name']}**!\n\n"
                f"⭐ **+{challenge['reward']} XP**"
            ),
            color=discord.Color.green()
        )

        embed.set_footer(
            text="Grid Guardian • Challenge Rewards"
        )

        await ctx.send(embed=embed)

    # ============================================================
    # PROGRESS
    # ============================================================

    @challenge.command(name="progress")
    @commands.guild_only()
    async def challenge_progress(
        self,
        ctx: commands.Context
    ):
        embed = await self.build_challenges_embed(ctx)

        await ctx.send(embed=embed)

    # ============================================================
    # HELP
    # ============================================================

    @challenge.command(name="help")
    @commands.guild_only()
    async def challenge_help(
        self,
        ctx: commands.Context
    ):
        embed = discord.Embed(
            title="⚡ Challenge Commands",
            description=(
                "`!challenge` — View your challenges\n"
                "`!challenge list` — View your challenges\n"
                "`!challenge progress` — View progress\n"
                "`!challenge claim <id>` — Claim a completed reward"
            ),
            color=EMBED_COLOR
        )

        embed.add_field(
            name="Challenge Types",
            value=(
                "⚡ Wattson Practice\n"
                "🧠 Setup Creation\n"
                "⭐ Setup Upvotes\n"
                "📚 Coach Lessons"
            ),
            inline=False
        )

        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Challenges(bot))