"""
Grid Guardian - Apex Clip Showcase

Community Apex Legends clip submission and showcase system.

Commands:
    !clip
    !clip submit
    !clip view <id>
    !clip search <text>
    !clip top
    !clip latest
    !clip mine
    !clip featured
    !clip feature <id>
    !clip unfeature <id>
    !clip delete <id>
    !clip remove <id>
    !clip help

Features:
    - Community clip submissions
    - Like system
    - Persistent like buttons
    - Featured clips
    - Search
    - Top clips
    - Latest clips
    - Creator profiles
    - Staff moderation
    - SQLite persistence
"""

import re
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
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_database() -> None:
    """Create clip database tables."""
    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS apex_clips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                message_id INTEGER,
                title TEXT NOT NULL,
                legend TEXT NOT NULL,
                platform TEXT NOT NULL,
                description TEXT NOT NULL,
                media_url TEXT NOT NULL,
                likes INTEGER NOT NULL DEFAULT 0,
                featured INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS apex_clip_likes (
                clip_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (clip_id, user_id),
                FOREIGN KEY (clip_id)
                    REFERENCES apex_clips(id)
                    ON DELETE CASCADE
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_apex_clips_guild
            ON apex_clips(guild_id, status)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_apex_clips_featured
            ON apex_clips(guild_id, featured, status)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_apex_clips_likes
            ON apex_clips(guild_id, likes)
            """
        )

        conn.commit()

    finally:
        conn.close()


# ============================================================
# CONSTANTS
# ============================================================

LEGENDS = {
    "any": "Any Legend",
    "wattson": "Wattson",
    "alter": "Alter",
    "ash": "Ash",
    "ballistic": "Ballistic",
    "bangalore": "Bangalore",
    "bloodhound": "Bloodhound",
    "catalyst": "Catalyst",
    "caustic": "Caustic",
    "conduit": "Conduit",
    "crypto": "Crypto",
    "fuse": "Fuse",
    "gibraltar": "Gibraltar",
    "lifeline": "Lifeline",
    "loba": "Loba",
    "mad maggie": "Mad Maggie",
    "madmaggie": "Mad Maggie",
    "mirage": "Mirage",
    "newcastle": "Newcastle",
    "octane": "Octane",
    "pathfinder": "Pathfinder",
    "rampart": "Rampart",
    "revenant": "Revenant",
    "seer": "Seer",
    "sparrow": "Sparrow",
    "valkyrie": "Valkyrie",
    "vantage": "Vantage",
    "wraith": "Wraith",
}

PLATFORMS = {
    "pc": "PC",
    "playstation": "PlayStation",
    "ps": "PlayStation",
    "xbox": "Xbox",
    "console": "Console",
    "crossplay": "Crossplay",
    "any": "Any Platform",
}


# ============================================================
# HELPERS
# ============================================================

def utc_now() -> str:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def normalize_legend(value: str) -> Optional[str]:
    """Normalize a legend name."""
    return LEGENDS.get(value.strip().lower())


def normalize_platform(value: str) -> Optional[str]:
    """Normalize a platform."""
    return PLATFORMS.get(value.strip().lower())


def is_staff(member: discord.Member) -> bool:
    """Check whether a member can moderate clips."""
    return (
        member.guild_permissions.manage_guild
        or member.guild_permissions.manage_messages
        or member.guild_permissions.administrator
    )


def get_clip(clip_id: int, guild_id: int):
    """Get a clip from the database."""
    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM apex_clips
            WHERE id = ?
              AND guild_id = ?
            """,
            (clip_id, guild_id),
        )

        return cursor.fetchone()

    finally:
        conn.close()


def get_creator_name(
    guild: discord.Guild,
    user_id: int,
) -> str:
    """Get a creator's display name."""
    member = guild.get_member(user_id)

    if member:
        return member.display_name

    return f"User {user_id}"


def truncate(text: str, length: int = 1000) -> str:
    """Safely truncate text."""
    if len(text) <= length:
        return text

    return text[: length - 3] + "..."


def is_supported_media_url(url: str) -> bool:
    """
    Basic media-link validation.

    The system intentionally stores the URL rather than downloading
    user content.
    """
    url = url.strip().lower()

    if not (
        url.startswith("https://")
        or url.startswith("http://")
    ):
        return False

    allowed_domains = (
        "youtube.com",
        "youtu.be",
        "youtube-nocookie.com",
        "tiktok.com",
        "instagram.com",
        "discord.com",
        "discord.gg",
        "streamable.com",
        "medal.tv",
    )

    return any(domain in url for domain in allowed_domains)


def format_clip_embed(
    guild: discord.Guild,
    clip,
) -> discord.Embed:
    """Build the main clip embed."""
    creator = guild.get_member(clip["user_id"])

    if creator:
        creator_text = creator.mention
    else:
        creator_text = f"<@{clip['user_id']}>"

    featured = "⭐ Featured" if clip["featured"] else "🎬 Community Clip"

    embed = discord.Embed(
        title=f"{featured} — #{clip['id']}",
        description=clip["description"],
        color=discord.Color.from_rgb(255, 105, 180),
    )

    embed.add_field(
        name="🎬 Clip",
        value=f"**{clip['title']}**",
        inline=False,
    )

    embed.add_field(
        name="⚡ Legend",
        value=clip["legend"],
        inline=True,
    )

    embed.add_field(
        name="🎮 Platform",
        value=clip["platform"],
        inline=True,
    )

    embed.add_field(
        name="❤️ Likes",
        value=str(clip["likes"]),
        inline=True,
    )

    embed.add_field(
        name="👤 Creator",
        value=creator_text,
        inline=True,
    )

    embed.add_field(
        name="🔗 Watch",
        value=clip["media_url"],
        inline=False,
    )

    embed.set_footer(
        text=f"Clip ID: {clip['id']}"
    )

    return embed


# ============================================================
# CLIP VIEW
# ============================================================

class ClipView(discord.ui.View):
    """
    Persistent clip interaction view.

    The clip ID is encoded into each button's custom ID so the
    correct database record can be retrieved after a restart.
    """

    def __init__(self, cog: "ClipShowcase", clip_id: int):
        super().__init__(timeout=None)

        self.cog = cog
        self.clip_id = clip_id

        self.like_button = discord.ui.Button(
            label="Like",
            emoji="❤️",
            style=discord.ButtonStyle.primary,
            custom_id=f"gridguardian:clip_like:{clip_id}",
        )

        self.like_button.callback = self.like_callback
        self.add_item(self.like_button)

    async def like_callback(
        self,
        interaction: discord.Interaction,
    ):
        """Handle a clip like."""
        await self.cog.handle_like(
            interaction,
            self.clip_id,
        )


# ============================================================
# COG
# ============================================================

class ClipShowcase(commands.Cog):
    """Apex Clip Showcase."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        initialize_database()

        # Register the generic persistent view handler.
        # Existing messages are represented by their custom IDs.
        bot.add_dynamic_items(ClipLikeButton)

    # ========================================================
    # MAIN COMMAND
    # ========================================================

    @commands.group(
        name="clip",
        invoke_without_command=True,
    )
    async def clip(self, ctx: commands.Context):
        """Open the Clip Showcase."""
        embed = discord.Embed(
            title="🎬 Apex Clip Showcase",
            description=(
                "Share your best Apex moments with the server.\n\n"
                "Submit clips, collect likes, and get featured."
            ),
            color=discord.Color.from_rgb(255, 105, 180),
        )

        embed.add_field(
            name="🎬 Browse",
            value=(
                "`!clip latest`\n"
                "`!clip top`\n"
                "`!clip featured`\n"
                "`!clip search <text>`"
            ),
            inline=True,
        )

        embed.add_field(
            name="📤 Submit",
            value=(
                "`!clip submit`\n"
                "`!clip mine`"
            ),
            inline=True,
        )

        embed.add_field(
            name="🛡️ Staff",
            value=(
                "`!clip feature <id>`\n"
                "`!clip unfeature <id>`\n"
                "`!clip remove <id>`"
            ),
            inline=False,
        )

        embed.set_footer(
            text="Use !clip help for detailed instructions."
        )

        await ctx.send(embed=embed)

    # ========================================================
    # HELP
    # ========================================================

    @clip.command(name="help")
    async def clip_help(self, ctx: commands.Context):
        """Show Clip Showcase help."""
        embed = discord.Embed(
            title="🎬 Clip Showcase Help",
            color=discord.Color.from_rgb(255, 105, 180),
        )

        embed.add_field(
            name="📤 Submit",
            value=(
                "`!clip submit Title | Legend | Platform | "
                "Description | Media URL`"
            ),
            inline=False,
        )

        embed.add_field(
            name="Example",
            value=(
                "`!clip submit 1v3 Wattson Hold | Wattson | "
                "PlayStation | Held the building solo | "
                "https://youtube.com/watch?v=example`"
            ),
            inline=False,
        )

        embed.add_field(
            name="🔎 Browse",
            value=(
                "`!clip view <id>` — View a clip\n"
                "`!clip search <text>` — Search clips\n"
                "`!clip latest` — Latest clips\n"
                "`!clip top` — Most liked\n"
                "`!clip featured` — Featured clips"
            ),
            inline=False,
        )

        embed.add_field(
            name="👤 Your Clips",
            value="`!clip mine`",
            inline=False,
        )

        embed.add_field(
            name="🛡️ Staff",
            value=(
                "`!clip feature <id>`\n"
                "`!clip unfeature <id>`\n"
                "`!clip remove <id>`"
            ),
            inline=False,
        )

        embed.add_field(
            name="🎮 Platforms",
            value="PC • PlayStation • Xbox • Console • Crossplay • Any",
            inline=False,
        )

        await ctx.send(embed=embed)

    # ========================================================
    # SUBMIT
    # ========================================================

    @clip.command(name="submit")
    async def clip_submit(
        self,
        ctx: commands.Context,
        *,
        raw: str = "",
    ):
        """Submit an Apex clip."""
        if not raw:
            await ctx.send(
                "❌ Please provide the clip information.\n\n"
                "Use `!clip help` for the format."
            )
            return

        parts = [part.strip() for part in raw.split("|")]

        if len(parts) != 5:
            await ctx.send(
                "❌ Invalid format.\n\n"
                "Use:\n"
                "`!clip submit Title | Legend | Platform | "
                "Description | Media URL`"
            )
            return

        (
            title,
            legend_input,
            platform_input,
            description,
            media_url,
        ) = parts

        legend = normalize_legend(legend_input)
        platform = normalize_platform(platform_input)

        if not legend:
            await ctx.send(
                "❌ Invalid legend.\n"
                "Use the legend name, such as `Wattson`."
            )
            return

        if not platform:
            await ctx.send(
                "❌ Invalid platform.\n"
                "Use PC, PlayStation, Xbox, Console, "
                "Crossplay, or Any."
            )
            return

        if not title:
            await ctx.send(
                "❌ Your clip needs a title."
            )
            return

        if len(title) > 100:
            await ctx.send(
                "❌ Title is too long. Maximum: 100 characters."
            )
            return

        if not description:
            await ctx.send(
                "❌ Please provide a description."
            )
            return

        if len(description) > 1000:
            await ctx.send(
                "❌ Description is too long. Maximum: 1000 characters."
            )
            return

        if not is_supported_media_url(media_url):
            await ctx.send(
                "❌ That doesn't look like a supported media link.\n\n"
                "Supported platforms include YouTube, TikTok, "
                "Instagram, Discord, Streamable, and Medal."
            )
            return

        conn = get_connection()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO apex_clips (
                    guild_id,
                    user_id,
                    channel_id,
                    message_id,
                    title,
                    legend,
                    platform,
                    description,
                    media_url,
                    likes,
                    featured,
                    status,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, 0, 0, 'active', ?, ?)
                """,
                (
                    ctx.guild.id,
                    ctx.author.id,
                    ctx.channel.id,
                    title,
                    legend,
                    platform,
                    description,
                    media_url,
                    utc_now(),
                    utc_now(),
                ),
            )

            clip_id = cursor.lastrowid

            conn.commit()

        except sqlite3.Error as exc:
            conn.rollback()

            print(f"[Clip Showcase] Database error: {exc}")

            await ctx.send(
                "❌ I couldn't save your clip right now."
            )
            return

        finally:
            conn.close()

        clip = get_clip(
            clip_id,
            ctx.guild.id,
        )

        embed = format_clip_embed(
            ctx.guild,
            clip,
        )

        view = ClipView(
            self,
            clip_id,
        )

        message = await ctx.send(
            embed=embed,
            view=view,
        )

        conn = get_connection()

        try:
            conn.execute(
                """
                UPDATE apex_clips
                SET message_id = ?
                WHERE id = ?
                  AND guild_id = ?
                """,
                (
                    message.id,
                    clip_id,
                    ctx.guild.id,
                ),
            )

            conn.commit()

        finally:
            conn.close()

    # ========================================================
    # VIEW
    # ========================================================

    @clip.command(name="view")
    async def clip_view(
        self,
        ctx: commands.Context,
        clip_id: int,
    ):
        """View a clip."""
        clip = get_clip(
            clip_id,
            ctx.guild.id,
        )

        if clip is None:
            await ctx.send(
                f"❌ Clip `#{clip_id}` doesn't exist."
            )
            return

        if clip["status"] != "active":
            await ctx.send(
                "❌ That clip is no longer available."
            )
            return

        embed = format_clip_embed(
            ctx.guild,
            clip,
        )

        await ctx.send(
            embed=embed,
            view=ClipView(self, clip_id),
        )

    # ========================================================
    # SEARCH
    # ========================================================

    @clip.command(name="search")
    async def clip_search(
        self,
        ctx: commands.Context,
        *,
        search_text: str,
    ):
        """Search clips."""
        search_text = search_text.strip()

        if not search_text:
            await ctx.send(
                "❌ Please provide something to search for."
            )
            return

        pattern = f"%{search_text}%"

        conn = get_connection()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    id,
                    title,
                    legend,
                    platform,
                    likes,
                    featured,
                    user_id
                FROM apex_clips
                WHERE guild_id = ?
                  AND status = 'active'
                  AND (
                      title LIKE ?
                      OR legend LIKE ?
                      OR description LIKE ?
                  )
                ORDER BY likes DESC, id DESC
                LIMIT 10
                """,
                (
                    ctx.guild.id,
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
                f"🔎 No clips matched **{search_text}**."
            )
            return

        embed = discord.Embed(
            title=f"🔎 Clip Search: {search_text}",
            color=discord.Color.from_rgb(255, 105, 180),
        )

        for row in rows:
            featured = " ⭐" if row["featured"] else ""

            embed.add_field(
                name=f"🎬 #{row['id']} — {row['title']}{featured}",
                value=(
                    f"**Legend:** {row['legend']}\n"
                    f"**Platform:** {row['platform']}\n"
                    f"❤️ **{row['likes']}** likes\n"
                    f"`!clip view {row['id']}`"
                ),
                inline=False,
            )

        await ctx.send(embed=embed)

    # ========================================================
    # TOP
    # ========================================================

    @clip.command(name="top")
    async def clip_top(self, ctx: commands.Context):
        """Show the most liked clips."""
        conn = get_connection()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    id,
                    title,
                    legend,
                    platform,
                    likes,
                    user_id
                FROM apex_clips
                WHERE guild_id = ?
                  AND status = 'active'
                ORDER BY likes DESC, id DESC
                LIMIT 10
                """,
                (ctx.guild.id,),
            )

            rows = cursor.fetchall()

        finally:
            conn.close()

        if not rows:
            await ctx.send(
                "🎬 There aren't any clips yet."
            )
            return

        embed = discord.Embed(
            title="🏆 Top Apex Clips",
            description="The most liked clips in the server.",
            color=discord.Color.from_rgb(255, 105, 180),
        )

        medals = ["🥇", "🥈", "🥉"]

        for index, row in enumerate(rows):
            prefix = (
                medals[index]
                if index < 3
                else f"**#{index + 1}**"
            )

            creator = get_creator_name(
                ctx.guild,
                row["user_id"],
            )

            embed.add_field(
                name=f"{prefix} {row['title']}",
                value=(
                    f"🎮 {row['legend']} • {row['platform']}\n"
                    f"❤️ **{row['likes']}** likes\n"
                    f"👤 {creator}\n"
                    f"`!clip view {row['id']}`"
                ),
                inline=False,
            )

        await ctx.send(embed=embed)

    # ========================================================
    # LATEST
    # ========================================================

    @clip.command(name="latest")
    async def clip_latest(self, ctx: commands.Context):
        """Show the latest clips."""
        conn = get_connection()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    id,
                    title,
                    legend,
                    platform,
                    likes,
                    user_id
                FROM apex_clips
                WHERE guild_id = ?
                  AND status = 'active'
                ORDER BY id DESC
                LIMIT 10
                """,
                (ctx.guild.id,),
            )

            rows = cursor.fetchall()

        finally:
            conn.close()

        if not rows:
            await ctx.send(
                "🎬 There aren't any clips yet."
            )
            return

        embed = discord.Embed(
            title="🆕 Latest Apex Clips",
            color=discord.Color.from_rgb(255, 105, 180),
        )

        for row in rows:
            creator = get_creator_name(
                ctx.guild,
                row["user_id"],
            )

            embed.add_field(
                name=f"🎬 #{row['id']} — {row['title']}",
                value=(
                    f"🎮 {row['legend']} • {row['platform']}\n"
                    f"❤️ {row['likes']} likes • "
                    f"👤 {creator}\n"
                    f"`!clip view {row['id']}`"
                ),
                inline=False,
            )

        await ctx.send(embed=embed)

    # ========================================================
    # MINE
    # ========================================================

    @clip.command(name="mine")
    async def clip_mine(self, ctx: commands.Context):
        """Show the user's clips."""
        conn = get_connection()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    id,
                    title,
                    legend,
                    platform,
                    likes,
                    featured,
                    status
                FROM apex_clips
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
                "🎬 You haven't submitted any clips yet."
            )
            return

        embed = discord.Embed(
            title=f"🎬 {ctx.author.display_name}'s Clips",
            color=discord.Color.from_rgb(255, 105, 180),
        )

        for row in rows:
            featured = " ⭐ Featured" if row["featured"] else ""

            embed.add_field(
                name=f"#{row['id']} — {row['title']}{featured}",
                value=(
                    f"🎮 {row['legend']} • {row['platform']}\n"
                    f"❤️ {row['likes']} likes\n"
                    f"Status: {row['status']}\n"
                    f"`!clip view {row['id']}`"
                ),
                inline=False,
            )

        await ctx.send(embed=embed)

    # ========================================================
    # FEATURED
    # ========================================================

    @clip.command(name="featured")
    async def clip_featured(self, ctx: commands.Context):
        """Show staff-featured clips."""
        conn = get_connection()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    id,
                    title,
                    legend,
                    platform,
                    likes,
                    user_id
                FROM apex_clips
                WHERE guild_id = ?
                  AND status = 'active'
                  AND featured = 1
                ORDER BY likes DESC, id DESC
                LIMIT 10
                """,
                (ctx.guild.id,),
            )

            rows = cursor.fetchall()

        finally:
            conn.close()

        if not rows:
            await ctx.send(
                "⭐ There are no featured clips yet."
            )
            return

        embed = discord.Embed(
            title="⭐ Featured Apex Clips",
            description="Clips selected by server staff.",
            color=discord.Color.gold(),
        )

        for row in rows:
            creator = get_creator_name(
                ctx.guild,
                row["user_id"],
            )

            embed.add_field(
                name=f"⭐ #{row['id']} — {row['title']}",
                value=(
                    f"🎮 {row['legend']} • {row['platform']}\n"
                    f"❤️ {row['likes']} likes • 👤 {creator}\n"
                    f"`!clip view {row['id']}`"
                ),
                inline=False,
            )

        await ctx.send(embed=embed)

    # ========================================================
    # FEATURE
    # ========================================================

    @clip.command(name="feature")
    @commands.has_guild_permissions(manage_guild=True)
    async def clip_feature(
        self,
        ctx: commands.Context,
        clip_id: int,
    ):
        """Feature a clip."""
        clip = get_clip(
            clip_id,
            ctx.guild.id,
        )

        if clip is None:
            await ctx.send(
                f"❌ Clip `#{clip_id}` doesn't exist."
            )
            return

        if clip["status"] != "active":
            await ctx.send(
                "❌ That clip isn't active."
            )
            return

        if clip["featured"]:
            await ctx.send(
                "⭐ That clip is already featured."
            )
            return

        conn = get_connection()

        try:
            conn.execute(
                """
                UPDATE apex_clips
                SET featured = 1,
                    updated_at = ?
                WHERE id = ?
                  AND guild_id = ?
                """,
                (
                    utc_now(),
                    clip_id,
                    ctx.guild.id,
                ),
            )

            conn.commit()

        finally:
            conn.close()

        await ctx.send(
            f"⭐ Featured **{clip['title']}** (`#{clip_id}`)."
        )

    # ========================================================
    # UNFEATURE
    # ========================================================

    @clip.command(name="unfeature")
    @commands.has_guild_permissions(manage_guild=True)
    async def clip_unfeature(
        self,
        ctx: commands.Context,
        clip_id: int,
    ):
        """Remove a clip from featured status."""
        clip = get_clip(
            clip_id,
            ctx.guild.id,
        )

        if clip is None:
            await ctx.send(
                f"❌ Clip `#{clip_id}` doesn't exist."
            )
            return

        if not clip["featured"]:
            await ctx.send(
                "ℹ️ That clip isn't featured."
            )
            return

        conn = get_connection()

        try:
            conn.execute(
                """
                UPDATE apex_clips
                SET featured = 0,
                    updated_at = ?
                WHERE id = ?
                  AND guild_id = ?
                """,
                (
                    utc_now(),
                    clip_id,
                    ctx.guild.id,
                ),
            )

            conn.commit()

        finally:
            conn.close()

        await ctx.send(
            f"⭐ Removed **{clip['title']}** from featured clips."
        )

    # ========================================================
    # DELETE
    # ========================================================

    @clip.command(name="delete")
    async def clip_delete(
        self,
        ctx: commands.Context,
        clip_id: int,
    ):
        """Delete your own clip."""
        clip = get_clip(
            clip_id,
            ctx.guild.id,
        )

        if clip is None:
            await ctx.send(
                f"❌ Clip `#{clip_id}` doesn't exist."
            )
            return

        if (
            clip["user_id"] != ctx.author.id
            and not is_staff(ctx.author)
        ):
            await ctx.send(
                "❌ You can only delete your own clips."
            )
            return

        conn = get_connection()

        try:
            conn.execute(
                """
                DELETE FROM apex_clip_likes
                WHERE clip_id = ?
                """,
                (clip_id,),
            )

            conn.execute(
                """
                DELETE FROM apex_clips
                WHERE id = ?
                  AND guild_id = ?
                """,
                (
                    clip_id,
                    ctx.guild.id,
                ),
            )

            conn.commit()

        finally:
            conn.close()

        await ctx.send(
            f"🗑️ Deleted **{clip['title']}** (`#{clip_id}`)."
        )

    # ========================================================
    # REMOVE
    # ========================================================

    @clip.command(name="remove")
    @commands.has_guild_permissions(manage_guild=True)
    async def clip_remove(
        self,
        ctx: commands.Context,
        clip_id: int,
    ):
        """Staff-remove a clip."""
        clip = get_clip(
            clip_id,
            ctx.guild.id,
        )

        if clip is None:
            await ctx.send(
                f"❌ Clip `#{clip_id}` doesn't exist."
            )
            return

        conn = get_connection()

        try:
            conn.execute(
                """
                UPDATE apex_clips
                SET status = 'removed',
                    updated_at = ?
                WHERE id = ?
                  AND guild_id = ?
                """,
                (
                    utc_now(),
                    clip_id,
                    ctx.guild.id,
                ),
            )

            conn.commit()

        finally:
            conn.close()

        await ctx.send(
            f"🛡️ Removed **{clip['title']}** (`#{clip_id}`)."
        )

    # ========================================================
    # LIKE HANDLER
    # ========================================================

    async def handle_like(
        self,
        interaction: discord.Interaction,
        clip_id: int,
    ):
        """Handle a clip like."""
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ This can only be used inside a server.",
                ephemeral=True,
            )
            return

        clip = get_clip(
            clip_id,
            interaction.guild.id,
        )

        if clip is None:
            await interaction.response.send_message(
                "❌ That clip no longer exists.",
                ephemeral=True,
            )
            return

        if clip["status"] != "active":
            await interaction.response.send_message(
                "❌ That clip is no longer available.",
                ephemeral=True,
            )
            return

        conn = get_connection()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT 1
                FROM apex_clip_likes
                WHERE clip_id = ?
                  AND user_id = ?
                """,
                (
                    clip_id,
                    interaction.user.id,
                ),
            )

            existing = cursor.fetchone()

            if existing:
                await interaction.response.send_message(
                    "❤️ You already liked this clip.",
                    ephemeral=True,
                )
                return

            cursor.execute(
                """
                INSERT INTO apex_clip_likes (
                    clip_id,
                    user_id,
                    created_at
                )
                VALUES (?, ?, ?)
                """,
                (
                    clip_id,
                    interaction.user.id,
                    utc_now(),
                ),
            )

            cursor.execute(
                """
                UPDATE apex_clips
                SET likes = likes + 1,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    utc_now(),
                    clip_id,
                ),
            )

            conn.commit()

            cursor.execute(
                """
                SELECT likes
                FROM apex_clips
                WHERE id = ?
                """,
                (clip_id,),
            )

            result = cursor.fetchone()

            new_likes = (
                result["likes"]
                if result
                else clip["likes"] + 1
            )

        except sqlite3.IntegrityError:
            conn.rollback()

            await interaction.response.send_message(
                "❤️ You already liked this clip.",
                ephemeral=True,
            )
            return

        except sqlite3.Error as exc:
            conn.rollback()

            print(f"[Clip Showcase] Like error: {exc}")

            await interaction.response.send_message(
                "❌ I couldn't save your like.",
                ephemeral=True,
            )
            return

        finally:
            conn.close()

        await interaction.response.send_message(
            f"❤️ Liked **{clip['title']}**!\n"
            f"Total likes: **{new_likes}**",
            ephemeral=True,
        )

        # Update the original clip message if possible.
        if clip["message_id"] and clip["channel_id"]:
            channel = self.bot.get_channel(
                clip["channel_id"]
            )

            if channel:
                try:
                    message = await channel.fetch_message(
                        clip["message_id"]
                    )

                    updated_clip = get_clip(
                        clip_id,
                        interaction.guild.id,
                    )

                    if updated_clip:
                        await message.edit(
                            embed=format_clip_embed(
                                interaction.guild,
                                updated_clip,
                            ),
                            view=ClipView(
                                self,
                                clip_id,
                            ),
                        )

                except (
                    discord.NotFound,
                    discord.Forbidden,
                    discord.HTTPException,
                ):
                    pass

    # ========================================================
    # ERROR HANDLING
    # ========================================================

    @clip.error
    async def clip_error(
        self,
        ctx: commands.Context,
        error: commands.CommandError,
    ):
        """Handle clip command errors."""
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(
                "❌ You need **Manage Server** permission "
                "to use that command."
            )
            return

        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                "❌ You're missing a required argument.\n"
                "Use `!clip help` for instructions."
            )
            return

        if isinstance(error, commands.BadArgument):
            await ctx.send(
                "❌ Invalid clip ID. Use a number such as "
                "`!clip view 1`."
            )
            return

        raise error


# ============================================================
# DYNAMIC PERSISTENT LIKE BUTTON
# ============================================================

class ClipLikeButton(
    discord.ui.DynamicItem[
        discord.ui.Button
    ],
    template=r"gridguardian:clip_like:(?P<clip_id>[0-9]+)",
):
    """
    Restart-safe dynamic like button.

    discord.py reconstructs this item from the custom_id,
    allowing old clip buttons to continue working after restart.
    """

    def __init__(self, clip_id: int):
        super().__init__(
            discord.ui.Button(
                label="Like",
                emoji="❤️",
                style=discord.ButtonStyle.primary,
                custom_id=f"gridguardian:clip_like:{clip_id}",
            )
        )

        self.clip_id = clip_id

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Button,
        match: re.Match[str],
    ):
        clip_id = int(match["clip_id"])

        return cls(clip_id)

    async def callback(
        self,
        interaction: discord.Interaction,
    ):
        """Handle the dynamic button callback."""
        cog = interaction.client.get_cog(
            "ClipShowcase"
        )

        if cog is None:
            await interaction.response.send_message(
                "❌ The Clip Showcase system isn't currently available.",
                ephemeral=True,
            )
            return

        await cog.handle_like(
            interaction,
            self.clip_id,
        )


# ============================================================
# SETUP
# ============================================================

async def setup(bot: commands.Bot):
    await bot.add_cog(ClipShowcase(bot))