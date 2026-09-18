"""
Grid Guardian - Wattson Tech Database

Community-driven database for Wattson mechanics, techniques, and tech.

Commands:
    !tech
    !tech add
    !tech view <id>
    !tech search <text>
    !tech category <category>
    !tech difficulty <difficulty>
    !tech platform <platform>
    !tech top
    !tech mine
    !tech pending
    !tech approve <id>
    !tech reject <id>
    !tech delete <id>
    !tech help

Database:
    wattson_tech
    wattson_tech_votes
"""

import sqlite3
from datetime import datetime, timezone
from typing import Optional

import discord
from discord.ext import commands


DB_PATH = "gridguardian.db"


# ============================================================
# DATABASE
# ============================================================

def get_connection() -> sqlite3.Connection:
    """Create a fresh SQLite connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database() -> None:
    """Create the Wattson Tech Database tables."""
    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS wattson_tech (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                platform TEXT NOT NULL,
                description TEXT NOT NULL,
                steps TEXT NOT NULL,
                media_url TEXT,
                approved INTEGER NOT NULL DEFAULT 0,
                upvotes INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS wattson_tech_votes (
                tech_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (tech_id, user_id),
                FOREIGN KEY (tech_id)
                    REFERENCES wattson_tech(id)
                    ON DELETE CASCADE
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_wattson_tech_guild
            ON wattson_tech(guild_id)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_wattson_tech_category
            ON wattson_tech(guild_id, category)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_wattson_tech_difficulty
            ON wattson_tech(guild_id, difficulty)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_wattson_tech_platform
            ON wattson_tech(guild_id, platform)
            """
        )

        conn.commit()

    finally:
        conn.close()


# ============================================================
# CONSTANTS / HELPERS
# ============================================================

VALID_CATEGORIES = {
    "fencing": "Fencing",
    "fence": "Fencing",
    "interception": "Interception",
    "intercept": "Interception",
    "pylon": "Pylon",
    "movement": "Movement",
    "positioning": "Positioning",
    "door": "Door Tech",
    "door tech": "Door Tech",
    "combat": "Combat",
    "setup": "Setup",
    "general": "General",
    "other": "Other",
}

VALID_DIFFICULTIES = {
    "easy": "Easy",
    "beginner": "Easy",
    "medium": "Medium",
    "intermediate": "Medium",
    "hard": "Hard",
    "advanced": "Hard",
    "expert": "Expert",
}

VALID_PLATFORMS = {
    "pc": "PC",
    "console": "Console",
    "playstation": "PlayStation",
    "ps": "PlayStation",
    "xbox": "Xbox",
    "all": "All Platforms",
    "any": "All Platforms",
}


def normalize_category(value: str) -> Optional[str]:
    """Return the canonical category name."""
    return VALID_CATEGORIES.get(value.strip().lower())


def normalize_difficulty(value: str) -> Optional[str]:
    """Return the canonical difficulty name."""
    return VALID_DIFFICULTIES.get(value.strip().lower())


def normalize_platform(value: str) -> Optional[str]:
    """Return the canonical platform name."""
    return VALID_PLATFORMS.get(value.strip().lower())


def utc_now() -> str:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def is_staff(member: discord.Member) -> bool:
    """Check whether a member can moderate tech submissions."""
    return (
        member.guild_permissions.manage_guild
        or member.guild_permissions.manage_messages
        or member.guild_permissions.administrator
    )


def truncate(text: str, length: int = 900) -> str:
    """Keep embed fields within a reasonable size."""
    if len(text) <= length:
        return text

    return text[: length - 3] + "..."


def parse_pipe_arguments(raw: str, expected: int) -> Optional[list[str]]:
    """
    Parse pipe-separated command input.

    Example:
        Name | Category | Difficulty | Platform | Description | Steps | URL
    """
    parts = [part.strip() for part in raw.split("|")]

    if len(parts) != expected:
        return None

    if any(not part for part in parts[:-1]):
        return None

    return parts


def format_steps(steps: str) -> str:
    """
    Turn numbered steps separated by '>' into readable Discord text.

    Example:
        Place fence > Rotate > Place second node
    """
    parts = [part.strip() for part in steps.split(">") if part.strip()]

    if not parts:
        return steps

    return "\n".join(
        f"**{index}.** {part}"
        for index, part in enumerate(parts, start=1)
    )


# ============================================================
# TECH VIEW
# ============================================================

class TechView(discord.ui.View):
    """Interactive buttons for a Wattson technique."""

    def __init__(self, tech_id: int):
        super().__init__(timeout=300)
        self.tech_id = tech_id

    @discord.ui.button(
        label="Upvote",
        emoji="⚡",
        style=discord.ButtonStyle.primary,
    )
    async def upvote(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "This button can only be used inside a server.",
                ephemeral=True,
            )
            return

        conn = get_connection()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, name, approved
                FROM wattson_tech
                WHERE id = ?
                  AND guild_id = ?
                """,
                (self.tech_id, interaction.guild.id),
            )

            tech = cursor.fetchone()

            if tech is None:
                await interaction.response.send_message(
                    "That technique no longer exists.",
                    ephemeral=True,
                )
                return

            if not tech["approved"]:
                await interaction.response.send_message(
                    "That technique has not been approved yet.",
                    ephemeral=True,
                )
                return

            cursor.execute(
                """
                SELECT 1
                FROM wattson_tech_votes
                WHERE tech_id = ?
                  AND user_id = ?
                """,
                (self.tech_id, interaction.user.id),
            )

            existing_vote = cursor.fetchone()

            if existing_vote:
                await interaction.response.send_message(
                    "You already upvoted this technique.",
                    ephemeral=True,
                )
                return

            cursor.execute(
                """
                INSERT INTO wattson_tech_votes
                (
                    tech_id,
                    user_id,
                    created_at
                )
                VALUES (?, ?, ?)
                """,
                (
                    self.tech_id,
                    interaction.user.id,
                    utc_now(),
                ),
            )

            cursor.execute(
                """
                UPDATE wattson_tech
                SET upvotes = upvotes + 1,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    utc_now(),
                    self.tech_id,
                ),
            )

            conn.commit()

            cursor.execute(
                """
                SELECT upvotes
                FROM wattson_tech
                WHERE id = ?
                """,
                (self.tech_id,),
            )

            result = cursor.fetchone()
            new_count = result["upvotes"] if result else 0

            await interaction.response.send_message(
                f"⚡ Upvoted **{tech['name']}**!\n"
                f"Total upvotes: **{new_count}**",
                ephemeral=True,
            )

        except sqlite3.Error:
            conn.rollback()

            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Something went wrong while saving your vote.",
                    ephemeral=True,
                )

        finally:
            conn.close()


# ============================================================
# COG
# ============================================================

class WattsonTech(commands.Cog):
    """Wattson Tech Database."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        initialize_database()

    # ========================================================
    # MAIN COMMAND
    # ========================================================

    @commands.group(
        name="tech",
        invoke_without_command=True,
    )
    async def tech(self, ctx: commands.Context):
        """Open the Wattson Tech Database."""
        embed = discord.Embed(
            title="⚡ Wattson Tech Database",
            description=(
                "A community database for Wattson mechanics, "
                "techniques, setups, and advanced tricks."
            ),
            color=discord.Color.from_rgb(255, 105, 180),
        )

        embed.add_field(
            name="📚 Browse",
            value=(
                "`!tech view <id>`\n"
                "`!tech search <text>`\n"
                "`!tech category <category>`\n"
                "`!tech difficulty <difficulty>`\n"
                "`!tech platform <platform>`\n"
                "`!tech top`"
            ),
            inline=True,
        )

        embed.add_field(
            name="📝 Submit",
            value=(
                "`!tech add`\n"
                "`!tech mine`"
            ),
            inline=True,
        )

        embed.add_field(
            name="🛡️ Staff",
            value=(
                "`!tech pending`\n"
                "`!tech approve <id>`\n"
                "`!tech reject <id>`\n"
                "`!tech delete <id>`"
            ),
            inline=False,
        )

        embed.set_footer(
            text="Use !tech help for detailed instructions."
        )

        await ctx.send(embed=embed)

    # ========================================================
    # HELP
    # ========================================================

    @tech.command(name="help")
    async def tech_help(self, ctx: commands.Context):
        """Show detailed Wattson Tech Database help."""
        embed = discord.Embed(
            title="⚡ Wattson Tech Database Help",
            color=discord.Color.from_rgb(255, 105, 180),
        )

        embed.add_field(
            name="📖 Browse",
            value=(
                "`!tech view 12` — View a technique\n"
                "`!tech search mantle` — Search\n"
                "`!tech category fencing` — Category filter\n"
                "`!tech difficulty hard` — Difficulty filter\n"
                "`!tech platform console` — Platform filter\n"
                "`!tech top` — Top techniques"
            ),
            inline=False,
        )

        embed.add_field(
            name="📝 Submit a Technique",
            value=(
                "Use this format:\n\n"
                "`!tech add Name | Category | Difficulty | "
                "Platform | Description | Steps | Media URL`\n\n"
                "**Example:**\n"
                "`!tech add Fast Fence Reset | Fencing | Hard | "
                "Console | Quickly reset your fence setup | "
                "Place first node > Rotate > Place second node | "
                "https://example.com/video`"
            ),
            inline=False,
        )

        embed.add_field(
            name="📂 Categories",
            value=(
                "Fencing • Interception • Pylon • Movement • "
                "Positioning • Door Tech • Combat • Setup • General"
            ),
            inline=False,
        )

        embed.add_field(
            name="🎯 Difficulties",
            value="Easy • Medium • Hard • Expert",
            inline=False,
        )

        embed.add_field(
            name="🎮 Platforms",
            value="PC • PlayStation • Xbox • Console • All Platforms",
            inline=False,
        )

        embed.add_field(
            name="🛡️ Staff Commands",
            value=(
                "`!tech pending`\n"
                "`!tech approve <id>`\n"
                "`!tech reject <id>`\n"
                "`!tech delete <id>`"
            ),
            inline=False,
        )

        embed.set_footer(
            text="Use > between individual steps."
        )

        await ctx.send(embed=embed)

    # ========================================================
    # ADD
    # ========================================================

    @tech.command(name="add")
    async def tech_add(
        self,
        ctx: commands.Context,
        *,
        raw: str = "",
    ):
        """Submit a new Wattson technique."""
        if not raw:
            await ctx.send(
                "❌ Please provide the technique information.\n\n"
                "Use `!tech help` for the exact format."
            )
            return

        parts = parse_pipe_arguments(raw, 7)

        if parts is None:
            await ctx.send(
                "❌ Invalid format.\n\n"
                "Use:\n"
                "`!tech add Name | Category | Difficulty | Platform | "
                "Description | Steps | Media URL`\n\n"
                "The Media URL can be `none` if you don't have one."
            )
            return

        (
            name,
            category_input,
            difficulty_input,
            platform_input,
            description,
            steps,
            media_url,
        ) = parts

        category = normalize_category(category_input)
        difficulty = normalize_difficulty(difficulty_input)
        platform = normalize_platform(platform_input)

        if category is None:
            await ctx.send(
                "❌ Invalid category.\n\n"
                "Available categories:\n"
                "Fencing, Interception, Pylon, Movement, "
                "Positioning, Door Tech, Combat, Setup, General"
            )
            return

        if difficulty is None:
            await ctx.send(
                "❌ Invalid difficulty.\n\n"
                "Use: Easy, Medium, Hard, or Expert."
            )
            return

        if platform is None:
            await ctx.send(
                "❌ Invalid platform.\n\n"
                "Use: PC, PlayStation, Xbox, Console, or All Platforms."
            )
            return

        if len(name) > 100:
            await ctx.send("❌ The technique name is too long. Maximum: 100 characters.")
            return

        if len(description) > 1500:
            await ctx.send(
                "❌ The description is too long. Maximum: 1500 characters."
            )
            return

        if len(steps) > 2000:
            await ctx.send(
                "❌ The steps are too long. Maximum: 2000 characters."
            )
            return

        if media_url.lower() == "none":
            media_url = ""

        conn = get_connection()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO wattson_tech
                (
                    guild_id,
                    user_id,
                    name,
                    category,
                    difficulty,
                    platform,
                    description,
                    steps,
                    media_url,
                    approved,
                    upvotes,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?)
                """,
                (
                    ctx.guild.id,
                    ctx.author.id,
                    name,
                    category,
                    difficulty,
                    platform,
                    description,
                    steps,
                    media_url,
                    utc_now(),
                    utc_now(),
                ),
            )

            tech_id = cursor.lastrowid
            conn.commit()

        except sqlite3.Error:
            conn.rollback()

            await ctx.send(
                "❌ I couldn't save that technique right now."
            )
            return

        finally:
            conn.close()

        embed = discord.Embed(
            title="⚡ Technique Submitted",
            description=(
                f"**{name}** has been submitted to the Wattson Tech Database."
            ),
            color=discord.Color.orange(),
        )

        embed.add_field(
            name="ID",
            value=f"`{tech_id}`",
            inline=True,
        )

        embed.add_field(
            name="Category",
            value=category,
            inline=True,
        )

        embed.add_field(
            name="Difficulty",
            value=difficulty,
            inline=True,
        )

        embed.add_field(
            name="Platform",
            value=platform,
            inline=True,
        )

        embed.add_field(
            name="Status",
            value="🟠 Pending staff approval",
            inline=True,
        )

        embed.set_footer(
            text="A staff member must approve it before it appears publicly."
        )

        await ctx.send(embed=embed)

    # ========================================================
    # VIEW
    # ========================================================

    @tech.command(name="view")
    async def tech_view(
        self,
        ctx: commands.Context,
        tech_id: int,
    ):
        """View a Wattson technique."""
        conn = get_connection()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT *
                FROM wattson_tech
                WHERE id = ?
                  AND guild_id = ?
                """,
                (
                    tech_id,
                    ctx.guild.id,
                ),
            )

            tech = cursor.fetchone()

        finally:
            conn.close()

        if tech is None:
            await ctx.send(
                f"❌ No technique with ID `{tech_id}` was found."
            )
            return

        if not tech["approved"] and not (
            tech["user_id"] == ctx.author.id or is_staff(ctx.author)
        ):
            await ctx.send(
                "❌ That technique has not been approved yet."
            )
            return

        status = "✅ Approved" if tech["approved"] else "🟠 Pending Approval"

        embed = discord.Embed(
            title=f"⚡ {tech['name']}",
            description=tech["description"],
            color=(
                discord.Color.from_rgb(255, 105, 180)
                if tech["approved"]
                else discord.Color.orange()
            ),
        )

        embed.add_field(
            name="📂 Category",
            value=tech["category"],
            inline=True,
        )

        embed.add_field(
            name="🎯 Difficulty",
            value=tech["difficulty"],
            inline=True,
        )

        embed.add_field(
            name="🎮 Platform",
            value=tech["platform"],
            inline=True,
        )

        embed.add_field(
            name="⚡ Upvotes",
            value=str(tech["upvotes"]),
            inline=True,
        )

        embed.add_field(
            name="📋 Steps",
            value=truncate(format_steps(tech["steps"]), 1000),
            inline=False,
        )

        embed.add_field(
            name="Status",
            value=status,
            inline=True,
        )

        author = ctx.guild.get_member(tech["user_id"])

        if author:
            submitted_by = author.mention
        else:
            submitted_by = f"<@{tech['user_id']}>"

        embed.add_field(
            name="👤 Submitted By",
            value=submitted_by,
            inline=True,
        )

        if tech["media_url"]:
            embed.add_field(
                name="🎬 Tutorial / Media",
                value=tech["media_url"],
                inline=False,
            )

        embed.set_footer(
            text=f"Technique ID: {tech['id']}"
        )

        view = TechView(tech["id"]) if tech["approved"] else None

        await ctx.send(
            embed=embed,
            view=view,
        )

    # ========================================================
    # SEARCH
    # ========================================================

    @tech.command(name="search")
    async def tech_search(
        self,
        ctx: commands.Context,
        *,
        search_text: str,
    ):
        """Search approved techniques."""
        search_text = search_text.strip()

        if not search_text:
            await ctx.send("❌ Please provide something to search for.")
            return

        if len(search_text) > 100:
            await ctx.send("❌ Search text is too long.")
            return

        pattern = f"%{search_text}%"

        conn = get_connection()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, name, category, difficulty, platform, upvotes
                FROM wattson_tech
                WHERE guild_id = ?
                  AND approved = 1
                  AND (
                      name LIKE ?
                      OR category LIKE ?
                      OR description LIKE ?
                      OR steps LIKE ?
                  )
                ORDER BY upvotes DESC, id DESC
                LIMIT 10
                """,
                (
                    ctx.guild.id,
                    pattern,
                    pattern,
                    pattern,
                    pattern,
                ),
            )

            rows = cursor.fetchall()

        finally:
            conn.close()

        if not rows:
            await ctx.send(
                f"🔎 No approved techniques matched **{search_text}**."
            )
            return

        embed = discord.Embed(
            title=f"🔎 Tech Search: {search_text}",
            color=discord.Color.from_rgb(255, 105, 180),
        )

        for row in rows:
            embed.add_field(
                name=f"⚡ #{row['id']} — {row['name']}",
                value=(
                    f"**Category:** {row['category']}\n"
                    f"**Difficulty:** {row['difficulty']}\n"
                    f"**Platform:** {row['platform']}\n"
                    f"**Upvotes:** {row['upvotes']}\n"
                    f"Use `!tech view {row['id']}`"
                ),
                inline=False,
            )

        embed.set_footer(
            text="Showing up to 10 matching techniques."
        )

        await ctx.send(embed=embed)

    # ========================================================
    # CATEGORY
    # ========================================================

    @tech.command(name="category")
    async def tech_category(
        self,
        ctx: commands.Context,
        *,
        category_input: str,
    ):
        """Browse techniques by category."""
        category = normalize_category(category_input)

        if category is None:
            await ctx.send(
                "❌ Invalid category.\n"
                "Use `!tech help` to see available categories."
            )
            return

        conn = get_connection()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, name, difficulty, platform, upvotes
                FROM wattson_tech
                WHERE guild_id = ?
                  AND category = ?
                  AND approved = 1
                ORDER BY upvotes DESC, id DESC
                LIMIT 10
                """,
                (
                    ctx.guild.id,
                    category,
                ),
            )

            rows = cursor.fetchall()

        finally:
            conn.close()

        if not rows:
            await ctx.send(
                f"📂 No approved techniques found in **{category}**."
            )
            return

        embed = discord.Embed(
            title=f"📂 {category} Techniques",
            color=discord.Color.from_rgb(255, 105, 180),
        )

        for row in rows:
            embed.add_field(
                name=f"⚡ #{row['id']} — {row['name']}",
                value=(
                    f"**Difficulty:** {row['difficulty']} • "
                    f"**Platform:** {row['platform']}\n"
                    f"⚡ {row['upvotes']} upvotes • "
                    f"`!tech view {row['id']}`"
                ),
                inline=False,
            )

        await ctx.send(embed=embed)

    # ========================================================
    # DIFFICULTY
    # ========================================================

    @tech.command(name="difficulty")
    async def tech_difficulty(
        self,
        ctx: commands.Context,
        *,
        difficulty_input: str,
    ):
        """Browse techniques by difficulty."""
        difficulty = normalize_difficulty(difficulty_input)

        if difficulty is None:
            await ctx.send(
                "❌ Invalid difficulty. Use Easy, Medium, Hard, or Expert."
            )
            return

        conn = get_connection()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, name, category, platform, upvotes
                FROM wattson_tech
                WHERE guild_id = ?
                  AND difficulty = ?
                  AND approved = 1
                ORDER BY upvotes DESC, id DESC
                LIMIT 10
                """,
                (
                    ctx.guild.id,
                    difficulty,
                ),
            )

            rows = cursor.fetchall()

        finally:
            conn.close()

        if not rows:
            await ctx.send(
                f"🎯 No approved **{difficulty}** techniques found."
            )
            return

        embed = discord.Embed(
            title=f"🎯 {difficulty} Wattson Tech",
            color=discord.Color.from_rgb(255, 105, 180),
        )

        for row in rows:
            embed.add_field(
                name=f"⚡ #{row['id']} — {row['name']}",
                value=(
                    f"**Category:** {row['category']} • "
                    f"**Platform:** {row['platform']}\n"
                    f"⚡ {row['upvotes']} upvotes • "
                    f"`!tech view {row['id']}`"
                ),
                inline=False,
            )

        await ctx.send(embed=embed)

    # ========================================================
    # PLATFORM
    # ========================================================

    @tech.command(name="platform")
    async def tech_platform(
        self,
        ctx: commands.Context,
        *,
        platform_input: str,
    ):
        """Browse techniques by platform."""
        platform = normalize_platform(platform_input)

        if platform is None:
            await ctx.send(
                "❌ Invalid platform. Use PC, PlayStation, Xbox, "
                "Console, or All Platforms."
            )
            return

        conn = get_connection()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, name, category, difficulty, upvotes
                FROM wattson_tech
                WHERE guild_id = ?
                  AND platform = ?
                  AND approved = 1
                ORDER BY upvotes DESC, id DESC
                LIMIT 10
                """,
                (
                    ctx.guild.id,
                    platform,
                ),
            )

            rows = cursor.fetchall()

        finally:
            conn.close()

        if not rows:
            await ctx.send(
                f"🎮 No approved techniques found for **{platform}**."
            )
            return

        embed = discord.Embed(
            title=f"🎮 {platform} Wattson Tech",
            color=discord.Color.from_rgb(255, 105, 180),
        )

        for row in rows:
            embed.add_field(
                name=f"⚡ #{row['id']} — {row['name']}",
                value=(
                    f"**Category:** {row['category']} • "
                    f"**Difficulty:** {row['difficulty']}\n"
                    f"⚡ {row['upvotes']} upvotes • "
                    f"`!tech view {row['id']}`"
                ),
                inline=False,
            )

        await ctx.send(embed=embed)

    # ========================================================
    # TOP
    # ========================================================

    @tech.command(name="top")
    async def tech_top(self, ctx: commands.Context):
        """Show the most upvoted techniques."""
        conn = get_connection()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, name, category, difficulty, platform, upvotes
                FROM wattson_tech
                WHERE guild_id = ?
                  AND approved = 1
                ORDER BY upvotes DESC, id DESC
                LIMIT 10
                """,
                (ctx.guild.id,),
            )

            rows = cursor.fetchall()

        finally:
            conn.close()

        if not rows:
            await ctx.send(
                "⚡ There are no approved techniques yet."
            )
            return

        embed = discord.Embed(
            title="🏆 Top Wattson Techniques",
            description="The most upvoted techniques in this server.",
            color=discord.Color.from_rgb(255, 105, 180),
        )

        medals = ["🥇", "🥈", "🥉"]

        for index, row in enumerate(rows):
            prefix = medals[index] if index < 3 else f"**#{index + 1}**"

            embed.add_field(
                name=f"{prefix} {row['name']}",
                value=(
                    f"ID: `{row['id']}` • "
                    f"{row['category']} • "
                    f"{row['difficulty']}\n"
                    f"⚡ **{row['upvotes']}** upvotes"
                ),
                inline=False,
            )

        await ctx.send(embed=embed)

    # ========================================================
    # MINE
    # ========================================================

    @tech.command(name="mine")
    async def tech_mine(self, ctx: commands.Context):
        """Show the user's submitted techniques."""
        conn = get_connection()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, name, category, difficulty, approved, upvotes
                FROM wattson_tech
                WHERE guild_id = ?
                  AND user_id = ?
                ORDER BY id DESC
                LIMIT 15
                """,
                (
                    ctx.guild.id,
                    ctx.author.id,
                ),
            )

            rows = cursor.fetchall()

        finally:
            conn.close()

        if not rows:
            await ctx.send(
                "📝 You haven't submitted any Wattson techniques yet."
            )
            return

        embed = discord.Embed(
            title=f"📝 {ctx.author.display_name}'s Tech",
            color=discord.Color.from_rgb(255, 105, 180),
        )

        for row in rows:
            status = "✅ Approved" if row["approved"] else "🟠 Pending"

            embed.add_field(
                name=f"#{row['id']} — {row['name']}",
                value=(
                    f"{row['category']} • {row['difficulty']}\n"
                    f"{status} • ⚡ {row['upvotes']} upvotes\n"
                    f"`!tech view {row['id']}`"
                ),
                inline=False,
            )

        await ctx.send(embed=embed)

    # ========================================================
    # PENDING
    # ========================================================

    @tech.command(name="pending")
    @commands.has_guild_permissions(manage_guild=True)
    async def tech_pending(self, ctx: commands.Context):
        """Show pending submissions."""
        conn = get_connection()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, user_id, name, category, difficulty, platform
                FROM wattson_tech
                WHERE guild_id = ?
                  AND approved = 0
                ORDER BY id ASC
                LIMIT 20
                """,
                (ctx.guild.id,),
            )

            rows = cursor.fetchall()

        finally:
            conn.close()

        if not rows:
            await ctx.send(
                "✅ There are no pending Wattson Tech submissions."
            )
            return

        embed = discord.Embed(
            title="🛡️ Pending Wattson Tech",
            description="Staff review queue.",
            color=discord.Color.orange(),
        )

        for row in rows:
            member = ctx.guild.get_member(row["user_id"])

            submitter = (
                member.mention
                if member
                else f"<@{row['user_id']}>"
            )

            embed.add_field(
                name=f"#{row['id']} — {row['name']}",
                value=(
                    f"**Submitter:** {submitter}\n"
                    f"**Category:** {row['category']}\n"
                    f"**Difficulty:** {row['difficulty']}\n"
                    f"**Platform:** {row['platform']}\n"
                    f"`!tech view {row['id']}`\n"
                    f"`!tech approve {row['id']}` • "
                    f"`!tech reject {row['id']}`"
                ),
                inline=False,
            )

        await ctx.send(embed=embed)

    # ========================================================
    # APPROVE
    # ========================================================

    @tech.command(name="approve")
    @commands.has_guild_permissions(manage_guild=True)
    async def tech_approve(
        self,
        ctx: commands.Context,
        tech_id: int,
    ):
        """Approve a pending technique."""
        conn = get_connection()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, name, approved
                FROM wattson_tech
                WHERE id = ?
                  AND guild_id = ?
                """,
                (
                    tech_id,
                    ctx.guild.id,
                ),
            )

            tech = cursor.fetchone()

            if tech is None:
                await ctx.send(
                    f"❌ No technique with ID `{tech_id}` exists."
                )
                return

            if tech["approved"]:
                await ctx.send(
                    "ℹ️ That technique is already approved."
                )
                return

            cursor.execute(
                """
                UPDATE wattson_tech
                SET approved = 1,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    utc_now(),
                    tech_id,
                ),
            )

            conn.commit()

        except sqlite3.Error:
            conn.rollback()

            await ctx.send(
                "❌ I couldn't approve that technique."
            )
            return

        finally:
            conn.close()

        await ctx.send(
            f"✅ Approved **{tech['name']}** (`#{tech_id}`)."
        )

    # ========================================================
    # REJECT
    # ========================================================

    @tech.command(name="reject")
    @commands.has_guild_permissions(manage_guild=True)
    async def tech_reject(
        self,
        ctx: commands.Context,
        tech_id: int,
    ):
        """
        Reject and permanently delete a pending technique.
        """
        conn = get_connection()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, name, approved
                FROM wattson_tech
                WHERE id = ?
                  AND guild_id = ?
                """,
                (
                    tech_id,
                    ctx.guild.id,
                ),
            )

            tech = cursor.fetchone()

            if tech is None:
                await ctx.send(
                    f"❌ No technique with ID `{tech_id}` exists."
                )
                return

            if tech["approved"]:
                await ctx.send(
                    "❌ That technique is already approved. "
                    "Use `!tech delete` if it needs to be removed."
                )
                return

            cursor.execute(
                """
                DELETE FROM wattson_tech_votes
                WHERE tech_id = ?
                """,
                (tech_id,),
            )

            cursor.execute(
                """
                DELETE FROM wattson_tech
                WHERE id = ?
                  AND guild_id = ?
                """,
                (
                    tech_id,
                    ctx.guild.id,
                ),
            )

            conn.commit()

        except sqlite3.Error:
            conn.rollback()

            await ctx.send(
                "❌ I couldn't reject that technique."
            )
            return

        finally:
            conn.close()

        await ctx.send(
            f"🗑️ Rejected **{tech['name']}** (`#{tech_id}`)."
        )

    # ========================================================
    # DELETE
    # ========================================================

    @tech.command(name="delete")
    async def tech_delete(
        self,
        ctx: commands.Context,
        tech_id: int,
    ):
        """Delete a technique."""
        conn = get_connection()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, user_id, name
                FROM wattson_tech
                WHERE id = ?
                  AND guild_id = ?
                """,
                (
                    tech_id,
                    ctx.guild.id,
                ),
            )

            tech = cursor.fetchone()

            if tech is None:
                await ctx.send(
                    f"❌ No technique with ID `{tech_id}` exists."
                )
                return

            owner = tech["user_id"] == ctx.author.id

            if not owner and not is_staff(ctx.author):
                await ctx.send(
                    "❌ You can only delete your own submissions "
                    "unless you're staff."
                )
                return

            cursor.execute(
                """
                DELETE FROM wattson_tech_votes
                WHERE tech_id = ?
                """,
                (tech_id,),
            )

            cursor.execute(
                """
                DELETE FROM wattson_tech
                WHERE id = ?
                  AND guild_id = ?
                """,
                (
                    tech_id,
                    ctx.guild.id,
                ),
            )

            conn.commit()

        except sqlite3.Error:
            conn.rollback()

            await ctx.send(
                "❌ I couldn't delete that technique."
            )
            return

        finally:
            conn.close()

        await ctx.send(
            f"🗑️ Deleted **{tech['name']}** (`#{tech_id}`)."
        )

    # ========================================================
    # ERROR HANDLING
    # ========================================================

    @tech.error
    async def tech_error(
        self,
        ctx: commands.Context,
        error: commands.CommandError,
    ):
        """Handle errors from the tech command group."""
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(
                "❌ You need **Manage Server** permission to use that command."
            )
            return

        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                "❌ You're missing a required argument.\n"
                "Use `!tech help` for instructions."
            )
            return

        if isinstance(error, commands.BadArgument):
            await ctx.send(
                "❌ Invalid argument.\n"
                "For technique IDs, use a number such as `!tech view 12`."
            )
            return

        raise error


# ============================================================
# SETUP
# ============================================================

async def setup(bot: commands.Bot):
    await bot.add_cog(WattsonTech(bot))