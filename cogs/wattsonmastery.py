import random
import sqlite3
import time

import discord
from discord.ext import commands

from cogs.utils.achievement_manager import unlock


DB_FILE = "gridguardian.db"
PRACTICE_COOLDOWN = 12 * 60 * 60  # 12 hours

TITLES = [
    (100, "Grid Guardian"),
    (75, "Fence Master"),
    (50, "Wattson Main"),
    (30, "Power Grid Expert"),
    (20, "Static Specialist"),
    (10, "Fence Engineer"),
    (5, "Electrical Apprentice"),
    (1, "New Recruit"),
]

TIPS = [
    "Place fences where enemies have to cross them instead of in random open space.",
    "Use Wattson's fences to control doorways, ziplines, staircases, and other choke points.",
    "Use fences defensively to make a building harder to push.",
    "Place fence nodes where enemies cannot easily destroy them from outside the doorway.",
    "Mix obvious defensive fences with less predictable placements.",
    "Wattson's Interception Pylon can protect your team from incoming ordnance while providing shield regeneration.",
    "Carry extra Ultimate Accelerants when you expect to hold buildings for a long time.",
    "A good Wattson setup should make it clear to your team which areas are safe and which are trapped.",
    "Practice placing fences quickly so you can set up before an enemy squad arrives.",
    "When rotating, think about where you could create a temporary defensive position if another squad appears.",
    "Use fences for information: a triggered fence can warn you that an enemy entered an area.",
    "Do not over-fence a room if the setup makes it difficult for your own teammates to move.",
]

MILESTONE_ACHIEVEMENTS = {
    5: "⚡ Wattson Mastery Level 5",
    10: "⚡ Wattson Mastery Level 10",
    25: "⚡ Wattson Mastery Level 25",
    50: "⚡ Wattson Mastery Level 50",
    100: "👑 Wattson Mastery Level 100",
}


def get_title(level: int) -> str:
    for required_level, title in TITLES:
        if level >= required_level:
            return title
    return "New Recruit"


def xp_required_for_level(level: int) -> int:
    return 100 + ((level - 1) * 50)


def get_progress_bar(current_xp: int, required_xp: int, length: int = 10) -> str:
    if required_xp <= 0:
        return "██████████"

    progress = min(max(current_xp / required_xp, 0), 1)
    filled = int(progress * length)
    return "█" * filled + "░" * (length - filled)


class WattsonMastery(commands.Cog):
    """Wattson-specific mastery progression and practice commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = DB_FILE
        self._setup_database()

    def _get_connection(self):
        return sqlite3.connect(self.db)

    def _setup_database(self):
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS wattson_mastery (
                    user_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    xp INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1,
                    last_practice REAL DEFAULT 0,
                    PRIMARY KEY (user_id, guild_id)
                )
                """
            )
            conn.commit()

    def _get_mastery(self, user_id: int, guild_id: int):
        with self._get_connection() as conn:
            row = conn.execute(
                """
                SELECT xp, level, last_practice
                FROM wattson_mastery
                WHERE user_id = ? AND guild_id = ?
                """,
                (user_id, guild_id),
            ).fetchone()

        if row is None:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO wattson_mastery
                    (user_id, guild_id, xp, level, last_practice)
                    VALUES (?, ?, 0, 1, 0)
                    """,
                    (user_id, guild_id),
                )
                conn.commit()
            return 0, 1, 0

        return row

    def _save_mastery(self, user_id, guild_id, xp, level, last_practice):
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO wattson_mastery
                (user_id, guild_id, xp, level, last_practice)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, guild_id)
                DO UPDATE SET
                    xp = excluded.xp,
                    level = excluded.level,
                    last_practice = excluded.last_practice
                """,
                (user_id, guild_id, xp, level, last_practice),
            )
            conn.commit()

    async def _award_milestone_achievements(self, user_id, old_level, new_level):
        for milestone, achievement_name in MILESTONE_ACHIEVEMENTS.items():
            if old_level < milestone <= new_level:
                try:
                    unlock(user_id, achievement_name)
                except Exception as exc:
                    print(
                        f"[Wattson Mastery] Could not unlock achievement "
                        f"for {user_id}: {exc}"
                    )

    @commands.group(
        name="wattson",
        invoke_without_command=True,
        case_insensitive=True,
    )
    async def wattson(self, ctx: commands.Context):
        """Wattson Mastery command group."""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="⚡ Wattson Mastery",
                description=(
                    "Use one of these commands:\n\n"
                    "`!wattson mastery` — View your mastery\n"
                    "`!wattson mastery @user` — View another user's mastery\n"
                    "`!wattson practice` — Complete a practice session\n"
                    "`!wattson tip` — Get a random Wattson tip"
                ),
                color=discord.Color.from_rgb(255, 170, 220),
            )
            await ctx.send(embed=embed)

    @wattson.command(name="mastery")
    async def mastery(self, ctx: commands.Context, member: discord.Member = None):
        """Show a user's Wattson mastery level."""
        target = member or ctx.author

        xp, level, _ = self._get_mastery(target.id, ctx.guild.id)
        required_xp = xp_required_for_level(level)
        progress = get_progress_bar(xp, required_xp)

        next_title = None
        for required_level, possible_title in reversed(TITLES):
            if required_level > level:
                next_title = (required_level, possible_title)

        if level >= 100:
            next_title_text = "👑 Maximum milestone reached"
        elif next_title:
            next_title_text = f"Level {next_title[0]} — {next_title[1]}"
        else:
            next_title_text = "Keep practicing!"

        embed = discord.Embed(
            title=f"⚡ {target.display_name}'s Wattson Mastery",
            color=discord.Color.from_rgb(255, 170, 220),
        )
        embed.set_thumbnail(url=target.display_avatar.url)

        embed.add_field(
            name="Mastery Level",
            value=f"**Level {level}**\n{get_title(level)}",
            inline=True,
        )
        embed.add_field(
            name="XP",
            value=f"**{xp} / {required_xp} XP**\n{progress}",
            inline=True,
        )
        embed.add_field(
            name="Next Title",
            value=next_title_text,
            inline=False,
        )

        embed.set_footer(text="Use !wattson practice to earn mastery XP.")
        await ctx.send(embed=embed)

    @wattson.command(name="practice")
    @commands.cooldown(1, PRACTICE_COOLDOWN, commands.BucketType.user)
    async def practice(self, ctx: commands.Context):
        """Complete a Wattson practice session and earn mastery XP."""
        xp, level, _ = self._get_mastery(ctx.author.id, ctx.guild.id)

        earned_xp = random.randint(50, 100)
        old_level = level
        xp += earned_xp
        levels_gained = 0

        while xp >= xp_required_for_level(level):
            xp -= xp_required_for_level(level)
            level += 1
            levels_gained += 1

        self._save_mastery(
            ctx.author.id,
            ctx.guild.id,
            xp,
            level,
            time.time(),
        )

        await self._award_milestone_achievements(
            ctx.author.id,
            old_level,
            level,
        )

        embed = discord.Embed(
            title="⚡ Wattson Practice Complete!",
            description=f"You earned **+{earned_xp} XP** toward your Wattson mastery.",
            color=discord.Color.from_rgb(255, 170, 220),
        )
        embed.add_field(
            name="Mastery",
            value=f"Level **{level}** — {get_title(level)}",
            inline=True,
        )
        embed.add_field(
            name="XP",
            value=f"**{xp} / {xp_required_for_level(level)} XP**",
            inline=True,
        )

        if levels_gained > 0:
            embed.add_field(
                name="🎉 Level Up!",
                value=(
                    f"You gained **{levels_gained}** level"
                    f"{'s' if levels_gained != 1 else ''}!"
                ),
                inline=False,
            )

        embed.set_footer(text="You can practice again in 12 hours.")
        await ctx.send(embed=embed)

    @practice.error
    async def practice_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.CommandOnCooldown):
            remaining = max(0, int(error.retry_after))
            hours = remaining // 3600
            minutes = (remaining % 3600) // 60
            wait_text = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"

            embed = discord.Embed(
                title="⏳ Practice On Cooldown",
                description=(
                    "You've already completed a practice session recently.\n\n"
                    f"Try again in **{wait_text}**."
                ),
                color=discord.Color.orange(),
            )
            await ctx.send(embed=embed)
            return

        raise error

    @wattson.command(name="tip")
    async def tip(self, ctx: commands.Context):
        """Send a random Wattson gameplay tip."""
        embed = discord.Embed(
            title="⚡ Wattson Tip",
            description=random.choice(TIPS),
            color=discord.Color.from_rgb(255, 170, 220),
        )
        embed.set_footer(text="Grid Guardian • Wattson Mastery")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(WattsonMastery(bot))
