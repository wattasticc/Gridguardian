import random
import sqlite3
import time
import discord
from discord.ext import commands

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

        if now - last < 60:
            await self.bot.process_commands(message)
            return

        self.cooldowns[message.author.id] = now

        xp_gain = random.randint(5, 15)

        cursor.execute(
            "SELECT xp, level FROM levels WHERE user_id=?",
            (message.author.id,)
        )

        data = cursor.fetchone()

        if data is None:
            cursor.execute(
                "INSERT INTO levels (user_id, xp, level) VALUES (?, ?, ?)",
                (message.author.id, xp_gain, 1)
            )
            db.commit()
        else:
            xp, level = data
            xp += xp_gain

            needed = level * 100

            if xp >= needed:
                xp = 0
                level += 1

                await message.channel.send(
                    f"🎉 {message.author.mention} reached **Level {level}!**"
                )

            cursor.execute(
                "UPDATE levels SET xp=?, level=? WHERE user_id=?",
                (xp, level, message.author.id)
            )

            db.commit()

        await self.bot.process_commands(message)

    @commands.command()
    async def rank(self, ctx):

        cursor.execute(
            "SELECT xp, level FROM levels WHERE user_id=?",
            (ctx.author.id,)
        )

        data = cursor.fetchone()

        if data is None:
            return await ctx.send("You don't have any XP yet.")

        xp, level = data

        embed = discord.Embed(
            title=f"{ctx.author.display_name}'s Rank",
            color=EMBED_COLOR
        )

        embed.add_field(name="⭐ Level", value=level)
        embed.add_field(name="⚡ XP", value=f"{xp}/{level*100}")

        await ctx.send(embed=embed)

    @commands.command()
    async def leaderboard(self, ctx):

        cursor.execute("""
        SELECT user_id, level, xp
        FROM levels
        ORDER BY level DESC, xp DESC
        LIMIT 10
        """)

        results = cursor.fetchall()

        if not results:
            return await ctx.send("Nobody has earned XP yet.")

        medals = ["🥇", "🥈", "🥉"]

        embed = discord.Embed(
            title="🏆 Grid Guardian Leaderboard",
            color=EMBED_COLOR
        )

        description = ""

        for i, (user_id, level, xp) in enumerate(results):

            member = ctx.guild.get_member(user_id)

            if member is None:
                continue

            if i < 3:
                place = medals[i]
            else:
                place = f"**{i+1}.**"

            description += (
                f"{place} {member.display_name} — "
                f"**Level {level}** ({xp} XP)\n"
            )

        embed.description = description

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Leveling(bot))