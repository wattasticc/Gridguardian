import discord
from discord.ext import commands

EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)

WELCOME_CHANNEL_NAME = "welcome"
AUTO_ROLE_NAME = None  # Example: "Member"


class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):

        channel = discord.utils.get(
            member.guild.text_channels,
            name=WELCOME_CHANNEL_NAME
        )

        if channel is None:
            return

        embed = discord.Embed(
            title="👋 Welcome!",
            description=(
                f"Welcome to **{member.guild.name}**, {member.mention}!\n\n"
                "We're glad you're here. Have fun and be sure to read the rules!"
            ),
            color=EMBED_COLOR
        )

        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Member #{member.guild.member_count}")

        await channel.send(embed=embed)

        if AUTO_ROLE_NAME:
            role = discord.utils.get(member.guild.roles, name=AUTO_ROLE_NAME)

            if role:
                await member.add_roles(role)


async def setup(bot):
    await bot.add_cog(Welcome(bot))