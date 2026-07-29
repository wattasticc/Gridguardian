import discord
from discord.ext import commands

EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)


class Suggestions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def suggest(self, ctx, *, suggestion):

        embed = discord.Embed(
            title="💡 New Suggestion",
            description=suggestion,
            color=EMBED_COLOR
        )

        embed.add_field(
            name="Suggested By",
            value=ctx.author.mention,
            inline=False
        )

        embed.set_footer(
            text=f"User ID: {ctx.author.id}"
        )

        message = await ctx.send(embed=embed)

        await message.add_reaction("👍")
        await message.add_reaction("👎")

        # Delete the user's original command
        await ctx.message.delete()


async def setup(bot):
    await bot.add_cog(Suggestions(bot))