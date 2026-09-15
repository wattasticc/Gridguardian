import random
import sqlite3
import time
from datetime import datetime, timezone

import discord
from discord.ext import commands


DB_PATH = "gridguardian.db"
EMBED_COLOR = discord.Color.from_rgb(255, 170, 220)

# ------------------------------------------------------------------
# Coaching content
# ------------------------------------------------------------------

COACH_TOPICS = {
    "wattson": {
        "title": "⚡ Wattson Coaching",
        "lessons": [
            ("Fence Fundamentals", "Place fences to control the route your opponent wants to take, not simply where they are standing."),
            ("Door Fights", "Fence doors when it creates a meaningful decision for the enemy. Keep enough space to fight without trapping yourself."),
            ("Building Holds", "Use fences to create layers of defense. Your strongest position is usually one where enemies must cross a predictable route."),
            ("Pylon Value", "Think of Interception Pylon as fight infrastructure: protect it when possible and use its utility to stabilize a position."),
            ("Aggressive Fencing", "Fences can create temporary space during a push. Place them where they force hesitation while your team takes the next piece of cover."),
            ("Node Discipline", "Avoid spending every node immediately. Keep a mental reserve so you can rebuild after an enemy destroys part of your setup."),
        ],
    },
    "fences": {
        "title": "🔌 Fence Coaching",
        "lessons": [
            ("Placement", "Prioritize routes, doors, stairs, corners, and narrow transitions where crossing the fence costs the enemy something."),
            ("Speed", "Practice placing nodes without stopping your movement. The goal is to make fencing part of your normal combat rhythm."),
            ("Crossing", "Learn which fence lines protect you while still leaving you a safe route to reposition."),
            ("Layering", "Two simple fence layers that protect different approaches can be more useful than one complicated setup."),
            ("Fight Awareness", "Do not stare at your fences during a fight. Once they are doing their job, return your attention to enemy movement."),
        ],
    },
    "movement": {
        "title": "🏃 Movement Coaching",
        "lessons": [
            ("Cover First", "Movement is most useful when it helps you reach better cover, break line of sight, or change the angle of a fight."),
            ("Strafing", "Use controlled strafes rather than moving randomly. Your goal is to make your movement harder to read while keeping your aim stable."),
            ("Repositioning", "After dealing damage, consider whether changing your angle gives you more value than immediately repeating the same peek."),
            ("Height", "High ground is useful because it can improve information and angles, but do not abandon safe cover just to gain height."),
        ],
    },
    "fights": {
        "title": "⚔️ Fight Coaching",
        "lessons": [
            ("Opening Damage", "After opening damage, identify whether your team has a temporary advantage. Use that window deliberately."),
            ("Resetting", "If your team loses the first exchange, create space and reset instead of repeatedly taking the same losing angle."),
            ("Focus Fire", "A coordinated 2v1 is usually easier to convert than several isolated 1v1s."),
            ("Space", "Think about the next piece of playable space you need before committing to a fight."),
            ("Third Parties", "Before finishing a long fight, check whether another team can realistically reach your position."),
        ],
    },
    "ranked": {
        "title": "🏆 Ranked Coaching",
        "lessons": [
            ("Rotation", "Rotate based on your team's resources, zone information, and available cover rather than following a route automatically."),
            ("Position", "A defensible position with multiple exits can be more valuable than a slightly better-looking spot with no escape route."),
            ("RP Decisions", "Do not let a single bad fight dictate the rest of the match. Reassess your resources and position after every major engagement."),
            ("End Game", "In late zones, preserve playable space and avoid unnecessary movement that exposes your team."),
            ("Team Play", "Communicate what you need: cover, a rotation, a reset, or a push. Clear calls reduce hesitation."),
        ],
    },
}

SCENARIOS = [
    {
        "title": "Door Pressure",
        "question": "Your team is holding a building. An enemy squad is outside the main door and you have a safe second exit. What is the best general approach?",
        "options": {
            "a": "Open the door and swing the entire team immediately.",
            "b": "Use the building and fences to control entrances while watching for a coordinated push.",
            "c": "Everyone stand directly on the door.",
            "d": "Leave the building with no information.",
        },
        "answer": "b",
        "explanation": "The building gives your team structure. Use your defensive setup to control approaches while maintaining an exit and gathering information.",
        "xp": 25,
    },
    {
        "title": "Bad First Trade",
        "question": "Your teammate takes heavy damage during the opening exchange. What should you generally prioritize?",
        "options": {
            "a": "Keep peeking the same angle.",
            "b": "Create space, stabilize, and reassess the fight.",
            "c": "Split away from the team.",
            "d": "Ignore the damage and full-send.",
        },
        "answer": "b",
        "explanation": "A lost opening trade changes the fight. A reset can restore your team's resources and prevent the enemy from converting their advantage.",
        "xp": 25,
    },
    {
        "title": "Late-Zone Fences",
        "question": "Your squad reaches a strong late-game position. What is a useful Wattson priority?",
        "options": {
            "a": "Spend every node immediately.",
            "b": "Build layered control around the approaches that matter most while keeping options for rebuilding.",
            "c": "Place every fence in the open.",
            "d": "Ignore the zone and chase damage.",
        },
        "answer": "b",
        "explanation": "Late-game value comes from controlling meaningful approaches and preserving the ability to adapt when the setup is damaged.",
        "xp": 30,
    },
    {
        "title": "Third-Party Risk",
        "question": "Your squad has a knock, but the fight has already taken a long time. What should you consider before committing?",
        "options": {
            "a": "Only the knocked player.",
            "b": "Whether another team can reach you and what resources you have left.",
            "c": "How many fences you have placed.",
            "d": "Nothing; always push.",
        },
        "answer": "b",
        "explanation": "A knock is valuable, but converting it is not always worth exposing your squad to a third party or an unfavorable position.",
        "xp": 30,
    },
    {
        "title": "Node Reserve",
        "question": "You are about to take a long building fight. Why might keeping a node available matter?",
        "options": {
            "a": "It does not matter.",
            "b": "You may need it to rebuild or create a new route after part of your setup is destroyed.",
            "c": "It increases weapon damage.",
            "d": "It changes your shield color.",
        },
        "answer": "b",
        "explanation": "Node flexibility lets you adapt after the enemy breaks your original setup instead of leaving you with no defensive options.",
        "xp": 25,
    },
]

DRILLS = {
    "fence-speed": {
        "name": "Fence Speed",
        "description": "In the firing range, repeatedly create short fence lines while moving between cover points. Focus on smooth placement rather than rushing.",
        "duration": "5–10 minutes",
        "focus": "Movement + node placement",
        "xp": 20,
    },
    "door": {
        "name": "Door Control",
        "description": "Practice setting a door fence, moving to a safe fighting position, and keeping an exit available.",
        "duration": "5–10 minutes",
        "focus": "Door fights",
        "xp": 20,
    },
    "stair": {
        "name": "Stair Control",
        "description": "Practice fencing stair approaches from multiple angles and identify which route you would use to retreat.",
        "duration": "5–10 minutes",
        "focus": "Vertical defense",
        "xp": 20,
    },
    "choke": {
        "name": "Choke Control",
        "description": "Find narrow transitions and practice creating a fence line that makes the route awkward without blocking your own rotation.",
        "duration": "5–10 minutes",
        "focus": "Area denial",
        "xp": 20,
    },
    "emergency": {
        "name": "Emergency Fence",
        "description": "Practice quickly creating a small defensive barrier after moving into a new piece of cover.",
        "duration": "5 minutes",
        "focus": "Fight stabilization",
        "xp": 25,
    },
    "rotation": {
        "name": "Rotation Drill",
        "description": "Choose a building, identify two exits, and practice moving between them while maintaining a defensive setup.",
        "duration": "10 minutes",
        "focus": "Positioning",
        "xp": 25,
    },
    "pylon": {
        "name": "Pylon Drill",
        "description": "Practice choosing safe Pylon locations that support the team without unnecessarily exposing the utility.",
        "duration": "10 minutes",
        "focus": "Utility placement",
        "xp": 25,
    },
    "mindgame": {
        "name": "Mindgame Drill",
        "description": "For each building you enter, predict which entrance an enemy is most likely to use and build your setup around that prediction.",
        "duration": "10 minutes",
        "focus": "Prediction",
        "xp": 25,
    },
}

SETUPS = {
    "doors": [
        ("Door denial", "Fence a meaningful entrance so an enemy must reveal their intention before committing."),
        ("Double-door hold", "Cover the two most important entrances while keeping a safe internal route for your team."),
        ("Door peek", "Use a fence to make a doorway dangerous while you fight from a nearby angle rather than standing on the threshold."),
    ],
    "buildings": [
        ("Layered hold", "Create an outer layer that slows an approach and an inner layer that protects your strongest fighting position."),
        ("Retreat route", "Keep one route intentionally usable so your squad can reset without destroying its own setup."),
        ("Crossfire hold", "Place control so your teammates can watch different approaches without isolating themselves."),
    ],
    "stairs": [
        ("Stair denial", "Fence a stair route that opponents are likely to use while maintaining a safe route for your squad."),
        ("Vertical fallback", "Keep a second position available in case the first stair line is destroyed."),
    ],
    "chokes": [
        ("Narrow choke", "Use a tight transition to make an enemy choose between taking the fence or changing their route."),
        ("Rotation choke", "Control the route that matters most to your team's next rotation rather than fencing every possible path."),
    ],
    "defense": [
        ("Layered defense", "Use multiple simple defensive layers instead of relying on one setup."),
        ("Anchor position", "Identify the position your team can safely fight from and build around it."),
        ("Reset space", "Protect an area where a damaged teammate can safely recover."),
    ],
    "pylon": [
        ("Protected Pylon", "Place the Pylon where it provides value while using nearby cover or structures to reduce unnecessary exposure."),
        ("Fight utility", "Think about what your team needs the Pylon to accomplish before placing it."),
    ],
    "rotation": [
        ("Two-exit hold", "Build around a position with two usable exits so your squad can adapt when the zone or enemy changes."),
        ("Zone transition", "When rotating, preserve enough utility to rebuild after reaching the next playable position."),
    ],
    "ranked": [
        ("Safe hold", "Prioritize defensible cover, information, and an exit over a flashy but isolated position."),
        ("End-game setup", "Use the smallest amount of setup necessary to control the approaches that actually matter."),
        ("Resource discipline", "Avoid wasting nodes and utility before the final position is established."),
    ],
}

DAILY_CHALLENGES = [
    ("Fence Planner", "Complete 1 Fence Speed drill.", 35, "fence-speed"),
    ("Door Specialist", "Complete 1 Door Control drill.", 35, "door"),
    ("Positioning", "Complete 1 Rotation drill.", 35, "rotation"),
    ("Pylon Sense", "Complete 1 Pylon drill.", 35, "pylon"),
    ("Defense", "Complete 1 Emergency Fence drill.", 35, "emergency"),
    ("Prediction", "Complete 1 Mindgame drill.", 35, "mindgame"),
]

TITLES = [
    (1, "New Recruit"),
    (5, "Electrical Apprentice"),
    (10, "Fence Engineer"),
    (20, "Static Specialist"),
    (30, "Power Grid Expert"),
    (50, "Wattson Main"),
    (75, "Fence Master"),
    (100, "Grid Guardian"),
]


def utc_now():
    return datetime.now(timezone.utc)


def ensure_tables():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS wattson_coach_stats (
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                scenarios_completed INTEGER DEFAULT 0,
                drills_completed INTEGER DEFAULT 0,
                lessons_viewed INTEGER DEFAULT 0,
                coach_xp INTEGER DEFAULT 0,
                current_streak INTEGER DEFAULT 0,
                best_streak INTEGER DEFAULT 0,
                last_daily TEXT,
                daily_challenge TEXT,
                daily_completed TEXT,
                PRIMARY KEY (user_id, guild_id)
            )
            """
        )
        conn.commit()


def get_stats(user_id, guild_id):
    ensure_tables()
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            """
            SELECT scenarios_completed, drills_completed, lessons_viewed,
                   coach_xp, current_streak, best_streak, last_daily,
                   daily_challenge, daily_completed
            FROM wattson_coach_stats
            WHERE user_id=? AND guild_id=?
            """,
            (user_id, guild_id),
        ).fetchone()

        if row is None:
            conn.execute(
                """
                INSERT INTO wattson_coach_stats
                (user_id, guild_id)
                VALUES (?, ?)
                """,
                (user_id, guild_id),
            )
            conn.commit()
            return (0, 0, 0, 0, 0, 0, None, None, None)

        return row


def update_stats(user_id, guild_id, **values):
    if not values:
        return

    allowed = {
        "scenarios_completed",
        "drills_completed",
        "lessons_viewed",
        "coach_xp",
        "current_streak",
        "best_streak",
        "last_daily",
        "daily_challenge",
        "daily_completed",
    }

    values = {key: value for key, value in values.items() if key in allowed}
    if not values:
        return

    ensure_tables()

    assignments = ", ".join(f"{key}=?" for key in values)
    params = list(values.values()) + [user_id, guild_id]

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            f"""
            UPDATE wattson_coach_stats
            SET {assignments}
            WHERE user_id=? AND guild_id=?
            """,
            params,
        )
        conn.commit()


def coach_level(xp):
    # Gentle progression: every 100 XP is another coach level.
    return min(100, (xp // 100) + 1)


def coach_title(level):
    if level >= 50:
        return "Master Coach"
    if level >= 30:
        return "Advanced Coach"
    if level >= 15:
        return "Tactical Coach"
    if level >= 5:
        return "Apprentice Coach"
    return "Rookie Coach"


def mastery_award(user_id, guild_id, xp):
    """Award coach XP and, when possible, also award Wattson Mastery XP."""
    scenarios, drills, lessons, coach_xp, streak, best, last_daily, challenge, completed = get_stats(
        user_id, guild_id
    )
    new_xp = coach_xp + xp
    update_stats(user_id, guild_id, coach_xp=new_xp)

    # Integrate with the existing Wattson Mastery cog without making it a hard dependency.
    try:
        from cogs.wattsonmastery import WattsonMastery

        cog = None
        # This is intentionally handled by the caller when a bot instance is available.
        return new_xp, cog
    except Exception:
        return new_xp, None


class ApexCoach(commands.Cog):
    """Interactive Apex/Wattson coaching system for Grid Guardian."""

    def __init__(self, bot):
        self.bot = bot
        ensure_tables()

    # --------------------------------------------------------------
    # Main group
    # --------------------------------------------------------------

    @commands.group(
        name="coach",
        invoke_without_command=True,
        case_insensitive=True,
    )
    async def coach(self, ctx):
        """Open the Apex Coach."""
        embed = discord.Embed(
            title="🎯 Grid Guardian — Apex Coach",
            description=(
                "Train your decision-making, positioning, and Wattson fundamentals.\n\n"
                "**Commands**\n"
                "`!coach topic` — Browse coaching topics\n"
                "`!coach lesson <topic>` — Get a lesson\n"
                "`!coach scenario` — Take a decision-making scenario\n"
                "`!coach answer <a/b/c/d>` — Answer the active scenario\n"
                "`!coach drills` — Browse training drills\n"
                "`!coach drill <name>` — Start a drill\n"
                "`!coach complete` — Complete your active drill\n"
                "`!coach daily` — Claim your daily coaching reward\n"
                "`!coach stats` — View coaching statistics\n"
                "`!coach progress` — View coaching progress\n"
            ),
            color=EMBED_COLOR,
        )
        embed.set_footer(text="Grid Guardian • Apex Coaching")
        await ctx.send(embed=embed)

    # --------------------------------------------------------------
    # Topic system
    # --------------------------------------------------------------

    @coach.command(name="topic", aliases=["topics"])
    async def topics(self, ctx):
        """List available coaching topics."""
        embed = discord.Embed(
            title="📚 Coaching Topics",
            description="Choose a topic with `!coach lesson <topic>`.",
            color=EMBED_COLOR,
        )

        for key, data in COACH_TOPICS.items():
            lesson_names = ", ".join(name for name, _ in data["lessons"][:3])
            embed.add_field(
                name=f"`{key}` — {data['title']}",
                value=lesson_names,
                inline=False,
            )

        await ctx.send(embed=embed)

    @coach.command(name="lesson")
    async def lesson(self, ctx, topic: str = None):
        """Show a random lesson from a topic."""
        if not topic:
            return await ctx.send("❌ Use `!coach lesson <topic>`. Try `!coach topics`.")

        topic = topic.lower()
        data = COACH_TOPICS.get(topic)

        if not data:
            return await ctx.send(
                f"❌ I don't recognize `{topic}`. Use `!coach topics` to see the available topics."
            )

        name, text = random.choice(data["lessons"])

        scenarios, drills, lessons_viewed, coach_xp, streak, best, last_daily, challenge, completed = get_stats(
            ctx.author.id, ctx.guild.id
        )
        update_stats(
            ctx.author.id,
            ctx.guild.id,
            lessons_viewed=lessons_viewed + 1,
        )

        embed = discord.Embed(
            title=data["title"],
            description=text,
            color=EMBED_COLOR,
        )
        embed.add_field(name="📖 Lesson", value=name, inline=False)
        embed.add_field(name="⭐ Coach XP", value="+5", inline=True)
        embed.set_footer(text="Keep practicing — knowledge becomes useful when you apply it.")
        await ctx.send(embed=embed)

        # Five XP is intentionally small for viewing content.
        mastery_award(ctx.author.id, ctx.guild.id, 5)

    # --------------------------------------------------------------
    # Scenario system
    # --------------------------------------------------------------

    @coach.command(name="scenario", aliases=["scen"])
    async def scenario(self, ctx):
        """Give the player a decision-making scenario."""
        scenario = random.choice(SCENARIOS)

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS wattson_active_scenarios (
                    user_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    scenario_id INTEGER NOT NULL,
                    created_at REAL NOT NULL,
                    PRIMARY KEY(user_id, guild_id)
                )
                """
            )
            scenario_id = SCENARIOS.index(scenario)
            conn.execute(
                """
                INSERT INTO wattson_active_scenarios
                (user_id, guild_id, scenario_id, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, guild_id)
                DO UPDATE SET
                    scenario_id=excluded.scenario_id,
                    created_at=excluded.created_at
                """,
                (
                    ctx.author.id,
                    ctx.guild.id,
                    scenario_id,
                    time.time(),
                ),
            )
            conn.commit()

        embed = discord.Embed(
            title=f"🧠 Scenario: {scenario['title']}",
            description=scenario["question"],
            color=EMBED_COLOR,
        )

        for letter, text in scenario["options"].items():
            embed.add_field(
                name=f"**{letter.upper()}**",
                value=text,
                inline=False,
            )

        embed.set_footer(text="Answer with !coach answer a/b/c/d")
        await ctx.send(embed=embed)

    @coach.command(name="answer")
    async def answer(self, ctx, choice: str = None):
        """Answer the active scenario."""
        if not choice or choice.lower() not in {"a", "b", "c", "d"}:
            return await ctx.send("❌ Answer with `a`, `b`, `c`, or `d`.")

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS wattson_active_scenarios (
                    user_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    scenario_id INTEGER NOT NULL,
                    created_at REAL NOT NULL,
                    PRIMARY KEY(user_id, guild_id)
                )
                """
            )
            row = conn.execute(
                """
                SELECT scenario_id, created_at
                FROM wattson_active_scenarios
                WHERE user_id=? AND guild_id=?
                """,
                (ctx.author.id, ctx.guild.id),
            ).fetchone()

            if row is None:
                return await ctx.send("❌ You don't have an active scenario. Use `!coach scenario`.")

            scenario_id, created_at = row
            conn.execute(
                """
                DELETE FROM wattson_active_scenarios
                WHERE user_id=? AND guild_id=?
                """,
                (ctx.author.id, ctx.guild.id),
            )
            conn.commit()

        if time.time() - created_at > 3600:
            return await ctx.send("⌛ That scenario expired. Start a new one with `!coach scenario`.")

        scenario = SCENARIOS[scenario_id]
        correct = choice.lower() == scenario["answer"]

        scenarios, drills, lessons, coach_xp, streak, best, last_daily, challenge, completed = get_stats(
            ctx.author.id, ctx.guild.id
        )

        if correct:
            update_stats(
                ctx.author.id,
                ctx.guild.id,
                scenarios_completed=scenarios + 1,
            )
            new_xp, _ = mastery_award(
                ctx.author.id,
                ctx.guild.id,
                scenario["xp"],
            )

            embed = discord.Embed(
                title="✅ Correct!",
                description=scenario["explanation"],
                color=discord.Color.green(),
            )
            embed.add_field(name="⭐ Coach XP", value=f"+{scenario['xp']}", inline=True)
            embed.add_field(name="📈 Total Coach XP", value=f"{new_xp:,}", inline=True)
        else:
            embed = discord.Embed(
                title="❌ Not quite",
                description=(
                    f"The stronger general answer was **{scenario['answer'].upper()}**.\n\n"
                    f"{scenario['explanation']}"
                ),
                color=discord.Color.red(),
            )

        embed.set_footer(text="Use !coach scenario for another situation.")
        await ctx.send(embed=embed)

    # --------------------------------------------------------------
    # Drill system
    # --------------------------------------------------------------

    @coach.command(name="drills", aliases=["drilllist"])
    async def drills(self, ctx):
        """List available drills."""
        embed = discord.Embed(
            title="🏋️ Apex Training Drills",
            description="Start one with `!coach drill <name>`.",
            color=EMBED_COLOR,
        )

        for key, drill in DRILLS.items():
            embed.add_field(
                name=f"`{key}` — {drill['name']}",
                value=f"{drill['focus']} • {drill['duration']} • +{drill['xp']} XP",
                inline=False,
            )

        await ctx.send(embed=embed)

    @coach.command(name="drill")
    async def drill(self, ctx, name: str = None):
        """Start a training drill."""
        if not name:
            return await ctx.send("❌ Use `!coach drills` to see available drills.")

        name = name.lower()
        drill_data = DRILLS.get(name)

        if not drill_data:
            return await ctx.send(
                f"❌ I don't recognize `{name}`. Use `!coach drills`."
            )

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS wattson_active_drills (
                    user_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    drill_name TEXT NOT NULL,
                    started_at REAL NOT NULL,
                    PRIMARY KEY(user_id, guild_id)
                )
                """
            )
            conn.execute(
                """
                INSERT INTO wattson_active_drills
                (user_id, guild_id, drill_name, started_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, guild_id)
                DO UPDATE SET
                    drill_name=excluded.drill_name,
                    started_at=excluded.started_at
                """,
                (
                    ctx.author.id,
                    ctx.guild.id,
                    name,
                    time.time(),
                ),
            )
            conn.commit()

        embed = discord.Embed(
            title=f"🏋️ {drill_data['name']}",
            description=drill_data["description"],
            color=EMBED_COLOR,
        )
        embed.add_field(name="⏱️ Suggested Time", value=drill_data["duration"], inline=True)
        embed.add_field(name="🎯 Focus", value=drill_data["focus"], inline=True)
        embed.add_field(name="⭐ Reward", value=f"+{drill_data['xp']} XP", inline=True)
        embed.set_footer(text="When you're finished, use !coach complete")
        await ctx.send(embed=embed)

    @coach.command(name="complete", aliases=["done"])
    async def complete(self, ctx):
        """Complete the active drill."""
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS wattson_active_drills (
                    user_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    drill_name TEXT NOT NULL,
                    started_at REAL NOT NULL,
                    PRIMARY KEY(user_id, guild_id)
                )
                """
            )
            row = conn.execute(
                """
                SELECT drill_name, started_at
                FROM wattson_active_drills
                WHERE user_id=? AND guild_id=?
                """,
                (ctx.author.id, ctx.guild.id),
            ).fetchone()

            if row is None:
                return await ctx.send("❌ You don't have an active drill. Use `!coach drill <name>`.")

            drill_name, started_at = row
            conn.execute(
                """
                DELETE FROM wattson_active_drills
                WHERE user_id=? AND guild_id=?
                """,
                (ctx.author.id, ctx.guild.id),
            )
            conn.commit()

        # Require a minimum amount of time so the command cannot be spammed.
        elapsed = time.time() - started_at
        if elapsed < 30:
            return await ctx.send(
                "⏳ Spend a little time on the drill before completing it."
            )

        drill_data = DRILLS.get(drill_name)
        if not drill_data:
            return await ctx.send("❌ That drill is no longer available.")

        scenarios, drills_completed, lessons, coach_xp, streak, best, last_daily, challenge, completed = get_stats(
            ctx.author.id, ctx.guild.id
        )

        update_stats(
            ctx.author.id,
            ctx.guild.id,
            drills_completed=drills_completed + 1,
        )
        new_xp, _ = mastery_award(
            ctx.author.id,
            ctx.guild.id,
            drill_data["xp"],
        )

        embed = discord.Embed(
            title="✅ Drill Complete",
            description=f"**{drill_data['name']}** completed.",
            color=discord.Color.green(),
        )
        embed.add_field(name="⭐ XP Earned", value=f"+{drill_data['xp']}", inline=True)
        embed.add_field(name="📈 Coach XP", value=f"{new_xp:,}", inline=True)
        await ctx.send(embed=embed)

    # --------------------------------------------------------------
    # Daily coaching
    # --------------------------------------------------------------

    @coach.command(name="daily")
    async def daily(self, ctx):
        """Claim the daily coaching reward."""
        today = utc_now().date().isoformat()
        stats = get_stats(ctx.author.id, ctx.guild.id)
        scenarios, drills, lessons, coach_xp, streak, best, last_daily, challenge, completed = stats

        if last_daily == today:
            return await ctx.send("⏳ You've already claimed today's coaching reward. Come back tomorrow.")

        yesterday = (utc_now().date()).fromordinal(utc_now().date().toordinal() - 1).isoformat()

        if last_daily == yesterday:
            new_streak = streak + 1
        else:
            new_streak = 1

        new_best = max(best, new_streak)
        reward = 25 + min(new_streak, 7) * 5

        update_stats(
            ctx.author.id,
            ctx.guild.id,
            current_streak=new_streak,
            best_streak=new_best,
            last_daily=today,
        )
        new_xp, _ = mastery_award(ctx.author.id, ctx.guild.id, reward)

        embed = discord.Embed(
            title="📅 Daily Coaching Claimed",
            description=f"Keep the streak going tomorrow.",
            color=EMBED_COLOR,
        )
        embed.add_field(name="🔥 Streak", value=f"{new_streak} day(s)", inline=True)
        embed.add_field(name="⭐ XP", value=f"+{reward}", inline=True)
        embed.add_field(name="📈 Coach XP", value=f"{new_xp:,}", inline=True)
        await ctx.send(embed=embed)

    # --------------------------------------------------------------
    # Stats / progress
    # --------------------------------------------------------------

    @coach.command(name="stats")
    async def stats(self, ctx, member: discord.Member = None):
        """View coaching statistics."""
        member = member or ctx.author
        (
            scenarios,
            drills,
            lessons,
            coach_xp,
            streak,
            best,
            last_daily,
            challenge,
            completed,
        ) = get_stats(member.id, ctx.guild.id)

        level = coach_level(coach_xp)
        title = coach_title(level)

        embed = discord.Embed(
            title=f"🎯 {member.display_name}'s Coach Profile",
            color=EMBED_COLOR,
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="🎖️ Level", value=f"**{level}**", inline=True)
        embed.add_field(name="🏷️ Title", value=f"**{title}**", inline=True)
        embed.add_field(name="⭐ Coach XP", value=f"**{coach_xp:,}**", inline=True)
        embed.add_field(name="🧠 Scenarios", value=f"{scenarios}", inline=True)
        embed.add_field(name="🏋️ Drills", value=f"{drills}", inline=True)
        embed.add_field(name="📚 Lessons", value=f"{lessons}", inline=True)
        embed.add_field(name="🔥 Current Streak", value=f"{streak} day(s)", inline=True)
        embed.add_field(name="🏆 Best Streak", value=f"{best} day(s)", inline=True)
        await ctx.send(embed=embed)

    @coach.command(name="progress")
    async def progress(self, ctx):
        """Show progress toward the next coach level."""
        (
            scenarios,
            drills,
            lessons,
            coach_xp,
            streak,
            best,
            last_daily,
            challenge,
            completed,
        ) = get_stats(ctx.author.id, ctx.guild.id)

        level = coach_level(coach_xp)
        title = coach_title(level)

        if level >= 100:
            bar = "████████████████████"
            progress_text = "Maximum coach level reached."
        else:
            current = coach_xp % 100
            filled = int(current / 100 * 20)
            bar = "█" * filled + "░" * (20 - filled)
            progress_text = f"{current}/100 XP to Level {level + 1}"

        embed = discord.Embed(
            title="📈 Coaching Progress",
            color=EMBED_COLOR,
        )
        embed.add_field(name="🎖️ Level", value=str(level), inline=True)
        embed.add_field(name="🏷️ Title", value=title, inline=True)
        embed.add_field(name="⭐ Total XP", value=f"{coach_xp:,}", inline=True)
        embed.add_field(
            name="Progress",
            value=f"`{bar}`\n{progress_text}",
            inline=False,
        )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(ApexCoach(bot))
