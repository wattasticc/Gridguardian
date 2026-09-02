import sqlite3
import discord
from discord.ext import commands


# ==========================================================
# CONFIGURATION
# ==========================================================

EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)

DATABASE = "gridguardian.db"


# ==========================================================
# DATABASE
# ==========================================================

db = sqlite3.connect(DATABASE)
cursor = db.cursor()


# Create the settings table if it doesn't exist
cursor.execute("""
CREATE TABLE IF NOT EXISTS settings (
    guild_id INTEGER PRIMARY KEY,
    welcome_channel_id INTEGER,
    log_channel_id INTEGER,
    suggestion_channel_id INTEGER,
    autorole_id INTEGER
)
""")


# ----------------------------------------------------------
# DATABASE MIGRATION
# ----------------------------------------------------------
# This makes sure older versions of Grid Guardian get the
# newer columns without requiring you to delete the database.
# ----------------------------------------------------------

cursor.execute("PRAGMA table_info(settings)")
existing_columns = {
    column[1]
    for column in cursor.fetchall()
}

required_columns = {
    "welcome_channel_id": "INTEGER",
    "log_channel_id": "INTEGER",
    "suggestion_channel_id": "INTEGER",
    "autorole_id": "INTEGER"
}

for column_name, column_type in required_columns.items():

    if column_name not in existing_columns:

        cursor.execute(
            f"ALTER TABLE settings ADD COLUMN "
            f"{column_name} {column_type}"
        )


db.commit()


# ==========================================================
# SETTINGS COG
# ==========================================================

class Settings(commands.Cog):

    def __init__(self, bot):
        self.bot = bot


    # ======================================================
    # DATABASE HELPERS
    # ======================================================

    def ensure_guild(self, guild_id):

        cursor.execute(
            """
            INSERT OR IGNORE INTO settings(guild_id)
            VALUES(?)
            """,
            (guild_id,)
        )

        db.commit()


    def get_settings(self, guild_id):

        self.ensure_guild(guild_id)

        cursor.execute(
            """
            SELECT
                welcome_channel_id,
                log_channel_id,
                suggestion_channel_id,
                autorole_id
            FROM settings
            WHERE guild_id=?
            """,
            (guild_id,)
        )

        return cursor.fetchone()


    # ======================================================
    # SET WELCOME CHANNEL
    # ======================================================

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setwelcome(
        self,
        ctx,
        channel: discord.TextChannel
    ):

        self.ensure_guild(ctx.guild.id)

        cursor.execute(
            """
            UPDATE settings
            SET welcome_channel_id=?
            WHERE guild_id=?
            """,
            (channel.id, ctx.guild.id)
        )

        db.commit()

        embed = discord.Embed(
            title="👋 Welcome Channel Updated",
            description=(
                f"Welcome messages will now be sent in "
                f"{channel.mention}."
            ),
            color=discord.Color.green()
        )

        await ctx.send(embed=embed)


    # ======================================================
    # SET LOG CHANNEL
    # ======================================================

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setlogs(
        self,
        ctx,
        channel: discord.TextChannel
    ):

        self.ensure_guild(ctx.guild.id)

        cursor.execute(
            """
            UPDATE settings
            SET log_channel_id=?
            WHERE guild_id=?
            """,
            (channel.id, ctx.guild.id)
        )

        db.commit()

        embed = discord.Embed(
            title="📜 Log Channel Updated",
            description=(
                f"Server logs will now be sent to "
                f"{channel.mention}."
            ),
            color=discord.Color.green()
        )

        await ctx.send(embed=embed)


    # ======================================================
    # SET SUGGESTION CHANNEL
    # ======================================================

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setsuggestions(
        self,
        ctx,
        channel: discord.TextChannel
    ):

        self.ensure_guild(ctx.guild.id)

        cursor.execute(
            """
            UPDATE settings
            SET suggestion_channel_id=?
            WHERE guild_id=?
            """,
            (channel.id, ctx.guild.id)
        )

        db.commit()

        embed = discord.Embed(
            title="💡 Suggestion Channel Updated",
            description=(
                f"Suggestions will now be sent to "
                f"{channel.mention}."
            ),
            color=discord.Color.green()
        )

        await ctx.send(embed=embed)


    # ======================================================
    # SET AUTOROLE
    # ======================================================

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setautorole(
        self,
        ctx,
        role: discord.Role
    ):

        self.ensure_guild(ctx.guild.id)

        # Make sure the bot can actually give the role
        if role >= ctx.guild.me.top_role:

            return await ctx.send(
                "❌ I can't give that role because it is "
                "higher than or equal to my highest role.\n\n"
                "Move my bot role above the autorole."
            )

        cursor.execute(
            """
            UPDATE settings
            SET autorole_id=?
            WHERE guild_id=?
            """,
            (role.id, ctx.guild.id)
        )

        db.commit()

        embed = discord.Embed(
            title="🎭 Autorole Updated",
            description=(
                f"New members will automatically receive "
                f"{role.mention}."
            ),
            color=discord.Color.green()
        )

        await ctx.send(embed=embed)


    # ======================================================
    # RESET WELCOME CHANNEL
    # ======================================================

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def resetwelcome(self, ctx):

        self.ensure_guild(ctx.guild.id)

        cursor.execute(
            """
            UPDATE settings
            SET welcome_channel_id=NULL
            WHERE guild_id=?
            """,
            (ctx.guild.id,)
        )

        db.commit()

        await ctx.send(
            "✅ Welcome channel has been reset."
        )


    # ======================================================
    # RESET LOG CHANNEL
    # ======================================================

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def resetlogs(self, ctx):

        self.ensure_guild(ctx.guild.id)

        cursor.execute(
            """
            UPDATE settings
            SET log_channel_id=NULL
            WHERE guild_id=?
            """,
            (ctx.guild.id,)
        )

        db.commit()

        await ctx.send(
            "✅ Log channel has been reset."
        )


    # ======================================================
    # RESET SUGGESTION CHANNEL
    # ======================================================

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def resetsuggestions(self, ctx):

        self.ensure_guild(ctx.guild.id)

        cursor.execute(
            """
            UPDATE settings
            SET suggestion_channel_id=NULL
            WHERE guild_id=?
            """,
            (ctx.guild.id,)
        )

        db.commit()

        await ctx.send(
            "✅ Suggestion channel has been reset."
        )


    # ======================================================
    # RESET AUTOROLE
    # ======================================================

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def resetautorole(self, ctx):

        self.ensure_guild(ctx.guild.id)

        cursor.execute(
            """
            UPDATE settings
            SET autorole_id=NULL
            WHERE guild_id=?
            """,
            (ctx.guild.id,)
        )

        db.commit()

        await ctx.send(
            "✅ Autorole has been reset."
        )


    # ======================================================
    # VIEW SETTINGS
    # ======================================================

    @commands.command()
    async def settings(self, ctx):

        data = self.get_settings(ctx.guild.id)

        welcome, logs, suggestions, autorole = data

        embed = discord.Embed(
            title="⚙️ Server Settings",
            description=(
                f"Current configuration for "
                f"**{ctx.guild.name}**"
            ),
            color=EMBED_COLOR
        )

        # Welcome
        embed.add_field(
            name="👋 Welcome Channel",
            value=(
                f"<#{welcome}>"
                if welcome
                else "❌ Not Set"
            ),
            inline=False
        )

        # Logs
        embed.add_field(
            name="📜 Log Channel",
            value=(
                f"<#{logs}>"
                if logs
                else "❌ Not Set"
            ),
            inline=False
        )

        # Suggestions
        embed.add_field(
            name="💡 Suggestion Channel",
            value=(
                f"<#{suggestions}>"
                if suggestions
                else "❌ Not Set"
            ),
            inline=False
        )

        # Autorole
        embed.add_field(
            name="🎭 Autorole",
            value=(
                f"<@&{autorole}>"
                if autorole
                else "❌ Not Set"
            ),
            inline=False
        )

        embed.set_footer(
            text="Grid Guardian • Server Configuration"
        )

        await ctx.send(embed=embed)


    # ======================================================
    # SERVER DASHBOARD
    # ======================================================

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def dashboard(self, ctx):

        welcome, logs, suggestions, autorole = (
            self.get_settings(ctx.guild.id)
        )


        # --------------------------------------------------
        # LEVEL ROLES
        # --------------------------------------------------

        try:

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM level_roles
                WHERE guild_id=?
                """,
                (ctx.guild.id,)
            )

            level_roles = cursor.fetchone()[0]

        except sqlite3.OperationalError:

            level_roles = 0


        # --------------------------------------------------
        # WARNINGS
        # --------------------------------------------------

        try:

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM warnings
                WHERE guild_id=?
                """,
                (ctx.guild.id,)
            )

            total_warnings = cursor.fetchone()[0]

        except sqlite3.OperationalError:

            # Older warning tables may not have guild_id
            try:

                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM warnings
                    """
                )

                total_warnings = cursor.fetchone()[0]

            except sqlite3.OperationalError:

                total_warnings = 0


        # --------------------------------------------------
        # ECONOMY
        # --------------------------------------------------

        try:

            cursor.execute(
                """
                SELECT SUM(balance)
                FROM economy
                """
            )

            total_coins = cursor.fetchone()[0]

            if total_coins is None:
                total_coins = 0

        except sqlite3.OperationalError:

            total_coins = 0


        # --------------------------------------------------
        # DASHBOARD EMBED
        # --------------------------------------------------

        embed = discord.Embed(
            title="⚡ Grid Guardian Dashboard",
            description=(
                f"Server statistics and configuration "
                f"for **{ctx.guild.name}**"
            ),
            color=EMBED_COLOR
        )


        # --------------------------------------------------
        # SERVER ICON
        # --------------------------------------------------

        if ctx.guild.icon:

            embed.set_thumbnail(
                url=ctx.guild.icon.url
            )


        # --------------------------------------------------
        # SERVER STATS
        # --------------------------------------------------

        embed.add_field(
            name="👥 Members",
            value=str(ctx.guild.member_count),
            inline=True
        )

        embed.add_field(
            name="⭐ Level Roles",
            value=str(level_roles),
            inline=True
        )

        embed.add_field(
            name="⚠️ Warnings",
            value=str(total_warnings),
            inline=True
        )

        embed.add_field(
            name="💰 Total Economy",
            value=f"{total_coins:,} Coins",
            inline=True
        )


        # --------------------------------------------------
        # CONFIGURATION
        # --------------------------------------------------

        embed.add_field(
            name="👋 Welcome Channel",
            value=(
                f"<#{welcome}>"
                if welcome
                else "❌ Not Set"
            ),
            inline=False
        )

        embed.add_field(
            name="📜 Log Channel",
            value=(
                f"<#{logs}>"
                if logs
                else "❌ Not Set"
            ),
            inline=False
        )

        embed.add_field(
            name="💡 Suggestion Channel",
            value=(
                f"<#{suggestions}>"
                if suggestions
                else "❌ Not Set"
            ),
            inline=False
        )

        embed.add_field(
            name="🎭 Autorole",
            value=(
                f"<@&{autorole}>"
                if autorole
                else "❌ Not Set"
            ),
            inline=False
        )


        # --------------------------------------------------
        # FOOTER
        # --------------------------------------------------

        embed.set_footer(
            text="Grid Guardian • Server Dashboard"
        )


        await ctx.send(
            embed=embed
        )


# ==========================================================
# SETUP
# ==========================================================

async def setup(bot):

    await bot.add_cog(
        Settings(bot)
    )