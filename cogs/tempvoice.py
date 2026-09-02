import sqlite3

import discord
from discord.ext import commands


EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)


# =========================================================
# DATABASE
# =========================================================

db = sqlite3.connect("gridguardian.db")
cursor = db.cursor()


cursor.execute("""
CREATE TABLE IF NOT EXISTS tempvoice_settings (
    guild_id INTEGER PRIMARY KEY,
    creator_channel_id INTEGER
)
""")


cursor.execute("""
CREATE TABLE IF NOT EXISTS tempvoice_channels (
    channel_id INTEGER PRIMARY KEY,
    guild_id INTEGER NOT NULL,
    owner_id INTEGER NOT NULL
)
""")


db.commit()


# =========================================================
# DATABASE HELPERS
# =========================================================

def get_settings(guild_id):

    cursor.execute("""
    SELECT creator_channel_id
    FROM tempvoice_settings
    WHERE guild_id=?
    """, (
        guild_id,
    ))

    return cursor.fetchone()


def get_temp_channel(channel_id):

    cursor.execute("""
    SELECT guild_id, owner_id
    FROM tempvoice_channels
    WHERE channel_id=?
    """, (
        channel_id,
    ))

    return cursor.fetchone()


def get_owned_channel(guild_id, owner_id):

    cursor.execute("""
    SELECT channel_id
    FROM tempvoice_channels
    WHERE guild_id=?
    AND owner_id=?
    """, (
        guild_id,
        owner_id,
    ))

    return cursor.fetchone()


# =========================================================
# TEMP VOICE VIEW
# =========================================================

class TempVoiceView(discord.ui.View):

    def __init__(self, cog):

        super().__init__(timeout=None)

        self.cog = cog


    # =====================================================
    # CHECK OWNER
    # =====================================================

    async def check_owner(self, interaction):

        channel = interaction.user.voice.channel if interaction.user.voice else None

        if channel is None:

            await interaction.response.send_message(
                "❌ You must be in a temporary voice channel.",
                ephemeral=True
            )

            return None


        data = get_temp_channel(
            channel.id
        )


        if data is None:

            await interaction.response.send_message(
                "❌ This is not a Grid Guardian temporary voice channel.",
                ephemeral=True
            )

            return None


        guild_id, owner_id = data


        if interaction.user.id != owner_id:

            await interaction.response.send_message(
                "❌ Only the owner of this voice channel can do that.",
                ephemeral=True
            )

            return None


        return channel


    # =====================================================
    # RENAME
    # =====================================================

    @discord.ui.button(
        label="Rename",
        emoji="✏️",
        style=discord.ButtonStyle.primary,
        custom_id="tempvoice_rename"
    )
    async def rename(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        channel = await self.check_owner(
            interaction
        )

        if channel is None:
            return


        modal = RenameVoiceModal(
            channel
        )

        await interaction.response.send_modal(
            modal
        )


    # =====================================================
    # USER LIMIT
    # =====================================================

    @discord.ui.button(
        label="User Limit",
        emoji="👥",
        style=discord.ButtonStyle.primary,
        custom_id="tempvoice_limit"
    )
    async def user_limit(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        channel = await self.check_owner(
            interaction
        )

        if channel is None:
            return


        modal = UserLimitModal(
            channel
        )

        await interaction.response.send_modal(
            modal
        )


    # =====================================================
    # LOCK
    # =====================================================

    @discord.ui.button(
        label="Lock / Unlock",
        emoji="🔒",
        style=discord.ButtonStyle.secondary,
        custom_id="tempvoice_lock"
    )
    async def lock(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        channel = await self.check_owner(
            interaction
        )

        if channel is None:
            return


        overwrite = channel.overwrites_for(
            interaction.guild.default_role
        )


        # If everyone can connect, lock it.
        # If everyone cannot connect, unlock it.

        if overwrite.connect is False:

            overwrite.connect = None

            await channel.set_permissions(
                interaction.guild.default_role,
                overwrite=overwrite
            )

            return await interaction.response.send_message(
                "🔓 Voice channel unlocked.",
                ephemeral=True
            )


        overwrite.connect = False


        await channel.set_permissions(
            interaction.guild.default_role,
            overwrite=overwrite
        )


        await interaction.response.send_message(
            "🔒 Voice channel locked.",
            ephemeral=True
        )


    # =====================================================
    # HIDE
    # =====================================================

    @discord.ui.button(
        label="Hide / Show",
        emoji="👁️",
        style=discord.ButtonStyle.secondary,
        custom_id="tempvoice_hide"
    )
    async def hide(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        channel = await self.check_owner(
            interaction
        )

        if channel is None:
            return


        overwrite = channel.overwrites_for(
            interaction.guild.default_role
        )


        if overwrite.view_channel is False:

            overwrite.view_channel = None

            await channel.set_permissions(
                interaction.guild.default_role,
                overwrite=overwrite
            )

            return await interaction.response.send_message(
                "👁️ Voice channel is now visible.",
                ephemeral=True
            )


        overwrite.view_channel = False


        await channel.set_permissions(
            interaction.guild.default_role,
            overwrite=overwrite
        )


        await interaction.response.send_message(
            "🙈 Voice channel is now hidden.",
            ephemeral=True
        )


    # =====================================================
    # TRANSFER OWNER
    # =====================================================

    @discord.ui.button(
        label="Transfer Owner",
        emoji="👑",
        style=discord.ButtonStyle.success,
        custom_id="tempvoice_transfer"
    )
    async def transfer(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        channel = await self.check_owner(
            interaction
        )

        if channel is None:
            return


        modal = TransferOwnerModal(
            channel
        )

        await interaction.response.send_modal(
            modal
        )


# =========================================================
# RENAME MODAL
# =========================================================

class RenameVoiceModal(discord.ui.Modal):

    def __init__(self, channel):

        super().__init__(
            title="Rename Voice Channel"
        )

        self.channel = channel


        self.name_input = discord.ui.TextInput(
            label="New Channel Name",
            placeholder="Enter a new name",
            max_length=100
        )


        self.add_item(
            self.name_input
        )


    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        new_name = self.name_input.value.strip()


        if not new_name:

            return await interaction.response.send_message(
                "❌ Please enter a valid name.",
                ephemeral=True
            )


        try:

            await self.channel.edit(
                name=new_name
            )

        except discord.Forbidden:

            return await interaction.response.send_message(
                "❌ I don't have permission to rename this channel.",
                ephemeral=True
            )


        await interaction.response.send_message(
            f"✏️ Voice channel renamed to **{new_name}**.",
            ephemeral=True
        )


# =========================================================
# USER LIMIT MODAL
# =========================================================

class UserLimitModal(discord.ui.Modal):

    def __init__(self, channel):

        super().__init__(
            title="Set User Limit"
        )

        self.channel = channel


        self.limit_input = discord.ui.TextInput(
            label="User Limit",
            placeholder="0 for unlimited",
            max_length=2
        )


        self.add_item(
            self.limit_input
        )


    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        try:

            limit = int(
                self.limit_input.value
            )

        except ValueError:

            return await interaction.response.send_message(
                "❌ Please enter a number.",
                ephemeral=True
            )


        if limit < 0 or limit > 99:

            return await interaction.response.send_message(
                "❌ The user limit must be between 0 and 99.",
                ephemeral=True
            )


        try:

            await self.channel.edit(
                user_limit=limit
            )

        except discord.Forbidden:

            return await interaction.response.send_message(
                "❌ I don't have permission to edit this channel.",
                ephemeral=True
            )


        if limit == 0:

            text = "unlimited"

        else:

            text = str(limit)


        await interaction.response.send_message(
            f"👥 User limit set to **{text}**.",
            ephemeral=True
        )


# =========================================================
# TRANSFER OWNER MODAL
# =========================================================

class TransferOwnerModal(discord.ui.Modal):

    def __init__(self, channel):

        super().__init__(
            title="Transfer Voice Channel"
        )

        self.channel = channel


        self.user_input = discord.ui.TextInput(
            label="New Owner User ID",
            placeholder="Paste their Discord User ID",
            max_length=30
        )


        self.add_item(
            self.user_input
        )


    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        try:

            user_id = int(
                self.user_input.value
            )

        except ValueError:

            return await interaction.response.send_message(
                "❌ Please enter a valid Discord User ID.",
                ephemeral=True
            )


        member = interaction.guild.get_member(
            user_id
        )


        if member is None:

            return await interaction.response.send_message(
                "❌ I couldn't find that member.",
                ephemeral=True
            )


        if member.bot:

            return await interaction.response.send_message(
                "❌ You cannot transfer ownership to a bot.",
                ephemeral=True
            )


        # Update database

        cursor.execute("""
        UPDATE tempvoice_channels
        SET owner_id=?
        WHERE channel_id=?
        """, (
            member.id,
            self.channel.id
        ))

        db.commit()


        # Give new owner access

        await self.channel.set_permissions(
            member,
            connect=True,
            speak=True,
            manage_channels=True
        )


        await interaction.response.send_message(
            f"👑 Voice channel ownership transferred to {member.mention}.",
            ephemeral=True
        )


# =========================================================
# TEMP VOICE COG
# =========================================================

class TempVoice(commands.Cog):

    def __init__(self, bot):

        self.bot = bot


    # =====================================================
    # SET CREATOR CHANNEL
    # =====================================================

    @commands.command()
    @commands.has_permissions(
        manage_guild=True
    )
    async def setvoicecreator(
        self,
        ctx,
        channel: discord.VoiceChannel
    ):

        cursor.execute("""
        INSERT INTO tempvoice_settings(
            guild_id,
            creator_channel_id
        )
        VALUES (?, ?)

        ON CONFLICT(guild_id)
        DO UPDATE SET
        creator_channel_id=excluded.creator_channel_id
        """, (
            ctx.guild.id,
            channel.id
        ))

        db.commit()


        embed = discord.Embed(
            title="🔊 Temporary Voice Channels Configured",
            description=(
                f"Members who join {channel.mention} "
                "will automatically receive their own "
                "temporary voice channel."
            ),
            color=EMBED_COLOR
        )


        await ctx.send(
            embed=embed
        )


    # =====================================================
    # MEMBER JOIN VOICE
    # =====================================================

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member,
        before,
        after
    ):

        if member.bot:
            return


        guild = member.guild


        settings = get_settings(
            guild.id
        )


        if settings is None:
            return


        creator_channel_id = settings[0]


        # =================================================
        # CREATE TEMP CHANNEL
        # =================================================

        if (
            after.channel
            and after.channel.id
            == creator_channel_id
        ):

            # Check if member already owns a channel

            existing = get_owned_channel(
                guild.id,
                member.id
            )


            if existing:

                existing_channel = guild.get_channel(
                    existing[0]
                )


                if existing_channel:

                    await member.move_to(
                        existing_channel
                    )

                    return


                # Remove broken database entry

                cursor.execute("""
                DELETE FROM tempvoice_channels
                WHERE channel_id=?
                """, (
                    existing[0],
                ))

                db.commit()


            creator_channel = after.channel


            category = creator_channel.category


            try:

                temp_channel = await guild.create_voice_channel(
                    name=f"{member.display_name}'s Channel",
                    category=category,
                    reason=(
                        f"Temporary voice channel created "
                        f"for {member}"
                    )
                )

            except (
                discord.Forbidden,
                discord.HTTPException
            ):

                return


            # Give owner permissions

            await temp_channel.set_permissions(
                member,
                connect=True,
                speak=True,
                manage_channels=True,
                move_members=True
            )


            # Save to database

            cursor.execute("""
            INSERT OR REPLACE INTO tempvoice_channels(
                channel_id,
                guild_id,
                owner_id
            )
            VALUES (?, ?, ?)
            """, (
                temp_channel.id,
                guild.id,
                member.id
            ))

            db.commit()


            # Move member

            try:

                await member.move_to(
                    temp_channel
                )

            except (
                discord.Forbidden,
                discord.HTTPException
            ):

                pass


            # Send management panel

            embed = discord.Embed(
                title="🔊 Voice Channel Controls",
                description=(
                    f"Welcome to your temporary voice channel, "
                    f"{member.mention}!\n\n"
                    "Use the buttons below to manage your channel."
                ),
                color=EMBED_COLOR
            )


            embed.add_field(
                name="✏️ Rename",
                value="Change the voice channel name.",
                inline=False
            )


            embed.add_field(
                name="👥 User Limit",
                value="Set the maximum number of users.",
                inline=False
            )


            embed.add_field(
                name="🔒 Lock / Unlock",
                value="Control who can join.",
                inline=False
            )


            embed.add_field(
                name="👁️ Hide / Show",
                value="Control who can see the channel.",
                inline=False
            )


            embed.add_field(
                name="👑 Transfer Owner",
                value="Give ownership to another member.",
                inline=False
            )


            await temp_channel.send(
                embed=embed,
                view=TempVoiceView(
                    self
                )
            )


        # =================================================
        # DELETE EMPTY TEMP CHANNELS
        # =================================================

        if before.channel:

            data = get_temp_channel(
                before.channel.id
            )


            if data:

                # Check if everyone left

                if len(before.channel.members) == 0:

                    channel_id = before.channel.id


                    try:

                        await before.channel.delete(
                            reason="Temporary voice channel is empty."
                        )

                    except (
                        discord.Forbidden,
                        discord.HTTPException
                    ):

                        pass


                    cursor.execute("""
                    DELETE FROM tempvoice_channels
                    WHERE channel_id=?
                    """, (
                        channel_id,
                    ))

                    db.commit()


    # =====================================================
    # VOICE SETTINGS
    # =====================================================

    @commands.command()
    async def voiceinfo(
        self,
        ctx
    ):

        settings = get_settings(
            ctx.guild.id
        )


        if settings is None:

            return await ctx.send(
                "❌ Temporary voice channels have not been configured."
            )


        channel = ctx.guild.get_channel(
            settings[0]
        )


        embed = discord.Embed(
            title="🔊 Temporary Voice Channels",
            color=EMBED_COLOR
        )


        embed.add_field(
            name="Creator Channel",
            value=(
                channel.mention
                if channel
                else "Unknown"
            ),
            inline=False
        )


        await ctx.send(
            embed=embed
        )


    # =====================================================
    # COMMAND ERRORS
    # =====================================================

    @setvoicecreator.error
    async def setvoicecreator_error(
        self,
        ctx,
        error
    ):

        if isinstance(
            error,
            commands.MissingPermissions
        ):

            return await ctx.send(
                "❌ You don't have permission to configure temporary voice channels."
            )


        if isinstance(
            error,
            commands.MissingRequiredArgument
        ):

            return await ctx.send(
                "❌ Usage: `!setvoicecreator <voice channel>`"
            )


        if isinstance(
            error,
            commands.BadArgument
        ):

            return await ctx.send(
                "❌ Please mention a valid voice channel."
            )


        raise error


# =========================================================
# SETUP
# =========================================================

async def setup(bot):

    cog = TempVoice(
        bot
    )

    await bot.add_cog(
        cog
    )

    bot.add_view(
        TempVoiceView(
            cog
        )
    )