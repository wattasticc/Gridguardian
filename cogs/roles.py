import discord
from discord.ext import commands

from views.role_view import (
    PlatformRoleView,
    AssaultRoleView,
    SkirmisherRoleView,
    ReconRoleView,
    ControllerRoleView,
    SupportRoleView
)


EMBED_COLOR = discord.Color.from_rgb(
    80,
    220,
    255
)


class Roles(commands.Cog):

    def __init__(self, bot):

        self.bot = bot


    # =================================================
    # PERSISTENT VIEWS
    # =================================================

    async def cog_load(self):

        self.bot.add_view(
            PlatformRoleView()
        )

        self.bot.add_view(
            AssaultRoleView()
        )

        self.bot.add_view(
            SkirmisherRoleView()
        )

        self.bot.add_view(
            ReconRoleView()
        )

        self.bot.add_view(
            ControllerRoleView()
        )

        self.bot.add_view(
            SupportRoleView()
        )


    # =================================================
    # PLATFORM PANEL
    # =================================================

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def roles(self, ctx):

        embed = discord.Embed(
            title="🎮 Choose Your Platform",
            description=(
                "Select the platform or platforms "
                "you play Apex Legends on."
            ),
            color=EMBED_COLOR
        )

        embed.add_field(
            name="Available Platforms",
            value=(
                "🖥️ **PC**\n"
                "🎮 **PlayStation**\n"
                "🟩 **Xbox**"
            ),
            inline=False
        )

        embed.set_footer(
            text="Click a button again to remove the role."
        )

        await ctx.send(
            embed=embed,
            view=PlatformRoleView()
        )


    # =================================================
    # ASSAULT PANEL
    # =================================================

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def assaultroles(self, ctx):

        embed = discord.Embed(
            title="⚔️ Assault Legends",
            description=(
                "Choose the Assault Legends "
                "you play."
            ),
            color=EMBED_COLOR
        )

        embed.add_field(
            name="Available Legends",
            value=(
                "🎯 **Ballistic**\n"
                "💥 **Bangalore**\n"
                "💣 **Fuse**\n"
                "🔥 **Mad Maggie**\n"
                "👻 **Revenant**"
            ),
            inline=False
        )

        embed.set_footer(
            text="Click a button again to remove the role."
        )

        await ctx.send(
            embed=embed,
            view=AssaultRoleView()
        )


    # =================================================
    # SKIRMISHER PANEL
    # =================================================

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def skirmisherroles(self, ctx):

        embed = discord.Embed(
            title="🏃 Skirmisher Legends",
            description=(
                "Choose the Skirmisher Legends "
                "you play."
            ),
            color=EMBED_COLOR
        )

        embed.add_field(
            name="Available Legends",
            value=(
                "🌀 **Alter**\n"
                "⚔️ **Ash**\n"
                "🏎️ **Axle**\n"
                "🌌 **Horizon**\n"
                "⚡ **Octane**\n"
                "🤖 **Pathfinder**\n"
                "🩸 **Wraith**"
            ),
            inline=False
        )

        embed.set_footer(
            text="Click a button again to remove the role."
        )

        await ctx.send(
            embed=embed,
            view=SkirmisherRoleView()
        )


    # =================================================
    # RECON PANEL
    # =================================================

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def reconroles(self, ctx):

        embed = discord.Embed(
            title="🔎 Recon Legends",
            description=(
                "Choose the Recon Legends "
                "you play."
            ),
            color=EMBED_COLOR
        )

        embed.add_field(
            name="Available Legends",
            value=(
                "🔎 **Bloodhound**\n"
                "💻 **Crypto**\n"
                "👁️ **Seer**\n"
                "🏹 **Sparrow**\n"
                "🚀 **Valkyrie**\n"
                "🎯 **Vantage**"
            ),
            inline=False
        )

        embed.set_footer(
            text="Click a button again to remove the role."
        )

        await ctx.send(
            embed=embed,
            view=ReconRoleView()
        )


    # =================================================
    # CONTROLLER PANEL
    # =================================================

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def controllerroles(self, ctx):

        embed = discord.Embed(
            title="⚡ Controller Legends",
            description=(
                "Choose the Controller Legends "
                "you play."
            ),
            color=EMBED_COLOR
        )

        embed.add_field(
            name="Available Legends",
            value=(
                "🌑 **Catalyst**\n"
                "☠️ **Caustic**\n"
                "🔧 **Rampart**\n"
                "⚡ **Wattson**"
            ),
            inline=False
        )

        embed.set_footer(
            text="Click a button again to remove the role."
        )

        await ctx.send(
            embed=embed,
            view=ControllerRoleView()
        )


    # =================================================
    # SUPPORT PANEL
    # =================================================

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def supportroles(self, ctx):

        embed = discord.Embed(
            title="❤️ Support Legends",
            description=(
                "Choose the Support Legends "
                "you play."
            ),
            color=EMBED_COLOR
        )

        embed.add_field(
            name="Available Legends",
            value=(
                "⚡ **Conduit**\n"
                "🛡️ **Gibraltar**\n"
                "❤️ **Lifeline**\n"
                "💎 **Loba**\n"
                "✨ **Mirage**\n"
                "🛡️ **Newcastle**"
            ),
            inline=False
        )

        embed.set_footer(
            text="Click a button again to remove the role."
        )

        await ctx.send(
            embed=embed,
            view=SupportRoleView()
        )


async def setup(bot):

    await bot.add_cog(
        Roles(bot)
    )