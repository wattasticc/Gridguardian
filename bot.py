import os
import asyncio
import traceback

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

@bot.event
async def on_ready():
    print("=" * 50)
    print("⚡ Grid Guardian is Online!")
    print(f"Logged in as: {bot.user}")
    print(f"Bot ID: {bot.user.id}")
    print(f"Process ID: {os.getpid()}")
    print("=" * 50)
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands.")
    except Exception as error:
        print(f"❌ Slash command sync error: {error}")
    await bot.change_presence(activity=discord.Game("⚡ Protecting Servers"))

@bot.event
async def on_command_error(ctx, error):
    if hasattr(ctx.command, "on_error"):
        return
    original = getattr(error, "original", error)
    print("=" * 50)
    print("❌ COMMAND ERROR")
    print(f"Command: {ctx.command}")
    print(f"User: {ctx.author}")
    print(f"Error: {repr(original)}")
    print("=" * 50)
    if isinstance(error, commands.CommandNotFound):
        return await ctx.send("❌ That command doesn't exist. Use `!help` to see the available commands.")
    if isinstance(error, commands.MissingPermissions):
        return await ctx.send("❌ You don't have permission to use that command.")
    if isinstance(error, commands.BotMissingPermissions):
        permissions = ", ".join(error.missing_permissions)
        return await ctx.send(f"❌ I don't have the required permissions to do that.\n\nMissing permissions: `{permissions}`")
    if isinstance(error, commands.MissingRequiredArgument):
        return await ctx.send("❌ You're missing a required argument.\n" f"Usage: `{ctx.prefix}{ctx.command}`")
    if isinstance(error, commands.MemberNotFound):
        return await ctx.send("❌ I couldn't find that member.")
    if isinstance(error, commands.UserNotFound):
        return await ctx.send("❌ I couldn't find that user.")
    if isinstance(error, commands.BadArgument):
        return await ctx.send("❌ One of the arguments you entered is invalid.")
    if isinstance(error, commands.CommandOnCooldown):
        return await ctx.send("⏳ Please wait " f"`{error.retry_after:.1f}` seconds before using that command again.")
    if isinstance(error, commands.DisabledCommand):
        return await ctx.send("❌ That command is currently disabled.")
    print("❌ UNHANDLED COMMAND ERROR:")
    traceback.print_exception(type(original), original, original.__traceback__)
    try:
        await ctx.send("❌ Something went wrong while running that command.\n\nThe error has been printed in the bot logs.")
    except discord.HTTPException:
        pass

async def load_cogs():
    await bot.load_extension("cogs.utility")
    await bot.load_extension("cogs.moderation")
    await bot.load_extension("cogs.automod")
    await bot.load_extension("cogs.tickets")
    await bot.load_extension("cogs.leveling")
    await bot.load_extension("cogs.welcome")
    await bot.load_extension("cogs.suggestions")
    await bot.load_extension("cogs.logging")
    await bot.load_extension("cogs.shop")
    await bot.load_extension("cogs.giveaways")
    await bot.load_extension("cogs.reactionroles")
    await bot.load_extension("cogs.apex")
    await bot.load_extension("cogs.apexnews")
    await bot.load_extension("cogs.apexmapnotify")
    await bot.load_extension("cogs.apexpatch")
    await bot.load_extension("cogs.wattsonmastery")
    await bot.load_extension("cogs.economy")
    await bot.load_extension("cogs.settings")
    await bot.load_extension("cogs.coach")
    await bot.load_extension("cogs.profile")
    await bot.load_extension("cogs.stats")
    await bot.load_extension("cogs.achievement_system")
    await bot.load_extension("cogs.progression_roles")
    await bot.load_extension("cogs.daily_quests")
    await bot.load_extension("cogs.roles")
    await bot.load_extension("cogs.backup")
    await bot.load_extension("cogs.afk")
    await bot.load_extension("cogs.quests")
    await bot.load_extension("cogs.notifications")
    await bot.load_extension("cogs.lfg")
    await bot.load_extension("cogs.clips")
    await bot.load_extension("cogs.weaponcompare")
    await bot.load_extension("cogs.matchups")
    await bot.load_extension("cogs.wattsonguides")
    await bot.load_extension("cogs.wattsontech")
    await bot.load_extension("cogs.tournaments")
    await bot.load_extension("cogs.youtube")
    await bot.load_extension("cogs.twitch")
    await bot.load_extension("cogs.help")
    await bot.load_extension("cogs.starboard")
    await bot.load_extension("cogs.reminders")
    await bot.load_extension("cogs.polls")
    await bot.load_extension("cogs.antiraid")
    await bot.load_extension("cogs.tempvoice")
    await bot.load_extension("cogs.daily")
    await bot.load_extension("cogs.weapons")
    await bot.load_extension("cogs.loadout")
    await bot.load_extension("cogs.setups")
    await bot.load_extension("cogs.leaderboards")
    await bot.load_extension("cogs.challenges")
    await bot.load_extension("cogs.legends")
    await bot.load_extension("cogs.tiktok")
    await bot.load_extension("cogs.instagram")
    await bot.load_extension("cogs.socialroles")
    await bot.load_extension("cogs.verification")
    print("=" * 50)
    print("✅ ALL COGS LOADED")
    print("⚡ Grid Guardian is fully loaded.")
    print("=" * 50)

async def main():
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN is missing from the environment.")
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
