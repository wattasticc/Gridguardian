import random
import sqlite3
import time
from datetime import datetime, timezone

import discord
from discord.ext import commands

from cogs.utils.achievement_manager import unlock


DB_FILE = "gridguardian.db"
PRACTICE_COOLDOWN = 12 * 60 * 60
DAILY_COOLDOWN = 24 * 60 * 60

PINK = discord.Color.from_rgb(255, 170, 220)
GOLD = discord.Color.gold()
GREEN = discord.Color.green()
ORANGE = discord.Color.orange()
RED = discord.Color.red()
BLUE = discord.Color.blurple()

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

MILESTONE_ACHIEVEMENTS = {
    5: "⚡ Wattson Mastery Level 5",
    10: "⚡ Wattson Mastery Level 10",
    25: "⚡ Wattson Mastery Level 25",
    50: "⚡ Wattson Mastery Level 50",
    100: "👑 Wattson Mastery Level 100",
}

TIPS = [
    "Place fences where enemies have to cross them instead of wasting nodes in open space.",
    "Doorways, stairs, ziplines, and chokepoints are natural places to think about fencing.",
    "A good defensive setup should still leave your own squad room to move.",
    "Hide or offset fence nodes when possible so enemies cannot destroy them as easily.",
    "Use different fence patterns so opponents cannot predict your setup.",
    "A triggered fence can provide information even when you cannot see the enemy directly.",
    "Carry Ultimate Accelerants when you expect to play long defensive holds.",
    "Practice fast fence placement so you can turn a temporary position into a defensible one quickly.",
    "When rotating, think about where you could make a temporary Wattson hold if another squad appears.",
    "Try to make your fences useful for both denial and information rather than decoration.",
    "Keep teammate movement in mind when placing fences around doors and interior routes.",
    "Learn the difference between a setup that protects you and a setup that simply looks complicated.",
]

DRILLS = {
    "fence-speed": {
        "name": "⚡ Fence Speed",
        "description": "Practice placing a complete two-node fence as quickly and cleanly as possible.",
        "difficulty": "Beginner",
    },
    "door": {
        "name": "🚪 Door Control",
        "description": "Practice protecting a doorway while keeping a usable route for your squad.",
        "difficulty": "Beginner",
    },
    "stair": {
        "name": "🪜 Stair Control",
        "description": "Practice using fence geometry to make a staircase uncomfortable to push.",
        "difficulty": "Intermediate",
    },
    "choke": {
        "name": "⚡ Chokepoint",
        "description": "Find a narrow route and build a setup that forces an enemy to respect it.",
        "difficulty": "Intermediate",
    },
    "emergency": {
        "name": "🛡️ Emergency Setup",
        "description": "Practice turning a bad position into a defensible temporary hold under time pressure.",
        "difficulty": "Advanced",
    },
    "rotation": {
        "name": "🏃 Rotation Setup",
        "description": "Choose a safe rotation point and identify where you would build a temporary hold.",
        "difficulty": "Advanced",
    },
    "pylon": {
        "name": "🔋 Pylon Placement",
        "description": "Practice identifying a protected location where your Pylon can support your squad without being needlessly exposed.",
        "difficulty": "Intermediate",
    },
    "mindgame": {
        "name": "🧠 Fence Mindgames",
        "description": "Build two different-looking setups that accomplish a similar defensive goal.",
        "difficulty": "Advanced",
    },
}

SETUP_CATEGORIES = {
    "doors": {
        "emoji": "🚪",
        "name": "Door Setups",
        "description": "Fence patterns for controlling doors and common entrances.",
    },
    "buildings": {
        "emoji": "🏠",
        "name": "Building Holds",
        "description": "General building-defense concepts for Wattson holds.",
    },
    "stairs": {
        "emoji": "🪜",
        "name": "Stair Setups",
        "description": "Ways to think about stair control and vertical pushes.",
    },
    "chokes": {
        "emoji": "⚡",
        "name": "Chokepoints",
        "description": "Setups for narrow routes, doors, and forced approaches.",
    },
    "defense": {
        "emoji": "🛡️",
        "name": "Defensive Holds",
        "description": "General defensive concepts for holding a position.",
    },
    "pylon": {
        "emoji": "🔋",
        "name": "Pylon Positions",
        "description": "General principles for protected Pylon placement.",
    },
    "rotation": {
        "emoji": "🏃",
        "name": "Rotation Holds",
        "description": "Temporary defensive setups for rotations and unstable positions.",
    },
    "ranked": {
        "emoji": "💎",
        "name": "Ranked Concepts",
        "description": "Wattson concepts for disciplined ranked play.",
    },
}

SETUP_GUIDES = {
    "doors": [
        ("Double-node doorway", "Connect nodes across the entrance so a direct push has to respect the fence.", "Beginner"),
        ("Offset doorway", "Keep the nodes less exposed by changing their positions instead of placing both directly in the open.", "Intermediate"),
        ("Two-route door", "Protect the main entrance while leaving your squad a clean alternate route.", "Intermediate"),
    ],
    "buildings": [
        ("Room lockdown", "Secure the important entry routes first, then avoid filling the room with unnecessary fences.", "Beginner"),
        ("Multi-door hold", "Prioritize the entrances an enemy is most likely to use instead of trying to cover every possible angle equally.", "Intermediate"),
        ("Retake setup", "Build a setup that still works if your squad has to briefly leave and re-enter the building.", "Advanced"),
    ],
    "stairs": [
        ("Stair denial", "Use the geometry of the stairs to make a direct climb harder to commit to.", "Beginner"),
        ("Vertical cross", "Think about how an enemy moving up or down changes the angles on your fence nodes.", "Intermediate"),
        ("Landing trap", "Use a landing or transition point as the location where the enemy has to make a decision.", "Advanced"),
    ],
    "chokes": [
        ("Narrow choke", "Use a limited route to force enemies to interact with your defensive setup.", "Beginner"),
        ("Layered choke", "Combine a fence with the rest of your squad's positioning rather than relying on the fence alone.", "Intermediate"),
        ("False opening", "Leave an apparent route while controlling the actual path you expect the enemy to take.", "Advanced"),
    ],
    "defense": [
        ("Core hold", "Identify the most important area of your position and build outward from it.", "Beginner"),
        ("Fallback hold", "Create a secondary area your squad can move to if the first room becomes unsafe.", "Intermediate"),
        ("Layered defense", "Use multiple defensive layers with clear movement paths for your teammates.", "Advanced"),
    ],
    "pylon": [
        ("Protected Pylon", "Look for a location where the Pylon can support the squad without being unnecessarily exposed.", "Beginner"),
        ("Pylon + fences", "Use fences to make the area around the Pylon less comfortable to push.", "Intermediate"),
        ("Pylon rotation", "Practice deciding when a temporary Pylon position is worth using during a rotation or fight.", "Advanced"),
    ],
    "rotation": [
        ("Quick hold", "Identify the safest nearby structure or choke and prepare a temporary defensive setup.", "Beginner"),
        ("Reset zone", "Create a small area where your squad can heal, reload, or regroup before continuing.", "Intermediate"),
        ("Third-party defense", "Use a temporary setup to make an otherwise vulnerable reset less inviting to another squad.", "Advanced"),
    ],
    "ranked": [
        ("Zone hold", "Prioritize position quality, teammate movement, and safe entry denial over excessive fencing.", "Intermediate"),
        ("Endgame setup", "Identify the few approaches that matter most and conserve resources for the final fight.", "Advanced"),
        ("Rotate then fortify", "Plan the defensive value of your destination before committing to a rotation.", "Advanced"),
    ],
}

CHALLENGES = [
    ("Fence Architect", "Create three different useful fence patterns in the Firing Range.", 75),
    ("Door Denial", "Practice three different doorway setups without blocking your own movement.", 60),
    ("Speed Grid", "Complete a clean fence placement drill three times in a row.", 100),
    ("Pylon Planner", "Practice identifying three protected Pylon locations in different areas.", 75),
    ("Chokepoint Control", "Find three narrow routes and design a defensive setup for each.", 100),
    ("Emergency Wattson", "Practice turning an exposed position into a temporary hold quickly.", 125),
    ("Mindgame", "Create two different-looking fence setups that defend the same route.", 100),
    ("Ranked Ready", "Design a defensive plan for a late-game zone before entering the next match.", 125),
]


def get_title(level: int) -> str:
    for required_level, title in TITLES:
        if level >= required_level:
            return title
    return "New Recruit"


def xp_required_for_level(level: int) -> int:
    return 100 + ((level - 1) * 50)


def get_progress_bar(current_xp: int, required_xp: int, length: int = 12) -> str:
    if required_xp <= 0:
        return "█" * length
    progress = min(max(current_xp / required_xp, 0), 1)
    filled = int(progress * length)
    return "█" * filled + "░" * (length - filled)


def format_seconds(seconds: int) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def utc_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class WattsonMastery(commands.Cog):
    """Complete Wattson-specific progression, training, challenges, and setup library."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = DB_FILE
        self._setup_database()

    def _get_connection(self):
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        return conn

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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS wattson_daily (
                    user_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    last_daily TEXT DEFAULT '',
                    streak INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, guild_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS wattson_challenges (
                    user_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    challenge_date TEXT NOT NULL,
                    challenge TEXT NOT NULL,
                    completed INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, guild_id, challenge_date)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS wattson_stats (
                    user_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    practices INTEGER DEFAULT 0,
                    tips INTEGER DEFAULT 0,
                    dailies INTEGER DEFAULT 0,
                    challenges_completed INTEGER DEFAULT 0,
                    drills_completed INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, guild_id)
                )
                """
            )
            conn.commit()

    def _get_mastery(self, user_id: int, guild_id: int):
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT xp, level, last_practice FROM wattson_mastery WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id),
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO wattson_mastery (user_id, guild_id, xp, level, last_practice) VALUES (?, ?, 0, 1, 0)",
                    (user_id, guild_id),
                )
                conn.commit()
                return 0, 1, 0
            return row["xp"], row["level"], row["last_practice"]

    def _save_mastery(self, user_id, guild_id, xp, level, last_practice=None):
        if last_practice is None:
            _, _, last_practice = self._get_mastery(user_id, guild_id)
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO wattson_mastery (user_id, guild_id, xp, level, last_practice)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, guild_id) DO UPDATE SET
                    xp = excluded.xp,
                    level = excluded.level,
                    last_practice = excluded.last_practice
                """,
                (user_id, guild_id, xp, level, last_practice),
            )
            conn.commit()

    def _increment_stat(self, user_id: int, guild_id: int, field: str, amount: int = 1):
        allowed = {"practices", "tips", "dailies", "challenges_completed", "drills_completed"}
        if field not in allowed:
            return
        with self._get_connection() as conn:
            conn.execute(
                f"""
                INSERT INTO wattson_stats (user_id, guild_id, {field}) VALUES (?, ?, ?)
                ON CONFLICT(user_id, guild_id) DO UPDATE SET {field} = {field} + excluded.{field}
                """,
                (user_id, guild_id, amount),
            )
            conn.commit()

    async def _award_xp(self, user_id: int, guild_id: int, amount: int):
        xp, level, last_practice = self._get_mastery(user_id, guild_id)
        old_level = level
        xp += amount
        levels_gained = 0

        while xp >= xp_required_for_level(level):
            xp -= xp_required_for_level(level)
            level += 1
            levels_gained += 1

        self._save_mastery(user_id, guild_id, xp, level, last_practice)
        await self._award_milestone_achievements(user_id, old_level, level)
        return xp, level, levels_gained

    async def _award_milestone_achievements(self, user_id, old_level, new_level):
        for milestone, achievement_name in MILESTONE_ACHIEVEMENTS.items():
            if old_level < milestone <= new_level:
                try:
                    unlock(user_id, achievement_name)
                except Exception as exc:
                    print(f"[Wattson Mastery] Achievement unlock failed for {user_id}: {exc}")

    def _cooldown_remaining(self, timestamp: float, cooldown: int) -> int:
        if not timestamp:
            return 0
        return max(0, int(cooldown - (time.time() - timestamp)))

    @commands.group(name="wattson", invoke_without_command=True, case_insensitive=True)
    async def wattson(self, ctx: commands.Context):
        """Wattson Mastery hub."""
        if ctx.invoked_subcommand is not None:
            return

        embed = discord.Embed(
            title="⚡ Wattson Mastery",
            description="Your complete Wattson training and progression system.",
            color=PINK,
        )
        embed.add_field(
            name="📈 Progression",
            value=(
                "`!wattson mastery` — Your level and XP\n"
                "`!wattson progress` — Detailed progress\n"
                "`!wattson leaderboard` — Server rankings\n"
                "`!wattson stats` — Your mastery statistics\n"
                "`!wattson title` — View your current title"
            ),
            inline=False,
        )
        embed.add_field(
            name="🎯 Training",
            value=(
                "`!wattson practice` — Earn practice XP\n"
                "`!wattson daily` — Daily training reward\n"
                "`!wattson challenge` — Get today's challenge\n"
                "`!wattson complete` — Complete today's challenge\n"
                "`!wattson drills` — Browse training drills\n"
                "`!wattson drill <name>` — Start a drill"
            ),
            inline=False,
        )
        embed.add_field(
            name="📚 Knowledge",
            value=(
                "`!wattson tip` — Random tip\n"
                "`!wattson setup` — Setup library\n"
                "`!wattson setup <category>` — Browse a category"
            ),
            inline=False,
        )
        embed.set_footer(text="Grid Guardian • Wattson Mastery")
        await ctx.send(embed=embed)

    @wattson.command(name="mastery")
    async def mastery(self, ctx: commands.Context, member: discord.Member = None):
        """Show Wattson mastery for a member."""
        target = member or ctx.author
        xp, level, _ = self._get_mastery(target.id, ctx.guild.id)
        required = xp_required_for_level(level)

        next_title = None
        for required_level, title in sorted(TITLES):
            if required_level > level:
                next_title = (required_level, title)
                break

        embed = discord.Embed(title=f"⚡ {target.display_name}'s Wattson Mastery", color=PINK)
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Level", value=f"**{level}**\n{get_title(level)}", inline=True)
        embed.add_field(name="XP", value=f"**{xp} / {required}**\n{get_progress_bar(xp, required)}", inline=True)
        embed.add_field(
            name="Next Title",
            value=(f"Level {next_title[0]} — {next_title[1]}" if next_title else "👑 Maximum title milestone"),
            inline=False,
        )
        embed.set_footer(text="Train consistently to climb the Wattson mastery ladder.")
        await ctx.send(embed=embed)

    @wattson.command(name="progress")
    async def progress(self, ctx: commands.Context):
        """Show detailed Wattson progression."""
        xp, level, _ = self._get_mastery(ctx.author.id, ctx.guild.id)
        required = xp_required_for_level(level)
        with self._get_connection() as conn:
            stats = conn.execute(
                "SELECT practices, tips, dailies, challenges_completed, drills_completed FROM wattson_stats WHERE user_id = ? AND guild_id = ?",
                (ctx.author.id, ctx.guild.id),
            ).fetchone()
            daily = conn.execute(
                "SELECT streak FROM wattson_daily WHERE user_id = ? AND guild_id = ?",
                (ctx.author.id, ctx.guild.id),
            ).fetchone()

        practices = stats["practices"] if stats else 0
        tips = stats["tips"] if stats else 0
        dailies = stats["dailies"] if stats else 0
        challenges = stats["challenges_completed"] if stats else 0
        drills = stats["drills_completed"] if stats else 0
        streak = daily["streak"] if daily else 0

        embed = discord.Embed(title="📊 Wattson Progress", color=PINK)
        embed.add_field(name="Mastery", value=f"Level **{level}** — {get_title(level)}", inline=False)
        embed.add_field(name="Current XP", value=f"{xp} / {required}\n{get_progress_bar(xp, required)}", inline=False)
        embed.add_field(name="🔥 Daily Streak", value=f"**{streak}** day(s)", inline=True)
        embed.add_field(name="⚡ Practices", value=str(practices), inline=True)
        embed.add_field(name="🎯 Challenges", value=str(challenges), inline=True)
        embed.add_field(name="🏋️ Drills", value=str(drills), inline=True)
        embed.add_field(name="💡 Tips Viewed", value=str(tips), inline=True)
        embed.add_field(name="📅 Dailies Claimed", value=str(dailies), inline=True)
        await ctx.send(embed=embed)

    @wattson.command(name="stats")
    async def stats(self, ctx: commands.Context):
        """Show Wattson training statistics."""
        await self.progress(ctx)

    @wattson.command(name="title")
    async def title(self, ctx: commands.Context, member: discord.Member = None):
        """Show a member's current Wattson title."""
        target = member or ctx.author
        _, level, _ = self._get_mastery(target.id, ctx.guild.id)
        embed = discord.Embed(
            title="⚡ Wattson Title",
            description=f"**{target.display_name}**\n\n## {get_title(level)}\nLevel {level}",
            color=PINK,
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        await ctx.send(embed=embed)

    @wattson.command(name="leaderboard", aliases=["lb", "top"])
    async def leaderboard(self, ctx: commands.Context):
        """Show the server's Wattson mastery leaderboard."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT user_id, xp, level FROM wattson_mastery WHERE guild_id = ? ORDER BY level DESC, xp DESC LIMIT 10",
                (ctx.guild.id,),
            ).fetchall()

        if not rows:
            await ctx.send("⚡ No Wattson mastery players yet. Use `!wattson practice` to start!")
            return

        lines = []
        for index, row in enumerate(rows, start=1):
            member = ctx.guild.get_member(row["user_id"])
            name = member.display_name if member else f"User {row['user_id']}"
            lines.append(f"**{index}.** {name} — Level **{row['level']}** • {get_title(row['level'])} • {row['xp']} XP")

        embed = discord.Embed(title="🏆 Wattson Mastery Leaderboard", description="\n".join(lines), color=GOLD)
        embed.set_footer(text="Top 10 Wattson mastery levels in this server")
        await ctx.send(embed=embed)

    @wattson.command(name="practice")
    async def practice(self, ctx: commands.Context):
        """Complete a practice session and earn mastery XP."""
        xp, level, last_practice = self._get_mastery(ctx.author.id, ctx.guild.id)
        remaining = self._cooldown_remaining(last_practice, PRACTICE_COOLDOWN)
        if remaining:
            embed = discord.Embed(
                title="⏳ Practice On Cooldown",
                description=f"You can practice again in **{format_seconds(remaining)}**.",
                color=ORANGE,
            )
            await ctx.send(embed=embed)
            return

        earned = random.randint(50, 100)
        xp, level, levels_gained = await self._award_xp(ctx.author.id, ctx.guild.id, earned)
        self._save_mastery(ctx.author.id, ctx.guild.id, xp, level, time.time())
        self._increment_stat(ctx.author.id, ctx.guild.id, "practices")

        embed = discord.Embed(
            title="⚡ Practice Complete!",
            description=f"You earned **+{earned} XP**.",
            color=PINK,
        )
        embed.add_field(name="Mastery", value=f"Level **{level}** — {get_title(level)}", inline=True)
        embed.add_field(name="XP", value=f"**{xp} / {xp_required_for_level(level)}**", inline=True)
        if levels_gained:
            embed.add_field(name="🎉 Level Up!", value=f"You gained **{levels_gained}** level(s)!", inline=False)
        embed.set_footer(text="Practice cooldown: 12 hours")
        await ctx.send(embed=embed)

    @wattson.command(name="daily")
    async def daily(self, ctx: commands.Context):
        """Claim the daily Wattson training reward."""
        today = utc_date()
        yesterday = datetime.now(timezone.utc).date().fromordinal(datetime.now(timezone.utc).date().toordinal() - 1).isoformat()

        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT last_daily, streak FROM wattson_daily WHERE user_id = ? AND guild_id = ?",
                (ctx.author.id, ctx.guild.id),
            ).fetchone()

            if row and row["last_daily"] == today:
                await ctx.send("📅 You already claimed today's Wattson training reward. Come back tomorrow!")
                return

            old_streak = row["streak"] if row else 0
            new_streak = old_streak + 1 if row and row["last_daily"] == yesterday else 1
            conn.execute(
                """
                INSERT INTO wattson_daily (user_id, guild_id, last_daily, streak)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, guild_id) DO UPDATE SET
                    last_daily = excluded.last_daily,
                    streak = excluded.streak
                """,
                (ctx.author.id, ctx.guild.id, today, new_streak),
            )
            conn.commit()

        earned = min(50 + ((new_streak - 1) * 5), 150)
        xp, level, levels_gained = await self._award_xp(ctx.author.id, ctx.guild.id, earned)
        self._increment_stat(ctx.author.id, ctx.guild.id, "dailies")

        embed = discord.Embed(title="📅 Daily Wattson Training", description=f"You earned **+{earned} XP**.", color=GOLD)
        embed.add_field(name="🔥 Streak", value=f"**{new_streak} day(s)**", inline=True)
        embed.add_field(name="Mastery", value=f"Level **{level}** — {get_title(level)}", inline=True)
        if levels_gained:
            embed.add_field(name="🎉 Level Up!", value=f"You gained **{levels_gained}** level(s)!", inline=False)
        embed.set_footer(text="Come back tomorrow to keep your streak alive.")
        await ctx.send(embed=embed)

    @wattson.command(name="streak")
    async def streak(self, ctx: commands.Context):
        """Show your daily Wattson training streak."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT streak, last_daily FROM wattson_daily WHERE user_id = ? AND guild_id = ?",
                (ctx.author.id, ctx.guild.id),
            ).fetchone()
        streak = row["streak"] if row else 0
        last = row["last_daily"] if row else "Never"
        await ctx.send(f"🔥 **{ctx.author.display_name}** has a Wattson training streak of **{streak} day(s)**. Last claim: **{last}**")

    @wattson.command(name="challenge", aliases=["quest"])
    async def challenge(self, ctx: commands.Context):
        """Show today's Wattson challenge."""
        today = utc_date()
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT challenge, completed FROM wattson_challenges WHERE user_id = ? AND guild_id = ? AND challenge_date = ?",
                (ctx.author.id, ctx.guild.id, today),
            ).fetchone()

            if row:
                challenge_text = row["challenge"]
                completed = bool(row["completed"])
                reward = next((r for n, d, r in CHALLENGES if n == challenge_text), 75)
            else:
                name, description, reward = random.choice(CHALLENGES)
                challenge_text = name
                conn.execute(
                    "INSERT INTO wattson_challenges (user_id, guild_id, challenge_date, challenge, completed) VALUES (?, ?, ?, ?, 0)",
                    (ctx.author.id, ctx.guild.id, today, challenge_text),
                )
                conn.commit()
                completed = False

        challenge_description = next((d for n, d, r in CHALLENGES if n == challenge_text), "Complete the challenge in-game.")
        embed = discord.Embed(title="🎯 Today's Wattson Challenge", description=f"## {challenge_text}\n{challenge_description}", color=PINK)
        embed.add_field(name="Reward", value=f"**+{reward} XP**", inline=True)
        embed.add_field(name="Status", value="✅ Completed" if completed else "🟡 In Progress", inline=True)
        if not completed:
            embed.set_footer(text="When you finish it, use !wattson complete")
        await ctx.send(embed=embed)

    @wattson.command(name="complete", aliases=["finish"])
    async def complete(self, ctx: commands.Context):
        """Mark today's Wattson challenge as completed and receive its XP reward."""
        today = utc_date()
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT challenge, completed FROM wattson_challenges WHERE user_id = ? AND guild_id = ? AND challenge_date = ?",
                (ctx.author.id, ctx.guild.id, today),
            ).fetchone()
            if not row:
                await ctx.send("🎯 You don't have a challenge yet. Use `!wattson challenge` first.")
                return
            if row["completed"]:
                await ctx.send("✅ You've already completed today's Wattson challenge.")
                return
            challenge_name = row["challenge"]
            reward = next((r for n, d, r in CHALLENGES if n == challenge_name), 75)
            conn.execute(
                "UPDATE wattson_challenges SET completed = 1 WHERE user_id = ? AND guild_id = ? AND challenge_date = ?",
                (ctx.author.id, ctx.guild.id, today),
            )
            conn.commit()

        xp, level, levels_gained = await self._award_xp(ctx.author.id, ctx.guild.id, reward)
        self._increment_stat(ctx.author.id, ctx.guild.id, "challenges_completed")

        embed = discord.Embed(title="🎯 Challenge Complete!", description=f"**{challenge_name}**\n\nYou earned **+{reward} XP**.", color=GREEN)
        embed.add_field(name="Mastery", value=f"Level **{level}** — {get_title(level)}", inline=True)
        embed.add_field(name="XP", value=f"**{xp} / {xp_required_for_level(level)}**", inline=True)
        if levels_gained:
            embed.add_field(name="🎉 Level Up!", value=f"You gained **{levels_gained}** level(s)!", inline=False)
        await ctx.send(embed=embed)

    @wattson.command(name="drills")
    async def drills(self, ctx: commands.Context):
        """List Wattson training drills."""
        lines = []
        for key, drill in DRILLS.items():
            lines.append(f"`{key}` — **{drill['name']}** • {drill['difficulty']}\n{drill['description']}")
        embed = discord.Embed(title="🏋️ Wattson Training Drills", description="\n\n".join(lines), color=BLUE)
        embed.set_footer(text="Use !wattson drill <name> to start one.")
        await ctx.send(embed=embed)

    @wattson.command(name="drill")
    async def drill(self, ctx: commands.Context, *, drill_name: str = None):
        """Start a named Wattson training drill."""
        if not drill_name:
            await ctx.send("🏋️ Choose a drill with `!wattson drills`.")
            return

        key = drill_name.lower().strip().replace(" ", "-")
        drill_data = DRILLS.get(key)
        if not drill_data:
            await ctx.send("❌ I couldn't find that drill. Use `!wattson drills` to see the available drills.")
            return

        embed = discord.Embed(title=drill_data["name"], description=drill_data["description"], color=PINK)
        embed.add_field(name="Difficulty", value=drill_data["difficulty"], inline=True)
        embed.add_field(name="Completion", value="Practice it in-game, then use `!wattson drilldone`.", inline=True)
        await ctx.send(embed=embed)

    @wattson.command(name="drilldone", aliases=["drillcomplete"])
    async def drilldone(self, ctx: commands.Context):
        """Record a completed Wattson drill."""
        earned = random.randint(20, 50)
        xp, level, levels_gained = await self._award_xp(ctx.author.id, ctx.guild.id, earned)
        self._increment_stat(ctx.author.id, ctx.guild.id, "drills_completed")

        embed = discord.Embed(title="🏋️ Drill Complete!", description=f"You earned **+{earned} XP**.", color=GREEN)
        embed.add_field(name="Mastery", value=f"Level **{level}** — {get_title(level)}", inline=True)
        embed.add_field(name="XP", value=f"**{xp} / {xp_required_for_level(level)}**", inline=True)
        if levels_gained:
            embed.add_field(name="🎉 Level Up!", value=f"You gained **{levels_gained}** level(s)!", inline=False)
        await ctx.send(embed=embed)

    @wattson.command(name="tip")
    async def tip(self, ctx: commands.Context):
        """Send a random Wattson gameplay tip."""
        self._increment_stat(ctx.author.id, ctx.guild.id, "tips")
        embed = discord.Embed(title="⚡ Wattson Tip", description=random.choice(TIPS), color=PINK)
        embed.set_footer(text="Grid Guardian • Wattson Mastery")
        await ctx.send(embed=embed)

    @wattson.command(name="setup", aliases=["setups", "library"])
    async def setup_library(self, ctx: commands.Context, category: str = None):
        """Browse the Wattson setup library."""
        if not category:
            lines = [f"{data['emoji']} `{key}` — **{data['name']}**\n{data['description']}" for key, data in SETUP_CATEGORIES.items()]
            embed = discord.Embed(title="📚 Wattson Setup Library", description="\n\n".join(lines), color=PINK)
            embed.set_footer(text="Use !wattson setup <category> to browse a category.")
            await ctx.send(embed=embed)
            return

        key = category.lower().strip().replace(" ", "")
        aliases = {
            "door": "doors",
            "building": "buildings",
            "stair": "stairs",
            "choke": "chokes",
            "pylonpositions": "pylon",
            "pylons": "pylon",
            "rank": "ranked",
        }
        key = aliases.get(key, key)
        if key not in SETUP_CATEGORIES:
            await ctx.send("❌ That setup category doesn't exist. Use `!wattson setup` to see the categories.")
            return

        data = SETUP_CATEGORIES[key]
        guides = SETUP_GUIDES.get(key, [])
        lines = [f"### {name}\n{description}\n**Difficulty:** {difficulty}" for name, description, difficulty in guides]
        embed = discord.Embed(title=f"{data['emoji']} {data['name']}", description="\n\n".join(lines), color=PINK)
        embed.set_footer(text="These are training concepts; exact placements depend on the location and current game state.")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(WattsonMastery(bot))
