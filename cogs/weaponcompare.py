"""
Grid Guardian - Apex Weapon Comparison

Server-managed Apex Legends weapon comparison database.

Commands:
    !wcompare
    !wcompare list
    !wcompare view <weapon>
    !wcompare compare <weapon1> <weapon2>
    !wcompare search <text>
    !wcompare category <category>
    !wcompare add
    !wcompare edit
    !wcompare delete
    !wcompare help

Add format:
    !wcompare add Name | Category | Ammo | Body | Head | Legs | Mag | Fire Rate | Description | Pros | Cons

Example:
    !wcompare add R-301 | Assault Rifle | Light | 14 | 25 | 12 | 18 | 810 | Reliable AR | Easy recoil | Lower close-range DPS

All weapon data is server-managed so staff can update values after Apex patches.
"""

import sqlite3
from datetime import datetime, timezone
from typing import Optional

import discord
from discord.ext import commands


DB_PATH = "gridguardian.db"


VALID_CATEGORIES = {
    "assault rifle": "Assault Rifle",
    "ar": "Assault Rifle",
    "smg": "SMG",
    "submachine gun": "SMG",
    "lmg": "LMG",
    "sniper": "Sniper",
    "sniper rifle": "Sniper",
    "marksman": "Marksman",
    "shotgun": "Shotgun",
    "pistol": "Pistol",
    "other": "Other",
}

VALID_AMMO = {
    "light": "Light",
    "heavy": "Heavy",
    "energy": "Energy",
    "sniper": "Sniper",
    "shotgun": "Shotgun Shells",
    "arrows": "Arrows",
    "special": "Special",
    "care package": "Care Package",
    "carepackage": "Care Package",
    "none": "None",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def connect_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def normalize_category(value: str) -> Optional[str]:
    return VALID_CATEGORIES.get(value.strip().lower())


def normalize_ammo(value: str) -> Optional[str]:
    return VALID_AMMO.get(value.strip().lower())


def parse_pipe_args(raw: str, expected: int) -> Optional[list[str]]:
    parts = [part.strip() for part in raw.split("|")]

    if len(parts) != expected:
        return None

    if any(not part for part in parts):
        return None

    return parts


def get_weapon(guild_id: int, name: str):
    conn = connect_db()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM apex_weapon_data
            WHERE guild_id = ?
              AND LOWER(name) = LOWER(?)
            """,
            (guild_id, name.strip()),
        )

        return cursor.fetchone()

    finally:
        conn.close()


def weapon_exists(guild_id: int, name: str) -> bool:
    return get_weapon(guild_id, name) is not None


class WeaponCompareView(discord.ui.View):
    def __init__(
        self,
        cog: "WeaponCompareCog",
        guild_id: int,
        weapon1: str,
        weapon2: str,
    ):
        super().__init__(timeout=300)

        self.cog = cog
        self.guild_id = guild_id
        self.weapon1 = weapon1
        self.weapon2 = weapon2

    @discord.ui.button(
        label="Compare Again",
        emoji="🔄",
        style=discord.ButtonStyle.primary,
    )
    async def compare_again(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        weapon_a = get_weapon(
            interaction.guild.id,
            self.weapon1,
        )

        weapon_b = get_weapon(
            interaction.guild.id,
            self.weapon2,
        )

        if weapon_a is None or weapon_b is None:
            await interaction.response.send_message(
                "One of these weapons is no longer in the database.",
                ephemeral=True,
            )
            return

        embed = self.cog.build_comparison_embed(
            weapon_a,
            weapon_b,
        )

        await interaction.response.edit_message(
            embed=embed,
            view=self,
        )


class WeaponCompareCog(commands.Cog):
    """Apex Legends weapon comparison system."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.setup_database()

    def setup_database(self):
        conn = connect_db()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS apex_weapon_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    ammo TEXT NOT NULL,
                    damage_body REAL NOT NULL,
                    damage_head REAL NOT NULL,
                    damage_legs REAL NOT NULL,
                    mag_size INTEGER NOT NULL,
                    fire_rate REAL NOT NULL,
                    description TEXT NOT NULL,
                    pros TEXT NOT NULL,
                    cons TEXT NOT NULL,
                    created_by INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(guild_id, name COLLATE NOCASE)
                )
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_weapon_guild_category
                ON apex_weapon_data(guild_id, category)
                """
            )

            conn.commit()

        finally:
            conn.close()

    @commands.group(
        name="wcompare",
        aliases=["weaponcompare", "weaponcomp"],
        invoke_without_command=True,
    )
    async def wcompare(self, ctx: commands.Context):
        """Apex weapon comparison system."""

        embed = discord.Embed(
            title="🔫 Weapon Comparison",
            description=(
                "Compare Apex weapons using the server's weapon database.\n\n"
                "**Commands**\n"
                "`!wcompare list` — List weapons\n"
                "`!wcompare view <weapon>` — View a weapon\n"
                "`!wcompare compare <weapon1> <weapon2>` — Compare two weapons\n"
                "`!wcompare search <text>` — Search weapons\n"
                "`!wcompare category <category>` — Filter by category\n"
                "`!wcompare add` — Add weapon data\n"
                "`!wcompare edit` — Edit weapon data\n"
                "`!wcompare delete <weapon>` — Delete weapon data\n"
                "`!wcompare help` — Detailed help"
            ),
            color=discord.Color.blurple(),
        )

        await ctx.send(embed=embed)

    @wcompare.command(name="list")
    async def weapon_list(self, ctx: commands.Context):
        """List all weapons."""

        conn = connect_db()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT name, category, ammo
                FROM apex_weapon_data
                WHERE guild_id = ?
                ORDER BY category ASC, name ASC
                """,
                (ctx.guild.id,),
            )

            rows = cursor.fetchall()

        finally:
            conn.close()

        if not rows:
            await ctx.send(
                "🔫 The weapon database is currently empty.\n"
                "A server administrator can add weapons with "
                "`!wcompare add`."
            )
            return

        embed = discord.Embed(
            title="🔫 Weapon Database",
            color=discord.Color.blurple(),
        )

        grouped = {}

        for row in rows:
            grouped.setdefault(row["category"], []).append(row)

        for category, weapons in grouped.items():
            text = "\n".join(
                f"• **{row['name']}** — {row['ammo']}"
                for row in weapons
            )

            embed.add_field(
                name=category,
                value=text[:1024],
                inline=False,
            )

        embed.set_footer(
            text=f"{len(rows)} weapon(s) in this server's database"
        )

        await ctx.send(embed=embed)

    @wcompare.command(name="view")
    async def weapon_view(
        self,
        ctx: commands.Context,
        *,
        weapon_name: str,
    ):
        """View detailed weapon information."""

        weapon = get_weapon(
            ctx.guild.id,
            weapon_name,
        )

        if weapon is None:
            await ctx.send(
                f"❌ I couldn't find **{weapon_name}** in the weapon database."
            )
            return

        embed = self.build_weapon_embed(weapon)

        await ctx.send(embed=embed)

    @wcompare.command(name="compare")
    async def weapon_compare(
        self,
        ctx: commands.Context,
        weapon1: str,
        weapon2: str,
    ):
        """Compare two weapons."""

        first = get_weapon(
            ctx.guild.id,
            weapon1,
        )

        second = get_weapon(
            ctx.guild.id,
            weapon2,
        )

        if first is None:
            await ctx.send(
                f"❌ **{weapon1}** isn't in the weapon database."
            )
            return

        if second is None:
            await ctx.send(
                f"❌ **{weapon2}** isn't in the weapon database."
            )
            return

        if first["id"] == second["id"]:
            await ctx.send(
                "❌ Choose two different weapons to compare."
            )
            return

        embed = self.build_comparison_embed(
            first,
            second,
        )

        await ctx.send(
            embed=embed,
            view=WeaponCompareView(
                self,
                ctx.guild.id,
                first["name"],
                second["name"],
            ),
        )

    @wcompare.command(name="search")
    async def weapon_search(
        self,
        ctx: commands.Context,
        *,
        search_text: str,
    ):
        """Search weapons."""

        search_text = search_text.strip()

        if not search_text:
            await ctx.send("❌ Enter something to search for.")
            return

        conn = connect_db()

        try:
            cursor = conn.cursor()

            pattern = f"%{search_text}%"

            cursor.execute(
                """
                SELECT name, category, ammo
                FROM apex_weapon_data
                WHERE guild_id = ?
                  AND (
                      name LIKE ? COLLATE NOCASE
                      OR category LIKE ? COLLATE NOCASE
                      OR ammo LIKE ? COLLATE NOCASE
                      OR description LIKE ? COLLATE NOCASE
                  )
                ORDER BY name ASC
                LIMIT 20
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
                f"❌ No weapons matched **{search_text}**."
            )
            return

        embed = discord.Embed(
            title=f"🔎 Weapon Search: {search_text}",
            color=discord.Color.blurple(),
        )

        for row in rows:
            embed.add_field(
                name=row["name"],
                value=(
                    f"**Category:** {row['category']}\n"
                    f"**Ammo:** {row['ammo']}"
                ),
                inline=True,
            )

        await ctx.send(embed=embed)

    @wcompare.command(name="category")
    async def weapon_category(
        self,
        ctx: commands.Context,
        *,
        category: str,
    ):
        """List weapons in a category."""

        normalized = normalize_category(category)

        if normalized is None:
            await ctx.send(
                "❌ Invalid category.\n"
                "Available: Assault Rifle, SMG, LMG, Sniper, "
                "Marksman, Shotgun, Pistol, Other."
            )
            return

        conn = connect_db()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT *
                FROM apex_weapon_data
                WHERE guild_id = ?
                  AND category = ?
                ORDER BY name ASC
                """,
                (
                    ctx.guild.id,
                    normalized,
                ),
            )

            rows = cursor.fetchall()

        finally:
            conn.close()

        if not rows:
            await ctx.send(
                f"❌ No **{normalized}** weapons have been added yet."
            )
            return

        embed = discord.Embed(
            title=f"🔫 {normalized}",
            color=discord.Color.blurple(),
        )

        for row in rows:
            embed.add_field(
                name=row["name"],
                value=(
                    f"**Ammo:** {row['ammo']}\n"
                    f"**Body:** {self.format_number(row['damage_body'])}\n"
                    f"**Head:** {self.format_number(row['damage_head'])}\n"
                    f"**Legs:** {self.format_number(row['damage_legs'])}"
                ),
                inline=True,
            )

        await ctx.send(embed=embed)

    @wcompare.command(name="add")
    @commands.has_guild_permissions(manage_guild=True)
    async def weapon_add(
        self,
        ctx: commands.Context,
        *,
        raw: str = "",
    ):
        """
        Add a weapon.

        Format:
        Name | Category | Ammo | Body | Head | Legs | Mag | Fire Rate | Description | Pros | Cons
        """

        parts = parse_pipe_args(raw, 11)

        if parts is None:
            await ctx.send(
                "❌ Incorrect format.\n\n"
                "**Use:**\n"
                "`!wcompare add Name | Category | Ammo | Body | "
                "Head | Legs | Mag | Fire Rate | Description | Pros | Cons`\n\n"
                "**Example:**\n"
                "`!wcompare add R-301 | Assault Rifle | Light | 14 | "
                "25 | 12 | 18 | 810 | Reliable AR | Easy recoil | "
                "Lower close-range DPS`"
            )
            return

        (
            name,
            category_raw,
            ammo_raw,
            body_raw,
            head_raw,
            legs_raw,
            mag_raw,
            fire_rate_raw,
            description,
            pros,
            cons,
        ) = parts

        category = normalize_category(category_raw)

        if category is None:
            await ctx.send(
                "❌ Invalid category.\n"
                "Available: Assault Rifle, SMG, LMG, Sniper, "
                "Marksman, Shotgun, Pistol, Other."
            )
            return

        ammo = normalize_ammo(ammo_raw)

        if ammo is None:
            await ctx.send(
                "❌ Invalid ammo type.\n"
                "Available: Light, Heavy, Energy, Sniper, "
                "Shotgun, Arrows, Special, Care Package, None."
            )
            return

        if len(name) > 80:
            await ctx.send(
                "❌ Weapon name must be 80 characters or fewer."
            )
            return

        if len(description) > 500:
            await ctx.send(
                "❌ Description must be 500 characters or fewer."
            )
            return

        if len(pros) > 500 or len(cons) > 500:
            await ctx.send(
                "❌ Pros and cons must each be 500 characters or fewer."
            )
            return

        try:
            damage_body = float(body_raw)
            damage_head = float(head_raw)
            damage_legs = float(legs_raw)
            mag_size = int(mag_raw)
            fire_rate = float(fire_rate_raw)
        except ValueError:
            await ctx.send(
                "❌ Body, head, legs, mag size, and fire rate "
                "must be valid numbers."
            )
            return

        if damage_body < 0 or damage_head < 0 or damage_legs < 0:
            await ctx.send(
                "❌ Damage values cannot be negative."
            )
            return

        if mag_size < 0:
            await ctx.send(
                "❌ Magazine size cannot be negative."
            )
            return

        if fire_rate < 0:
            await ctx.send(
                "❌ Fire rate cannot be negative."
            )
            return

        if weapon_exists(ctx.guild.id, name):
            await ctx.send(
                f"❌ **{name}** already exists in the database.\n"
                f"Use `!wcompare edit {name}` to update it."
            )
            return

        now = utc_now()

        conn = connect_db()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO apex_weapon_data (
                    guild_id,
                    name,
                    category,
                    ammo,
                    damage_body,
                    damage_head,
                    damage_legs,
                    mag_size,
                    fire_rate,
                    description,
                    pros,
                    cons,
                    created_by,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ctx.guild.id,
                    name,
                    category,
                    ammo,
                    damage_body,
                    damage_head,
                    damage_legs,
                    mag_size,
                    fire_rate,
                    description,
                    pros,
                    cons,
                    ctx.author.id,
                    now,
                    now,
                ),
            )

            conn.commit()

        except sqlite3.IntegrityError:
            conn.rollback()

            await ctx.send(
                f"❌ **{name}** already exists."
            )
            return

        except sqlite3.Error:
            conn.rollback()

            await ctx.send(
                "❌ Database error while adding the weapon."
            )
            return

        finally:
            conn.close()

        await ctx.send(
            f"✅ Added **{name}** to the weapon comparison database."
        )

    @wcompare.command(name="edit")
    @commands.has_guild_permissions(manage_guild=True)
    async def weapon_edit(
        self,
        ctx: commands.Context,
        *,
        raw: str = "",
    ):
        """
        Edit a weapon.

        Format:
        Name | Category | Ammo | Body | Head | Legs | Mag | Fire Rate | Description | Pros | Cons
        """

        parts = parse_pipe_args(raw, 11)

        if parts is None:
            await ctx.send(
                "❌ Incorrect format.\n\n"
                "`!wcompare edit Name | Category | Ammo | Body | "
                "Head | Legs | Mag | Fire Rate | Description | Pros | Cons`"
            )
            return

        (
            name,
            category_raw,
            ammo_raw,
            body_raw,
            head_raw,
            legs_raw,
            mag_raw,
            fire_rate_raw,
            description,
            pros,
            cons,
        ) = parts

        existing = get_weapon(
            ctx.guild.id,
            name,
        )

        if existing is None:
            await ctx.send(
                f"❌ **{name}** isn't in the database."
            )
            return

        category = normalize_category(category_raw)
        ammo = normalize_ammo(ammo_raw)

        if category is None:
            await ctx.send(
                "❌ Invalid category."
            )
            return

        if ammo is None:
            await ctx.send(
                "❌ Invalid ammo type."
            )
            return

        try:
            damage_body = float(body_raw)
            damage_head = float(head_raw)
            damage_legs = float(legs_raw)
            mag_size = int(mag_raw)
            fire_rate = float(fire_rate_raw)
        except ValueError:
            await ctx.send(
                "❌ Damage, magazine size, and fire rate "
                "must be valid numbers."
            )
            return

        now = utc_now()

        conn = connect_db()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE apex_weapon_data
                SET
                    category = ?,
                    ammo = ?,
                    damage_body = ?,
                    damage_head = ?,
                    damage_legs = ?,
                    mag_size = ?,
                    fire_rate = ?,
                    description = ?,
                    pros = ?,
                    cons = ?,
                    updated_at = ?
                WHERE id = ?
                  AND guild_id = ?
                """,
                (
                    category,
                    ammo,
                    damage_body,
                    damage_head,
                    damage_legs,
                    mag_size,
                    fire_rate,
                    description,
                    pros,
                    cons,
                    now,
                    existing["id"],
                    ctx.guild.id,
                ),
            )

            conn.commit()

        except sqlite3.Error:
            conn.rollback()

            await ctx.send(
                "❌ Database error while editing the weapon."
            )
            return

        finally:
            conn.close()

        await ctx.send(
            f"✅ Updated **{name}**."
        )

    @wcompare.command(name="delete")
    @commands.has_guild_permissions(manage_guild=True)
    async def weapon_delete(
        self,
        ctx: commands.Context,
        *,
        weapon_name: str,
    ):
        """Delete a weapon."""

        weapon = get_weapon(
            ctx.guild.id,
            weapon_name,
        )

        if weapon is None:
            await ctx.send(
                f"❌ **{weapon_name}** isn't in the database."
            )
            return

        conn = connect_db()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                DELETE FROM apex_weapon_data
                WHERE id = ?
                  AND guild_id = ?
                """,
                (
                    weapon["id"],
                    ctx.guild.id,
                ),
            )

            conn.commit()

        except sqlite3.Error:
            conn.rollback()

            await ctx.send(
                "❌ Database error while deleting the weapon."
            )
            return

        finally:
            conn.close()

        await ctx.send(
            f"🗑️ Removed **{weapon['name']}** from the database."
        )

    @wcompare.command(name="help")
    async def weapon_help(self, ctx: commands.Context):
        """Show detailed help."""

        embed = discord.Embed(
            title="🔫 Weapon Comparison Help",
            description=(
                "The weapon database lets your server keep its own "
                "up-to-date weapon information."
            ),
            color=discord.Color.blurple(),
        )

        embed.add_field(
            name="View",
            value=(
                "`!wcompare view R-301`\n"
                "`!wcompare list`"
            ),
            inline=False,
        )

        embed.add_field(
            name="Compare",
            value=(
                "`!wcompare compare R-301 Flatline`"
            ),
            inline=False,
        )

        embed.add_field(
            name="Search",
            value=(
                "`!wcompare search rifle`\n"
                "`!wcompare category SMG`"
            ),
            inline=False,
        )

        embed.add_field(
            name="Staff — Add",
            value=(
                "`!wcompare add Name | Category | Ammo | Body | "
                "Head | Legs | Mag | Fire Rate | Description | Pros | Cons`"
            ),
            inline=False,
        )

        embed.add_field(
            name="Staff — Edit",
            value=(
                "`!wcompare edit Name | Category | Ammo | Body | "
                "Head | Legs | Mag | Fire Rate | Description | Pros | Cons`"
            ),
            inline=False,
        )

        embed.add_field(
            name="Staff — Delete",
            value=(
                "`!wcompare delete <weapon>`"
            ),
            inline=False,
        )

        embed.add_field(
            name="Categories",
            value=(
                "Assault Rifle • SMG • LMG • Sniper • "
                "Marksman • Shotgun • Pistol • Other"
            ),
            inline=False,
        )

        embed.set_footer(
            text="Weapon data is managed by server staff."
        )

        await ctx.send(embed=embed)

    @staticmethod
    def format_number(value) -> str:
        value = float(value)

        if value.is_integer():
            return str(int(value))

        return f"{value:.2f}".rstrip("0").rstrip(".")

    def build_weapon_embed(
        self,
        weapon: sqlite3.Row,
    ) -> discord.Embed:
        embed = discord.Embed(
            title=f"🔫 {weapon['name']}",
            description=weapon["description"],
            color=discord.Color.blurple(),
        )

        embed.add_field(
            name="Category",
            value=weapon["category"],
            inline=True,
        )

        embed.add_field(
            name="Ammo",
            value=weapon["ammo"],
            inline=True,
        )

        embed.add_field(
            name="Magazine",
            value=str(weapon["mag_size"]),
            inline=True,
        )

        embed.add_field(
            name="Damage",
            value=(
                f"**Body:** {self.format_number(weapon['damage_body'])}\n"
                f"**Head:** {self.format_number(weapon['damage_head'])}\n"
                f"**Legs:** {self.format_number(weapon['damage_legs'])}"
            ),
            inline=True,
        )

        embed.add_field(
            name="Fire Rate",
            value=self.format_number(weapon["fire_rate"]),
            inline=True,
        )

        embed.add_field(
            name="Pros",
            value=weapon["pros"],
            inline=False,
        )

        embed.add_field(
            name="Cons",
            value=weapon["cons"],
            inline=False,
        )

        embed.set_footer(
            text=f"Last updated: {weapon['updated_at']} UTC"
        )

        return embed

    def build_comparison_embed(
        self,
        first: sqlite3.Row,
        second: sqlite3.Row,
    ) -> discord.Embed:
        def stat_line(label: str, value1, value2) -> str:
            return (
                f"**{label}**\n"
                f"{first['name']}: `{self.format_number(value1)}`\n"
                f"{second['name']}: `{self.format_number(value2)}`"
            )

        embed = discord.Embed(
            title=f"🔫 {first['name']} vs {second['name']}",
            description=(
                f"**{first['category']}** vs **{second['category']}**"
            ),
            color=discord.Color.blurple(),
        )

        embed.add_field(
            name="Ammo",
            value=(
                f"{first['name']}: `{first['ammo']}`\n"
                f"{second['name']}: `{second['ammo']}`"
            ),
            inline=True,
        )

        embed.add_field(
            name="Magazine",
            value=(
                f"{first['name']}: `{first['mag_size']}`\n"
                f"{second['name']}: `{second['mag_size']}`"
            ),
            inline=True,
        )

        embed.add_field(
            name="Fire Rate",
            value=(
                f"{first['name']}: `{self.format_number(first['fire_rate'])}`\n"
                f"{second['name']}: `{self.format_number(second['fire_rate'])}`"
            ),
            inline=True,
        )

        embed.add_field(
            name="Body Damage",
            value=(
                f"{first['name']}: `{self.format_number(first['damage_body'])}`\n"
                f"{second['name']}: `{self.format_number(second['damage_body'])}`"
            ),
            inline=True,
        )

        embed.add_field(
            name="Head Damage",
            value=(
                f"{first['name']}: `{self.format_number(first['damage_head'])}`\n"
                f"{second['name']}: `{self.format_number(second['damage_head'])}`"
            ),
            inline=True,
        )

        embed.add_field(
            name="Leg Damage",
            value=(
                f"{first['name']}: `{self.format_number(first['damage_legs'])}`\n"
                f"{second['name']}: `{self.format_number(second['damage_legs'])}`"
            ),
            inline=True,
        )

        embed.add_field(
            name=f"{first['name']} — Pros",
            value=first["pros"],
            inline=False,
        )

        embed.add_field(
            name=f"{first['name']} — Cons",
            value=first["cons"],
            inline=False,
        )

        embed.add_field(
            name=f"{second['name']} — Pros",
            value=second["pros"],
            inline=False,
        )

        embed.add_field(
            name=f"{second['name']} — Cons",
            value=second["cons"],
            inline=False,
        )

        embed.set_footer(
            text="Stats are maintained by server staff."
        )

        return embed

    @wcompare.error
    async def wcompare_error(
        self,
        ctx: commands.Context,
        error: commands.CommandError,
    ):
        if isinstance(
            error,
            commands.MissingPermissions,
        ):
            await ctx.send(
                "❌ You need **Manage Server** permission to modify "
                "the weapon database."
            )
            return

        if isinstance(
            error,
            commands.MissingRequiredArgument,
        ):
            await ctx.send(
                "❌ You're missing a required argument. "
                "Use `!wcompare help`."
            )
            return

        if isinstance(
            error,
            commands.BadArgument,
        ):
            await ctx.send(
                "❌ Invalid argument. Use `!wcompare help`."
            )
            return

        raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(WeaponCompareCog(bot))