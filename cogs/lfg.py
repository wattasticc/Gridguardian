"""
Grid Guardian - Apex LFG System

Apex Legends Looking For Group system.

Commands:
    !lfg
    !lfg create
    !lfg list
    !lfg mine
    !lfg close <id>
    !lfg remove <id>
    !lfg help

Features:
    - Interactive LFG creation
    - Join / leave buttons
    - Party size limits
    - Platform, mode, rank, region, microphone, and playstyle
    - Persistent SQLite storage
    - Automatic expiration
    - Server-specific LFG posts
    - Owner controls
    - Staff removal
"""

import asyncio
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Optional

import discord
from discord.ext import commands


DB_PATH = "gridguardian.db"

# LFG posts expire after this amount of time.
LFG_EXPIRATION_HOURS = 6


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
    """Create LFG tables."""
    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS apex_lfg (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                message_id INTEGER,
                owner_id INTEGER NOT NULL,
                platform TEXT NOT NULL,
                mode TEXT NOT NULL,
                rank TEXT NOT NULL,
                region TEXT NOT NULL,
                mic TEXT NOT NULL,
                playstyle TEXT NOT NULL,
                description TEXT NOT NULL,
                max_players INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS apex_lfg_players (
                lfg_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                joined_at TEXT NOT NULL,
                PRIMARY KEY (lfg_id, user_id),
                FOREIGN KEY (lfg_id)
                    REFERENCES apex_lfg(id)
                    ON DELETE CASCADE
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_apex_lfg_guild
            ON apex_lfg(guild_id, status)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_apex_lfg_expiration
            ON apex_lfg(expires_at)
            """
        )

        conn.commit()

    finally:
        conn.close()


# ============================================================
# CONSTANTS
# ============================================================

PLATFORMS = {
    "pc": "PC",
    "playstation": "PlayStation",
    "ps": "PlayStation",
    "xbox": "Xbox",
    "console": "Console",
    "crossplay": "Crossplay",
    "any": "Any Platform",
}

MODES = {
    "ranked": "Ranked",
    "pubs": "Public Matches",
    "public": "Public Matches",
    "mixtape": "Mixtape",
    "ltm": "Limited-Time Mode",
    "custom": "Custom",
    "any": "Any Mode",
}

RANKS = {
    "rookie": "Rookie",
    "bronze": "Bronze",
    "silver": "Silver",
    "gold": "Gold",
    "platinum": "Platinum",
    "plat": "Platinum",
    "diamond": "Diamond",
    "master": "Master",
    "masters": "Master",
    "pred": "Predator",
    "predator": "Predator",
    "any": "Any Rank",
}

REGIONS = {
    "na": "North America",
    "north america": "North America",
    "eu": "Europe",
    "europe": "Europe",
    "apac": "Asia-Pacific",
    "asia": "Asia-Pacific",
    "oce": "Oceania",
    "oceania": "Oceania",
    "sa": "South America",
    "south america": "South America",
    "any": "Any Region",
}

MICS = {
    "required": "Required",
    "yes": "Required",
    "preferred": "Preferred",
    "optional": "Optional",
    "no": "Not Required",
    "none": "Not Required",
}

PLAYSTYLES = {
    "aggressive": "Aggressive",
    "aggro": "Aggressive",
    "balanced": "Balanced",
    "passive": "Passive",
    "casual": "Casual",
    "competitive": "Competitive",
    "chill": "Chill",
    "any": "Any Playstyle",
}


# ============================================================
# HELPERS
# ============================================================

def utc_now() -> datetime:
    """Return timezone-aware current UTC time."""
    return datetime.now(timezone.utc)


def utc_iso() -> str:
    """Return current UTC timestamp as ISO string."""
    return utc_now().isoformat()


def parse_choice(
    value: str,
    choices: dict[str, str],
) -> Optional[str]:
    """Normalize a user choice."""
    return choices.get(value.strip().lower())


def is_staff(member: discord.Member) -> bool:
    """Check whether a member can manage LFG posts."""
    return (
        member.guild_permissions.manage_guild
        or member.guild_permissions.manage_messages
        or member.guild_permissions.administrator
    )


def get_lfg(lfg_id: int, guild_id: int):
    """Get an LFG post for a specific guild."""
    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM apex_lfg
            WHERE id = ?
              AND guild_id = ?
            """,
            (lfg_id, guild_id),
        )

        return cursor.fetchone()

    finally:
        conn.close()


def get_players(lfg_id: int) -> list[int]:
    """Get all players in an LFG."""
    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT user_id
            FROM apex_lfg_players
            WHERE lfg_id = ?
            ORDER BY joined_at ASC
            """,
            (lfg_id,),
        )

        return [row["user_id"] for row in cursor.fetchall()]

    finally:
        conn.close()


def format_players(
    guild: discord.Guild,
    player_ids: list[int],
) -> str:
    """Format LFG players for an embed."""
    if not player_ids:
        return "No players yet."

    mentions = []

    for user_id in player_ids:
        member = guild.get_member(user_id)

        if member:
            mentions.append(f"• {member.mention}")
        else:
            mentions.append(f"• <@{user_id}>")

    return "\n".join(mentions)


async def get_message(
    bot: commands.Bot,
    channel_id: int,
    message_id: int,
):
    """Try to fetch an LFG message."""
    channel = bot.get_channel(channel_id)

    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None

    if not isinstance(channel, discord.TextChannel):
        return None

    try:
        return await channel.fetch_message(message_id)
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        return None


# ============================================================
# LFG EMBED
# ============================================================

def build_lfg_embed(
    guild: discord.Guild,
    lfg,
    players: list[int],
) -> discord.Embed:
    """Build the LFG embed."""
    owner = guild.get_member(lfg["owner_id"])

    if owner:
        owner_text = owner.mention
    else:
        owner_text = f"<@{lfg['owner_id']}>"

    current_players = len(players)
    max_players = lfg["max_players"]

    if current_players >= max_players:
        party_status = "🔴 FULL"
    else:
        party_status = f"🟢 {current_players}/{max_players}"

    embed = discord.Embed(
        title=f"🎯 Apex LFG — #{lfg['id']}",
        description=lfg["description"],
        color=discord.Color.from_rgb(255, 105, 180),
    )

    embed.add_field(
        name="🎮 Platform",
        value=lfg["platform"],
        inline=True,
    )

    embed.add_field(
        name="🎯 Mode",
        value=lfg["mode"],
        inline=True,
    )

    embed.add_field(
        name="🏆 Rank",
        value=lfg["rank"],
        inline=True,
    )

    embed.add_field(
        name="🌎 Region",
        value=lfg["region"],
        inline=True,
    )

    embed.add_field(
        name="🎙️ Mic",
        value=lfg["mic"],
        inline=True,
    )

    embed.add_field(
        name="⚔️ Playstyle",
        value=lfg["playstyle"],
        inline=True,
    )

    embed.add_field(
        name="👥 Party",
        value=party_status,
        inline=True,
    )

    embed.add_field(
        name="👑 Host",
        value=owner_text,
        inline=True,
    )

    embed.add_field(
        name="👥 Players",
        value=format_players(guild, players),
        inline=False,
    )

    embed.set_footer(
        text=(
            "Join with the button below • "
            f"Expires after {LFG_EXPIRATION_HOURS} hours"
        )
    )

    return embed


# ============================================================
# LFG VIEW
# ============================================================

class LFGView(discord.ui.View):
    """Interactive LFG controls."""

    def __init__(self, cog: "ApexLFG", lfg_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.lfg_id = lfg_id

    @discord.ui.button(
        label="Join LFG",
        emoji="🎮",
        style=discord.ButtonStyle.success,
        custom_id="lfg_join",
    )
    async def join_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await self.cog.handle_join(interaction, self.lfg_id)

    @discord.ui.button(
        label="Leave",
        emoji="🚪",
        style=discord.ButtonStyle.secondary,
        custom_id="lfg_leave",
    )
    async def leave_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await self.cog.handle_leave(interaction, self.lfg_id)

    @discord.ui.button(
        label="Close LFG",
        emoji="🔒",
        style=discord.ButtonStyle.danger,
        custom_id="lfg_close",
    )
    async def close_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await self.cog.handle_close(interaction, self.lfg_id)


# ============================================================
# COG
# ============================================================

class ApexLFG(commands.Cog):
    """Apex Legends Looking For Group system."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cleanup_task: Optional[asyncio.Task] = None

        initialize_database()

        self.cleanup_task = asyncio.create_task(
            self.cleanup_expired_loop()
        )

    def cog_unload(self):
        """Cancel cleanup task when cog unloads."""
        if self.cleanup_task:
            self.cleanup_task.cancel()

    # ========================================================
    # CLEANUP
    # ========================================================

    async def cleanup_expired_loop(self):
        """Periodically expire old LFG posts."""
        await self.bot.wait_until_ready()

        while not self.bot.is_closed():
            try:
                await self.cleanup_expired()
            except Exception as exc:
                print(f"[LFG] Cleanup error: {exc}")

            await asyncio.sleep(300)

    async def cleanup_expired(self):
        """Expire old open LFG posts."""
        now = utc_now().isoformat()

        conn = get_connection()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, guild_id, channel_id, message_id
                FROM apex_lfg
                WHERE status = 'open'
                  AND expires_at <= ?
                """,
                (now,),
            )

            expired = cursor.fetchall()

            cursor.execute(
                """
                UPDATE apex_lfg
                SET status = 'expired'
                WHERE status = 'open'
                  AND expires_at <= ?
                """,
                (now,),
            )

            conn.commit()

        finally:
            conn.close()

        for lfg in expired:
            if not lfg["message_id"]:
                continue

            message = await get_message(
                self.bot,
                lfg["channel_id"],
                lfg["message_id"],
            )

            if message is None:
                continue

            try:
                await message.edit(
                    content="⏰ **This LFG has expired.**",
                    view=None,
                )
            except discord.HTTPException:
                pass

    # ========================================================
    # MAIN COMMAND
    # ========================================================

    @commands.group(
        name="lfg",
        invoke_without_command=True,
    )
    async def lfg(self, ctx: commands.Context):
        """Open the Apex LFG system."""
        embed = discord.Embed(
            title="🎯 Apex LFG",
            description=(
                "Find Apex teammates in your server.\n\n"
                "Create an LFG post, join another player's "
                "party, or browse active groups."
            ),
            color=discord.Color.from_rgb(255, 105, 180),
        )

        embed.add_field(
            name="🎮 Commands",
            value=(
                "`!lfg create` — Create an LFG\n"
                "`!lfg list` — Active LFGs\n"
                "`!lfg mine` — Your LFGs"
            ),
            inline=False,
        )

        embed.add_field(
            name="🔧 Management",
            value=(
                "`!lfg close <id>` — Close your LFG\n"
                "`!lfg remove <id>` — Staff removal"
            ),
            inline=False,
        )

        embed.set_footer(
            text="Use !lfg help for detailed instructions."
        )

        await ctx.send(embed=embed)

    # ========================================================
    # HELP
    # ========================================================

    @lfg.command(name="help")
    async def lfg_help(self, ctx: commands.Context):
        """Show detailed LFG help."""
        embed = discord.Embed(
            title="🎯 Apex LFG Help",
            color=discord.Color.from_rgb(255, 105, 180),
        )

        embed.add_field(
            name="Create",
            value=(
                "`!lfg create <platform> | <mode> | <rank> | "
                "<region> | <mic> | <playstyle> | <max players> | "
                "<description>`"
            ),
            inline=False,
        )

        embed.add_field(
            name="Example",
            value=(
                "`!lfg create PlayStation | Ranked | Diamond | "
                "NA | Required | Aggressive | 3 | "
                "Looking for teammates to grind ranked.`"
            ),
            inline=False,
        )

        embed.add_field(
            name="Browse",
            value=(
                "`!lfg list` — Active LFG posts\n"
                "`!lfg mine` — Your active LFGs"
            ),
            inline=False,
        )

        embed.add_field(
            name="Manage",
            value=(
                "`!lfg close <id>` — Close your LFG\n"
                "`!lfg remove <id>` — Staff-only removal"
            ),
            inline=False,
        )

        embed.add_field(
            name="Platforms",
            value=(
                "PC • PlayStation • Xbox • Console • "
                "Crossplay • Any Platform"
            ),
            inline=False,
        )

        embed.add_field(
            name="Modes",
            value=(
                "Ranked • Public Matches • Mixtape • "
                "Limited-Time Mode • Custom • Any Mode"
            ),
            inline=False,
        )

        embed.add_field(
            name="Ranks",
            value=(
                "Rookie • Bronze • Silver • Gold • Platinum • "
                "Diamond • Master • Predator • Any Rank"
            ),
            inline=False,
        )

        embed.add_field(
            name="Regions",
            value=(
                "North America • Europe • Asia-Pacific • "
                "Oceania • South America • Any Region"
            ),
            inline=False,
        )

        await ctx.send(embed=embed)

    # ========================================================
    # CREATE
    # ========================================================

    @lfg.command(name="create")
    async def lfg_create(
        self,
        ctx: commands.Context,
        *,
        raw: str = "",
    ):
        """Create an Apex LFG."""
        if not raw:
            await ctx.send(
                "❌ Please provide the LFG information.\n\n"
                "Use `!lfg help` for the format."
            )
            return

        parts = [part.strip() for part in raw.split("|")]

        if len(parts) != 8:
            await ctx.send(
                "❌ Invalid format.\n\n"
                "Use:\n"
                "`!lfg create Platform | Mode | Rank | Region | "
                "Mic | Playstyle | Max Players | Description`"
            )
            return

        (
            platform_input,
            mode_input,
            rank_input,
            region_input,
            mic_input,
            playstyle_input,
            max_players_input,
            description,
        ) = parts

        platform = parse_choice(platform_input, PLATFORMS)
        mode = parse_choice(mode_input, MODES)
        rank = parse_choice(rank_input, RANKS)
        region = parse_choice(region_input, REGIONS)
        mic = parse_choice(mic_input, MICS)
        playstyle = parse_choice(playstyle_input, PLAYSTYLES)

        if not platform:
            await ctx.send(
                "❌ Invalid platform.\n"
                "Use `!lfg help` to see valid options."
            )
            return

        if not mode:
            await ctx.send(
                "❌ Invalid mode.\n"
                "Use `!lfg help` to see valid options."
            )
            return

        if not rank:
            await ctx.send(
                "❌ Invalid rank.\n"
                "Use `!lfg help` to see valid options."
            )
            return

        if not region:
            await ctx.send(
                "❌ Invalid region.\n"
                "Use `!lfg help` to see valid options."
            )
            return

        if not mic:
            await ctx.send(
                "❌ Invalid microphone preference.\n"
                "Use Required, Preferred, Optional, or Not Required."
            )
            return

        if not playstyle:
            await ctx.send(
                "❌ Invalid playstyle.\n"
                "Use Aggressive, Balanced, Passive, Casual, "
                "Competitive, Chill, or Any."
            )
            return

        try:
            max_players = int(max_players_input)
        except ValueError:
            await ctx.send(
                "❌ Max players must be a number."
            )
            return

        if max_players < 2 or max_players > 3:
            await ctx.send(
                "❌ Max players must be between **2 and 3**."
            )
            return

        description = description.strip()

        if not description:
            await ctx.send(
                "❌ Please provide a description."
            )
            return

        if len(description) > 1000:
            await ctx.send(
                "❌ Your description is too long. Maximum: 1000 characters."
            )
            return

        # Check for an existing active LFG from this user.
        conn = get_connection()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id
                FROM apex_lfg
                WHERE guild_id = ?
                  AND owner_id = ?
                  AND status = 'open'
                LIMIT 1
                """,
                (
                    ctx.guild.id,
                    ctx.author.id,
                ),
            )

            existing = cursor.fetchone()

            if existing:
                await ctx.send(
                    f"❌ You already have an active LFG: "
                    f"`#{existing['id']}`\n"
                    f"Close it before creating another one."
                )
                return

            now = utc_now()
            expires = now + timedelta(hours=LFG_EXPIRATION_HOURS)

            cursor.execute(
                """
                INSERT INTO apex_lfg (
                    guild_id,
                    channel_id,
                    message_id,
                    owner_id,
                    platform,
                    mode,
                    rank,
                    region,
                    mic,
                    playstyle,
                    description,
                    max_players,
                    status,
                    created_at,
                    expires_at
                )
                VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)
                """,
                (
                    ctx.guild.id,
                    ctx.channel.id,
                    ctx.author.id,
                    platform,
                    mode,
                    rank,
                    region,
                    mic,
                    playstyle,
                    description,
                    max_players,
                    now.isoformat(),
                    expires.isoformat(),
                ),
            )

            lfg_id = cursor.lastrowid

            # Host automatically joins their own LFG.
            cursor.execute(
                """
                INSERT INTO apex_lfg_players (
                    lfg_id,
                    user_id,
                    joined_at
                )
                VALUES (?, ?, ?)
                """,
                (
                    lfg_id,
                    ctx.author.id,
                    now.isoformat(),
                ),
            )

            conn.commit()

        except sqlite3.Error as exc:
            conn.rollback()

            print(f"[LFG] Database error creating LFG: {exc}")

            await ctx.send(
                "❌ I couldn't create the LFG right now."
            )
            return

        finally:
            conn.close()

        lfg = get_lfg(lfg_id, ctx.guild.id)
        players = get_players(lfg_id)

        embed = build_lfg_embed(
            ctx.guild,
            lfg,
            players,
        )

        view = LFGView(self, lfg_id)

        message = await ctx.send(
            embed=embed,
            view=view,
        )

        conn = get_connection()

        try:
            conn.execute(
                """
                UPDATE apex_lfg
                SET message_id = ?
                WHERE id = ?
                  AND guild_id = ?
                """,
                (
                    message.id,
                    lfg_id,
                    ctx.guild.id,
                ),
            )

            conn.commit()

        finally:
            conn.close()

    # ========================================================
    # LIST
    # ========================================================

    @lfg.command(name="list")
    async def lfg_list(self, ctx: commands.Context):
        """List active LFGs."""
        conn = get_connection()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT *
                FROM apex_lfg
                WHERE guild_id = ?
                  AND status = 'open'
                ORDER BY created_at DESC
                LIMIT 15
                """,
                (ctx.guild.id,),
            )

            rows = cursor.fetchall()

        finally:
            conn.close()

        if not rows:
            await ctx.send(
                "🎯 There are no active LFGs right now.\n"
                "Create one with `!lfg create`."
            )
            return

        embed = discord.Embed(
            title="🎯 Active Apex LFGs",
            description="Currently open groups in this server.",
            color=discord.Color.from_rgb(255, 105, 180),
        )

        for row in rows:
            players = get_players(row["id"])

            if len(players) >= row["max_players"]:
                status = "🔴 FULL"
            else:
                status = f"🟢 {len(players)}/{row['max_players']}"

            owner = ctx.guild.get_member(row["owner_id"])

            owner_text = (
                owner.display_name
                if owner
                else f"User {row['owner_id']}"
            )

            embed.add_field(
                name=f"🎮 #{row['id']} — {row['mode']} ({status})",
                value=(
                    f"**Host:** {owner_text}\n"
                    f"**Platform:** {row['platform']}\n"
                    f"**Rank:** {row['rank']}\n"
                    f"**Region:** {row['region']}\n"
                    f"**Playstyle:** {row['playstyle']}\n"
                    f"`!tech` isn't needed — use the buttons on the "
                    f"LFG post to join."
                ),
                inline=False,
            )

        embed.set_footer(
            text="Use the Join button on an LFG post to join."
        )

        await ctx.send(embed=embed)

    # ========================================================
    # MINE
    # ========================================================

    @lfg.command(name="mine")
    async def lfg_mine(self, ctx: commands.Context):
        """Show the user's active LFGs."""
        conn = get_connection()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT *
                FROM apex_lfg
                WHERE guild_id = ?
                  AND owner_id = ?
                  AND status = 'open'
                ORDER BY created_at DESC
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
                "🎯 You don't have any active LFGs."
            )
            return

        embed = discord.Embed(
            title="🎯 Your Active LFGs",
            color=discord.Color.from_rgb(255, 105, 180),
        )

        for row in rows:
            players = get_players(row["id"])

            embed.add_field(
                name=f"#{row['id']} — {row['mode']}",
                value=(
                    f"**Party:** {len(players)}/{row['max_players']}\n"
                    f"**Platform:** {row['platform']}\n"
                    f"**Rank:** {row['rank']}\n"
                    f"`!lfg close {row['id']}` to close"
                ),
                inline=False,
            )

        await ctx.send(embed=embed)

    # ========================================================
    # CLOSE
    # ========================================================

    @lfg.command(name="close")
    async def lfg_close(
        self,
        ctx: commands.Context,
        lfg_id: int,
    ):
        """Close an LFG owned by the user."""
        lfg = get_lfg(lfg_id, ctx.guild.id)

        if lfg is None:
            await ctx.send(
                f"❌ LFG `#{lfg_id}` doesn't exist."
            )
            return

        if lfg["owner_id"] != ctx.author.id and not is_staff(ctx.author):
            await ctx.send(
                "❌ Only the LFG host or staff can close this LFG."
            )
            return

        if lfg["status"] != "open":
            await ctx.send(
                f"ℹ️ LFG `#{lfg_id}` is already closed."
            )
            return

        conn = get_connection()

        try:
            conn.execute(
                """
                UPDATE apex_lfg
                SET status = 'closed'
                WHERE id = ?
                  AND guild_id = ?
                """,
                (
                    lfg_id,
                    ctx.guild.id,
                ),
            )

            conn.commit()

        finally:
            conn.close()

        if lfg["message_id"]:
            message = await get_message(
                self.bot,
                lfg["channel_id"],
                lfg["message_id"],
            )

            if message:
                try:
                    await message.edit(
                        content="🔒 **This LFG has been closed.**",
                        view=None,
                    )
                except discord.HTTPException:
                    pass

        await ctx.send(
            f"🔒 Closed LFG `#{lfg_id}`."
        )

    # ========================================================
    # REMOVE
    # ========================================================

    @lfg.command(name="remove")
    @commands.has_guild_permissions(manage_guild=True)
    async def lfg_remove(
        self,
        ctx: commands.Context,
        lfg_id: int,
    ):
        """Staff-only LFG removal."""
        lfg = get_lfg(lfg_id, ctx.guild.id)

        if lfg is None:
            await ctx.send(
                f"❌ LFG `#{lfg_id}` doesn't exist."
            )
            return

        conn = get_connection()

        try:
            conn.execute(
                """
                UPDATE apex_lfg
                SET status = 'removed'
                WHERE id = ?
                  AND guild_id = ?
                """,
                (
                    lfg_id,
                    ctx.guild.id,
                ),
            )

            conn.commit()

        finally:
            conn.close()

        if lfg["message_id"]:
            message = await get_message(
                self.bot,
                lfg["channel_id"],
                lfg["message_id"],
            )

            if message:
                try:
                    await message.edit(
                        content="🛡️ **This LFG was removed by staff.**",
                        view=None,
                    )
                except discord.HTTPException:
                    pass

        await ctx.send(
            f"🛡️ Removed LFG `#{lfg_id}`."
        )

    # ========================================================
    # JOIN
    # ========================================================

    async def handle_join(
        self,
        interaction: discord.Interaction,
        lfg_id: int,
    ):
        """Handle an LFG join request."""
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ This can only be used in a server.",
                ephemeral=True,
            )
            return

        lfg = get_lfg(
            lfg_id,
            interaction.guild.id,
        )

        if lfg is None:
            await interaction.response.send_message(
                "❌ That LFG no longer exists.",
                ephemeral=True,
            )
            return

        if lfg["status"] != "open":
            await interaction.response.send_message(
                "🔒 That LFG is no longer open.",
                ephemeral=True,
            )
            return

        # Check expiration.
        if datetime.fromisoformat(lfg["expires_at"]) <= utc_now():
            conn = get_connection()

            try:
                conn.execute(
                    """
                    UPDATE apex_lfg
                    SET status = 'expired'
                    WHERE id = ?
                    """,
                    (lfg_id,),
                )
                conn.commit()
            finally:
                conn.close()

            await interaction.response.send_message(
                "⏰ That LFG has expired.",
                ephemeral=True,
            )
            return

        players = get_players(lfg_id)

        if interaction.user.id in players:
            await interaction.response.send_message(
                "ℹ️ You're already in this LFG.",
                ephemeral=True,
            )
            return

        if len(players) >= lfg["max_players"]:
            await interaction.response.send_message(
                "🔴 This LFG is already full.",
                ephemeral=True,
            )
            return

        conn = get_connection()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO apex_lfg_players (
                    lfg_id,
                    user_id,
                    joined_at
                )
                VALUES (?, ?, ?)
                """,
                (
                    lfg_id,
                    interaction.user.id,
                    utc_iso(),
                ),
            )

            conn.commit()

        except sqlite3.IntegrityError:
            conn.rollback()

            await interaction.response.send_message(
                "ℹ️ You're already in this LFG.",
                ephemeral=True,
            )
            return

        finally:
            conn.close()

        players = get_players(lfg_id)

        updated_lfg = get_lfg(
            lfg_id,
            interaction.guild.id,
        )

        embed = build_lfg_embed(
            interaction.guild,
            updated_lfg,
            players,
        )

        try:
            await interaction.message.edit(
                embed=embed,
                view=LFGView(self, lfg_id),
            )
        except discord.HTTPException:
            pass

        await interaction.response.send_message(
            "🎮 You joined the LFG!",
            ephemeral=True,
        )

    # ========================================================
    # LEAVE
    # ========================================================

    async def handle_leave(
        self,
        interaction: discord.Interaction,
        lfg_id: int,
    ):
        """Handle an LFG leave request."""
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ This can only be used in a server.",
                ephemeral=True,
            )
            return

        lfg = get_lfg(
            lfg_id,
            interaction.guild.id,
        )

        if lfg is None:
            await interaction.response.send_message(
                "❌ That LFG no longer exists.",
                ephemeral=True,
            )
            return

        if lfg["status"] != "open":
            await interaction.response.send_message(
                "🔒 That LFG is no longer open.",
                ephemeral=True,
            )
            return

        if interaction.user.id == lfg["owner_id"]:
            await interaction.response.send_message(
                "❌ The host can't leave their own LFG.\n"
                "Use **Close LFG** instead.",
                ephemeral=True,
            )
            return

        conn = get_connection()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                DELETE FROM apex_lfg_players
                WHERE lfg_id = ?
                  AND user_id = ?
                """,
                (
                    lfg_id,
                    interaction.user.id,
                ),
            )

            removed = cursor.rowcount > 0

            conn.commit()

        finally:
            conn.close()

        if not removed:
            await interaction.response.send_message(
                "ℹ️ You're not currently in this LFG.",
                ephemeral=True,
            )
            return

        players = get_players(lfg_id)
        updated_lfg = get_lfg(
            lfg_id,
            interaction.guild.id,
        )

        embed = build_lfg_embed(
            interaction.guild,
            updated_lfg,
            players,
        )

        try:
            await interaction.message.edit(
                embed=embed,
                view=LFGView(self, lfg_id),
            )
        except discord.HTTPException:
            pass

        await interaction.response.send_message(
            "🚪 You left the LFG.",
            ephemeral=True,
        )

    # ========================================================
    # CLOSE BUTTON
    # ========================================================

    async def handle_close(
        self,
        interaction: discord.Interaction,
        lfg_id: int,
    ):
        """Handle the close button."""
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ This can only be used in a server.",
                ephemeral=True,
            )
            return

        lfg = get_lfg(
            lfg_id,
            interaction.guild.id,
        )

        if lfg is None:
            await interaction.response.send_message(
                "❌ That LFG no longer exists.",
                ephemeral=True,
            )
            return

        if (
            interaction.user.id != lfg["owner_id"]
            and not is_staff(interaction.user)
        ):
            await interaction.response.send_message(
                "❌ Only the host or staff can close this LFG.",
                ephemeral=True,
            )
            return

        if lfg["status"] != "open":
            await interaction.response.send_message(
                "ℹ️ This LFG is already closed.",
                ephemeral=True,
            )
            return

        conn = get_connection()

        try:
            conn.execute(
                """
                UPDATE apex_lfg
                SET status = 'closed'
                WHERE id = ?
                """,
                (lfg_id,),
            )

            conn.commit()

        finally:
            conn.close()

        try:
            await interaction.message.edit(
                content="🔒 **This LFG has been closed.**",
                view=None,
            )
        except discord.HTTPException:
            pass

        await interaction.response.send_message(
            "🔒 LFG closed.",
            ephemeral=True,
        )

    # ========================================================
    # ERROR HANDLING
    # ========================================================

    @lfg.error
    async def lfg_error(
        self,
        ctx: commands.Context,
        error: commands.CommandError,
    ):
        """Handle LFG command errors."""
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(
                "❌ You need **Manage Server** permission "
                "to use that command."
            )
            return

        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                "❌ You're missing a required argument.\n"
                "Use `!lfg help` for instructions."
            )
            return

        if isinstance(error, commands.BadArgument):
            await ctx.send(
                "❌ Invalid LFG ID. Use a number such as `!lfg close 1`."
            )
            return

        raise error


# ============================================================
# SETUP
# ============================================================

async def setup(bot: commands.Bot):
    await bot.add_cog(ApexLFG(bot))