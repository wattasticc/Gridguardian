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
CREATE TABLE IF NOT EXISTS starboard_settings (
    guild_id INTEGER PRIMARY KEY,
    channel_id INTEGER,
    required_stars INTEGER DEFAULT 5
)
""")


cursor.execute("""
CREATE TABLE IF NOT EXISTS starboard_messages (
    original_message_id INTEGER PRIMARY KEY,
    starboard_message_id INTEGER NOT NULL,
    guild_id INTEGER NOT NULL
)
""")


db.commit()


# =========================================================
# STARBOARD COG
# =========================================================

class Starboard(commands.Cog):

    def __init__(self, bot):

        self.bot = bot


    # =====================================================
    # GET SETTINGS
    # =====================================================

    def get_settings(self, guild_id):

        cursor.execute("""
        SELECT channel_id, required_stars
        FROM starboard_settings
        WHERE guild_id=?
        """, (
            guild_id,
        ))

        return cursor.fetchone()


    # =====================================================
    # GET STAR COUNT
    # =====================================================

    def get_star_count(self, message):

        for reaction in message.reactions:

            if str(reaction.emoji) == "⭐":

                return reaction.count

        return 0


    # =====================================================
    # CREATE STARBOARD EMBED
    # =====================================================

    def create_embed(
        self,
        message,
        star_count
    ):

        embed = discord.Embed(
            description=message.content or "*No text content*",
            color=EMBED_COLOR,
            timestamp=message.created_at
        )


        embed.set_author(
            name=message.author.display_name,
            icon_url=message.author.display_avatar.url
        )


        embed.add_field(
            name="⭐ Stars",
            value=str(star_count),
            inline=True
        )


        embed.add_field(
            name="📍 Channel",
            value=message.channel.mention,
            inline=True
        )


        embed.add_field(
            name="🔗 Jump to Message",
            value=f"[Click Here]({message.jump_url})",
            inline=False
        )


        # Add image attachment if available

        for attachment in message.attachments:

            if attachment.content_type:

                if attachment.content_type.startswith(
                    "image"
                ):

                    embed.set_image(
                        url=attachment.url
                    )

                    break


        embed.set_footer(
            text=f"Message ID: {message.id}"
        )


        return embed


    # =====================================================
    # PROCESS STARBOARD
    # =====================================================

    async def process_message(
        self,
        message
    ):

        # Ignore DMs

        if message.guild is None:

            return


        # Ignore bot messages

        if message.author.bot:

            return


        # Get starboard settings

        settings = self.get_settings(
            message.guild.id
        )


        if settings is None:

            return


        channel_id, required_stars = settings


        starboard_channel = message.guild.get_channel(
            channel_id
        )


        if not isinstance(
            starboard_channel,
            discord.TextChannel
        ):

            return


        # Don't star messages inside the starboard itself

        if message.channel.id == channel_id:

            return


        star_count = self.get_star_count(
            message
        )


        # Check database

        cursor.execute("""
        SELECT starboard_message_id
        FROM starboard_messages
        WHERE original_message_id=?
        """, (
            message.id,
        ))

        result = cursor.fetchone()


        # =================================================
        # MESSAGE DOESN'T HAVE ENOUGH STARS
        # =================================================

        if star_count < required_stars:

            # If it already exists, remove it

            if result:

                try:

                    star_message = await starboard_channel.fetch_message(
                        result[0]
                    )

                    await star_message.delete()

                except (
                    discord.NotFound,
                    discord.Forbidden,
                    discord.HTTPException
                ):

                    pass


                cursor.execute("""
                DELETE FROM starboard_messages
                WHERE original_message_id=?
                """, (
                    message.id,
                ))

                db.commit()


            return


        # =================================================
        # MESSAGE ALREADY ON STARBOARD
        # =================================================

        if result:

            try:

                star_message = await starboard_channel.fetch_message(
                    result[0]
                )


                embed = self.create_embed(
                    message,
                    star_count
                )


                await star_message.edit(
                    content=(
                        f"⭐ **{star_count}**"
                    ),
                    embed=embed
                )


                return


            except discord.NotFound:

                # Database entry exists but message was deleted

                cursor.execute("""
                DELETE FROM starboard_messages
                WHERE original_message_id=?
                """, (
                    message.id,
                ))

                db.commit()


        # =================================================
        # CREATE STARBOARD MESSAGE
        # =================================================

        embed = self.create_embed(
            message,
            star_count
        )


        try:

            star_message = await starboard_channel.send(
                content=f"⭐ **{star_count}**",
                embed=embed
            )

        except (
            discord.Forbidden,
            discord.HTTPException
        ):

            return


        cursor.execute("""
        INSERT OR REPLACE INTO starboard_messages(
            original_message_id,
            starboard_message_id,
            guild_id
        )
        VALUES (?, ?, ?)
        """, (
            message.id,
            star_message.id,
            message.guild.id
        ))

        db.commit()


    # =====================================================
    # REACTION ADDED
    # =====================================================

    @commands.Cog.listener()
    async def on_raw_reaction_add(
        self,
        payload
    ):

        if str(payload.emoji) != "⭐":

            return


        if payload.guild_id is None:

            return


        guild = self.bot.get_guild(
            payload.guild_id
        )


        if guild is None:

            return


        channel = guild.get_channel(
            payload.channel_id
        )


        if not isinstance(
            channel,
            discord.TextChannel
        ):

            return


        try:

            message = await channel.fetch_message(
                payload.message_id
            )

        except (
            discord.NotFound,
            discord.Forbidden,
            discord.HTTPException
        ):

            return


        await self.process_message(
            message
        )


    # =====================================================
    # REACTION REMOVED
    # =====================================================

    @commands.Cog.listener()
    async def on_raw_reaction_remove(
        self,
        payload
    ):

        if str(payload.emoji) != "⭐":

            return


        if payload.guild_id is None:

            return


        guild = self.bot.get_guild(
            payload.guild_id
        )


        if guild is None:

            return


        channel = guild.get_channel(
            payload.channel_id
        )


        if not isinstance(
            channel,
            discord.TextChannel
        ):

            return


        try:

            message = await channel.fetch_message(
                payload.message_id
            )

        except (
            discord.NotFound,
            discord.Forbidden,
            discord.HTTPException
        ):

            return


        await self.process_message(
            message
        )


    # =====================================================
    # ORIGINAL MESSAGE DELETED
    # =====================================================

    @commands.Cog.listener()
    async def on_raw_message_delete(
        self,
        payload
    ):

        cursor.execute("""
        SELECT starboard_message_id, guild_id
        FROM starboard_messages
        WHERE original_message_id=?
        """, (
            payload.message_id,
        ))

        result = cursor.fetchone()


        if result is None:

            return


        starboard_message_id, guild_id = result


        settings = self.get_settings(
            guild_id
        )


        if settings:

            channel_id, _ = settings


            guild = self.bot.get_guild(
                guild_id
            )


            if guild:

                channel = guild.get_channel(
                    channel_id
                )


                if isinstance(
                    channel,
                    discord.TextChannel
                ):

                    try:

                        message = await channel.fetch_message(
                            starboard_message_id
                        )

                        await message.delete()

                    except (
                        discord.NotFound,
                        discord.Forbidden,
                        discord.HTTPException
                    ):

                        pass


        cursor.execute("""
        DELETE FROM starboard_messages
        WHERE original_message_id=?
        """, (
            payload.message_id,
        ))

        db.commit()


    # =====================================================
    # SET STARBOARD CHANNEL
    # =====================================================

    @commands.command()
    @commands.has_permissions(
        manage_guild=True
    )
    async def setstarboard(
        self,
        ctx,
        channel: discord.TextChannel
    ):

        cursor.execute("""
        INSERT INTO starboard_settings(
            guild_id,
            channel_id,
            required_stars
        )
        VALUES (?, ?, 5)

        ON CONFLICT(guild_id)
        DO UPDATE SET
        channel_id=excluded.channel_id
        """, (
            ctx.guild.id,
            channel.id
        ))

        db.commit()


        embed = discord.Embed(
            title="⭐ Starboard Configured",
            description=(
                f"Starboard channel set to "
                f"{channel.mention}.\n\n"
                "Messages need **5 ⭐ reactions** "
                "to appear."
            ),
            color=EMBED_COLOR
        )


        await ctx.send(
            embed=embed
        )


    # =====================================================
    # SET REQUIRED STARS
    # =====================================================

    @commands.command()
    @commands.has_permissions(
        manage_guild=True
    )
    async def setstars(
        self,
        ctx,
        amount: int
    ):

        if amount < 1:

            return await ctx.send(
                "❌ The star requirement must be at least 1."
            )


        if amount > 100:

            return await ctx.send(
                "❌ The star requirement cannot be above 100."
            )


        settings = self.get_settings(
            ctx.guild.id
        )


        if settings is None:

            return await ctx.send(
                "❌ Set a starboard channel first using "
                "`!setstarboard #channel`."
            )


        cursor.execute("""
        UPDATE starboard_settings
        SET required_stars=?
        WHERE guild_id=?
        """, (
            amount,
            ctx.guild.id
        ))

        db.commit()


        embed = discord.Embed(
            title="⭐ Star Requirement Updated",
            description=(
                f"Messages now need **{amount} ⭐ reactions** "
                "to appear on the starboard."
            ),
            color=EMBED_COLOR
        )


        await ctx.send(
            embed=embed
        )


    # =====================================================
    # STARBOARD STATUS
    # =====================================================

    @commands.command()
    async def starboard(
        self,
        ctx
    ):

        settings = self.get_settings(
            ctx.guild.id
        )


        if settings is None:

            return await ctx.send(
                "❌ The starboard has not been configured yet."
            )


        channel_id, required_stars = settings


        channel = ctx.guild.get_channel(
            channel_id
        )


        channel_text = (
            channel.mention
            if channel
            else "Unknown channel"
        )


        embed = discord.Embed(
            title="⭐ Starboard Settings",
            color=EMBED_COLOR
        )


        embed.add_field(
            name="📍 Channel",
            value=channel_text,
            inline=True
        )


        embed.add_field(
            name="⭐ Required Stars",
            value=str(required_stars),
            inline=True
        )


        await ctx.send(
            embed=embed
        )


    # =====================================================
    # ERROR HANDLER
    # =====================================================

    @setstarboard.error
    @setstars.error
    async def starboard_error(
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


        if isinstance(
            error,
            commands.MissingRequiredArgument
        ):

            return await ctx.send(
                "❌ You're missing a required argument."
            )


        if isinstance(
            error,
            commands.BadArgument
        ):

            return await ctx.send(
                "❌ One of the arguments you entered is invalid."
            )


        raise error


# =========================================================
# SETUP
# =========================================================

async def setup(bot):

    await bot.add_cog(
        Starboard(bot)
    )