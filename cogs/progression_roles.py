import sqlite3
from typing import Optional

import discord
from discord.ext import commands


DB_PATH = "gridguardian.db"
EMBED_COLOR = discord.Color.blurple()


# ============================================================
# DEFAULT MILESTONES
# ============================================================

MASTERY_MILESTONES = {
    1: "Grid Recruit",
    5: "Junior Engineer",
    10: "Fence Specialist",
    20: "Grid Commander",
    30: "Electrical Expert",
    50: "Power Grid Master",
    75: "Grid Legend",
    100: "Master of the Grid",
}


class ProgressionRoles(commands.Cog):
    """Automatic Discord roles for Wattson progression."""

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

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS progression_roles (
                guild_id INTEGER NOT NULL,
                milestone INTEGER NOT NULL,
                role_id INTEGER NOT NULL,
                PRIMARY KEY (guild_id, milestone)
            )
            """
        )

        conn.commit()
        conn.close()

    # ============================================================
    # DATABASE OPERATIONS
    # ============================================================

    def get_role_id(
        self,
        guild_id: int,
        milestone: int
    ) -> Optional[int]:
        conn = self.db_connect()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT role_id
            FROM progression_roles
            WHERE guild_id = ?
              AND milestone = ?
            """,
            (
                guild_id,
                milestone
            )
        )

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return row["role_id"]

    def set_role(
        self,
        guild_id: int,
        milestone: int,
        role_id: int
    ):
        conn = self.db_connect()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO progression_roles (
                guild_id,
                milestone,
                role_id
            )
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, milestone)
            DO UPDATE SET role_id = excluded.role_id
            """,
            (
                guild_id,
                milestone,
                role_id
            )
        )

        conn.commit()
        conn.close()

    def remove_role(
        self,
        guild_id: int,
        milestone: int
    ):
        conn = self.db_connect()
        cursor = conn.cursor()

        cursor.execute(
            """
            DELETE FROM progression_roles
            WHERE guild_id = ?
              AND milestone = ?
            """,
            (
                guild_id,
                milestone
            )
        )

        conn.commit()
        conn.close()

    def get_configured_roles(
        self,
        guild_id: int
    ):
        conn = self.db_connect()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT milestone, role_id
            FROM progression_roles
            WHERE guild_id = ?
            ORDER BY milestone ASC
            """,
            (guild_id,)
        )

        rows = cursor.fetchall()
        conn.close()

        return rows

    # ============================================================
    # MASTERY
    # ============================================================

    def get_mastery_level(
        self,
        guild_id: int,
        user_id: int
    ) -> int:
        conn = self.db_connect()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT level
                FROM wattson_mastery
                WHERE guild_id = ?
                  AND user_id = ?
                """,
                (
                    guild_id,
                    user_id
                )
            )

            row = cursor.fetchone()

        except sqlite3.OperationalError:
            conn.close()
            return 1

        conn.close()

        if not row:
            return 1

        return row["level"]

    # ============================================================
    # ROLE MANAGEMENT
    # ============================================================

    async def apply_progression_roles(
        self,
        member: discord.Member
    ):
        """Apply the highest earned configured mastery role."""

        if member.bot:
            return []

        guild = member.guild

        mastery_level = self.get_mastery_level(
            guild.id,
            member.id
        )

        configured = self.get_configured_roles(
            guild.id
        )

        if not configured:
            return []

        earned_roles = []
        highest_role = None
        highest_milestone = 0

        for row in configured:
            milestone = row["milestone"]
            role_id = row["role_id"]

            if mastery_level < milestone:
                continue

            role = guild.get_role(role_id)

            if role is None:
                continue

            if milestone >= highest_milestone:
                highest_milestone = milestone
                highest_role = role

        if highest_role is None:
            return []

        # --------------------------------------------------------
        # Permission / hierarchy safety
        # --------------------------------------------------------

        if guild.me is None:
            return []

        if highest_role >= guild.me.top_role:
            return []

        if highest_role.is_default():
            return []

        # --------------------------------------------------------
        # Remove lower progression roles
        # --------------------------------------------------------

        for row in configured:
            role = guild.get_role(row["role_id"])

            if role is None:
                continue

            if role == highest_role:
                continue

            if role in member.roles:
                if role >= guild.me.top_role:
                    continue

                try:
                    await member.remove_roles(
                        role,
                        reason="Wattson progression role update"
                    )
                except discord.HTTPException:
                    pass

        # --------------------------------------------------------
        # Add highest role
        # --------------------------------------------------------

        if highest_role not in member.roles:
            try:
                await member.add_roles(
                    highest_role,
                    reason=(
                        "Wattson Mastery progression"
                    )
                )

                earned_roles.append(
                    highest_role
                )

            except discord.HTTPException:
                pass

        return earned_roles

    # ============================================================
    # CHECK ALL MILESTONES
    # ============================================================

    async def update_member_roles(
        self,
        member: discord.Member
    ):
        return await self.apply_progression_roles(
            member
        )

    # ============================================================
    # COMMAND GROUP
    # ============================================================

    @commands.group(
        name="progression",
        aliases=["prole", "masteryrole"],
        invoke_without_command=True
    )
    @commands.guild_only()
    async def progression(
        self,
        ctx: commands.Context
    ):
        """Wattson progression role commands."""

        embed = discord.Embed(
            title="⚡ Wattson Progression Roles",
            description=(
                "`!progression setup @role <level>`\n"
                "Configure a mastery role.\n\n"
                "`!progression remove <level>`\n"
                "Remove a configured milestone.\n\n"
                "`!progression list`\n"
                "View configured roles.\n\n"
                "`!progression sync [@user]`\n"
                "Update a member's roles.\n\n"
                "`!progression check`\n"
                "Check your current progression."
            ),
            color=EMBED_COLOR
        )

        await ctx.send(embed=embed)

    # ============================================================
    # SETUP ROLE
    # ============================================================

    @progression.command(name="setup")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def progression_setup(
        self,
        ctx: commands.Context,
        role: discord.Role,
        milestone: int
    ):
        """Configure a Discord role for a mastery milestone."""

        if milestone < 1:
            await ctx.send(
                "❌ The mastery level must be at least **1**."
            )
            return

        if milestone > 100:
            await ctx.send(
                "❌ The maximum supported mastery level is **100**."
            )
            return

        if role.is_default():
            await ctx.send(
                "❌ You cannot use @everyone as a progression role."
            )
            return

        if role.managed:
            await ctx.send(
                "❌ That role is managed by an integration and "
                "cannot be assigned by the bot."
            )
            return

        if ctx.guild.me is None:
            await ctx.send(
                "❌ I couldn't determine my bot member."
            )
            return

        if role >= ctx.guild.me.top_role:
            await ctx.send(
                "❌ I can't assign that role because it is above "
                "or equal to my highest role."
            )
            return

        self.set_role(
            ctx.guild.id,
            milestone,
            role.id
        )

        embed = discord.Embed(
            title="⚡ Progression Role Configured",
            description=(
                f"{role.mention} will now be awarded when a member "
                f"reaches **Wattson Mastery Level {milestone}**."
            ),
            color=discord.Color.green()
        )

        await ctx.send(embed=embed)

    # ============================================================
    # REMOVE ROLE
    # ============================================================

    @progression.command(name="remove")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def progression_remove(
        self,
        ctx: commands.Context,
        milestone: int
    ):
        """Remove a mastery role milestone."""

        role_id = self.get_role_id(
            ctx.guild.id,
            milestone
        )

        if role_id is None:
            await ctx.send(
                f"❌ No role is configured for level **{milestone}**."
            )
            return

        self.remove_role(
            ctx.guild.id,
            milestone
        )

        await ctx.send(
            f"✅ Removed the progression role for "
            f"**Mastery Level {milestone}**."
        )

    # ============================================================
    # LIST
    # ============================================================

    @progression.command(name="list")
    @commands.guild_only()
    async def progression_list(
        self,
        ctx: commands.Context
    ):
        """Show all configured progression roles."""

        rows = self.get_configured_roles(
            ctx.guild.id
        )

        embed = discord.Embed(
            title="⚡ Configured Progression Roles",
            color=EMBED_COLOR
        )

        if not rows:
            embed.description = (
                "No progression roles are configured yet.\n\n"
                "An administrator can use:\n"
                "`!progression setup @role <level>`"
            )

            await ctx.send(embed=embed)
            return

        lines = []

        for row in rows:
            role = ctx.guild.get_role(
                row["role_id"]
            )

            if role:
                role_text = role.mention
            else:
                role_text = (
                    f"Deleted Role "
                    f"`{row['role_id']}`"
                )

            milestone_name = MASTERY_MILESTONES.get(
                row["milestone"]
            )

            if milestone_name:
                name = milestone_name
            else:
                name = "Custom Milestone"

            lines.append(
                f"**Level {row['milestone']}** — "
                f"{role_text}\n"
                f"　{name}"
            )

        embed.description = "\n\n".join(
            lines
        )

        await ctx.send(embed=embed)

    # ============================================================
    # SYNC
    # ============================================================

    @progression.command(name="sync")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def progression_sync(
        self,
        ctx: commands.Context,
        member: Optional[discord.Member] = None
    ):
        """Synchronize a member's progression role."""

        member = member or ctx.author

        roles = await self.update_member_roles(
            member
        )

        if roles:
            role_names = ", ".join(
                role.name
                for role in roles
            )

            await ctx.send(
                f"✅ Updated {member.mention}'s progression roles.\n"
                f"Assigned: **{role_names}**"
            )
        else:
            level = self.get_mastery_level(
                ctx.guild.id,
                member.id
            )

            await ctx.send(
                f"✅ Checked {member.mention}'s progression.\n"
                f"Current Wattson Mastery: **Level {level}**"
            )

    # ============================================================
    # CHECK
    # ============================================================

    @progression.command(name="check")
    @commands.guild_only()
    async def progression_check(
        self,
        ctx: commands.Context
    ):
        """Check your current progression role."""

        level = self.get_mastery_level(
            ctx.guild.id,
            ctx.author.id
        )

        rows = self.get_configured_roles(
            ctx.guild.id
        )

        highest_milestone = 0
        highest_role = None

        for row in rows:
            milestone = row["milestone"]

            if level < milestone:
                continue

            role = ctx.guild.get_role(
                row["role_id"]
            )

            if role and milestone >= highest_milestone:
                highest_milestone = milestone
                highest_role = role

        embed = discord.Embed(
            title="⚡ Your Wattson Progression",
            color=EMBED_COLOR
        )

        embed.add_field(
            name="Mastery Level",
            value=f"**Level {level}**",
            inline=True
        )

        if highest_role:
            embed.add_field(
                name="Current Role",
                value=highest_role.mention,
                inline=True
            )

            embed.add_field(
                name="Next Milestone",
                value=(
                    self.get_next_milestone(
                        level,
                        rows
                    )
                ),
                inline=True
            )

        else:
            embed.add_field(
                name="Current Role",
                value="No progression role yet.",
                inline=True
            )

            embed.add_field(
                name="Next Milestone",
                value=(
                    self.get_next_milestone(
                        level,
                        rows
                    )
                ),
                inline=True
            )

        await ctx.send(embed=embed)

    # ============================================================
    # NEXT MILESTONE
    # ============================================================

    def get_next_milestone(
        self,
        level: int,
        rows
    ):
        next_milestone = None

        for row in rows:
            milestone = row["milestone"]

            if milestone > level:
                if (
                    next_milestone is None
                    or milestone < next_milestone
                ):
                    next_milestone = milestone

        if next_milestone is None:
            return "🏆 All configured milestones reached!"

        remaining = next_milestone - level

        return (
            f"Level **{next_milestone}** "
            f"(**{remaining}** levels away)"
        )

    # ============================================================
    # HELP
    # ============================================================

    @progression.command(name="help")
    @commands.guild_only()
    async def progression_help(
        self,
        ctx: commands.Context
    ):
        embed = discord.Embed(
            title="⚡ Progression Role Help",
            description=(
                "**Admin Commands**\n"
                "`!progression setup @role 5`\n"
                "`!progression setup @role 10`\n"
                "`!progression remove 5`\n"
                "`!progression sync @user`\n\n"
                "**Member Commands**\n"
                "`!progression list`\n"
                "`!progression check`\n"
                "`!progression help`"
            ),
            color=EMBED_COLOR
        )

        embed.add_field(
            name="Suggested Milestones",
            value=(
                "Level 1 — Grid Recruit\n"
                "Level 5 — Junior Engineer\n"
                "Level 10 — Fence Specialist\n"
                "Level 20 — Grid Commander\n"
                "Level 30 — Electrical Expert\n"
                "Level 50 — Power Grid Master\n"
                "Level 75 — Grid Legend\n"
                "Level 100 — Master of the Grid"
            ),
            inline=False
        )

        await ctx.send(embed=embed)

    # ============================================================
    # ERROR HANDLERS
    # ============================================================

    @progression_setup.error
    async def progression_setup_error(
        self,
        ctx: commands.Context,
        error
    ):
        if isinstance(
            error,
            commands.MissingPermissions
        ):
            await ctx.send(
                "❌ You need **Manage Server** permission "
                "to configure progression roles."
            )
            return

        if isinstance(
            error,
            commands.MissingRequiredArgument
        ):
            await ctx.send(
                "❌ Usage: `!progression setup @role <level>`"
            )
            return

        if isinstance(
            error,
            commands.BadArgument
        ):
            await ctx.send(
                "❌ I couldn't find that role or the level "
                "wasn't a valid number."
            )
            return

        raise error

    @progression_remove.error
    async def progression_remove_error(
        self,
        ctx: commands.Context,
        error
    ):
        if isinstance(
            error,
            commands.MissingPermissions
        ):
            await ctx.send(
                "❌ You need **Manage Server** permission."
            )
            return

        if isinstance(
            error,
            commands.MissingRequiredArgument
        ):
            await ctx.send(
                "❌ Usage: `!progression remove <level>`"
            )
            return

        if isinstance(
            error,
            commands.BadArgument
        ):
            await ctx.send(
                "❌ The milestone must be a number."
            )
            return

        raise error

    @progression_sync.error
    async def progression_sync_error(
        self,
        ctx: commands.Context,
        error
    ):
        if isinstance(
            error,
            commands.MissingPermissions
        ):
            await ctx.send(
                "❌ You need **Manage Server** permission."
            )
            return

        if isinstance(
            error,
            commands.BadArgument
        ):
            await ctx.send(
                "❌ I couldn't find that member."
            )
            return

        raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(
        ProgressionRoles(bot)
    )