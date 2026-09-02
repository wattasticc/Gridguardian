import os
import asyncio
import traceback

import discord
from discord.ext import commands
from dotenv import load_dotenv


# ==========================================================
# ENVIRONMENT
# ==========================================================

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")


# ==========================================================
# INTENTS
# ==========================================================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True


# ==========================================================
# BOT
# ==========================================================

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None
)


# ==========================================================
# BOT READY
# ==========================================================

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

        print(
            f"✅ Synced {len(synced)} slash commands."
        )

    except Exception as error:

        print(
            f"❌ Slash command sync error: {error}"
        )

    await bot.change_presence(
        activity=discord.Game(
            "⚡ Protecting Servers"
        )
    )


# ==========================================================
# COMMAND ERRORS
# ==========================================================

@bot.event
async def on_command_error(ctx, error):

    # Ignore commands handled by a cog's local error handler.
    if hasattr(ctx.command, "on_error"):
        return

    original = getattr(
        error,
        "original",
        error
    )

    print("=" * 50)
    print("❌ COMMAND ERROR")
    print(
        f"Command: {ctx.command}"
    )
    print(
        f"User: {ctx.author}"
    )
    print(
        f"Error: {repr(original)}"
    )
    print("=" * 50)

    # ======================================================
    # COMMAND NOT FOUND
    # ======================================================

    if isinstance(
        error,
        commands.CommandNotFound
    ):

        return await ctx.send(
            "❌ That command doesn't exist. "
            "Use `!help` to see the available commands."
        )

    # ======================================================
    # MISSING PERMISSIONS
    # ======================================================

    if isinstance(
        error,
        commands.MissingPermissions
    ):

        return await ctx.send(
            "❌ You don't have permission "
            "to use that command."
        )

    # ======================================================
    # BOT MISSING PERMISSIONS
    # ======================================================

    if isinstance(
        error,
        commands.BotMissingPermissions
    ):

        permissions = ", ".join(
            error.missing_permissions
        )

        return await ctx.send(
            "❌ I don't have the required "
            "permissions to do that.\n\n"
            f"Missing permissions: `{permissions}`"
        )

    # ======================================================
    # MISSING ARGUMENT
    # ======================================================

    if isinstance(
        error,
        commands.MissingRequiredArgument
    ):

        return await ctx.send(
            "❌ You're missing a required argument.\n"
            f"Usage: `{ctx.prefix}{ctx.command}`"
        )

    # ======================================================
    # MEMBER NOT FOUND
    # ======================================================

    if isinstance(
        error,
        commands.MemberNotFound
    ):

        return await ctx.send(
            "❌ I couldn't find that member."
        )

    # ======================================================
    # USER NOT FOUND
    # ======================================================

    if isinstance(
        error,
        commands.UserNotFound
    ):

        return await ctx.send(
            "❌ I couldn't find that user."
        )

    # ======================================================
    # BAD ARGUMENT
    # ======================================================

    if isinstance(
        error,
        commands.BadArgument
    ):

        return await ctx.send(
            "❌ One of the arguments you "
            "entered is invalid."
        )

    # ======================================================
    # COMMAND ON COOLDOWN
    # ======================================================

    if isinstance(
        error,
        commands.CommandOnCooldown
    ):

        return await ctx.send(
            "⏳ Please wait "
            f"`{error.retry_after:.1f}` seconds "
            "before using that command again."
        )

    # ======================================================
    # COMMAND DISABLED
    # ======================================================

    if isinstance(
        error,
        commands.DisabledCommand
    ):

        return await ctx.send(
            "❌ That command is currently disabled."
        )

    # ======================================================
    # UNKNOWN ERROR
    # ======================================================

    print(
        "❌ UNHANDLED COMMAND ERROR:"
    )

    traceback.print_exception(
        type(original),
        original,
        original.__traceback__
    )

    try:

        await ctx.send(
            "❌ Something went wrong while "
            "running that command.\n\n"
            "The error has been printed in "
            "the bot logs."
        )

    except discord.HTTPException:
        pass


# ==========================================================
# LOAD COGS
# ==========================================================

async def load_cogs():

    # ======================================================
    # GROUP 1
    # ======================================================

    print("Loading Utility...")
    await bot.load_extension("cogs.utility")
    print("✅ Utility Loaded")

    print("Loading Moderation...")
    await bot.load_extension("cogs.moderation")
    print("✅ Moderation Loaded")

    print("Loading AutoMod...")
    await bot.load_extension("cogs.automod")
    print("✅ AutoMod Loaded")

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

    # ======================================================
    # SHOP
    # ======================================================

    print("Loading Shop...")
    await bot.load_extension("cogs.shop")
    print("✅ Shop Loaded")

    # ======================================================
    # GROUP 2
    # ======================================================

    print("Loading Giveaways...")
    await bot.load_extension("cogs.giveaways")
    print("✅ Giveaways Loaded")

    print("Loading Reaction Roles...")
    await bot.load_extension("cogs.reactionroles")
    print("✅ Reaction Roles Loaded")

    print("Loading Apex...")
    await bot.load_extension("cogs.apex")
    print("✅ Apex Loaded")

    print("Loading Economy...")
    await bot.load_extension("cogs.economy")
    print("✅ Economy Loaded")

    print("Loading Settings...")
    await bot.load_extension("cogs.settings")
    print("✅ Settings Loaded")

    # ======================================================
    # GROUP 3
    # ======================================================

    print("Loading Coach...")
    await bot.load_extension("cogs.coach")
    print("✅ Coach Loaded")

    print("Loading Profile...")
    await bot.load_extension("cogs.profile")
    print("✅ Profile Loaded")

    print("Loading Stats...")
    await bot.load_extension("cogs.stats")
    print("✅ Stats Loaded")

    print("Loading Roles...")
    await bot.load_extension("cogs.roles")
    print("✅ Roles Loaded")

    print("Loading Backup...")
    await bot.load_extension("cogs.backup")
    print("✅ Backup Loaded")

    print("Loading AFK...")
    await bot.load_extension("cogs.afk")
    print("✅ AFK Loaded")

    print("Loading Achievements...")
    await bot.load_extension("cogs.achievements")
    print("✅ Achievements Loaded")

    print("Loading Quests...")
    await bot.load_extension("cogs.quests")
    print("✅ Quests Loaded")

    print("Loading Notifications...")
    await bot.load_extension("cogs.notifications")
    print("✅ Notifications Loaded")

    print("Loading YouTube...")
    await bot.load_extension("cogs.youtube")
    print("✅ YouTube Loaded")

    print("Loading Twitch...")
    await bot.load_extension("cogs.twitch")
    print("✅ Twitch Loaded")

    print("Loading Help...")
    await bot.load_extension("cogs.help")
    print("✅ Help Loaded")

    print("Loading Starboard...")
    await bot.load_extension("cogs.starboard")
    print("✅ Starboard Loaded")

    print("Loading Reminders...")
    await bot.load_extension("cogs.reminders")
    print("✅ Reminders Loaded")

    print("Loading Polls...")
    await bot.load_extension("cogs.polls")
    print("✅ Polls Loaded")

    print("Loading Anti-Raid...")
    await bot.load_extension("cogs.antiraid")
    print("✅ Anti-Raid Loaded")

    print("Loading Temporary Voice...")
    await bot.load_extension("cogs.tempvoice")
    print("✅ Temporary Voice Loaded")

    print("Loading Level Rewards...")
    await bot.load_extension("cogs.levelrewards")
    print("✅ Level Rewards Loaded")

    print("Loading Daily Rewards...")
    await bot.load_extension("cogs.daily")
    print("✅ Daily Rewards Loaded")

    print("Loading Weapons...")
    await bot.load_extension("cogs.weapons")
    print("✅ Weapons Loaded")

    print("Loading Legends...")
    await bot.load_extension("cogs.legends")
    print("✅ Legends Loaded")

    print("Loading TikTok...")
    await bot.load_extension("cogs.tiktok")
    print("🎵 TikTok Loaded")

    print("Loading Instagram...")
    await bot.load_extension("cogs.instagram")
    print("📸 Instagram Loaded")

    # ======================================================
    # SOCIAL ROLES
    # ======================================================

    print("Loading Social Roles...")
    await bot.load_extension("cogs.socialroles")
    print("✅ Social Roles Loaded")

    # ======================================================
    # VERIFICATION
    # ======================================================

    print("Loading Verification...")
    await bot.load_extension("cogs.verification")
    print("✅ Verification Loaded")

    # ======================================================
    # COMPLETE
    # ======================================================

    print("=" * 50)
    print("✅ ALL COGS LOADED")
    print("⚡ Grid Guardian is fully loaded.")
    print("=" * 50)


# ==========================================================
# START BOT
# ==========================================================

async def main():

    async with bot:

        print("=" * 50)
        print("🚀 Starting Grid Guardian...")
        print(f"Process ID: {os.getpid()}")
        print("=" * 50)

        await load_cogs()

        print("=" * 50)
        print("🚀 Connecting to Discord...")
        print("=" * 50)

        await bot.start(TOKEN)


# ==========================================================
# RUN
# ==========================================================

if __name__ == "__main__":

    asyncio.run(main())