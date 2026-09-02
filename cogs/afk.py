import sqlite3
import discord
from discord.ext import commands

EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)


# ==========================================================
# DATABASE
# ==========================================================

db = sqlite3.connect("gridguardian.db")
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS afk (
    user_id INTEGER PRIMARY KEY,
    reason TEXT
)
""")

db.commit()


# ==========================================================
# AFK COG
# ==========================================================

class AFK(commands.Cog):

    def __init__(self, bot):
        self.bot = bot


    # ======================================================
    # SET AFK
    # ======================================================

    @commands.command()
    async def afk(self, ctx, *, reason="AFK"):

        cursor.execute(
            "INSERT OR REPLACE INTO afk VALUES (?, ?)",
            (ctx.author.id, reason)
        )

        db.commit()

        embed = discord.Embed(
            title="💤 AFK Enabled",
            description=(
                f"You are now AFK.\n\n"
                f"**Reason:** {reason}"
            ),
            color=EMBED_COLOR
        )

        await ctx.send(embed=embed)


    # ======================================================
    # AFK MESSAGE LISTENER
    # ======================================================

    @commands.Cog.listener()
    async def on_message(self, message):

        # Ignore bots
        if message.author.bot:
            return

        # Ignore the AFK command itself.
        # Otherwise !afk would immediately remove the AFK status.
        if message.content.startswith("!afk"):
            return


        # ==================================================
        # REMOVE AFK WHEN USER TALKS
        # ==================================================

        cursor.execute(
            "SELECT reason FROM afk WHERE user_id=?",
            (message.author.id,)
        )

        afk_data = cursor.fetchone()

        if afk_data:

            cursor.execute(
                "DELETE FROM afk WHERE user_id=?",
                (message.author.id,)
            )

            db.commit()

            await message.channel.send(
                f"👋 Welcome back {message.author.mention}, "
                "your AFK has been removed."
            )


        # ==================================================
        # CHECK MENTIONS
        # ==================================================

        for member in message.mentions:

            cursor.execute(
                "SELECT reason FROM afk WHERE user_id=?",
                (member.id,)
            )

            data = cursor.fetchone()

            if data:

                embed = discord.Embed(
                    title="💤 User is AFK",
                    description=(
                        f"{member.mention} is currently AFK.\n\n"
                        f"**Reason:** {data[0]}"
                    ),
                    color=discord.Color.orange()
                )

                await message.channel.send(embed=embed)


# ==========================================================
# SETUP
# ==========================================================

async def setup(bot):
    await bot.add_cog(AFK(bot))