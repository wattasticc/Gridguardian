import discord
from discord.ext import commands
from datetime import timedelta


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # Temporary warning storage
        self.user_warnings = {}


    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason="No reason provided"):
        if member == ctx.author:
            return await ctx.send("❌ You can't kick yourself.")

        await member.kick(reason=reason)

        embed = discord.Embed(
            title="👢 Member Kicked",
            color=discord.Color.red()
        )

        embed.add_field(name="Member", value=member.mention, inline=False)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)

        await ctx.send(embed=embed)


    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason="No reason provided"):
        if member == ctx.author:
            return await ctx.send("❌ You can't ban yourself.")

        await member.ban(reason=reason)

        embed = discord.Embed(
            title="🔨 Member Banned",
            color=discord.Color.red()
        )

        embed.add_field(name="Member", value=member.mention, inline=False)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)

        await ctx.send(embed=embed)


    @commands.command()
    @commands.has_permissions(moderate_members=True)
    async def timeout(self, ctx, member: discord.Member, minutes: int, *, reason="No reason provided"):
        await member.timeout(
            timedelta(minutes=minutes),
            reason=reason
        )

        embed = discord.Embed(
            title="⏱️ Member Timed Out",
            color=discord.Color.orange()
        )

        embed.add_field(name="Member", value=member.mention)
        embed.add_field(name="Duration", value=f"{minutes} minute(s)")
        embed.add_field(name="Reason", value=reason)

        await ctx.send(embed=embed)


    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx, amount: int):
        await ctx.channel.purge(limit=amount + 1)

        msg = await ctx.send(f"🧹 Deleted {amount} messages.")
        await msg.delete(delay=3)


    @commands.command()
    @commands.has_permissions(moderate_members=True)
    async def warn(self, ctx, member: discord.Member, *, reason="No reason provided"):

        if member.id not in self.user_warnings:
            self.user_warnings[member.id] = []

        self.user_warnings[member.id].append(reason)

        embed = discord.Embed(
            title="⚠️ Member Warned",
            color=discord.Color.gold()
        )

        embed.add_field(name="Member", value=member.mention)
        embed.add_field(name="Warnings", value=len(self.user_warnings[member.id]))
        embed.add_field(name="Reason", value=reason, inline=False)

        await ctx.send(embed=embed)


    @commands.command()
    async def warnings(self, ctx, member: discord.Member):

        if member.id not in self.user_warnings:
            return await ctx.send("✅ This member has no warnings.")

        embed = discord.Embed(
            title=f"Warnings for {member}",
            color=discord.Color.gold()
        )

        for i, warning in enumerate(self.user_warnings[member.id], start=1):
            embed.add_field(
                name=f"Warning {i}",
                value=warning,
                inline=False
            )

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Moderation(bot))