import discord
from discord.ext import commands

EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)


class Notifications(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # =========================================================
    # TWITCH
    # =========================================================

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def twitch(self, ctx, *, message):

        role = discord.utils.get(
            ctx.guild.roles,
            name="Twitch Notifications"
        )

        if role is None:
            return await ctx.send(
                "❌ The **Twitch Notifications** role doesn't exist."
            )

        embed = discord.Embed(
            title="🟣 Twitch Notification",
            description=message,
            color=EMBED_COLOR
        )

        embed.set_footer(
            text="Grid Guardian • Twitch"
        )

        await ctx.send(
            content=role.mention,
            embed=embed
        )

    # =========================================================
    # YOUTUBE
    # =========================================================

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def youtube(self, ctx, *, message):

        role = discord.utils.get(
            ctx.guild.roles,
            name="YouTube Notifications"
        )

        if role is None:
            return await ctx.send(
                "❌ The **YouTube Notifications** role doesn't exist."
            )

        embed = discord.Embed(
            title="▶️ YouTube Notification",
            description=message,
            color=EMBED_COLOR
        )

        embed.set_footer(
            text="Grid Guardian • YouTube"
        )

        await ctx.send(
            content=role.mention,
            embed=embed
        )

    # =========================================================
    # TIKTOK
    # =========================================================

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def tiktok(self, ctx, *, message):

        role = discord.utils.get(
            ctx.guild.roles,
            name="TikTok Notifications"
        )

        if role is None:
            return await ctx.send(
                "❌ The **TikTok Notifications** role doesn't exist."
            )

        embed = discord.Embed(
            title="🎵 TikTok Notification",
            description=message,
            color=EMBED_COLOR
        )

        embed.set_footer(
            text="Grid Guardian • TikTok"
        )

        await ctx.send(
            content=role.mention,
            embed=embed
        )

    # =========================================================
    # INSTAGRAM
    # =========================================================

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def instagram(self, ctx, *, message):

        role = discord.utils.get(
            ctx.guild.roles,
            name="Instagram Notifications"
        )

        if role is None:
            return await ctx.send(
                "❌ The **Instagram Notifications** role doesn't exist."
            )

        embed = discord.Embed(
            title="📸 Instagram Notification",
            description=message,
            color=EMBED_COLOR
        )

        embed.set_footer(
            text="Grid Guardian • Instagram"
        )

        await ctx.send(
            content=role.mention,
            embed=embed
        )


# =========================================================
# SETUP
# =========================================================

async def setup(bot):
    await bot.add_cog(Notifications(bot))