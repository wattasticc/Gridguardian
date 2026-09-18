import math
import sqlite3
from typing import Optional

import discord
from discord.ext import commands


DB_PATH = "gridguardian.db"
EMBED_COLOR = discord.Color.blurple()

PAGE_SIZE = 10


class Leaderboards(commands.Cog):
    """Server leaderboard system for Grid Guardian."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.initialize_database()

    # ============================================================
    # DATABASE
    # ============================================================

    def db_connect(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize_database(self):
        conn = self.db_connect()
        cursor = conn.cursor()

        # Make sure the setup vote table exists if the Setup Library
        # is installed.
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS wattson_setup_votes (
                setup_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                PRIMARY KEY (setup_id, user_id)
            )
            """
        )

        conn.commit()
        conn.close()

    # ============================================================
    # USER HELPERS
    # ============================================================

    async def get_member_name(
        self,
        guild: discord.Guild,
        user_id: int
    ) -> str:
        member = guild.get_member(user_id)

        if member:
            return member.display_name

        try:
            user = await self.bot.fetch_user(user_id)
            return user.display_name
        except Exception:
            return f"User {user_id}"

    async def get_avatar(
        self,
        guild: discord.Guild,
        user_id: int
    ) -> Optional[str]:
        member = guild.get_member(user_id)

        if member:
            return member.display_avatar.url

        try:
            user = await self.bot.fetch_user(user_id)
            return user.display_avatar.url
        except Exception:
            return None

    # ============================================================
    # LEADERBOARD DATA
    # ============================================================

    def get_level_leaderboard(self, guild_id: int):
        conn = self.db_connect()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT user_id, xp, level
            FROM levels
            ORDER BY level DESC, xp DESC
            LIMIT 100
            """
        )

        rows = cursor.fetchall()
        conn.close()

        return rows

    def get_mastery_leaderboard(self, guild_id: int):
        conn = self.db_connect()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT user_id, xp, level
            FROM wattson_mastery
            WHERE guild_id = ?
            ORDER BY level DESC, xp DESC
            LIMIT 100
            """,
            (guild_id,)
        )

        rows = cursor.fetchall()
        conn.close()

        return rows

    def get_setup_leaderboard(self, guild_id: int):
        conn = self.db_connect()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                user_id,
                COUNT(*) AS setup_count,
                COALESCE(SUM(upvotes), 0) AS total_upvotes
            FROM wattson_setups
            WHERE guild_id = ?
            GROUP BY user_id
            ORDER BY total_upvotes DESC, setup_count DESC
            LIMIT 100
            """,
            (guild_id,)
        )

        rows = cursor.fetchall()
        conn.close()

        return rows

    # ============================================================
    # EMBED BUILDERS
    # ============================================================

    def base_embed(
        self,
        title: str,
        description: str
    ) -> discord.Embed:
        embed = discord.Embed(
            title=title,
            description=description,
            color=EMBED_COLOR
        )

        embed.set_footer(text="Grid Guardian • Server Leaderboards")

        return embed

    async def build_level_embed(
        self,
        ctx: commands.Context,
        rows,
        page: int
    ):
        total = len(rows)

        if total == 0:
            return self.base_embed(
                "🏆 Server Level Leaderboard",
                "There isn't any level data yet."
            )

        total_pages = max(1, math.ceil(total / PAGE_SIZE))

        page = max(0, min(page, total_pages - 1))

        start = page * PAGE_SIZE
        end = start + PAGE_SIZE

        page_rows = rows[start:end]

        lines = []

        for index, row in enumerate(page_rows, start=start + 1):
            user_id = row["user_id"]
            level = row["level"]
            xp = row["xp"]

            name = await self.get_member_name(ctx.guild, user_id)

            if index == 1:
                medal = "🥇"
            elif index == 2:
                medal = "🥈"
            elif index == 3:
                medal = "🥉"
            else:
                medal = f"`#{index}`"

            lines.append(
                f"{medal} **{name}**\n"
                f"　Level **{level}** • **{xp:,} XP**"
            )

        embed = self.base_embed(
            "🏆 Server Level Leaderboard",
            "\n\n".join(lines)
        )

        embed.set_footer(
            text=f"Grid Guardian • Page {page + 1}/{total_pages}"
        )

        return embed

    async def build_mastery_embed(
        self,
        ctx: commands.Context,
        rows,
        page: int
    ):
        total = len(rows)

        if total == 0:
            return self.base_embed(
                "⚡ Wattson Mastery Leaderboard",
                "Nobody has earned Wattson Mastery XP yet."
            )

        total_pages = max(1, math.ceil(total / PAGE_SIZE))

        page = max(0, min(page, total_pages - 1))

        start = page * PAGE_SIZE
        end = start + PAGE_SIZE

        page_rows = rows[start:end]

        lines = []

        for index, row in enumerate(page_rows, start=start + 1):
            user_id = row["user_id"]
            level = row["level"]
            xp = row["xp"]

            name = await self.get_member_name(ctx.guild, user_id)

            if index == 1:
                medal = "🥇"
            elif index == 2:
                medal = "🥈"
            elif index == 3:
                medal = "🥉"
            else:
                medal = f"`#{index}`"

            lines.append(
                f"{medal} **{name}**\n"
                f"　⚡ Mastery Level **{level}** • **{xp:,} XP**"
            )

        embed = self.base_embed(
            "⚡ Wattson Mastery Leaderboard",
            "\n\n".join(lines)
        )

        embed.set_footer(
            text=f"Grid Guardian • Page {page + 1}/{total_pages}"
        )

        return embed

    async def build_setup_embed(
        self,
        ctx: commands.Context,
        rows,
        page: int
    ):
        total = len(rows)

        if total == 0:
            return self.base_embed(
                "🧠 Setup Creator Leaderboard",
                "Nobody has submitted any Wattson setups yet."
            )

        total_pages = max(1, math.ceil(total / PAGE_SIZE))

        page = max(0, min(page, total_pages - 1))

        start = page * PAGE_SIZE
        end = start + PAGE_SIZE

        page_rows = rows[start:end]

        lines = []

        for index, row in enumerate(page_rows, start=start + 1):
            user_id = row["user_id"]
            setup_count = row["setup_count"]
            upvotes = row["total_upvotes"]

            name = await self.get_member_name(ctx.guild, user_id)

            if index == 1:
                medal = "🥇"
            elif index == 2:
                medal = "🥈"
            elif index == 3:
                medal = "🥉"
            else:
                medal = f"`#{index}`"

            lines.append(
                f"{medal} **{name}**\n"
                f"　⭐ **{upvotes:,}** upvotes • "
                f"🧠 **{setup_count:,}** setups"
            )

        embed = self.base_embed(
            "🧠 Setup Creator Leaderboard",
            "\n\n".join(lines)
        )

        embed.set_footer(
            text=f"Grid Guardian • Page {page + 1}/{total_pages}"
        )

        return embed

    # ============================================================
    # PAGINATION VIEW
    # ============================================================

    class LeaderboardView(discord.ui.View):
        def __init__(
            self,
            cog,
            ctx,
            leaderboard_type,
            rows,
            page=0
        ):
            super().__init__(timeout=180)

            self.cog = cog
            self.ctx = ctx
            self.leaderboard_type = leaderboard_type
            self.rows = rows
            self.page = page

            self.update_buttons()

        def update_buttons(self):
            total_pages = max(
                1,
                math.ceil(len(self.rows) / PAGE_SIZE)
            )

            self.previous_button.disabled = self.page <= 0
            self.next_button.disabled = self.page >= total_pages - 1

        async def interaction_check(
            self,
            interaction: discord.Interaction
        ) -> bool:
            if interaction.user.id != self.ctx.author.id:
                await interaction.response.send_message(
                    "❌ Only the person who opened this leaderboard can use these buttons.",
                    ephemeral=True
                )
                return False

            return True

        async def refresh(self, interaction: discord.Interaction):
            self.update_buttons()

            if self.leaderboard_type == "levels":
                embed = await self.cog.build_level_embed(
                    self.ctx,
                    self.rows,
                    self.page
                )

            elif self.leaderboard_type == "mastery":
                embed = await self.cog.build_mastery_embed(
                    self.ctx,
                    self.rows,
                    self.page
                )

            else:
                embed = await self.cog.build_setup_embed(
                    self.ctx,
                    self.rows,
                    self.page
                )

            await interaction.response.edit_message(
                embed=embed,
                view=self
            )

        @discord.ui.button(
            label="Previous",
            emoji="◀️",
            style=discord.ButtonStyle.secondary
        )
        async def previous_button(
            self,
            interaction: discord.Interaction,
            button: discord.ui.Button
        ):
            if self.page > 0:
                self.page -= 1

            await self.refresh(interaction)

        @discord.ui.button(
            label="Next",
            emoji="▶️",
            style=discord.ButtonStyle.secondary
        )
        async def next_button(
            self,
            interaction: discord.Interaction,
            button: discord.ui.Button
        ):
            total_pages = max(
                1,
                math.ceil(len(self.rows) / PAGE_SIZE)
            )

            if self.page < total_pages - 1:
                self.page += 1

            await self.refresh(interaction)

        async def on_timeout(self):
            for child in self.children:
                if isinstance(child, discord.ui.Button):
                    child.disabled = True

    # ============================================================
    # MAIN COMMAND
    # ============================================================

    @commands.group(
        name="leaderboard",
        aliases=["lb", "leaderboards"],
        invoke_without_command=True
    )
    @commands.guild_only()
    async def leaderboard(self, ctx: commands.Context):
        """Display server leaderboards."""

        embed = self.base_embed(
            "🏆 Grid Guardian Leaderboards",
            (
                "**Available leaderboards:**\n\n"
                "📈 `!leaderboard levels`\n"
                "　Server XP and levels\n\n"
                "⚡ `!leaderboard mastery`\n"
                "　Wattson Mastery progression\n\n"
                "🧠 `!leaderboard setups`\n"
                "　Wattson Setup Library creators\n\n"
                "🔎 `!leaderboard rank [@user]`\n"
                "　View someone's ranks"
            )
        )

        await ctx.send(embed=embed)

    # ============================================================
    # LEVEL LEADERBOARD
    # ============================================================

    @leaderboard.command(name="levels")
    @commands.guild_only()
    async def leaderboard_levels(self, ctx: commands.Context):
        """Show the server XP leaderboard."""

        try:
            rows = self.get_level_leaderboard(ctx.guild.id)
        except sqlite3.OperationalError:
            await ctx.send(
                "❌ The leveling system hasn't been initialized yet."
            )
            return

        embed = await self.build_level_embed(
            ctx,
            rows,
            0
        )

        view = self.LeaderboardView(
            self,
            ctx,
            "levels",
            rows,
            0
        )

        await ctx.send(
            embed=embed,
            view=view
        )

    # ============================================================
    # MASTERY LEADERBOARD
    # ============================================================

    @leaderboard.command(name="mastery")
    @commands.guild_only()
    async def leaderboard_mastery(self, ctx: commands.Context):
        """Show the Wattson Mastery leaderboard."""

        try:
            rows = self.get_mastery_leaderboard(ctx.guild.id)
        except sqlite3.OperationalError:
            await ctx.send(
                "❌ The Wattson Mastery system hasn't been initialized yet."
            )
            return

        embed = await self.build_mastery_embed(
            ctx,
            rows,
            0
        )

        view = self.LeaderboardView(
            self,
            ctx,
            "mastery",
            rows,
            0
        )

        await ctx.send(
            embed=embed,
            view=view
        )

    # ============================================================
    # SETUP LEADERBOARD
    # ============================================================

    @leaderboard.command(
        name="setups",
        aliases=["setup"]
    )
    @commands.guild_only()
    async def leaderboard_setups(self, ctx: commands.Context):
        """Show the Wattson Setup creator leaderboard."""

        try:
            rows = self.get_setup_leaderboard(ctx.guild.id)
        except sqlite3.OperationalError:
            await ctx.send(
                "❌ The Wattson Setup Library hasn't been initialized yet."
            )
            return

        embed = await self.build_setup_embed(
            ctx,
            rows,
            0
        )

        view = self.LeaderboardView(
            self,
            ctx,
            "setups",
            rows,
            0
        )

        await ctx.send(
            embed=embed,
            view=view
        )

    # ============================================================
    # PERSONAL RANK
    # ============================================================

    @leaderboard.command(name="rank")
    @commands.guild_only()
    async def leaderboard_rank(
        self,
        ctx: commands.Context,
        member: Optional[discord.Member] = None
    ):
        """Show a user's leaderboard positions."""

        member = member or ctx.author
        user_id = member.id
        guild_id = ctx.guild.id

        conn = self.db_connect()
        cursor = conn.cursor()

        # --------------------------------------------------------
        # Level rank
        # --------------------------------------------------------

        level_rank = None
        level_data = None

        try:
            cursor.execute(
                """
                SELECT user_id, xp, level
                FROM levels
                ORDER BY level DESC, xp DESC
                """
            )

            level_rows = cursor.fetchall()

            for index, row in enumerate(level_rows, start=1):
                if row["user_id"] == user_id:
                    level_rank = index
                    level_data = row
                    break

        except sqlite3.OperationalError:
            pass

        # --------------------------------------------------------
        # Mastery rank
        # --------------------------------------------------------

        mastery_rank = None
        mastery_data = None

        try:
            cursor.execute(
                """
                SELECT user_id, xp, level
                FROM wattson_mastery
                WHERE guild_id = ?
                ORDER BY level DESC, xp DESC
                """,
                (guild_id,)
            )

            mastery_rows = cursor.fetchall()

            for index, row in enumerate(mastery_rows, start=1):
                if row["user_id"] == user_id:
                    mastery_rank = index
                    mastery_data = row
                    break

        except sqlite3.OperationalError:
            pass

        # --------------------------------------------------------
        # Setup rank
        # --------------------------------------------------------

        setup_rank = None
        setup_data = None

        try:
            cursor.execute(
                """
                SELECT
                    user_id,
                    COUNT(*) AS setup_count,
                    COALESCE(SUM(upvotes), 0) AS total_upvotes
                FROM wattson_setups
                WHERE guild_id = ?
                GROUP BY user_id
                ORDER BY total_upvotes DESC, setup_count DESC
                """,
                (guild_id,)
            )

            setup_rows = cursor.fetchall()

            for index, row in enumerate(setup_rows, start=1):
                if row["user_id"] == user_id:
                    setup_rank = index
                    setup_data = row
                    break

        except sqlite3.OperationalError:
            pass

        conn.close()

        # --------------------------------------------------------
        # Build embed
        # --------------------------------------------------------

        embed = discord.Embed(
            title=f"📊 {member.display_name}'s Ranks",
            color=EMBED_COLOR
        )

        embed.set_thumbnail(
            url=member.display_avatar.url
        )

        # Level
        if level_data:
            embed.add_field(
                name="📈 Server Level",
                value=(
                    f"**Rank:** #{level_rank}\n"
                    f"**Level:** {level_data['level']}\n"
                    f"**XP:** {level_data['xp']:,}"
                ),
                inline=False
            )
        else:
            embed.add_field(
                name="📈 Server Level",
                value="No level data yet.",
                inline=False
            )

        # Mastery
        if mastery_data:
            embed.add_field(
                name="⚡ Wattson Mastery",
                value=(
                    f"**Rank:** #{mastery_rank}\n"
                    f"**Level:** {mastery_data['level']}\n"
                    f"**XP:** {mastery_data['xp']:,}"
                ),
                inline=False
            )
        else:
            embed.add_field(
                name="⚡ Wattson Mastery",
                value="No Wattson Mastery data yet.",
                inline=False
            )

        # Setups
        if setup_data:
            embed.add_field(
                name="🧠 Setup Creator",
                value=(
                    f"**Rank:** #{setup_rank}\n"
                    f"**Setups:** {setup_data['setup_count']:,}\n"
                    f"**Upvotes:** {setup_data['total_upvotes']:,}"
                ),
                inline=False
            )
        else:
            embed.add_field(
                name="🧠 Setup Creator",
                value="No setup submissions yet.",
                inline=False
            )

        embed.set_footer(
            text="Grid Guardian • Personal Rankings"
        )

        await ctx.send(embed=embed)

    # ============================================================
    # HELP
    # ============================================================

    @leaderboard.command(name="help")
    @commands.guild_only()
    async def leaderboard_help(self, ctx: commands.Context):
        """Show leaderboard commands."""

        embed = discord.Embed(
            title="🏆 Leaderboard Commands",
            description=(
                "`!leaderboard` — Show leaderboard menu\n"
                "`!leaderboard levels` — Server XP leaderboard\n"
                "`!leaderboard mastery` — Wattson Mastery leaderboard\n"
                "`!leaderboard setups` — Setup creator leaderboard\n"
                "`!leaderboard rank` — Your ranks\n"
                "`!leaderboard rank @user` — Someone else's ranks"
            ),
            color=EMBED_COLOR
        )

        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Leaderboards(bot))