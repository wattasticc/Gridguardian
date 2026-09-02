import discord
from discord.ext import commands

EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)


class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def stats(self, ctx):

        guild = ctx.guild

        humans = len([m for m in guild.members if not m.bot])
        bots = len([m for m in guild.members if m.bot])

        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)

        embed = discord.Embed(
            title="📊 Server Statistics",
            color=EMBED_COLOR
        )

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        embed.add_field(
            name="👥 Members",
            value=guild.member_count,
            inline=True
        )

        embed.add_field(
            name="🧑 Humans",
            value=humans,
            inline=True
        )

        embed.add_field(
            name="🤖 Bots",
            value=bots,
            inline=True
        )

        embed.add_field(
            name="💬 Text Channels",
            value=text_channels,
            inline=True
        )

        embed.add_field(
            name="🔊 Voice Channels",
            value=voice_channels,
            inline=True
        )

        embed.add_field(
            name="🎭 Roles",
            value=len(guild.roles),
            inline=True
        )

        embed.add_field(
            name="😀 Emojis",
            value=len(guild.emojis),
            inline=True
        )

        embed.add_field(
            name="🚀 Boost Level",
            value=guild.premium_tier,
            inline=True
        )

        embed.add_field(
            name="💎 Boosts",
            value=guild.premium_subscription_count,
            inline=True
        )

        embed.set_footer(
            text=f"Server ID: {guild.id}"
        )

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Stats(bot))