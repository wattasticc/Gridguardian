import sqlite3
import discord
from discord.ext import commands

EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)

db = sqlite3.connect("gridguardian.db")
cursor = db.cursor()


class Profile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def profile(self, ctx, member: discord.Member = None):

        if member is None:
            member = ctx.author

        # -------------------------
        # LEVEL
        # -------------------------

        cursor.execute(
            "SELECT level, xp FROM levels WHERE user_id=?",
            (member.id,)
        )

        data = cursor.fetchone()

        if data:
            level, xp = data
        else:
            level = 1
            xp = 0

        xp_needed = level * 100

        # Progress Bar
        percent = min(int((xp / xp_needed) * 10), 10)
        bar = "█" * percent + "░" * (10 - percent)

        # -------------------------
        # ECONOMY
        # -------------------------

        balance = 0

        try:
            cursor.execute(
                "SELECT balance FROM economy WHERE user_id=?",
                (member.id,)
            )

            data = cursor.fetchone()

            if data:
                balance = data[0]

        except:
            pass

        # -------------------------
        # ACHIEVEMENTS
        # -------------------------

        achievements = 0

        try:
            cursor.execute("""
            SELECT COUNT(*)
            FROM achievements
            WHERE user_id=?
            """, (member.id,))

            achievements = cursor.fetchone()[0]

        except:
            pass

        # -------------------------
        # SERVER RANK
        # -------------------------

        cursor.execute("""
        SELECT user_id
        FROM levels
        ORDER BY level DESC, xp DESC
        """)

        leaderboard = cursor.fetchall()

        rank = "Unranked"

        for i, user in enumerate(leaderboard):

            if user[0] == member.id:
                rank = f"#{i + 1}"
                break

        # -------------------------
        # ROLES
        # -------------------------

        roles = [
            role.mention
            for role in member.roles
            if role.name != "@everyone"
        ]

        role_text = ", ".join(roles[:8])

        if not role_text:
            role_text = "None"

        # -------------------------
        # EMBED
        # -------------------------

        embed = discord.Embed(
            title="⚡ Grid Guardian Profile",
            color=EMBED_COLOR
        )

        embed.set_author(
            name=member.display_name,
            icon_url=member.display_avatar.url
        )

        embed.set_thumbnail(
            url=member.display_avatar.url
        )

        embed.add_field(
            name="⭐ Level",
            value=level,
            inline=True
        )

        embed.add_field(
            name="🏆 Rank",
            value=rank,
            inline=True
        )

        embed.add_field(
            name="💰 Coins",
            value=f"{balance:,}",
            inline=True
        )

        embed.add_field(
            name="⚡ XP Progress",
            value=f"{bar}\n{xp}/{xp_needed}",
            inline=False
        )

        embed.add_field(
            name="🏅 Achievements",
            value=f"{achievements} Unlocked",
            inline=True
        )

        embed.add_field(
            name="📅 Joined",
            value=member.joined_at.strftime("%b %d, %Y"),
            inline=True
        )

        embed.add_field(
            name="🎭 Roles",
            value=role_text,
            inline=False
        )

        embed.set_footer(
            text=f"User ID • {member.id}"
        )

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Profile(bot))