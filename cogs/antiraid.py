import time
from collections import defaultdict, deque

import discord
from discord.ext import commands


EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)


# =========================================================
# ANTI-RAID COG
# =========================================================

class AntiRaid(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        # -------------------------------------------------
        # JOIN TRACKING
        # -------------------------------------------------

        self.join_times = defaultdict(deque)

        # Number of joins allowed during the time window
        self.join_limit = 8
        self.time_window = 15

        # Prevent repeated raid alerts
        self.raid_cooldowns = {}

        # Keep track of locked channels
        self.locked_channels = set()


    # =====================================================
    # CHECK RAID COOLDOWN
    # =====================================================

    def can_alert(self, guild_id):

        current_time = time.time()

        last_alert = self.raid_cooldowns.get(
            guild_id,
            0
        )

        # Don't spam alerts
        if current_time - last_alert < 60:
            return False

        self.raid_cooldowns[guild_id] = current_time

        return True


    # =====================================================
    # GET LOG CHANNEL
    # =====================================================

    async def get_log_channel(self, guild):

        import sqlite3

        try:

            db = sqlite3.connect("gridguardian.db")
            cursor = db.cursor()

            cursor.execute("""
            SELECT log_channel_id
            FROM settings
            WHERE guild_id=?
            """, (
                guild.id,
            ))

            result = cursor.fetchone()

            db.close()

            if result and result[0]:

                channel = guild.get_channel(
                    result[0]
                )

                if isinstance(
                    channel,
                    discord.TextChannel
                ):

                    return channel

        except Exception as error:

            print(
                f"AntiRaid database error: {error}"
            )

        return None


    # =====================================================
    # RAID DETECTION
    # =====================================================

    @commands.Cog.listener()
    async def on_member_join(self, member):

        guild = member.guild

        current_time = time.time()

        joins = self.join_times[
            guild.id
        ]


        # Remove old joins outside the window

        while (
            joins
            and current_time - joins[0]
            > self.time_window
        ):

            joins.popleft()


        joins.append(
            current_time
        )


        # -------------------------------------------------
        # CHECK FOR RAID
        # -------------------------------------------------

        if len(joins) < self.join_limit:

            return


        if not self.can_alert(
            guild.id
        ):

            return


        embed = discord.Embed(
            title="🚨 POSSIBLE RAID DETECTED",
            description=(
                f"**{len(joins)} members joined "
                f"within {self.time_window} seconds.**\n\n"
                "Grid Guardian recommends locking "
                "the server until staff checks the situation."
            ),
            color=discord.Color.red()
        )

        embed.add_field(
            name="🛡️ Recommended Action",
            value=(
                "Use `!lockdown` to prevent members "
                "from sending messages in channels."
            ),
            inline=False
        )


        log_channel = await self.get_log_channel(
            guild
        )


        # Send to log channel

        if log_channel:

            try:

                await log_channel.send(
                    embed=embed
                )

            except (
                discord.Forbidden,
                discord.HTTPException
            ):

                pass


        # Also send to server owner if possible

        try:

            owner = guild.owner

            if owner:

                await owner.send(
                    embed=embed
                )

        except (
            discord.Forbidden,
            discord.HTTPException
        ):

            pass


        print(
            f"🚨 Possible raid detected "
            f"in {guild.name}"
        )


    # =====================================================
    # LOCKDOWN
    # =====================================================

    @commands.command()
    @commands.has_permissions(
        manage_guild=True
    )
    async def lockdown(
        self,
        ctx
    ):

        guild = ctx.guild

        await ctx.send(
            "🔒 Locking server channels..."
        )


        locked_count = 0


        for channel in guild.channels:

            if not isinstance(
                channel,
                (
                    discord.TextChannel,
                    discord.VoiceChannel
                )
            ):

                continue


            # Skip channels where the bot cannot edit
            if not channel.permissions_for(
                guild.me
            ).manage_channels:

                continue


            try:

                overwrite = channel.overwrites_for(
                    guild.default_role
                )


                # Save channel so we know it was locked

                self.locked_channels.add(
                    channel.id
                )


                # Lock text channels

                if isinstance(
                    channel,
                    discord.TextChannel
                ):

                    overwrite.send_messages = False


                # Lock voice channels

                if isinstance(
                    channel,
                    discord.VoiceChannel
                ):

                    overwrite.connect = False


                await channel.set_permissions(
                    guild.default_role,
                    overwrite=overwrite,
                    reason=(
                        f"Server lockdown activated by "
                        f"{ctx.author}"
                    )
                )


                locked_count += 1


            except (
                discord.Forbidden,
                discord.HTTPException
            ):

                pass


        embed = discord.Embed(
            title="🔒 SERVER LOCKDOWN ACTIVATED",
            description=(
                f"Locked **{locked_count} channels**.\n\n"
                "Members can no longer send messages "
                "or join locked voice channels."
            ),
            color=discord.Color.red()
        )

        embed.set_footer(
            text=f"Activated by {ctx.author}"
        )


        await ctx.send(
            embed=embed
        )


    # =====================================================
    # UNLOCKDOWN
    # =====================================================

    @commands.command()
    @commands.has_permissions(
        manage_guild=True
    )
    async def unlockdown(
        self,
        ctx
    ):

        guild = ctx.guild

        await ctx.send(
            "🔓 Unlocking server channels..."
        )


        unlocked_count = 0


        for channel in guild.channels:

            if not isinstance(
                channel,
                (
                    discord.TextChannel,
                    discord.VoiceChannel
                )
            ):

                continue


            # Only unlock channels locked by this session

            if channel.id not in self.locked_channels:

                continue


            try:

                overwrite = channel.overwrites_for(
                    guild.default_role
                )


                if isinstance(
                    channel,
                    discord.TextChannel
                ):

                    overwrite.send_messages = None


                if isinstance(
                    channel,
                    discord.VoiceChannel
                ):

                    overwrite.connect = None


                await channel.set_permissions(
                    guild.default_role,
                    overwrite=overwrite,
                    reason=(
                        f"Server lockdown removed by "
                        f"{ctx.author}"
                    )
                )


                unlocked_count += 1


            except (
                discord.Forbidden,
                discord.HTTPException
            ):

                pass


        self.locked_channels.clear()


        embed = discord.Embed(
            title="🔓 SERVER LOCKDOWN REMOVED",
            description=(
                f"Unlocked **{unlocked_count} channels**."
            ),
            color=discord.Color.green()
        )

        embed.set_footer(
            text=f"Removed by {ctx.author}"
        )


        await ctx.send(
            embed=embed
        )


    # =====================================================
    # CHANNEL LOCK
    # =====================================================

    @commands.command()
    @commands.has_permissions(
        manage_channels=True
    )
    async def lock(
        self,
        ctx
    ):

        overwrite = ctx.channel.overwrites_for(
            ctx.guild.default_role
        )

        overwrite.send_messages = False


        try:

            await ctx.channel.set_permissions(
                ctx.guild.default_role,
                overwrite=overwrite,
                reason=(
                    f"Channel locked by {ctx.author}"
                )
            )

        except discord.Forbidden:

            return await ctx.send(
                "❌ I don't have permission to lock this channel."
            )


        embed = discord.Embed(
            title="🔒 Channel Locked",
            description=(
                "This channel has been locked."
            ),
            color=discord.Color.red()
        )


        await ctx.send(
            embed=embed
        )


    # =====================================================
    # CHANNEL UNLOCK
    # =====================================================

    @commands.command()
    @commands.has_permissions(
        manage_channels=True
    )
    async def unlock(
        self,
        ctx
    ):

        overwrite = ctx.channel.overwrites_for(
            ctx.guild.default_role
        )

        overwrite.send_messages = None


        try:

            await ctx.channel.set_permissions(
                ctx.guild.default_role,
                overwrite=overwrite,
                reason=(
                    f"Channel unlocked by {ctx.author}"
                )
            )

        except discord.Forbidden:

            return await ctx.send(
                "❌ I don't have permission to unlock this channel."
            )


        embed = discord.Embed(
            title="🔓 Channel Unlocked",
            description=(
                "This channel has been unlocked."
            ),
            color=discord.Color.green()
        )


        await ctx.send(
            embed=embed
        )


    # =====================================================
    # ERROR HANDLER
    # =====================================================

    @lockdown.error
    @unlockdown.error
    @lock.error
    @unlock.error
    async def antiraid_error(
        self,
        ctx,
        error
    ):

        if isinstance(
            error,
            commands.MissingPermissions
        ):

            return await ctx.send(
                "❌ You don't have permission to use that command."
            )


        raise error


# =========================================================
# SETUP
# =========================================================

async def setup(bot):

    await bot.add_cog(
        AntiRaid(bot)
    )