import sqlite3
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands


EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)


# =========================================================
# DATABASE
# =========================================================

db = sqlite3.connect("gridguardian.db")
cursor = db.cursor()


cursor.execute("""
CREATE TABLE IF NOT EXISTS daily_rewards (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    last_claim TEXT,
    streak INTEGER NOT NULL DEFAULT 0,

    PRIMARY KEY (guild_id, user_id)
)
""")


db.commit()


# =========================================================
# SETTINGS
# =========================================================

DAILY_REWARD = 100
STREAK_BONUS_PER_DAY = 10
MAX_STREAK_BONUS = 500

COOLDOWN_HOURS = 24


# =========================================================
# DAILY COG
# =========================================================

class Daily(commands.Cog):

    def __init__(self, bot):

        self.bot = bot


    # =====================================================
    # ADD MONEY
    # =====================================================

    def add_money(self, guild_id, user_id, amount):

        """
        Supports the most common Grid Guardian economy
        database layouts.
        """

        economy_tables = [
            ("economy", "balance"),
            ("users", "balance")
        ]


        for table, balance_column in economy_tables:

            try:

                cursor.execute(
                    f"""
                    SELECT {balance_column}
                    FROM {table}
                    WHERE guild_id=?
                    AND user_id=?
                    """,
                    (
                        guild_id,
                        user_id
                    )
                )


                result = cursor.fetchone()


                if result is None:

                    cursor.execute(
                        f"""
                        INSERT INTO {table}(
                            guild_id,
                            user_id,
                            {balance_column}
                        )
                        VALUES (?, ?, ?)
                        """,
                        (
                            guild_id,
                            user_id,
                            amount
                        )
                    )


                else:

                    cursor.execute(
                        f"""
                        UPDATE {table}
                        SET {balance_column}
                        = {balance_column} + ?
                        WHERE guild_id=?
                        AND user_id=?
                        """,
                        (
                            amount,
                            guild_id,
                            user_id
                        )
                    )


                db.commit()

                return True


            except sqlite3.Error:

                continue


        return False


    # =====================================================
    # GET DAILY DATA
    # =====================================================

    def get_daily_data(
        self,
        guild_id,
        user_id
    ):

        cursor.execute("""
        SELECT last_claim, streak
        FROM daily_rewards
        WHERE guild_id=?
        AND user_id=?
        """, (
            guild_id,
            user_id
        ))


        return cursor.fetchone()


    # =====================================================
    # DAILY COMMAND
    # =====================================================

    @commands.command()
    async def daily(
        self,
        ctx
    ):

        guild_id = ctx.guild.id
        user_id = ctx.author.id


        now = datetime.now(
            timezone.utc
        )


        data = self.get_daily_data(
            guild_id,
            user_id
        )


        # =================================================
        # FIRST CLAIM
        # =================================================

        if data is None:

            streak = 1


        else:

            last_claim_text, old_streak = data


            try:

                last_claim = datetime.fromisoformat(
                    last_claim_text
                )


            except (
                ValueError,
                TypeError
            ):

                last_claim = None


            # =============================================
            # COOLDOWN
            # =============================================

            if last_claim is not None:

                time_since_claim = (
                    now - last_claim
                )


                cooldown = timedelta(
                    hours=COOLDOWN_HOURS
                )


                if time_since_claim < cooldown:

                    remaining = (
                        cooldown - time_since_claim
                    )


                    total_seconds = int(
                        remaining.total_seconds()
                    )


                    hours = total_seconds // 3600

                    minutes = (
                        total_seconds % 3600
                    ) // 60


                    embed = discord.Embed(
                        title="⏳ Daily Reward Already Claimed",
                        description=(
                            f"You can claim your next reward "
                            f"in **{hours}h {minutes}m**."
                        ),
                        color=discord.Color.orange()
                    )


                    embed.add_field(
                        name="🔥 Current Streak",
                        value=f"{old_streak} day(s)",
                        inline=False
                    )


                    return await ctx.send(
                        embed=embed
                    )


                # =========================================
                # STREAK
                # =========================================

                if time_since_claim <= timedelta(
                    hours=48
                ):

                    streak = old_streak + 1


                else:

                    streak = 1


            else:

                streak = 1


        # =================================================
        # CALCULATE REWARD
        # =================================================

        streak_bonus = min(
            streak * STREAK_BONUS_PER_DAY,
            MAX_STREAK_BONUS
        )


        total_reward = (
            DAILY_REWARD
            + streak_bonus
        )


        # =================================================
        # ADD MONEY
        # =================================================

        success = self.add_money(
            guild_id,
            user_id,
            total_reward
        )


        if not success:

            return await ctx.send(
                "❌ I couldn't find the economy database table.\n\n"
                "We may need to connect this command to your existing "
                "`economy.py` system."
            )


        # =================================================
        # SAVE DAILY DATA
        # =================================================

        cursor.execute("""
        INSERT INTO daily_rewards(
            guild_id,
            user_id,
            last_claim,
            streak
        )
        VALUES (?, ?, ?, ?)

        ON CONFLICT(guild_id, user_id)
        DO UPDATE SET
        last_claim=excluded.last_claim,
        streak=excluded.streak
        """, (
            guild_id,
            user_id,
            now.isoformat(),
            streak
        ))


        db.commit()


        # =================================================
        # SUCCESS EMBED
        # =================================================

        embed = discord.Embed(
            title="🎁 Daily Reward Claimed!",
            description=(
                f"{ctx.author.mention} claimed their daily reward!"
            ),
            color=discord.Color.green()
        )


        embed.add_field(
            name="💰 Base Reward",
            value=f"{DAILY_REWARD:,} coins",
            inline=True
        )


        embed.add_field(
            name="🔥 Streak Bonus",
            value=f"{streak_bonus:,} coins",
            inline=True
        )


        embed.add_field(
            name="💵 Total Earned",
            value=f"{total_reward:,} coins",
            inline=False
        )


        embed.add_field(
            name="🔥 Current Streak",
            value=f"{streak} day(s)",
            inline=False
        )


        embed.set_footer(
            text="Come back in 24 hours to continue your streak!"
        )


        await ctx.send(
            embed=embed
        )


    # =====================================================
    # STREAK COMMAND
    # =====================================================

    @commands.command()
    async def streak(
        self,
        ctx,
        member: discord.Member = None
    ):

        member = member or ctx.author


        data = self.get_daily_data(
            ctx.guild.id,
            member.id
        )


        if data is None:

            streak = 0
            last_claim = "Never"


        else:

            last_claim_text, streak = data


            try:

                date = datetime.fromisoformat(
                    last_claim_text
                )


                last_claim = date.strftime(
                    "%B %d, %Y"
                )


            except (
                ValueError,
                TypeError
            ):

                last_claim = "Unknown"


        embed = discord.Embed(
            title=f"🔥 {member.display_name}'s Daily Streak",
            color=EMBED_COLOR
        )


        embed.set_thumbnail(
            url=member.display_avatar.url
        )


        embed.add_field(
            name="🔥 Current Streak",
            value=f"{streak} day(s)",
            inline=True
        )


        embed.add_field(
            name="📅 Last Claim",
            value=last_claim,
            inline=True
        )


        await ctx.send(
            embed=embed
        )


# =========================================================
# SETUP
# =========================================================

async def setup(bot):

    await bot.add_cog(
        Daily(bot)
    )