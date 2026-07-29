import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None
)

EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)

log_channels = {}

user_warnings = {}

@bot.event
async def on_ready():
    print("=" * 40)
    print("⚡ Grid Guardian is Online!")
    print(f"Logged in as {bot.user}")
    print("=" * 40)

    await bot.change_presence(
        activity=discord.Game("⚡ Protecting Servers")
    )


@bot.command()
async def ping(ctx):
    await ctx.send(f"🏓 Pong! `{round(bot.latency * 1000)}ms`")


@bot.command()
async def hello(ctx):
    await ctx.send(f"👋 Hello {ctx.author.mention}!")

@bot.command()
async def help(ctx):
    embed = discord.Embed(
        title="⚡ Grid Guardian Commands",
        color=EMBED_COLOR
    )

    embed.add_field(
        name="🛠 General",
        value=(
            "`!ping` - Check bot latency.\n"
            "`!hello` - Say hello.\n"
            "`!help` - Show this menu."
        ),
        inline=False
    )

    embed.set_footer(text="More commands coming soon...")

    await ctx.send(embed=embed)

@bot.command()
async def avatar(ctx, member: discord.Member = None):
    if member is None:
        member = ctx.author

    embed = discord.Embed(
        title=f"{member.display_name}'s Avatar",
        color=EMBED_COLOR
    )
    embed.set_image(url=member.display_avatar.url)
    await ctx.send(embed=embed)


@bot.command()
async def userinfo(ctx, member: discord.Member = None):
    if member is None:
        member = ctx.author

    embed = discord.Embed(
        title=f"User Info - {member}",
        color=EMBED_COLOR
    )

    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="Display Name", value=member.display_name, inline=True)
    embed.add_field(name="Joined Server", value=member.joined_at.strftime("%b %d, %Y"), inline=True)
    embed.add_field(name="Account Created", value=member.created_at.strftime("%b %d, %Y"), inline=True)

    await ctx.send(embed=embed)


@bot.command()
async def serverinfo(ctx):
    guild = ctx.guild

    embed = discord.Embed(
        title=f"{guild.name}",
        color=EMBED_COLOR
    )

    embed.add_field(name="Members", value=guild.member_count)
    embed.add_field(name="Owner", value=guild.owner)
    embed.add_field(name="Created", value=guild.created_at.strftime("%b %d, %Y"))

    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    await ctx.send(embed=embed)


@bot.command()
async def say(ctx, *, message):
    await ctx.send(message)

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason provided"):
    if member == ctx.author:
        await ctx.send("❌ You can't kick yourself.")
        return

    try:
        await member.kick(reason=reason)

        embed = discord.Embed(
            title="👢 Member Kicked",
            color=discord.Color.red()
        )

        embed.add_field(name="Member", value=member.mention, inline=False)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)

        await ctx.send(embed=embed)

    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to kick that member.")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use that command.")

    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ You're missing a required argument.")

    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ I couldn't find that member.")

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="No reason provided"):
    if member == ctx.author:
        await ctx.send("❌ You can't ban yourself.")
        return

    try:
        await member.ban(reason=reason)

        embed = discord.Embed(
            title="🔨 Member Banned",
            color=discord.Color.red()
        )

        embed.add_field(name="Member", value=member.mention, inline=False)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)

        await ctx.send(embed=embed)

    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to ban that member.")

from datetime import timedelta

@bot.command()
@commands.has_permissions(moderate_members=True)
async def timeout(ctx, member: discord.Member, minutes: int, *, reason="No reason provided"):
    if member == ctx.author:
        await ctx.send("❌ You can't timeout yourself.")
        return

    try:
        await member.timeout(
            timedelta(minutes=minutes),
            reason=reason
        )

        embed = discord.Embed(
            title="⏱️ Member Timed Out",
            color=EMBED_COLOR
        )

        embed.add_field(name="Member", value=member.mention, inline=False)
        embed.add_field(name="Duration", value=f"{minutes} minute(s)", inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)

        await ctx.send(embed=embed)

    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to timeout that member.")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int):
    if amount <= 0:
        await ctx.send("❌ Please enter a number greater than 0.")
        return

    await ctx.channel.purge(limit=amount + 1)

    confirmation = await ctx.send(f"🧹 Deleted {amount} message(s).")
    await confirmation.delete(delay=3)

@bot.command()
@commands.has_permissions(moderate_members=True)
async def warn(ctx, member: discord.Member, *, reason="No reason provided"):
    if member.bot:
        await ctx.send("❌ You can't warn bots.")
        return

    if member == ctx.author:
        await ctx.send("❌ You can't warn yourself.")
        return

    if member.id not in user_warnings:
        user_warnings[member.id] = []

    user_warnings[member.id].append(reason)

    embed = discord.Embed(
        title="⚠️ Member Warned",
        color=discord.Color.orange()
    )

    embed.add_field(name="Member", value=member.mention, inline=False)
    embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="Total Warnings", value=len(user_warnings[member.id]), inline=False)

    await ctx.send(embed=embed)

@bot.command()
async def warnings(ctx, member: discord.Member):
    if member.id not in user_warnings or len(user_warnings[member.id]) == 0:
        await ctx.send(f"✅ {member.mention} has no warnings.")
        return

    embed = discord.Embed(
        title=f"⚠️ Warnings for {member}",
        color=discord.Color.orange()
    )

    for i, reason in enumerate(user_warnings[member.id], start=1):
        embed.add_field(
            name=f"Warning {i}",
            value=reason,
            inline=False
        )

    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def setlog(ctx, channel: discord.TextChannel):
    log_channels[ctx.guild.id] = channel.id

    embed = discord.Embed(
        title="📜 Log Channel Set",
        description=f"Logging channel set to {channel.mention}.",
        color=discord.Color.green()
    )

    await ctx.send(embed=embed)

@bot.event
async def on_message_delete(message):
    if message.author.bot:
        return

    guild = message.guild
    if guild is None:
        return

    if guild.id not in log_channels:
        return

    channel = bot.get_channel(log_channels[guild.id])
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
        value=message.content if message.content else "*No text content*",
        inline=False
    )

    await channel.send(embed=embed)

@bot.event
async def on_message_edit(before, after):
    if before.author.bot:
        return

    if before.content == after.content:
        return

    guild = before.guild
    if guild is None:
        return

    if guild.id not in log_channels:
        return

    channel = bot.get_channel(log_channels[guild.id])
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
        name="Channel",
        value=before.channel.mention,
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

@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, *, user):
    banned_users = [entry async for entry in ctx.guild.bans()]

    for ban_entry in banned_users:
        if str(ban_entry.user) == user:
            await ctx.guild.unban(ban_entry.user)

            embed = discord.Embed(
                title="🔓 Member Unbanned",
                color=discord.Color.green()
            )

            embed.add_field(
                name="Member",
                value=str(ban_entry.user),
                inline=False
            )

            embed.add_field(
                name="Moderator",
                value=ctx.author.mention,
                inline=False
            )

            await ctx.send(embed=embed)
            return

    await ctx.send("❌ That user isn't banned.")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def lock(ctx):
    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = False

    await ctx.channel.set_permissions(
        ctx.guild.default_role,
        overwrite=overwrite
    )

    embed = discord.Embed(
        title="🔒 Channel Locked",
        description=f"{ctx.channel.mention} has been locked.",
        color=discord.Color.red()
    )

    embed.set_footer(text=f"Locked by {ctx.author}")

    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(manage_channels=True)
async def unlock(ctx):
    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = None

    await ctx.channel.set_permissions(
        ctx.guild.default_role,
        overwrite=overwrite
    )

    embed = discord.Embed(
        title="🔓 Channel Unlocked",
        description=f"{ctx.channel.mention} has been unlocked.",
        color=discord.Color.green()
    )

    embed.set_footer(text=f"Unlocked by {ctx.author}")

    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(manage_channels=True)
async def slowmode(ctx, seconds: int):
    if seconds < 0:
        await ctx.send("❌ Slowmode can't be negative.")
        return

    if seconds > 21600:
        await ctx.send("❌ Maximum slowmode is 21600 seconds (6 hours).")
        return

    await ctx.channel.edit(slowmode_delay=seconds)

    if seconds == 0:
        embed = discord.Embed(
            title="🐌 Slowmode Disabled",
            description=f"Slowmode has been turned off in {ctx.channel.mention}.",
            color=discord.Color.green()
        )
    else:
        embed = discord.Embed(
            title="🐌 Slowmode Enabled",
            description=f"Slowmode is now **{seconds} second(s)** in {ctx.channel.mention}.",
            color=discord.Color.orange()
        )

    embed.set_footer(text=f"Changed by {ctx.author}")
    await ctx.send(embed=embed)
    
bot.run(TOKEN)