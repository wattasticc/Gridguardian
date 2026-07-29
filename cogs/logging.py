import discord
from discord.ext import commands

EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)

LOG_CHANNEL_NAME = "logs"


class Logging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_log_channel(self, guild):
        return discord.utils.get(
            guild.text_channels,
            name=LOG_CHANNEL_NAME
        )

    @commands.Cog.listener()
    async def on_message_delete(self, message):

        if message.author.bot:
            return

        channel = self.get_log_channel(message.guild)

        if channel is None:
            return

        embed = discord.Embed(
            title="🗑️ Message Deleted",
            color=discord.Color.red()
        )

        embed.add_field(
            name="Author",
            value=message.author.mention,
            inline=False
        )

        embed.add_field(
            name="Channel",
            value=message.channel.mention,
            inline=False
        )

        embed.add_field(
            name="Content",
            value=message.content if message.content else "*No text*",
            inline=False
        )

        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):

        if before.author.bot:
            return

        if before.content == after.content:
            return

        channel = self.get_log_channel(before.guild)

        if channel is None:
            return

        embed = discord.Embed(
            title="✏️ Message Edited",
            color=discord.Color.orange()
        )

        embed.add_field(
            name="Author",
            value=before.author.mention,
            inline=False
        )

        embed.add_field(
            name="Before",
            value=before.content if before.content else "*No text*",
            inline=False
        )

        embed.add_field(
            name="After",
            value=after.content if after.content else "*No text*",
            inline=False
        )

        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member):

        channel = self.get_log_channel(member.guild)

        if channel is None:
            return

        embed = discord.Embed(
            title="✅ Member Joined",
            description=f"{member.mention} joined the server.",
            color=discord.Color.green()
        )

        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member):

        channel = self.get_log_channel(member.guild)

        if channel is None:
            return

        embed = discord.Embed(
            title="👋 Member Left",
            description=f"{member} left the server.",
            color=discord.Color.red()
        )

        await channel.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Logging(bot))