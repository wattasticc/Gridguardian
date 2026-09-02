import discord
from discord.ext import commands


EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)


class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    # ==========================================================
    # PING
    # ==========================================================

    @commands.command()
    async def ping(self, ctx):

        latency = round(self.bot.latency * 1000)

        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Latency: **{latency}ms**",
            color=EMBED_COLOR
        )

        await ctx.send(embed=embed)


    # ==========================================================
    # HELLO
    # ==========================================================

    @commands.command()
    async def hello(self, ctx):

        embed = discord.Embed(
            title="👋 Hello!",
            description=f"Welcome, {ctx.author.mention}!",
            color=EMBED_COLOR
        )

        await ctx.send(embed=embed)


    # ==========================================================
    # AVATAR
    # ==========================================================

    @commands.command()
    async def avatar(self, ctx, member: discord.Member = None):

        member = member or ctx.author

        embed = discord.Embed(
            title=f"{member.display_name}'s Avatar",
            color=EMBED_COLOR
        )

        embed.set_image(url=member.display_avatar.url)

        await ctx.send(embed=embed)


    # ==========================================================
    # USER INFO
    # ==========================================================

    @commands.command()
    async def userinfo(self, ctx, member: discord.Member = None):

        member = member or ctx.author

        embed = discord.Embed(
            title=f"👤 {member}",
            color=EMBED_COLOR
        )

        embed.set_thumbnail(url=member.display_avatar.url)

        embed.add_field(
            name="Display Name",
            value=member.display_name,
            inline=True
        )

        embed.add_field(
            name="ID",
            value=member.id,
            inline=True
        )

        embed.add_field(
            name="Joined Server",
            value=member.joined_at.strftime("%b %d, %Y"),
            inline=False
        )

        embed.add_field(
            name="Account Created",
            value=member.created_at.strftime("%b %d, %Y"),
            inline=False
        )

        embed.add_field(
            name="Top Role",
            value=member.top_role.mention,
            inline=False
        )

        await ctx.send(embed=embed)


    # ==========================================================
    # SERVER INFO
    # ==========================================================

    @commands.command()
    async def serverinfo(self, ctx):

        guild = ctx.guild

        embed = discord.Embed(
            title=f"🌐 {guild.name}",
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
            name="💬 Channels",
            value=len(guild.channels),
            inline=True
        )

        embed.add_field(
            name="🎭 Roles",
            value=len(guild.roles),
            inline=True
        )

        embed.add_field(
            name="👑 Owner",
            value=guild.owner,
            inline=False
        )

        embed.add_field(
            name="📅 Created",
            value=guild.created_at.strftime("%b %d, %Y"),
            inline=False
        )

        await ctx.send(embed=embed)


# ==========================================================
# SETUP
# ==========================================================

async def setup(bot):
    await bot.add_cog(Utility(bot))