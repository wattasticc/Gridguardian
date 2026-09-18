"""
Grid Guardian - Apex Legend Matchups

Wattson-focused matchup database.

Commands:
    !matchup
    !matchup view <legend>
    !matchup search <text>
    !matchup list
    !matchup add <legend> | <difficulty> | <overview> | <advantages> | <disadvantages> | <strategy> | <tips>
    !matchup edit <legend> | <difficulty> | <overview> | <advantages> | <disadvantages> | <strategy> | <tips>
    !matchup delete <legend>
    !matchup help

Database:
    apex_matchups
"""

import sqlite3
from datetime import datetime, timezone
from typing import Optional

import discord
from discord.ext import commands


DB_PATH = "gridguardian.db"


LEGENDS = {
    "alter",
    "ash",
    "ballistic",
    "bangalore",
    "caustic",
    "conduit",
    "crypto",
    "fuse",
    "gibraltar",
    "horizon",
    "lifeline",
    "loba",
    "mad maggie",
    "mirage",
    "newcastle",
    "octane",
    "pathfinder",
    "rampart",
    "revenant",
    "seer",
    "sparrow",
    "valkyrie",
    "vantage",
    "wattson",
    "wraith",
    "catalyst",
    "bloodhound",
    "lithium",
}


DIFFICULTIES = {
    "easy",
    "medium",
    "hard",
}


LEGEND_ALIASES = {
    "maggie": "mad maggie",
    "madmaggie": "mad maggie",
    "bang": "bangalore",
    "gibby": "gibraltar",
    "path": "pathfinder",
    "lifeline": "lifeline",
    "crypto": "crypto",
    "newcastle": "newcastle",
    "valk": "valkyrie",
    "vantage": "vantage",
    "rev": "revenant",
    "catalyst": "catalyst",
    "caustic": "caustic",
    "fuse": "fuse",
    "wattson": "wattson",
    "wraith": "wraith",
    "horizon": "horizon",
    "octane": "octane",
    "loba": "loba",
    "mirage": "mirage",
    "seer": "seer",
    "bloodhound": "bloodhound",
    "ash": "ash",
    "alter": "alter",
    "ballistic": "ballistic",
    "conduit": "conduit",
    "rampart": "rampart",
    "gibraltar": "gibraltar",
    "sparrow": "sparrow",
}


# ============================================================
# DATABASE
# ============================================================

def connect_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    conn = connect_db()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS apex_matchups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                legend TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                overview TEXT NOT NULL,
                advantages TEXT NOT NULL,
                disadvantages TEXT NOT NULL,
                strategy TEXT NOT NULL,
                tips TEXT NOT NULL,
                created_by INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(guild_id, legend)
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_apex_matchups_guild
            ON apex_matchups(guild_id)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_apex_matchups_legend
            ON apex_matchups(guild_id, legend)
            """
        )

        conn.commit()

    finally:
        conn.close()


# ============================================================
# HELPERS
# ============================================================

def normalize_legend(name: str) -> Optional[str]:
    value = name.strip().lower()

    if value in LEGEND_ALIASES:
        return LEGEND_ALIASES[value]

    if value in LEGENDS:
        return value

    return None


def get_matchup(
    guild_id: int,
    legend: str,
) -> Optional[sqlite3.Row]:
    conn = connect_db()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM apex_matchups
            WHERE guild_id = ?
              AND legend = ?
            """,
            (guild_id, legend),
        )

        return cursor.fetchone()

    finally:
        conn.close()


def get_all_matchups(guild_id: int) -> list[sqlite3.Row]:
    conn = connect_db()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM apex_matchups
            WHERE guild_id = ?
            ORDER BY legend ASC
            """,
            (guild_id,),
        )

        return cursor.fetchall()

    finally:
        conn.close()


def difficulty_emoji(difficulty: str) -> str:
    return {
        "easy": "🟢",
        "medium": "🟡",
        "hard": "🔴",
    }.get(difficulty, "⚪")


def pretty_legend(legend: str) -> str:
    return legend.title()


def split_bullets(text: str) -> list[str]:
    """
    Converts a stored bullet list into clean display lines.

    Users can enter:
        First thing; Second thing; Third thing

    or:
        First thing
        Second thing
    """

    if ";" in text:
        items = text.split(";")
    else:
        items = text.splitlines()

    return [
        item.strip(" -•\t")
        for item in items
        if item.strip(" -•\t")
    ]


def format_bullets(text: str) -> str:
    items = split_bullets(text)

    if not items:
        return "None provided."

    return "\n".join(
        f"• {item}"
        for item in items[:15]
    )


# ============================================================
# MATCHUP VIEW
# ============================================================

class MatchupView(discord.ui.View):
    def __init__(self, matchup_id: int):
        super().__init__(timeout=300)
        self.matchup_id = matchup_id


# ============================================================
# COG
# ============================================================

class LegendMatchups(commands.Cog):
    """Wattson-focused Apex legend matchup database."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        init_db()

    # ========================================================
    # ROOT
    # ========================================================

    @commands.group(
        name="matchup",
        aliases=["matchups", "counter"],
        invoke_without_command=True,
    )
    @commands.guild_only()
    async def matchup(self, ctx: commands.Context):
        """Apex legend matchup database."""

        embed = discord.Embed(
            title="🧙 Wattson Legend Matchups",
            description=(
                "Learn how to approach different legends "
                "when playing Wattson.\n\n"
                "**Examples**\n"
                "`!matchup view Bangalore`\n"
                "`!matchup view Horizon`\n"
                "`!matchup list`"
            ),
            color=discord.Color.from_rgb(255, 105, 180),
        )

        embed.add_field(
            name="🔎 Browse",
            value=(
                "`!matchup view <legend>`\n"
                "`!matchup search <text>`\n"
                "`!matchup list`"
            ),
            inline=False,
        )

        embed.add_field(
            name="🛠️ Staff",
            value=(
                "`!matchup add ...`\n"
                "`!matchup edit ...`\n"
                "`!matchup delete <legend>`"
            ),
            inline=False,
        )

        await ctx.send(embed=embed)

    # ========================================================
    # HELP
    # ========================================================

    @matchup.command(name="help")
    async def matchup_help(self, ctx: commands.Context):
        """Show matchup commands."""

        embed = discord.Embed(
            title="🧙 Legend Matchup Help",
            color=discord.Color.from_rgb(255, 105, 180),
        )

        embed.add_field(
            name="View",
            value=(
                "`!matchup view <legend>`\n"
                "`!matchup search <text>`\n"
                "`!matchup list`"
            ),
            inline=False,
        )

        embed.add_field(
            name="Add",
            value=(
                "`!matchup add Legend | Difficulty | Overview | "
                "Advantages | Disadvantages | Strategy | Tips`"
            ),
            inline=False,
        )

        embed.add_field(
            name="Example",
            value=(
                "`!matchup add Bangalore | hard | "
                "Bangalore can disrupt Wattson setups with her ultimate. | "
                "Fences control doorways; Pylon can help with incoming ordnance; "
                "Defensive buildings favor Wattson. | "
                "Smoke reduces visibility; Rolling Thunder can force movement. | "
                "Keep an escape route; avoid relying on one doorway; "
                "place fences where smoke does not completely hide your setup. | "
                "Save Pylon for important engagements; spread fence nodes; "
                "do not overcommit to one building.`"
            ),
            inline=False,
        )

        embed.add_field(
            name="Edit",
            value=(
                "`!matchup edit Legend | Difficulty | Overview | "
                "Advantages | Disadvantages | Strategy | Tips`"
            ),
            inline=False,
        )

        embed.add_field(
            name="Delete",
            value="`!matchup delete <legend>`",
            inline=False,
        )

        embed.add_field(
            name="Difficulty",
            value=(
                "🟢 Easy\n"
                "🟡 Medium\n"
                "🔴 Hard"
            ),
            inline=True,
        )

        embed.set_footer(
            text="Matchups are community strategy information, not guaranteed outcomes."
        )

        await ctx.send(embed=embed)

    # ========================================================
    # VIEW
    # ========================================================

    @matchup.command(name="view")
    @commands.guild_only()
    async def matchup_view(
        self,
        ctx: commands.Context,
        *,
        legend_name: str,
    ):
        """View a matchup."""

        legend = normalize_legend(legend_name)

        if not legend:
            await ctx.send(
                "❌ I don't recognize that legend.\n"
                "Use `!matchup list` to see available matchups."
            )
            return

        matchup = get_matchup(
            ctx.guild.id,
            legend,
        )

        if not matchup:
            await ctx.send(
                f"❌ There isn't a matchup guide for "
                f"**{pretty_legend(legend)}** yet."
            )
            return

        embed = discord.Embed(
            title=f"🧙 Wattson vs {pretty_legend(legend)}",
            description=matchup["overview"],
            color=discord.Color.from_rgb(255, 105, 180),
        )

        embed.add_field(
            name="Difficulty",
            value=(
                f"{difficulty_emoji(matchup['difficulty'])} "
                f"{matchup['difficulty'].title()}"
            ),
            inline=True,
        )

        embed.add_field(
            name="Guide ID",
            value=f"`#{matchup['id']}`",
            inline=True,
        )

        embed.add_field(
            name="⚡ Wattson Advantages",
            value=format_bullets(
                matchup["advantages"]
            ),
            inline=False,
        )

        embed.add_field(
            name="⚠️ Disadvantages",
            value=format_bullets(
                matchup["disadvantages"]
            ),
            inline=False,
        )

        embed.add_field(
            name="🎯 Recommended Strategy",
            value=format_bullets(
                matchup["strategy"]
            ),
            inline=False,
        )

        embed.add_field(
            name="🧠 Tips",
            value=format_bullets(
                matchup["tips"]
            ),
            inline=False,
        )

        embed.set_footer(
            text="Use matchup search or matchup list to find other legends."
        )

        await ctx.send(
            embed=embed,
            view=MatchupView(matchup["id"]),
        )

    # ========================================================
    # SEARCH
    # ========================================================

    @matchup.command(name="search")
    @commands.guild_only()
    async def matchup_search(
        self,
        ctx: commands.Context,
        *,
        query: str,
    ):
        """Search matchup guides."""

        query = query.strip()

        if not query:
            await ctx.send(
                "❌ Enter something to search for."
            )
            return

        search = f"%{query}%"

        conn = connect_db()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT *
                FROM apex_matchups
                WHERE guild_id = ?
                  AND (
                      legend LIKE ?
                      OR difficulty LIKE ?
                      OR overview LIKE ?
                      OR advantages LIKE ?
                      OR disadvantages LIKE ?
                      OR strategy LIKE ?
                      OR tips LIKE ?
                  )
                ORDER BY legend ASC
                LIMIT 15
                """,
                (
                    ctx.guild.id,
                    search,
                    search,
                    search,
                    search,
                    search,
                    search,
                    search,
                ),
            )

            results = cursor.fetchall()

        finally:
            conn.close()

        if not results:
            await ctx.send(
                f"🔎 No matchup guides found for `{query}`."
            )
            return

        embed = discord.Embed(
            title=f"🔎 Matchup Search — {query}",
            color=discord.Color.from_rgb(255, 105, 180),
        )

        lines = []

        for result in results:
            lines.append(
                f"**{pretty_legend(result['legend'])}**\n"
                f"{difficulty_emoji(result['difficulty'])} "
                f"{result['difficulty'].title()}\n"
                f"{result['overview'][:180]}"
            )

        embed.description = "\n\n".join(lines)

        embed.set_footer(
            text="Use !matchup view <legend> for the full guide."
        )

        await ctx.send(embed=embed)

    # ========================================================
    # LIST
    # ========================================================

    @matchup.command(name="list")
    @commands.guild_only()
    async def matchup_list(self, ctx: commands.Context):
        """List all available matchup guides."""

        matchups = get_all_matchups(
            ctx.guild.id
        )

        if not matchups:
            await ctx.send(
                "📚 There aren't any matchup guides yet."
            )
            return

        embed = discord.Embed(
            title="🧙 Wattson Matchup Library",
            description=(
                "Available legend matchup guides:"
            ),
            color=discord.Color.from_rgb(255, 105, 180),
        )

        lines = []

        for matchup in matchups:
            lines.append(
                f"{difficulty_emoji(matchup['difficulty'])} "
                f"**{pretty_legend(matchup['legend'])}** — "
                f"`{matchup['difficulty']}`"
            )

        embed.description += "\n" + "\n".join(lines)

        embed.set_footer(
            text="Use !matchup view <legend> to open a guide."
        )

        await ctx.send(embed=embed)

    # ========================================================
    # ADD
    # ========================================================

    @matchup.command(name="add")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def matchup_add(
        self,
        ctx: commands.Context,
        *,
        data: str,
    ):
        """Add a matchup guide."""

        parts = [
            part.strip()
            for part in data.split("|", 6)
        ]

        if len(parts) != 7:
            await ctx.send(
                "❌ Use:\n"
                "`!matchup add Legend | Difficulty | Overview | "
                "Advantages | Disadvantages | Strategy | Tips`"
            )
            return

        (
            legend_input,
            difficulty,
            overview,
            advantages,
            disadvantages,
            strategy,
            tips,
        ) = parts

        legend = normalize_legend(legend_input)

        if not legend:
            await ctx.send(
                "❌ Invalid legend.\n"
                "Use `!matchup list` or `!matchup help`."
            )
            return

        difficulty = difficulty.lower()

        if difficulty not in DIFFICULTIES:
            await ctx.send(
                "❌ Difficulty must be one of:\n"
                "`easy`, `medium`, `hard`"
            )
            return

        if not overview:
            await ctx.send(
                "❌ Overview cannot be empty."
            )
            return

        if not advantages:
            await ctx.send(
                "❌ Advantages cannot be empty."
            )
            return

        if not disadvantages:
            await ctx.send(
                "❌ Disadvantages cannot be empty."
            )
            return

        if not strategy:
            await ctx.send(
                "❌ Strategy cannot be empty."
            )
            return

        if not tips:
            await ctx.send(
                "❌ Tips cannot be empty."
            )
            return

        conn = connect_db()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id
                FROM apex_matchups
                WHERE guild_id = ?
                  AND legend = ?
                """,
                (
                    ctx.guild.id,
                    legend,
                ),
            )

            if cursor.fetchone():
                await ctx.send(
                    f"❌ A matchup for **{pretty_legend(legend)}** "
                    f"already exists.\n"
                    f"Use `!matchup edit {pretty_legend(legend)}` instead."
                )
                return

            cursor.execute(
                """
                INSERT INTO apex_matchups (
                    guild_id,
                    legend,
                    difficulty,
                    overview,
                    advantages,
                    disadvantages,
                    strategy,
                    tips,
                    created_by,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ctx.guild.id,
                    legend,
                    difficulty,
                    overview[:2000],
                    advantages[:3000],
                    disadvantages[:3000],
                    strategy[:3000],
                    tips[:3000],
                    ctx.author.id,
                    now_iso(),
                    now_iso(),
                ),
            )

            matchup_id = cursor.lastrowid

            conn.commit()

        finally:
            conn.close()

        embed = discord.Embed(
            title="🧙 Matchup Added",
            description=(
                f"**Wattson vs {pretty_legend(legend)}**\n\n"
                f"Matchup ID: `#{matchup_id}`"
            ),
            color=discord.Color.green(),
        )

        embed.add_field(
            name="Difficulty",
            value=(
                f"{difficulty_emoji(difficulty)} "
                f"{difficulty.title()}"
            ),
            inline=True,
        )

        embed.add_field(
            name="Created By",
            value=ctx.author.mention,
            inline=True,
        )

        await ctx.send(embed=embed)

    # ========================================================
    # EDIT
    # ========================================================

    @matchup.command(name="edit")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def matchup_edit(
        self,
        ctx: commands.Context,
        *,
        data: str,
    ):
        """Edit an existing matchup guide."""

        parts = [
            part.strip()
            for part in data.split("|", 6)
        ]

        if len(parts) != 7:
            await ctx.send(
                "❌ Use:\n"
                "`!matchup edit Legend | Difficulty | Overview | "
                "Advantages | Disadvantages | Strategy | Tips`"
            )
            return

        (
            legend_input,
            difficulty,
            overview,
            advantages,
            disadvantages,
            strategy,
            tips,
        ) = parts

        legend = normalize_legend(legend_input)

        if not legend:
            await ctx.send(
                "❌ Invalid legend."
            )
            return

        difficulty = difficulty.lower()

        if difficulty not in DIFFICULTIES:
            await ctx.send(
                "❌ Difficulty must be `easy`, `medium`, or `hard`."
            )
            return

        if not all(
            [
                overview,
                advantages,
                disadvantages,
                strategy,
                tips,
            ]
        ):
            await ctx.send(
                "❌ All matchup sections must contain information."
            )
            return

        existing = get_matchup(
            ctx.guild.id,
            legend,
        )

        if not existing:
            await ctx.send(
                f"❌ No matchup exists for "
                f"**{pretty_legend(legend)}**."
            )
            return

        conn = connect_db()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE apex_matchups
                SET difficulty = ?,
                    overview = ?,
                    advantages = ?,
                    disadvantages = ?,
                    strategy = ?,
                    tips = ?,
                    updated_at = ?
                WHERE guild_id = ?
                  AND legend = ?
                """,
                (
                    difficulty,
                    overview[:2000],
                    advantages[:3000],
                    disadvantages[:3000],
                    strategy[:3000],
                    tips[:3000],
                    now_iso(),
                    ctx.guild.id,
                    legend,
                ),
            )

            conn.commit()

        finally:
            conn.close()

        await ctx.send(
            f"✅ Matchup for **{pretty_legend(legend)}** updated."
        )

    # ========================================================
    # DELETE
    # ========================================================

    @matchup.command(name="delete")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def matchup_delete(
        self,
        ctx: commands.Context,
        *,
        legend_name: str,
    ):
        """Delete a matchup guide."""

        legend = normalize_legend(legend_name)

        if not legend:
            await ctx.send(
                "❌ Invalid legend."
            )
            return

        existing = get_matchup(
            ctx.guild.id,
            legend,
        )

        if not existing:
            await ctx.send(
                f"❌ No matchup exists for "
                f"**{pretty_legend(legend)}**."
            )
            return

        conn = connect_db()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                DELETE FROM apex_matchups
                WHERE guild_id = ?
                  AND legend = ?
                """,
                (
                    ctx.guild.id,
                    legend,
                ),
            )

            conn.commit()

        finally:
            conn.close()

        await ctx.send(
            f"🗑️ Matchup for **{pretty_legend(legend)}** deleted."
        )

    # ========================================================
    # ERROR HANDLER
    # ========================================================

    @matchup.error
    async def matchup_error(
        self,
        ctx: commands.Context,
        error: commands.CommandError,
    ):
        if isinstance(
            error,
            commands.MissingPermissions,
        ):
            await ctx.send(
                "❌ You need **Manage Server** permission to do that."
            )
            return

        if isinstance(
            error,
            commands.MissingRequiredArgument,
        ):
            await ctx.send(
                "❌ You're missing a required argument.\n"
                "Use `!matchup help`."
            )
            return

        if isinstance(
            error,
            commands.BadArgument,
        ):
            await ctx.send(
                "❌ One of the values you entered isn't valid."
            )
            return

        raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(LegendMatchups(bot))