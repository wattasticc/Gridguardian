import random
import sqlite3
import time
import discord
from discord.ext import commands
from cogs.utils.achievement_manager import unlock

EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)

db = sqlite3.connect("gridguardian.db")
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS levels (
    user_id INTEGER PRIMARY KEY,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS level_roles (
    guild_id INTEGER,
    level INTEGER,
    role_id INTEGER,
    PRIMARY KEY (guild_id, level)
)
""")

db.commit()


class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cooldowns = {}

    @commands.Cog.listener()
    async def on_message(self, message):

        if message.author.bot:
            return

        now = time.time()
        last = self.cooldowns.get(message.author.id, 0)

        # 60-second XP cooldown
        if now - last < 60:
            return

        self.cooldowns[message.author.id] = now

        xp_gain = random.randint(5, 15)

        cursor.execute(
            "SELECT xp, level FROM levels WHERE user_id=?",
            (message.author.id,)
        )

        data = cursor.fetchone()

        # --------------------------------------------------
        # NEW USER
        # --------------------------------------------------

        if data is None:

            cursor.execute(
                """
                INSERT INTO levels(user_id, xp, level)
                VALUES (?, ?, ?)
                """,
                (
                    message.author.id,
                    xp_gain,
                    1
                )
            )

            db.commit()

            return

        # --------------------------------------------------
        # EXISTING USER
        # --------------------------------------------------

        xp, level = data

        xp += xp_gain

        needed = level * 100

        # --------------------------------------------------
        # LEVEL UP
        # --------------------------------------------------

        if xp >= needed:

            xp -= needed
            level += 1

            # --------------------------------------------------
            # AUTOMATIC ACHIEVEMENTS
            # --------------------------------------------------

            if level == 5:
                unlock(
                    message.author.id,
                    "⭐ Level 5"
                )

            elif level == 10:
                unlock(
                    message.author.id,
                    "⭐ Level 10"
                )

            elif level == 25:
                unlock(
                    message.author.id,
                    "⭐ Level 25"
                )

            elif level == 50:
                unlock(
                    message.author.id,
                    "🌟 Level 50"
                )

            elif level == 100:
                unlock(
                    message.author.id,
                    "👑 Level 100"
                )

            # --------------------------------------------------
            # LEVEL ROLES
            # --------------------------------------------------

            if message.guild is not None:

                cursor.execute(
                    """
                    SELECT role_id
                    FROM level_roles
                    WHERE guild_id=?
                    AND level=?
                    """,
                    (
                        message.guild.id,
                        level
                    )
                )

                result = cursor.fetchone()

                if result:

                    role = message.guild.get_role(result[0])

                    if role:

                        try:
                            await message.author.add_roles(role)

                            embed = discord.Embed(
                                title="🎉 Level Up!",
                                description=(
                                    f"{message.author.mention} reached "
                                    f"**Level {level}**!\n\n"
                                    f"🏅 New Role: {role.mention}"
                                ),
                                color=discord.Color.gold()
                            )

                            await message.channel.send(
                                embed=embed
                            )

                        except discord.Forbidden:
                            embed = discord.Embed(
                                title="🎉 Level Up!",
                                description=(
                                    f"{message.author.mention} reached "
                                    f"**Level {level}**!"
                                ),
                                color=discord.Color.gold()
                            )

                            await message.channel.send(
                                embed=embed
                            )

                    else:

                        embed = discord.Embed(
                            title="🎉 Level Up!",
                            description=(
                                f"{message.author.mention} reached "
                                f"**Level {level}**!"
                            ),
                            color=discord.Color.gold()
                        )

                        await message.channel.send(
                            embed=embed
                        )

                else:

                    embed = discord.Embed(
                        title="🎉 Level Up!",
                        description=(
                            f"{message.author.mention} reached "
                            f"**Level {level}**!"
                        ),
                        color=discord.Color.gold()
                    )

                    await message.channel.send(
                        embed=embed
                    )

        # --------------------------------------------------
        # SAVE XP / LEVEL
        # --------------------------------------------------

        cursor.execute(
            """
            UPDATE levels
            SET xp=?, level=?
            WHERE user_id=?
            """,
            (
                xp,
                level,
                message.author.id
            )
        )

        db.commit()

    # --------------------------------------------------
    # RANK
    # --------------------------------------------------

    @commands.command()
    async def rank(self, ctx):

        cursor.execute(
            """
            SELECT xp, level
            FROM levels
            WHERE user_id=?
            """,
            (ctx.author.id,)
        )

        data = cursor.fetchone()

        if data is None:
            return await ctx.send(
                "You don't have any XP yet."
            )

        xp, level = data

        xp_needed = level * 100

        percent = min(
            int((xp / xp_needed) * 10),
            10
        )

        bar = (
            "█" * percent
            + "░" * (10 - percent)
        )

        embed = discord.Embed(
            title=f"⭐ {ctx.author.display_name}'s Rank",
            color=EMBED_COLOR
        )

        embed.set_thumbnail(
            url=ctx.author.display_avatar.url
        )

        embed.add_field(
            name="⭐ Level",
            value=level,
            inline=True
        )

        embed.add_field(
            name="⚡ XP",
            value=f"{xp}/{xp_needed}",
            inline=True
        )

        embed.add_field(
            name="📈 Progress",
            value=bar,
            inline=False
        )

        await ctx.send(embed=embed)

    # --------------------------------------------------
    # SET LEVEL ROLE
    # --------------------------------------------------

    @commands.has_permissions(administrator=True)
    @commands.command()
    async def setlevelrole(
        self,
        ctx,
        level: int,
        role: discord.Role
    ):

        if level < 1:
            return await ctx.send(
                "❌ Level must be 1 or higher."
            )

        cursor.execute(
            """
            INSERT OR REPLACE INTO level_roles
            VALUES (?, ?, ?)
            """,
            (
                ctx.guild.id,
                level,
                role.id
            )
        )

        db.commit()

        embed = discord.Embed(
            title="✅ Level Role Added",
            description=(
                f"Members will receive {role.mention}\n"
                f"when they reach **Level {level}**."
            ),
            color=discord.Color.green()
        )

        await ctx.send(embed=embed)

    # --------------------------------------------------
    # LEADERBOARD
    # --------------------------------------------------

    @commands.command(aliases=["lb"])
    async def leaderboard(self, ctx):

        cursor.execute(
            """
            SELECT user_id, level, xp
            FROM levels
            ORDER BY level DESC, xp DESC
            LIMIT 10
            """
        )

        results = cursor.fetchall()

        if not results:
            return await ctx.send(
                "Nobody has earned XP yet."
            )

        medals = [
            "🥇",
            "🥈",
            "🥉"
        ]

        embed = discord.Embed(
            title="🏆 Grid Guardian Leaderboard",
            description="Top 10 members by level",
            color=EMBED_COLOR
        )

        for index, (user_id, level, xp) in enumerate(results):

            member = ctx.guild.get_member(user_id)

            if member is None:
                continue

            if index < 3:
                place = medals[index]
            else:
                place = f"**{index + 1}.**"

            embed.add_field(
                name=f"{place} {member.display_name}",
                value=(
                    f"⭐ Level **{level}**\n"
                    f"⚡ XP **{xp}/{level * 100}**"
                ),
                inline=False
            )

        embed.set_footer(
            text=f"Requested by {ctx.author.display_name}"
        )

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Leveling(bot))