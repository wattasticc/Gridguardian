import discord
from discord.ext import commands

EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)


class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.command()
    async def ping(self, ctx):
        await ctx.send(f"🏓 Pong! {round(self.bot.latency * 1000)}ms")


    @commands.command()
    async def hello(self, ctx):
        await ctx.send(f"👋 Hello {ctx.author.mention}!")


    @commands.command()
    async def avatar(self, ctx, member: discord.Member = None):
        if member is None:
            member = ctx.author

        embed = discord.Embed(
            title=f"{member.display_name}'s Avatar",
            color=EMBED_COLOR
        )

        embed.set_image(url=member.display_avatar.url)
        await ctx.send(embed=embed)


    @commands.command(name="help")
    async def help_command(self, ctx):
        embed = discord.Embed(
            title="⚡ Grid Guardian Commands",
            color=EMBED_COLOR
        )

        embed.add_field(
            name="🛠 General",
            value=(
                "`!ping` - Check bot latency.\n"
                "`!hello` - Say hello.\n"
                "`!help` - Show this menu.\n"
                "`!avatar` - View a user's avatar.\n"
                "`!userinfo` - View user information.\n"
                "`!serverinfo` - View server information."
            ),
            inline=False
        )

        await ctx.send(embed=embed)


    @commands.command()
    async def userinfo(self, ctx, member: discord.Member = None):
        if member is None:
            member = ctx.author

        embed = discord.Embed(
            title=f"User Info - {member}",
            color=EMBED_COLOR
        )

        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Display Name", value=member.display_name)
        embed.add_field(
            name="Joined Server",
            value=member.joined_at.strftime("%b %d, %Y")
        )
        embed.add_field(
            name="Account Created",
            value=member.created_at.strftime("%b %d, %Y")
        )

        await ctx.send(embed=embed)


    @commands.command()
    async def serverinfo(self, ctx):
        guild = ctx.guild

        embed = discord.Embed(
            title=guild.name,
            color=EMBED_COLOR
        )

        embed.add_field(name="Members", value=guild.member_count)
        embed.add_field(name="Owner", value=guild.owner)
        embed.add_field(
            name="Created",
            value=guild.created_at.strftime("%b %d, %Y")
        )

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Utility(bot))