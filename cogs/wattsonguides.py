"""
Grid Guardian - Wattson Guide Database

Features:
    - Create Wattson guides
    - Search guides
    - Browse by category
    - Browse by difficulty
    - View individual guides
    - Upvote guides
    - Personal guide list
    - Staff moderation
    - SQLite persistence

Commands:
    !guide
    !guide add <title> | <category> | <difficulty> | <description> | <steps> | <media_url>
    !guide view <id>
    !guide search <text>
    !guide category <category>
    !guide difficulty <difficulty>
    !guide top
    !guide latest
    !guide mine
    !guide delete <id>
    !guide approve <id>
    !guide pending
    !guide help
"""

import sqlite3
from datetime import datetime, timezone
from typing import Optional

import discord
from discord.ext import commands


DB_PATH = "gridguardian.db"


CATEGORIES = {
    "beginner",
    "advanced",
    "mechanics",
    "fences",
    "pylon",
    "ranked",
    "movement",
    "teamplay",
    "positioning",
    "endgame",
    "general",
}

DIFFICULTIES = {
    "beginner",
    "intermediate",
    "advanced",
    "expert",
}


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
            CREATE TABLE IF NOT EXISTS wattson_guides (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                description TEXT NOT NULL,
                steps TEXT NOT NULL,
                media_url TEXT,
                upvotes INTEGER NOT NULL DEFAULT 0,
                approved INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS wattson_guide_votes (
                guide_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (guide_id, user_id)
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_wattson_guides_guild
            ON wattson_guides(guild_id)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_wattson_guides_category
            ON wattson_guides(guild_id, category)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_wattson_guides_difficulty
            ON wattson_guides(guild_id, difficulty)
            """
        )

        conn.commit()

    finally:
        conn.close()


def get_guide(
    guide_id: int,
    guild_id: int,
) -> Optional[sqlite3.Row]:
    conn = connect_db()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM wattson_guides
            WHERE id = ?
              AND guild_id = ?
            """,
            (guide_id, guild_id),
        )

        return cursor.fetchone()

    finally:
        conn.close()


def is_staff(member: discord.Member) -> bool:
    return member.guild_permissions.manage_guild


def shorten(text: str, length: int) -> str:
    if len(text) <= length:
        return text

    return text[: length - 3] + "..."


# ============================================================
# GUIDE VIEW
# ============================================================

class GuideView(discord.ui.View):
    def __init__(self, guide_id: int):
        super().__init__(timeout=300)
        self.guide_id = guide_id

        self.add_item(GuideUpvoteButton(guide_id))


class GuideUpvoteButton(discord.ui.Button):
    def __init__(self, guide_id: int):
        super().__init__(
            label="Upvote",
            emoji="⬆️",
            style=discord.ButtonStyle.primary,
            custom_id=f"gridguardian:guide_upvote:{guide_id}",
        )

        self.guide_id = guide_id

    async def callback(
        self,
        interaction: discord.Interaction,
    ):
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This can only be used in a server.",
                ephemeral=True,
            )
            return

        conn = connect_db()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id
                FROM wattson_guides
                WHERE id = ?
                  AND guild_id = ?
                  AND approved = 1
                """,
                (
                    self.guide_id,
                    interaction.guild.id,
                ),
            )

            guide = cursor.fetchone()

            if not guide:
                await interaction.response.send_message(
                    "❌ That guide no longer exists.",
                    ephemeral=True,
                )
                return

            cursor.execute(
                """
                SELECT 1
                FROM wattson_guide_votes
                WHERE guide_id = ?
                  AND user_id = ?
                """,
                (
                    self.guide_id,
                    interaction.user.id,
                ),
            )

            existing_vote = cursor.fetchone()

            if existing_vote:
                await interaction.response.send_message(
                    "❌ You already upvoted this guide.",
                    ephemeral=True,
                )
                return

            cursor.execute(
                """
                INSERT INTO wattson_guide_votes (
                    guide_id,
                    user_id,
                    created_at
                )
                VALUES (?, ?, ?)
                """,
                (
                    self.guide_id,
                    interaction.user.id,
                    now_iso(),
                ),
            )

            cursor.execute(
                """
                UPDATE wattson_guides
                SET upvotes = upvotes + 1,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    now_iso(),
                    self.guide_id,
                ),
            )

            conn.commit()

        finally:
            conn.close()

        await interaction.response.send_message(
            "⬆️ Guide upvoted!",
            ephemeral=True,
        )


# ============================================================
# COG
# ============================================================

class WattsonGuideDatabase(commands.Cog):
    """Wattson community guide database."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        init_db()

    # ========================================================
    # ROOT
    # ========================================================

    @commands.group(
        name="guide",
        aliases=["guides", "wguide"],
        invoke_without_command=True,
    )
    @commands.guild_only()
    async def guide(self, ctx: commands.Context):
        """Wattson Guide Database."""

        embed = discord.Embed(
            title="⚡ Wattson Guide Database",
            description=(
                "A searchable library of Wattson guides "
                "for the Power Grid.\n\n"
                "**Quick start**\n"
                "`!guide search fences`\n"
                "`!guide category mechanics`\n"
                "`!guide top`\n"
                "`!guide view 1`"
            ),
            color=discord.Color.from_rgb(255, 105, 180),
        )

        embed.add_field(
            name="Browse",
            value=(
                "`!guide search <text>`\n"
                "`!guide category <category>`\n"
                "`!guide difficulty <difficulty>`\n"
                "`!guide top`\n"
                "`!guide latest`"
            ),
            inline=True,
        )

        embed.add_field(
            name="Create",
            value=(
                "`!guide add ...`\n"
                "`!guide mine`\n"
                "`!guide delete <id>`"
            ),
            inline=True,
        )

        embed.add_field(
            name="Staff",
            value=(
                "`!guide approve <id>`\n"
                "`!guide pending`"
            ),
            inline=True,
        )

        await ctx.send(embed=embed)

    # ========================================================
    # HELP
    # ========================================================

    @guide.command(name="help")
    async def guide_help(self, ctx: commands.Context):
        """Show guide commands."""

        embed = discord.Embed(
            title="⚡ Wattson Guide Database Help",
            color=discord.Color.from_rgb(255, 105, 180),
        )

        embed.add_field(
            name="Create a Guide",
            value=(
                "`!guide add Title | Category | Difficulty | "
                "Description | Steps | Media URL`\n\n"
                "**Example:**\n"
                "`!guide add Basic Fence Placement | "
                "fences | beginner | Learn the fundamentals | "
                "1. Place node A\\n2. Place node B\\n3. Connect them | "
                "https://youtube.com/...`"
            ),
            inline=False,
        )

        embed.add_field(
            name="Browse",
            value=(
                "`!guide view <id>`\n"
                "`!guide search <text>`\n"
                "`!guide category <category>`\n"
                "`!guide difficulty <difficulty>`\n"
                "`!guide top`\n"
                "`!guide latest`\n"
                "`!guide mine`"
            ),
            inline=False,
        )

        embed.add_field(
            name="Staff",
            value=(
                "`!guide approve <id>`\n"
                "`!guide pending`\n"
                "`!guide delete <id>`"
            ),
            inline=False,
        )

        embed.add_field(
            name="Categories",
            value=", ".join(sorted(CATEGORIES)),
            inline=False,
        )

        embed.add_field(
            name="Difficulties",
            value=", ".join(sorted(DIFFICULTIES)),
            inline=False,
        )

        await ctx.send(embed=embed)

    # ========================================================
    # ADD
    # ========================================================

    @guide.command(name="add")
    @commands.guild_only()
    async def guide_add(
        self,
        ctx: commands.Context,
        *,
        data: str,
    ):
        """
        Add a guide.

        Format:
        Title | Category | Difficulty | Description | Steps | Media URL
        """

        parts = [part.strip() for part in data.split("|", 5)]

        if len(parts) != 6:
            await ctx.send(
                "❌ Use:\n"
                "`!guide add Title | Category | Difficulty | "
                "Description | Steps | Media URL`"
            )
            return

        (
            title,
            category,
            difficulty,
            description,
            steps,
            media_url,
        ) = parts

        category = category.lower()
        difficulty = difficulty.lower()

        if not title:
            await ctx.send("❌ Guide title cannot be empty.")
            return

        if category not in CATEGORIES:
            await ctx.send(
                "❌ Invalid category.\n"
                f"Available categories: `{', '.join(sorted(CATEGORIES))}`"
            )
            return

        if difficulty not in DIFFICULTIES:
            await ctx.send(
                "❌ Invalid difficulty.\n"
                f"Available difficulties: `{', '.join(sorted(DIFFICULTIES))}`"
            )
            return

        if not description:
            await ctx.send(
                "❌ Guide description cannot be empty."
            )
            return

        if not steps:
            await ctx.send(
                "❌ Guide steps cannot be empty."
            )
            return

        if len(title) > 100:
            await ctx.send(
                "❌ Guide title must be 100 characters or fewer."
            )
            return

        if len(description) > 1000:
            await ctx.send(
                "❌ Description must be 1,000 characters or fewer."
            )
            return

        if len(steps) > 4000:
            await ctx.send(
                "❌ Steps must be 4,000 characters or fewer."
            )
            return

        if media_url and len(media_url) > 500:
            await ctx.send(
                "❌ Media URL must be 500 characters or fewer."
            )
            return

        conn = connect_db()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO wattson_guides (
                    guild_id,
                    user_id,
                    title,
                    category,
                    difficulty,
                    description,
                    steps,
                    media_url,
                    upvotes,
                    approved,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 1, ?, ?)
                """,
                (
                    ctx.guild.id,
                    ctx.author.id,
                    title,
                    category,
                    difficulty,
                    description,
                    steps,
                    media_url or None,
                    now_iso(),
                    now_iso(),
                ),
            )

            guide_id = cursor.lastrowid

            conn.commit()

        finally:
            conn.close()

        embed = discord.Embed(
            title="⚡ Guide Added",
            description=(
                f"**{title}**\n\n"
                f"Guide ID: `#{guide_id}`"
            ),
            color=discord.Color.green(),
        )

        embed.add_field(
            name="Category",
            value=category.title(),
            inline=True,
        )

        embed.add_field(
            name="Difficulty",
            value=difficulty.title(),
            inline=True,
        )

        embed.add_field(
            name="Author",
            value=ctx.author.mention,
            inline=True,
        )

        embed.add_field(
            name="View",
            value=f"`!guide view {guide_id}`",
            inline=False,
        )

        await ctx.send(embed=embed)

    # ========================================================
    # VIEW
    # ========================================================

    @guide.command(name="view")
    @commands.guild_only()
    async def guide_view(
        self,
        ctx: commands.Context,
        guide_id: int,
    ):
        """View a guide."""

        guide = get_guide(
            guide_id,
            ctx.guild.id,
        )

        if not guide:
            await ctx.send("❌ Guide not found.")
            return

        if not guide["approved"] and not is_staff(ctx.author):
            await ctx.send("❌ That guide is awaiting approval.")
            return

        author = ctx.guild.get_member(guide["user_id"])

        embed = discord.Embed(
            title=f"⚡ #{guide['id']} — {guide['title']}",
            description=guide["description"],
            color=discord.Color.from_rgb(255, 105, 180),
        )

        embed.add_field(
            name="Category",
            value=guide["category"].title(),
            inline=True,
        )

        embed.add_field(
            name="Difficulty",
            value=guide["difficulty"].title(),
            inline=True,
        )

        embed.add_field(
            name="⬆️ Upvotes",
            value=str(guide["upvotes"]),
            inline=True,
        )

        embed.add_field(
            name="📖 Steps",
            value=guide["steps"],
            inline=False,
        )

        embed.add_field(
            name="Author",
            value=(
                author.mention
                if author
                else f"<@{guide['user_id']}>"
            ),
            inline=True,
        )

        embed.add_field(
            name="Status",
            value=(
                "✅ Approved"
                if guide["approved"]
                else "⏳ Pending Approval"
            ),
            inline=True,
        )

        if guide["media_url"]:
            embed.add_field(
                name="🎬 Tutorial / Media",
                value=f"[Open Media]({guide['media_url']})",
                inline=False,
            )

        embed.set_footer(
            text="Use the button below to upvote this guide."
        )

        await ctx.send(
            embed=embed,
            view=GuideView(guide_id),
        )

    # ========================================================
    # SEARCH
    # ========================================================

    @guide.command(name="search")
    @commands.guild_only()
    async def guide_search(
        self,
        ctx: commands.Context,
        *,
        query: str,
    ):
        """Search guides."""

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
                FROM wattson_guides
                WHERE guild_id = ?
                  AND approved = 1
                  AND (
                      title LIKE ?
                      OR category LIKE ?
                      OR difficulty LIKE ?
                      OR description LIKE ?
                      OR steps LIKE ?
                  )
                ORDER BY upvotes DESC, id DESC
                LIMIT 15
                """,
                (
                    ctx.guild.id,
                    search,
                    search,
                    search,
                    search,
                    search,
                ),
            )

            guides = cursor.fetchall()

        finally:
            conn.close()

        if not guides:
            await ctx.send(
                f"🔎 No guides found for `{query}`."
            )
            return

        embed = discord.Embed(
            title=f"🔎 Guide Search — {query}",
            color=discord.Color.from_rgb(255, 105, 180),
        )

        lines = []

        for guide in guides:
            lines.append(
                f"**#{guide['id']} — {guide['title']}**\n"
                f"{guide['category'].title()} • "
                f"{guide['difficulty'].title()} • "
                f"⬆️ `{guide['upvotes']}`"
            )

        embed.description = "\n\n".join(lines)

        embed.set_footer(
            text="Use !guide view <id> to read a guide."
        )

        await ctx.send(embed=embed)

    # ========================================================
    # CATEGORY
    # ========================================================

    @guide.command(name="category")
    @commands.guild_only()
    async def guide_category(
        self,
        ctx: commands.Context,
        *,
        category: str,
    ):
        """Browse guides by category."""

        category = category.strip().lower()

        if category not in CATEGORIES:
            await ctx.send(
                "❌ Invalid category.\n"
                f"Available: `{', '.join(sorted(CATEGORIES))}`"
            )
            return

        conn = connect_db()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT *
                FROM wattson_guides
                WHERE guild_id = ?
                  AND category = ?
                  AND approved = 1
                ORDER BY upvotes DESC, id DESC
                LIMIT 15
                """,
                (
                    ctx.guild.id,
                    category,
                ),
            )

            guides = cursor.fetchall()

        finally:
            conn.close()

        if not guides:
            await ctx.send(
                f"📚 No guides found in `{category}`."
            )
            return

        embed = discord.Embed(
            title=f"📚 {category.title()} Guides",
            color=discord.Color.from_rgb(255, 105, 180),
        )

        lines = []

        for guide in guides:
            lines.append(
                f"**#{guide['id']} — {guide['title']}**\n"
                f"{guide['difficulty'].title()} • "
                f"⬆️ `{guide['upvotes']}`"
            )

        embed.description = "\n\n".join(lines)

        await ctx.send(embed=embed)

    # ========================================================
    # DIFFICULTY
    # ========================================================

    @guide.command(name="difficulty")
    @commands.guild_only()
    async def guide_difficulty(
        self,
        ctx: commands.Context,
        *,
        difficulty: str,
    ):
        """Browse guides by difficulty."""

        difficulty = difficulty.strip().lower()

        if difficulty not in DIFFICULTIES:
            await ctx.send(
                "❌ Invalid difficulty.\n"
                f"Available: `{', '.join(sorted(DIFFICULTIES))}`"
            )
            return

        conn = connect_db()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT *
                FROM wattson_guides
                WHERE guild_id = ?
                  AND difficulty = ?
                  AND approved = 1
                ORDER BY upvotes DESC, id DESC
                LIMIT 15
                """,
                (
                    ctx.guild.id,
                    difficulty,
                ),
            )

            guides = cursor.fetchall()

        finally:
            conn.close()

        if not guides:
            await ctx.send(
                f"📚 No `{difficulty}` guides found."
            )
            return

        embed = discord.Embed(
            title=f"📚 {difficulty.title()} Guides",
            color=discord.Color.from_rgb(255, 105, 180),
        )

        lines = []

        for guide in guides:
            lines.append(
                f"**#{guide['id']} — {guide['title']}**\n"
                f"{guide['category'].title()} • "
                f"⬆️ `{guide['upvotes']}`"
            )

        embed.description = "\n\n".join(lines)

        await ctx.send(embed=embed)

    # ========================================================
    # TOP
    # ========================================================

    @guide.command(name="top")
    @commands.guild_only()
    async def guide_top(self, ctx: commands.Context):
        """Show most-upvoted guides."""

        conn = connect_db()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT *
                FROM wattson_guides
                WHERE guild_id = ?
                  AND approved = 1
                ORDER BY upvotes DESC, id DESC
                LIMIT 10
                """,
                (ctx.guild.id,),
            )

            guides = cursor.fetchall()

        finally:
            conn.close()

        if not guides:
            await ctx.send(
                "📚 There aren't any guides yet."
            )
            return

        embed = discord.Embed(
            title="🏆 Top Wattson Guides",
            description="Most upvoted guides in the Power Grid.",
            color=discord.Color.gold(),
        )

        lines = []

        for position, guide in enumerate(guides, start=1):
            lines.append(
                f"**{position}. #{guide['id']} — {guide['title']}**\n"
                f"{guide['category'].title()} • "
                f"{guide['difficulty'].title()} • "
                f"⬆️ `{guide['upvotes']}`"
            )

        embed.add_field(
            name="Guides",
            value="\n\n".join(lines),
            inline=False,
        )

        await ctx.send(embed=embed)

    # ========================================================
    # LATEST
    # ========================================================

    @guide.command(name="latest")
    @commands.guild_only()
    async def guide_latest(self, ctx: commands.Context):
        """Show newest guides."""

        conn = connect_db()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT *
                FROM wattson_guides
                WHERE guild_id = ?
                  AND approved = 1
                ORDER BY id DESC
                LIMIT 10
                """,
                (ctx.guild.id,),
            )

            guides = cursor.fetchall()

        finally:
            conn.close()

        if not guides:
            await ctx.send(
                "📚 There aren't any guides yet."
            )
            return

        embed = discord.Embed(
            title="🆕 Latest Wattson Guides",
            color=discord.Color.from_rgb(255, 105, 180),
        )

        lines = []

        for guide in guides:
            lines.append(
                f"**#{guide['id']} — {guide['title']}**\n"
                f"{guide['category'].title()} • "
                f"{guide['difficulty'].title()} • "
                f"⬆️ `{guide['upvotes']}`"
            )

        embed.description = "\n\n".join(lines)

        await ctx.send(embed=embed)

    # ========================================================
    # MINE
    # ========================================================

    @guide.command(name="mine")
    @commands.guild_only()
    async def guide_mine(self, ctx: commands.Context):
        """Show guides created by the user."""

        conn = connect_db()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT *
                FROM wattson_guides
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

            guides = cursor.fetchall()

        finally:
            conn.close()

        if not guides:
            await ctx.send(
                "📚 You haven't created any guides yet."
            )
            return

        embed = discord.Embed(
            title="📚 My Wattson Guides",
            color=discord.Color.from_rgb(255, 105, 180),
        )

        lines = []

        for guide in guides:
            status = (
                "✅"
                if guide["approved"]
                else "⏳"
            )

            lines.append(
                f"{status} **#{guide['id']} — {guide['title']}**\n"
                f"{guide['category'].title()} • "
                f"{guide['difficulty'].title()} • "
                f"⬆️ `{guide['upvotes']}`"
            )

        embed.description = "\n\n".join(lines)

        await ctx.send(embed=embed)

    # ========================================================
    # DELETE
    # ========================================================

    @guide.command(name="delete")
    @commands.guild_only()
    async def guide_delete(
        self,
        ctx: commands.Context,
        guide_id: int,
    ):
        """Delete a guide."""

        guide = get_guide(
            guide_id,
            ctx.guild.id,
        )

        if not guide:
            await ctx.send("❌ Guide not found.")
            return

        if (
            guide["user_id"] != ctx.author.id
            and not is_staff(ctx.author)
        ):
            await ctx.send(
                "❌ You can only delete your own guides."
            )
            return

        conn = connect_db()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                DELETE FROM wattson_guide_votes
                WHERE guide_id = ?
                """,
                (guide_id,),
            )

            cursor.execute(
                """
                DELETE FROM wattson_guides
                WHERE id = ?
                  AND guild_id = ?
                """,
                (
                    guide_id,
                    ctx.guild.id,
                ),
            )

            conn.commit()

        finally:
            conn.close()

        await ctx.send(
            f"🗑️ Guide `#{guide_id}` has been deleted."
        )

    # ========================================================
    # APPROVE
    # ========================================================

    @guide.command(name="approve")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def guide_approve(
        self,
        ctx: commands.Context,
        guide_id: int,
    ):
        """Approve a guide."""

        guide = get_guide(
            guide_id,
            ctx.guild.id,
        )

        if not guide:
            await ctx.send("❌ Guide not found.")
            return

        if guide["approved"]:
            await ctx.send(
                "✅ That guide is already approved."
            )
            return

        conn = connect_db()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE wattson_guides
                SET approved = 1,
                    updated_at = ?
                WHERE id = ?
                  AND guild_id = ?
                """,
                (
                    now_iso(),
                    guide_id,
                    ctx.guild.id,
                ),
            )

            conn.commit()

        finally:
            conn.close()

        await ctx.send(
            f"✅ Guide **#{guide_id} — {guide['title']}** "
            f"has been approved."
        )

    # ========================================================
    # PENDING
    # ========================================================

    @guide.command(name="pending")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def guide_pending(self, ctx: commands.Context):
        """Show pending guides."""

        conn = connect_db()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT *
                FROM wattson_guides
                WHERE guild_id = ?
                  AND approved = 0
                ORDER BY id ASC
                LIMIT 20
                """,
                (ctx.guild.id,),
            )

            guides = cursor.fetchall()

        finally:
            conn.close()

        if not guides:
            await ctx.send(
                "✅ There are no pending guides."
            )
            return

        embed = discord.Embed(
            title="⏳ Pending Wattson Guides",
            color=discord.Color.orange(),
        )

        lines = []

        for guide in guides:
            lines.append(
                f"**#{guide['id']} — {guide['title']}**\n"
                f"Author: <@{guide['user_id']}>\n"
                f"Category: `{guide['category']}` • "
                f"Difficulty: `{guide['difficulty']}`"
            )

        embed.description = "\n\n".join(lines)

        embed.set_footer(
            text="Use !guide approve <id> to approve a guide."
        )

        await ctx.send(embed=embed)

    # ========================================================
    # ERROR HANDLER
    # ========================================================

    @guide.error
    async def guide_error(
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
                "Use `!guide help` for the correct format."
            )
            return

        if isinstance(
            error,
            commands.BadArgument,
        ):
            await ctx.send(
                "❌ That value isn't valid.\n"
                "Use `!guide help` for the command format."
            )
            return

        raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(WattsonGuideDatabase(bot))