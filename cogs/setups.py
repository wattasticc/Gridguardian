import re
import sqlite3
from datetime import datetime, timezone

import discord
from discord.ext import commands


# ============================================================
# GRID GUARDIAN — WATTSON SETUP LIBRARY
# ============================================================

DB_PATH = "gridguardian.db"
EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)

MAPS = {
    "we": "World's Edge",
    "worlds-edge": "World's Edge",
    "worlds edge": "World's Edge",

    "sp": "Storm Point",
    "storm-point": "Storm Point",
    "storm point": "Storm Point",

    "olympus": "Olympus",

    "bm": "Broken Moon",
    "broken-moon": "Broken Moon",
    "broken moon": "Broken Moon",

    "ed": "E-District",
    "e-district": "E-District",
    "e district": "E-District",

    "kc": "King's Canyon",
    "kings-canyon": "King's Canyon",
    "kings canyon": "King's Canyon",
    "king's canyon": "King's Canyon",
}

CATEGORIES = {
    "building": "🏢 Building",
    "endgame": "🏆 Endgame",
    "zone": "⭕ Zone",
    "fences": "⚡ Fences",
    "fence": "⚡ Fences",
    "pylon": "🔋 Pylon",
    "survival": "🛡️ Survival",
    "ranked": "💎 Ranked",
    "poi": "📍 POI",
}


# ============================================================
# DATABASE
# ============================================================

def db_connect():
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    with db_connect() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS wattson_setups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                map_name TEXT NOT NULL,
                category TEXT NOT NULL,
                location TEXT NOT NULL,
                description TEXT NOT NULL,
                media_url TEXT,
                upvotes INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        db.execute(
            """
            CREATE TABLE IF NOT EXISTS wattson_setup_votes (
                setup_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                PRIMARY KEY(setup_id, user_id)
            )
            """
        )

        db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_wattson_setups_guild_map
            ON wattson_setups(guild_id, map_name)
            """
        )

        db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_wattson_setups_guild_category
            ON wattson_setups(guild_id, category)
            """
        )

        db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_wattson_setups_user
            ON wattson_setups(guild_id, user_id)
            """
        )


# ============================================================
# HELPERS
# ============================================================

def clean_text(value, max_length):
    value = re.sub(r"\s+", " ", value.strip())
    return value[:max_length]


def normalize_map(value):
    return MAPS.get(value.lower().strip())


def normalize_category(value):
    return CATEGORIES.get(value.lower().strip())


def setup_url_is_valid(url):
    if not url:
        return True

    return url.lower().startswith(
        (
            "https://",
            "http://",
        )
    )


def get_setup(setup_id, guild_id):
    with db_connect() as db:
        return db.execute(
            """
            SELECT *
            FROM wattson_setups
            WHERE id = ?
              AND guild_id = ?
            """,
            (setup_id, guild_id),
        ).fetchone()


def format_map_name(map_name):
    return MAPS.get(
        map_name.lower(),
        map_name.replace("-", " ").title(),
    )


def format_category(category):
    return CATEGORIES.get(
        category.lower(),
        category.title(),
    )


def creator_mention(guild, user_id):
    member = guild.get_member(user_id)

    if member:
        return member.mention

    return f"<@{user_id}>"


# ============================================================
# EMBEDS
# ============================================================

def create_setup_embed(setup, guild):
    embed = discord.Embed(
        title=f"⚡ {setup['name']}",
        description=setup["description"],
        color=EMBED_COLOR,
    )

    embed.add_field(
        name="🗺️ Map",
        value=format_map_name(setup["map_name"]),
        inline=True,
    )

    embed.add_field(
        name="📂 Category",
        value=format_category(setup["category"]),
        inline=True,
    )

    embed.add_field(
        name="📍 Location",
        value=setup["location"],
        inline=True,
    )

    embed.add_field(
        name="⭐ Upvotes",
        value=str(setup["upvotes"]),
        inline=True,
    )

    embed.add_field(
        name="👤 Creator",
        value=creator_mention(guild, setup["user_id"]),
        inline=True,
    )

    embed.add_field(
        name="🆔 Setup ID",
        value=f"`#{setup['id']}`",
        inline=True,
    )

    if setup["media_url"]:
        embed.add_field(
            name="🔗 Media",
            value=setup["media_url"],
            inline=False,
        )

    try:
        created_at = datetime.fromisoformat(
            setup["created_at"]
        )

        embed.set_footer(
            text=(
                f"Created "
                f"{discord.utils.format_dt(created_at, 'R')} "
                f"• Wattson Setup Library"
            )
        )

    except (ValueError, TypeError):
        embed.set_footer(
            text="Wattson Setup Library"
        )

    return embed


def create_list_embed(rows, title):
    embed = discord.Embed(
        title=title,
        color=EMBED_COLOR,
    )

    if not rows:
        embed.description = (
            "No Wattson setups matched your search."
        )
        return embed

    lines = []

    for setup in rows:
        lines.append(
            f"**`#{setup['id']}` {setup['name']}**\n"
            f"{format_map_name(setup['map_name'])} • "
            f"{format_category(setup['category'])} • "
            f"📍 {setup['location']} • "
            f"⭐ {setup['upvotes']}"
        )

    embed.description = "\n\n".join(lines)

    embed.set_footer(
        text=f"{len(rows)} setup(s) found"
    )

    return embed


# ============================================================
# SETUP VIEW
# ============================================================

class SetupView(discord.ui.View):
    def __init__(self, setup_id):
        super().__init__(timeout=300)
        self.setup_id = setup_id

    @discord.ui.button(
        label="Upvote",
        emoji="⭐",
        style=discord.ButtonStyle.primary,
    )
    async def upvote(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if not interaction.guild:
            return

        with db_connect() as db:
            setup = db.execute(
                """
                SELECT *
                FROM wattson_setups
                WHERE id = ?
                  AND guild_id = ?
                """,
                (
                    self.setup_id,
                    interaction.guild.id,
                ),
            ).fetchone()

            if not setup:
                await interaction.response.send_message(
                    "❌ This setup no longer exists.",
                    ephemeral=True,
                )
                return

            existing_vote = db.execute(
                """
                SELECT 1
                FROM wattson_setup_votes
                WHERE setup_id = ?
                  AND user_id = ?
                """,
                (
                    self.setup_id,
                    interaction.user.id,
                ),
            ).fetchone()

            if existing_vote:
                await interaction.response.send_message(
                    "ℹ️ You already upvoted this setup.",
                    ephemeral=True,
                )
                return

            db.execute(
                """
                INSERT INTO wattson_setup_votes (
                    setup_id,
                    user_id
                )
                VALUES (?, ?)
                """,
                (
                    self.setup_id,
                    interaction.user.id,
                ),
            )

            db.execute(
                """
                UPDATE wattson_setups
                SET upvotes = upvotes + 1,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    self.setup_id,
                ),
            )

            updated_setup = db.execute(
                """
                SELECT *
                FROM wattson_setups
                WHERE id = ?
                """,
                (self.setup_id,),
            ).fetchone()

        await interaction.response.edit_message(
            embed=create_setup_embed(
                updated_setup,
                interaction.guild,
            ),
            view=SetupView(self.setup_id),
        )


# ============================================================
# COG
# ============================================================

class Setups(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        initialize_database()

    # ========================================================
    # !setup
    # ========================================================

    @commands.group(
        name="setup",
        invoke_without_command=True,
        case_insensitive=True,
    )
    @commands.guild_only()
    async def setup_group(self, ctx):
        """Wattson Setup Library."""

        embed = discord.Embed(
            title="⚡ Wattson Setup Library",
            description=(
                "Save and discover useful Wattson setups "
                "from your community.\n\n"

                "**📚 Commands**\n"
                "`!setup add`\n"
                "`!setup view <id>`\n"
                "`!setup search <text>`\n"
                "`!setup map <map>`\n"
                "`!setup category <category>`\n"
                "`!setup mine`\n"
                "`!setup top`\n"
                "`!setup delete <id>`\n"
                "`!setup help`"
            ),
            color=EMBED_COLOR,
        )

        embed.add_field(
            name="➕ Add a Setup",
            value=(
                "`!setup add Name | Map | Category | "
                "Location | Description | Media URL`"
            ),
            inline=False,
        )

        embed.add_field(
            name="🗺️ Maps",
            value=(
                "World's Edge • Storm Point • Olympus • "
                "Broken Moon • E-District • King's Canyon"
            ),
            inline=False,
        )

        embed.set_footer(
            text="Use !setup help for detailed instructions."
        )

        await ctx.send(embed=embed)

    # ========================================================
    # ADD
    # ========================================================

    @setup_group.command(name="add")
    @commands.guild_only()
    async def setup_add(self, ctx, *, data: str):
        """
        Add a Wattson setup.

        Format:
        !setup add Name | Map | Category | Location | Description | Media URL
        """

        parts = [
            part.strip()
            for part in data.split("|")
        ]

        if len(parts) < 5:
            await ctx.send(
                "❌ Incorrect format.\n\n"
                "Use:\n"
                "`!setup add Name | Map | Category | "
                "Location | Description | Media URL`\n\n"
                "The Media URL is optional.",
                delete_after=12,
            )
            return

        name = clean_text(
            parts[0],
            80,
        )

        map_name = parts[1].lower().strip()

        category = parts[2].lower().strip()

        location = clean_text(
            parts[3],
            100,
        )

        description = clean_text(
            parts[4],
            1000,
        )

        media_url = (
            clean_text(parts[5], 500)
            if len(parts) >= 6
            else ""
        )

        if not name:
            await ctx.send(
                "❌ Setup name cannot be empty.",
                delete_after=5,
            )
            return

        if map_name not in MAPS:
            await ctx.send(
                "❌ Invalid map.\n\n"
                "Available maps:\n"
                "`WE` • `Storm Point` • `Olympus` • "
                "`Broken Moon` • `E-District` • `King's Canyon`",
                delete_after=8,
            )
            return

        if category not in CATEGORIES:
            await ctx.send(
                "❌ Invalid category.\n\n"
                "Available categories:\n"
                "`building` • `endgame` • `zone` • `fences` • "
                "`pylon` • `survival` • `ranked` • `poi`",
                delete_after=8,
            )
            return

        if not location:
            await ctx.send(
                "❌ Location cannot be empty.",
                delete_after=5,
            )
            return

        if not description:
            await ctx.send(
                "❌ Description cannot be empty.",
                delete_after=5,
            )
            return

        if not setup_url_is_valid(media_url):
            await ctx.send(
                "❌ Media URL must begin with "
                "`https://` or `http://`.",
                delete_after=6,
            )
            return

        now = datetime.now(
            timezone.utc
        ).isoformat()

        with db_connect() as db:
            cursor = db.execute(
                """
                INSERT INTO wattson_setups (
                    guild_id,
                    user_id,
                    name,
                    map_name,
                    category,
                    location,
                    description,
                    media_url,
                    upvotes,
                    created_at,
                    updated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?
                )
                """,
                (
                    ctx.guild.id,
                    ctx.author.id,
                    name,
                    map_name,
                    category,
                    location,
                    description,
                    media_url or None,
                    now,
                    now,
                ),
            )

            setup_id = cursor.lastrowid

        setup = get_setup(
            setup_id,
            ctx.guild.id,
        )

        await ctx.send(
            content=(
                "✅ **Setup added to the Wattson Setup Library!**"
            ),
            embed=create_setup_embed(
                setup,
                ctx.guild,
            ),
            view=SetupView(setup_id),
        )

    # ========================================================
    # VIEW
    # ========================================================

    @setup_group.command(name="view")
    @commands.guild_only()
    async def setup_view(
        self,
        ctx,
        setup_id: int,
    ):
        """View a setup by ID."""

        setup = get_setup(
            setup_id,
            ctx.guild.id,
        )

        if not setup:
            await ctx.send(
                "❌ I couldn't find that setup.",
                delete_after=5,
            )
            return

        await ctx.send(
            embed=create_setup_embed(
                setup,
                ctx.guild,
            ),
            view=SetupView(setup_id),
        )

    # ========================================================
    # SEARCH
    # ========================================================

    @setup_group.command(name="search")
    @commands.guild_only()
    async def setup_search(
        self,
        ctx,
        *,
        query: str,
    ):
        """Search setup names, locations, and descriptions."""

        query = clean_text(
            query,
            100,
        )

        if not query:
            await ctx.send(
                "❌ Enter something to search for.",
                delete_after=5,
            )
            return

        pattern = f"%{query}%"

        with db_connect() as db:
            rows = db.execute(
                """
                SELECT *
                FROM wattson_setups
                WHERE guild_id = ?
                  AND (
                    name LIKE ?
                    OR location LIKE ?
                    OR description LIKE ?
                  )
                ORDER BY upvotes DESC, id DESC
                LIMIT 100
                """,
                (
                    ctx.guild.id,
                    pattern,
                    pattern,
                    pattern,
                ),
            ).fetchall()

        await ctx.send(
            embed=create_list_embed(
                rows,
                f"🔎 Setup Search: {query}",
            )
        )

    # ========================================================
    # MAP
    # ========================================================

    @setup_group.command(name="map")
    @commands.guild_only()
    async def setup_map(
        self,
        ctx,
        *,
        map_name: str,
    ):
        """Browse setups for a map."""

        map_key = map_name.lower().strip()

        if map_key not in MAPS:
            await ctx.send(
                "❌ Invalid map.\n\n"
                "Try `WE`, `Storm Point`, `Olympus`, "
                "`Broken Moon`, `E-District`, or `King's Canyon`.",
                delete_after=8,
            )
            return

        with db_connect() as db:
            rows = db.execute(
                """
                SELECT *
                FROM wattson_setups
                WHERE guild_id = ?
                  AND map_name = ?
                ORDER BY upvotes DESC, id DESC
                LIMIT 100
                """,
                (
                    ctx.guild.id,
                    map_key,
                ),
            ).fetchall()

        await ctx.send(
            embed=create_list_embed(
                rows,
                f"🗺️ {MAPS[map_key]} Setups",
            )
        )

    # ========================================================
    # CATEGORY
    # ========================================================

    @setup_group.command(name="category")
    @commands.guild_only()
    async def setup_category(
        self,
        ctx,
        *,
        category: str,
    ):
        """Browse setups by category."""

        category_key = category.lower().strip()

        if category_key not in CATEGORIES:
            await ctx.send(
                "❌ Invalid category.\n\n"
                "Try `building`, `endgame`, `zone`, `fences`, "
                "`pylon`, `survival`, `ranked`, or `poi`.",
                delete_after=8,
            )
            return

        with db_connect() as db:
            rows = db.execute(
                """
                SELECT *
                FROM wattson_setups
                WHERE guild_id = ?
                  AND category = ?
                ORDER BY upvotes DESC, id DESC
                LIMIT 100
                """,
                (
                    ctx.guild.id,
                    category_key,
                ),
            ).fetchall()

        await ctx.send(
            embed=create_list_embed(
                rows,
                f"{CATEGORIES[category_key]} Setups",
            )
        )

    # ========================================================
    # MINE
    # ========================================================

    @setup_group.command(name="mine")
    @commands.guild_only()
    async def setup_mine(self, ctx):
        """Show your submitted setups."""

        with db_connect() as db:
            rows = db.execute(
                """
                SELECT *
                FROM wattson_setups
                WHERE guild_id = ?
                  AND user_id = ?
                ORDER BY id DESC
                LIMIT 100
                """,
                (
                    ctx.guild.id,
                    ctx.author.id,
                ),
            ).fetchall()

        await ctx.send(
            embed=create_list_embed(
                rows,
                f"⚡ {ctx.author.display_name}'s Setups",
            )
        )

    # ========================================================
    # TOP
    # ========================================================

    @setup_group.command(name="top")
    @commands.guild_only()
    async def setup_top(self, ctx):
        """Show the most-upvoted setups."""

        with db_connect() as db:
            rows = db.execute(
                """
                SELECT *
                FROM wattson_setups
                WHERE guild_id = ?
                ORDER BY upvotes DESC, id DESC
                LIMIT 100
                """,
                (ctx.guild.id,),
            ).fetchall()

        await ctx.send(
            embed=create_list_embed(
                rows,
                "🏆 Top Wattson Setups",
            )
        )

    # ========================================================
    # DELETE
    # ========================================================

    @setup_group.command(name="delete")
    @commands.guild_only()
    async def setup_delete(
        self,
        ctx,
        setup_id: int,
    ):
        """Delete one of your own setups."""

        setup = get_setup(
            setup_id,
            ctx.guild.id,
        )

        if not setup:
            await ctx.send(
                "❌ I couldn't find that setup.",
                delete_after=5,
            )
            return

        is_staff = (
            ctx.author.guild_permissions.manage_guild
            or ctx.author.guild_permissions.administrator
        )

        if (
            setup["user_id"] != ctx.author.id
            and not is_staff
        ):
            await ctx.send(
                "❌ You can only delete your own setups.",
                delete_after=5,
            )
            return

        with db_connect() as db:
            db.execute(
                """
                DELETE FROM wattson_setup_votes
                WHERE setup_id = ?
                """,
                (setup_id,),
            )

            db.execute(
                """
                DELETE FROM wattson_setups
                WHERE id = ?
                  AND guild_id = ?
                """,
                (
                    setup_id,
                    ctx.guild.id,
                ),
            )

        await ctx.send(
            f"🗑️ Setup `#{setup_id}` has been deleted.",
            delete_after=8,
        )

    # ========================================================
    # HELP
    # ========================================================

    @setup_group.command(name="help")
    @commands.guild_only()
    async def setup_help(self, ctx):
        """Detailed Setup Library help."""

        embed = discord.Embed(
            title="⚡ Wattson Setup Library",
            description=(
                "Build a community database of useful Wattson "
                "setups, locations, fence setups, and endgame holds."
            ),
            color=EMBED_COLOR,
        )

        embed.add_field(
            name="➕ Add",
            value=(
                "`!setup add Name | Map | Category | "
                "Location | Description | Media URL`"
            ),
            inline=False,
        )

        embed.add_field(
            name="📖 View",
            value="`!setup view 1`",
            inline=False,
        )

        embed.add_field(
            name="🔎 Search",
            value="`!setup search Fragment`",
            inline=False,
        )

        embed.add_field(
            name="🗺️ Map",
            value="`!setup map WE`",
            inline=False,
        )

        embed.add_field(
            name="📂 Category",
            value="`!setup category fences`",
            inline=False,
        )

        embed.add_field(
            name="👤 Your Setups",
            value="`!setup mine`",
            inline=False,
        )

        embed.add_field(
            name="🏆 Top Setups",
            value="`!setup top`",
            inline=False,
        )

        embed.add_field(
            name="🗑️ Delete",
            value="`!setup delete 1`",
            inline=False,
        )

        embed.add_field(
            name="🗺️ Maps",
            value=", ".join(
                dict.fromkeys(MAPS.values())
            ),
            inline=False,
        )

        embed.add_field(
            name="📂 Categories",
            value=", ".join(
                dict.fromkeys(CATEGORIES.values())
            ),
            inline=False,
        )

        await ctx.send(embed=embed)

    # ========================================================
    # ERROR HANDLER
    # ========================================================

    @setup_group.error
    async def setup_group_error(
        self,
        ctx,
        error,
    ):
        if isinstance(
            error,
            commands.MissingRequiredArgument,
        ):
            await ctx.send(
                "❌ You're missing a required argument. "
                "Use `!setup help`.",
                delete_after=6,
            )
            return

        if isinstance(
            error,
            commands.BadArgument,
        ):
            await ctx.send(
                "❌ I couldn't understand that argument. "
                "Use `!setup help`.",
                delete_after=6,
            )
            return

        raise error


# ============================================================
# SETUP
# ============================================================

async def setup(bot):
    await bot.add_cog(Setups(bot))