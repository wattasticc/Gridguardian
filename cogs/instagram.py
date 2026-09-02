import asyncio
import os
import sqlite3

import aiohttp
import discord
from discord.ext import commands, tasks


# ==========================================================
# CONFIGURATION
# ==========================================================

EMBED_COLOR = discord.Color.from_rgb(225, 48, 108)

CHECK_INTERVAL_MINUTES = 5


# ==========================================================
# INSTAGRAM API CONFIGURATION
# ==========================================================

INSTAGRAM_ACCESS_TOKEN = os.getenv(
    "INSTAGRAM_ACCESS_TOKEN"
)

INSTAGRAM_API_BASE = os.getenv(
    "INSTAGRAM_API_BASE",
    "https://graph.instagram.com"
)


# ==========================================================
# DATABASE
# ==========================================================

db = sqlite3.connect(
    "gridguardian.db",
    timeout=30,
    check_same_thread=False
)

# Give SQLite time to wait for another cog to finish a write instead
# of immediately raising "database is locked".
db.execute("PRAGMA busy_timeout = 30000")
db.execute("PRAGMA journal_mode = WAL")
db.execute("PRAGMA synchronous = NORMAL")

cursor = db.cursor()


cursor.execute("""
CREATE TABLE IF NOT EXISTS instagram_settings (
    guild_id INTEGER PRIMARY KEY,
    instagram_user_id TEXT,
    channel_id INTEGER,
    role_id INTEGER
)
""")


cursor.execute("""
CREATE TABLE IF NOT EXISTS instagram_posts (
    guild_id INTEGER NOT NULL,
    media_id TEXT NOT NULL,
    PRIMARY KEY (guild_id, media_id)
)
""")


db.commit()


# ==========================================================
# INSTAGRAM COG
# ==========================================================

class Instagram(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        # Prevent the automatic loop and manual checks from using
        # this cog's database connection at the same time.
        self.check_lock = asyncio.Lock()

        self.instagram_loop.start()


    # ======================================================
    # COG UNLOAD
    # ======================================================

    def cog_unload(self):

        self.instagram_loop.cancel()


    # ======================================================
    # DATABASE HELPERS
    # ======================================================

    def get_settings(self, guild_id):

        cursor.execute("""
        SELECT
            instagram_user_id,
            channel_id,
            role_id
        FROM instagram_settings
        WHERE guild_id = ?
        """, (
            guild_id,
        ))

        return cursor.fetchone()


    def save_settings(
        self,
        guild_id,
        instagram_user_id,
        channel_id,
        role_id
    ):

        cursor.execute("""
        INSERT INTO instagram_settings (
            guild_id,
            instagram_user_id,
            channel_id,
            role_id
        )
        VALUES (?, ?, ?, ?)

        ON CONFLICT(guild_id)
        DO UPDATE SET

            instagram_user_id =
                excluded.instagram_user_id,

            channel_id =
                excluded.channel_id,

            role_id =
                excluded.role_id
        """, (
            guild_id,
            instagram_user_id,
            channel_id,
            role_id
        ))

        db.commit()


    def delete_settings(self, guild_id):

        cursor.execute("""
        DELETE FROM instagram_settings
        WHERE guild_id = ?
        """, (
            guild_id,
        ))

        db.commit()


    # ======================================================
    # CHECK IF POST WAS ALREADY SENT
    # ======================================================

    def post_exists(
        self,
        guild_id,
        media_id
    ):

        cursor.execute("""
        SELECT 1
        FROM instagram_posts
        WHERE guild_id = ?
        AND media_id = ?
        """, (
            guild_id,
            media_id
        ))

        return cursor.fetchone() is not None


    def save_post(
        self,
        guild_id,
        media_id
    ):

        cursor.execute("""
        INSERT OR IGNORE INTO instagram_posts (
            guild_id,
            media_id
        )
        VALUES (?, ?)
        """, (
            guild_id,
            media_id
        ))

        db.commit()


    # ======================================================
    # GET INSTAGRAM MEDIA
    # ======================================================

    async def get_instagram_media(
        self,
        instagram_user_id
    ):

        if not INSTAGRAM_ACCESS_TOKEN:

            print(
                "⚠️ INSTAGRAM_ACCESS_TOKEN is not set."
            )

            return None


        endpoint = (
            f"{INSTAGRAM_API_BASE}/"
            f"{instagram_user_id}/media"
        )


        params = {

            "fields": (
                "id,"
                "caption,"
                "media_type,"
                "media_url,"
                "thumbnail_url,"
                "permalink,"
                "timestamp"
            ),

            "limit": 10,

            "access_token":
                INSTAGRAM_ACCESS_TOKEN
        }


        timeout = aiohttp.ClientTimeout(
            total=20
        )


        try:

            async with aiohttp.ClientSession(
                timeout=timeout
            ) as session:

                async with session.get(
                    endpoint,
                    params=params
                ) as response:

                    if response.status != 200:

                        response_text = (
                            await response.text()
                        )

                        print(
                            "⚠️ Instagram API error: "
                            f"{response.status}"
                        )

                        print(
                            response_text
                        )

                        return None


                    data = (
                        await response.json()
                    )


        except Exception as error:

            print(
                f"⚠️ Instagram check failed: "
                f"{error}"
            )

            return None


        return data.get(
            "data",
            []
        )


    # ======================================================
    # SEND INSTAGRAM NOTIFICATION
    # ======================================================

    async def send_instagram_notification(
        self,
        guild,
        channel,
        role_id,
        media
    ):

        media_type = media.get(
            "media_type",
            "POST"
        )

        caption = media.get(
            "caption",
            ""
        )

        permalink = media.get(
            "permalink",
            ""
        )

        media_url = media.get(
            "media_url"
        )

        thumbnail_url = media.get(
            "thumbnail_url"
        )


        # --------------------------------------------------
        # CLEAN CAPTION
        # --------------------------------------------------

        if not caption:

            caption = (
                "A new Instagram post was uploaded!"
            )


        if len(caption) > 3500:

            caption = (
                caption[:3500]
                + "..."
            )


        # --------------------------------------------------
        # DETERMINE POST TYPE
        # --------------------------------------------------

        if media_type == "VIDEO":

            title = (
                "🎥 New Instagram Video!"
            )


        elif media_type == "CAROUSEL_ALBUM":

            title = (
                "📸 New Instagram Carousel!"
            )


        else:

            title = (
                "📸 New Instagram Post!"
            )


        # --------------------------------------------------
        # CREATE EMBED
        # --------------------------------------------------

        embed = discord.Embed(
            title=title,
            description=caption,
            color=EMBED_COLOR
        )


        if permalink:

            embed.add_field(
                name="🔗 View Post",
                value=(
                    f"[Open on Instagram]"
                    f"({permalink})"
                ),
                inline=False
            )


        # --------------------------------------------------
        # IMAGE / VIDEO THUMBNAIL
        # --------------------------------------------------

        image_to_use = (
            media_url
            or thumbnail_url
        )


        if image_to_use:

            embed.set_image(
                url=image_to_use
            )


        embed.set_footer(
            text=(
                "Grid Guardian • Instagram Notifications"
            )
        )


        # --------------------------------------------------
        # ROLE PING
        # --------------------------------------------------

        content = None


        if role_id:

            role = guild.get_role(
                role_id
            )


            if role:

                content = (
                    f"{role.mention} "
                    "New Instagram post!"
                )


        # --------------------------------------------------
        # SEND
        # --------------------------------------------------

        try:

            await channel.send(
                content=content,
                embed=embed,
                allowed_mentions=(
                    discord.AllowedMentions(
                        roles=True
                    )
                )
            )


        except Exception as error:

            print(
                "⚠️ Could not send Instagram "
                f"notification: {error}"
            )


    # ======================================================
    # CHECK ONE SERVER
    # ======================================================

    async def check_guild(
        self,
        guild_id
    ):

        async with self.check_lock:
            await self._check_guild(guild_id)


    async def _check_guild(
        self,
        guild_id
    ):

        settings = self.get_settings(
            guild_id
        )


        if not settings:

            return


        (
            instagram_user_id,
            channel_id,
            role_id
        ) = settings


        if not instagram_user_id:

            return


        guild = self.bot.get_guild(
            guild_id
        )


        if not guild:

            return


        channel = guild.get_channel(
            channel_id
        )


        if not channel:

            return


        media_list = (
            await self.get_instagram_media(
                instagram_user_id
            )
        )


        if media_list is None:

            return


        new_posts = []


        for media in reversed(
            media_list
        ):

            media_id = media.get(
                "id"
            )


            if not media_id:

                continue


            if self.post_exists(
                guild_id,
                media_id
            ):

                continue


            new_posts.append(
                media
            )


        # --------------------------------------------------
        # FIRST RUN PROTECTION
        # --------------------------------------------------

        cursor.execute("""
        SELECT COUNT(*)
        FROM instagram_posts
        WHERE guild_id = ?
        """, (
            guild_id,
        ))


        saved_count = (
            cursor.fetchone()[0]
        )


        if saved_count == 0:

            for media in media_list:

                media_id = media.get(
                    "id"
                )


                if media_id:

                    self.save_post(
                        guild_id,
                        media_id
                    )


            print(
                f"📸 Instagram initialized "
                f"for {guild.name}."
            )

            return


        # --------------------------------------------------
        # SEND NEW POSTS
        # --------------------------------------------------

        for media in new_posts:

            media_id = media.get(
                "id"
            )


            await self.send_instagram_notification(
                guild,
                channel,
                role_id,
                media
            )


            self.save_post(
                guild_id,
                media_id
            )


            print(
                f"📸 New Instagram post detected "
                f"in {guild.name}."
            )


    # ======================================================
    # AUTOMATIC CHECK LOOP
    # ======================================================

    @tasks.loop(
        minutes=CHECK_INTERVAL_MINUTES
    )
    async def instagram_loop(self):

        for guild in self.bot.guilds:

            try:

                await self.check_guild(
                    guild.id
                )


            except Exception as error:

                print(
                    f"⚠️ Instagram error for "
                    f"{guild.name}: {error}"
                )


    @instagram_loop.before_loop
    async def before_instagram_loop(self):

        await self.bot.wait_until_ready()


    # ======================================================
    # INSTAGRAM COMMAND GROUP
    # ======================================================

    # IMPORTANT:
    # The command is NOT named "instagram" because another
    # cog already uses that command or alias.
    #
    # Use:
    #
    # !instagramnotify
    # !ignotify
    # !instanotify

    @commands.group(
        name="instagramnotify",
        aliases=[
            "ignotify",
            "instanotify"
        ],
        invoke_without_command=True
    )
    async def instagramnotify(
        self,
        ctx
    ):

        embed = discord.Embed(
            title="📸 Instagram Notifications",
            description=(
                "Automatically post new Instagram "
                "content in Discord."
            ),
            color=EMBED_COLOR
        )


        embed.add_field(
            name="⚙️ Setup",
            value=(
                "`!instagramnotify setup "
                "<instagram_user_id> <#channel>`"
            ),
            inline=False
        )


        embed.add_field(
            name="🔔 Notification Role",
            value=(
                "`!instagramnotify role @role`\n"
                "`!instagramnotify role off`"
            ),
            inline=False
        )


        embed.add_field(
            name="📊 Status",
            value=(
                "`!instagramnotify status`"
            ),
            inline=False
        )


        embed.add_field(
            name="🔄 Check Now",
            value=(
                "`!instagramnotify check`"
            ),
            inline=False
        )


        embed.add_field(
            name="🗑️ Disable",
            value=(
                "`!instagramnotify disable`"
            ),
            inline=False
        )


        await ctx.send(
            embed=embed
        )


    # ======================================================
    # SETUP COMMAND
    # ======================================================

    @instagramnotify.command(
        name="setup"
    )
    @commands.has_permissions(
        administrator=True
    )
    async def instagram_setup(
        self,
        ctx,
        instagram_user_id,
        channel: discord.TextChannel
    ):

        current_settings = (
            self.get_settings(
                ctx.guild.id
            )
        )


        role_id = None


        if current_settings:

            role_id = (
                current_settings[2]
            )


        self.save_settings(
            ctx.guild.id,
            instagram_user_id,
            channel.id,
            role_id
        )


        cursor.execute("""
        DELETE FROM instagram_posts
        WHERE guild_id = ?
        """, (
            ctx.guild.id,
        ))

        db.commit()


        embed = discord.Embed(
            title="✅ Instagram Notifications Enabled",
            color=EMBED_COLOR
        )


        embed.add_field(
            name="📸 Instagram User ID",
            value=(
                f"`{instagram_user_id}`"
            ),
            inline=False
        )


        embed.add_field(
            name="📢 Discord Channel",
            value=channel.mention,
            inline=False
        )


        embed.add_field(
            name="⏱️ Check Interval",
            value=(
                f"Every "
                f"{CHECK_INTERVAL_MINUTES} minutes"
            ),
            inline=False
        )


        embed.set_footer(
            text=(
                "Grid Guardian • Instagram Notifications"
            )
        )


        await ctx.send(
            embed=embed
        )


    # ======================================================
    # ROLE COMMAND
    # ======================================================

    @instagramnotify.command(
        name="role"
    )
    @commands.has_permissions(
        administrator=True
    )
    async def instagram_role(
        self,
        ctx,
        role=None
    ):

        settings = self.get_settings(
            ctx.guild.id
        )


        if not settings:

            return await ctx.send(
                "❌ Instagram notifications have "
                "not been set up yet.\n\n"
                "Use:\n"
                "`!instagramnotify setup "
                "<instagram_user_id> <#channel>`"
            )


        instagram_user_id = (
            settings[0]
        )

        channel_id = (
            settings[1]
        )


        # --------------------------------------------------
        # TURN ROLE OFF
        # --------------------------------------------------

        if role:

            if role.lower() in [
                "off",
                "none",
                "disable"
            ]:

                self.save_settings(
                    ctx.guild.id,
                    instagram_user_id,
                    channel_id,
                    None
                )


                return await ctx.send(
                    "🔕 Instagram role pings "
                    "have been disabled."
                )


        # --------------------------------------------------
        # VALIDATE ROLE
        # --------------------------------------------------

        if not ctx.message.role_mentions:

            return await ctx.send(
                "❌ Please mention a role.\n\n"
                "**Example:**\n"
                "`!instagramnotify role @Instagram`"
            )


        selected_role = (
            ctx.message.role_mentions[0]
        )


        self.save_settings(
            ctx.guild.id,
            instagram_user_id,
            channel_id,
            selected_role.id
        )


        await ctx.send(
            "✅ Instagram notifications will "
            f"now ping {selected_role.mention}."
        )


    # ======================================================
    # STATUS COMMAND
    # ======================================================

    @instagramnotify.command(
        name="status"
    )
    async def instagram_status(
        self,
        ctx
    ):

        settings = self.get_settings(
            ctx.guild.id
        )


        if not settings:

            return await ctx.send(
                "📸 Instagram notifications "
                "are currently disabled."
            )


        (
            instagram_user_id,
            channel_id,
            role_id
        ) = settings


        channel = ctx.guild.get_channel(
            channel_id
        )


        role = None


        if role_id:

            role = ctx.guild.get_role(
                role_id
            )


        embed = discord.Embed(
            title="📸 Instagram Notification Status",
            color=EMBED_COLOR
        )


        embed.add_field(
            name="Status",
            value="🟢 Enabled",
            inline=False
        )


        embed.add_field(
            name="Instagram User ID",
            value=(
                f"`{instagram_user_id}`"
            ),
            inline=False
        )


        embed.add_field(
            name="Discord Channel",
            value=(
                channel.mention
                if channel
                else "Unknown"
            ),
            inline=False
        )


        embed.add_field(
            name="Notification Role",
            value=(
                role.mention
                if role
                else "None"
            ),
            inline=False
        )


        embed.add_field(
            name="Check Interval",
            value=(
                f"Every "
                f"{CHECK_INTERVAL_MINUTES} minutes"
            ),
            inline=False
        )


        await ctx.send(
            embed=embed
        )


    # ======================================================
    # DISABLE COMMAND
    # ======================================================

    @instagramnotify.command(
        name="disable"
    )
    @commands.has_permissions(
        administrator=True
    )
    async def instagram_disable(
        self,
        ctx
    ):

        self.delete_settings(
            ctx.guild.id
        )


        cursor.execute("""
        DELETE FROM instagram_posts
        WHERE guild_id = ?
        """, (
            ctx.guild.id,
        ))

        db.commit()


        await ctx.send(
            "🗑️ Instagram notifications "
            "have been disabled."
        )


    # ======================================================
    # MANUAL CHECK
    # ======================================================

    @instagramnotify.command(
        name="check"
    )
    @commands.has_permissions(
        administrator=True
    )
    async def instagram_check(
        self,
        ctx
    ):

        await ctx.send(
            "🔄 Checking Instagram..."
        )


        await self.check_guild(
            ctx.guild.id
        )


        await ctx.send(
            "✅ Instagram check completed."
        )


    # ======================================================
    # ERROR HANDLER
    # ======================================================

    @instagram_setup.error
    async def instagram_setup_error(
        self,
        ctx,
        error
    ):

        if isinstance(
            error,
            commands.MissingPermissions
        ):

            return await ctx.send(
                "❌ You need Administrator "
                "permissions to configure Instagram."
            )


        if isinstance(
            error,
            commands.MissingRequiredArgument
        ):

            return await ctx.send(
                "❌ Incorrect setup command.\n\n"
                "Use:\n"
                "`!instagramnotify setup "
                "<instagram_user_id> <#channel>`"
            )


        await ctx.send(
            f"❌ Error: `{error}`"
        )


# ==========================================================
# SETUP
# ==========================================================

async def setup(bot):

    await bot.add_cog(
        Instagram(bot)
    )