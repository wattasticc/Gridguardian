import os
import asyncio
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


@bot.event
async def on_ready():
    print("=" * 40)
    print("⚡ Grid Guardian is Online!")
    print(f"Logged in as {bot.user}")
    print("=" * 40)

    await bot.change_presence(
        activity=discord.Game("⚡ Protecting Servers")
    )


@bot.event
async def on_command_error(ctx, error):
    print(f"\nERROR: {repr(error)}\n")

    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ That command doesn't exist.")

    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use that command.")

    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ You're missing a required argument.")

    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ I couldn't find that member.")

    else:
        raise error


async def load_cogs():
    print("Loading Utility...")
    await bot.load_extension("cogs.utility")
    print("✅ Utility Loaded")

    print("Loading Moderation...")
    await bot.load_extension("cogs.moderation")
    print("✅ Moderation Loaded")

    print("Loading Tickets...")
    await bot.load_extension("cogs.tickets")
    print("✅ Tickets Loaded")

    print("Loading Leveling...")
    await bot.load_extension("cogs.leveling")
    print("✅ Leveling Loaded")

    print("Loading Welcome...")
    await bot.load_extension("cogs.welcome")
    print("✅ Welcome Loaded")

    print("Loading Suggestions...")
    await bot.load_extension("cogs.suggestions")
    print("✅ Suggestions Loaded")

    print("Loading Logging...")
    await bot.load_extension("cogs.logging")
    print("✅ Logging Loaded")


async def main():
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)


asyncio.run(main())