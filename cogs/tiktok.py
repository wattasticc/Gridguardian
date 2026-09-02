import asyncio
import sqlite3
from datetime import datetime, timezone

import discord
from discord.ext import commands, tasks
import yt_dlp


# ==========================================================
# CONFIGURATION
# ==========================================================

EMBED_COLOR = discord.Color.from_rgb(
    80,
    220,
    255
)

CHECK_INTERVAL_MINUTES = 10


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


# ==========================================================
# DATABASE SETUP
# ==========================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS tiktok_settings (
    guild_id INTEGER PRIMARY KEY,
    username TEXT,
    channel_id INTEGER,
    role_id INTEGER,
    last_video_id TEXT,
    last_video_url TEXT,
    updated_at TEXT
)
""")


# ----------------------------------------------------------
# DATABASE MIGRATION
#
# Adds role_id if you already created the table before this
# version of the TikTok cog.
# ----------------------------------------------------------

cursor.execute("""
PRAGMA table_info(tiktok_settings)
""")

existing_columns = {
    row[1]
    for row in cursor.fetchall()
}


if "role_id" not in existing_columns:

    cursor.execute("""
    ALTER TABLE tiktok_settings
    ADD COLUMN role_id INTEGER
    """)


db.commit()


# ==========================================================
# TIKTOK COG
# ==========================================================

class TikTok(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.check_lock = asyncio.Lock()

        self.tiktok_check_loop.start()


    # ======================================================
    # COG UNLOAD
    # ======================================================

    def cog_unload(self):

        self.tiktok_check_loop.cancel()


    # ======================================================
    # DATABASE HELPERS
    # ======================================================

    def get_settings(self, guild_id):

        cursor.execute("""
        SELECT
            username,
            channel_id,
            role_id,
            last_video_id,
            last_video_url,
            updated_at
        FROM tiktok_settings
        WHERE guild_id = ?
        """, (
            guild_id,
        ))


        row = cursor.fetchone()


        if row is None:

            return None


        return {
            "username": row[0],
            "channel_id": row[1],
            "role_id": row[2],
            "last_video_id": row[3],
            "last_video_url": row[4],
            "updated_at": row[5]
        }


    def create_settings(self, guild_id):

        timestamp = datetime.now(
            timezone.utc
        ).isoformat()


        cursor.execute("""
        INSERT OR IGNORE INTO tiktok_settings (
            guild_id,
            username,
            channel_id,
            role_id,
            last_video_id,
            last_video_url,
            updated_at
        )
        VALUES (
            ?,
            NULL,
            NULL,
            NULL,
            NULL,
            NULL,
            ?
        )
        """, (
            guild_id,
            timestamp
        ))


        db.commit()


    def update_username(
        self,
        guild_id,
        username
    ):

        timestamp = datetime.now(
            timezone.utc
        ).isoformat()


        self.create_settings(
            guild_id
        )


        cursor.execute("""
        UPDATE tiktok_settings
        SET
            username = ?,
            last_video_id = NULL,
            last_video_url = NULL,
            updated_at = ?
        WHERE guild_id = ?
        """, (
            username,
            timestamp,
            guild_id
        ))


        db.commit()


    def update_channel(
        self,
        guild_id,
        channel_id
    ):

        timestamp = datetime.now(
            timezone.utc
        ).isoformat()


        self.create_settings(
            guild_id
        )


        cursor.execute("""
        UPDATE tiktok_settings
        SET
            channel_id = ?,
            updated_at = ?
        WHERE guild_id = ?
        """, (
            channel_id,
            timestamp,
            guild_id
        ))


        db.commit()


    def update_role(
        self,
        guild_id,
        role_id
    ):

        timestamp = datetime.now(
            timezone.utc
        ).isoformat()


        self.create_settings(
            guild_id
        )


        cursor.execute("""
        UPDATE tiktok_settings
        SET
            role_id = ?,
            updated_at = ?
        WHERE guild_id = ?
        """, (
            role_id,
            timestamp,
            guild_id
        ))


        db.commit()


    def update_last_video(
        self,
        guild_id,
        video_id,
        video_url
    ):

        timestamp = datetime.now(
            timezone.utc
        ).isoformat()


        self.create_settings(
            guild_id
        )


        cursor.execute("""
        UPDATE tiktok_settings
        SET
            last_video_id = ?,
            last_video_url = ?,
            updated_at = ?
        WHERE guild_id = ?
        """, (
            video_id,
            video_url,
            timestamp,
            guild_id
        ))


        db.commit()


    # ======================================================
    # USERNAME CLEANUP
    # ======================================================

    @staticmethod
    def clean_username(username):

        username = username.strip()


        if username.startswith("@"):

            username = username[1:]


        username = username.replace(
            "https://www.tiktok.com/@",
            ""
        )


        username = username.replace(
            "https://tiktok.com/@",
            ""
        )


        username = username.split(
            "/"
        )[0]


        username = username.split(
            "?"
        )[0]


        return username.strip()


    # ======================================================
    # GET LATEST TIKTOK
    # ======================================================

    async def get_latest_tiktok(
        self,
        username
    ):

        profile_url = (
            f"https://www.tiktok.com/@{username}"
        )


        ydl_options = {

            "quiet": True,

            "no_warnings": True,

            "extract_flat": False,

            "playlistend": 1,

            "skip_download": True,

            "noplaylist": False

        }


        def extract_video():

            with yt_dlp.YoutubeDL(
                ydl_options
            ) as ydl:

                return ydl.extract_info(
                    profile_url,
                    download=False
                )


        try:

            data = await asyncio.to_thread(
                extract_video
            )


        except Exception as error:

            print(
                "⚠️ TikTok check failed for "
                f"@{username}: {error}"
            )

            return None


        if data is None:

            return None


        entries = data.get(
            "entries"
        )


        if entries:

            entries = list(
                entries
            )


            if not entries:

                return None


            video = entries[0]


        else:

            video = data


        video_id = video.get(
            "id"
        )


        video_url = video.get(
            "webpage_url"
        )


        if not video_url:

            video_url = video.get(
                "original_url"
            )


        if not video_url and video_id:

            video_url = (
                f"https://www.tiktok.com/@"
                f"{username}/video/{video_id}"
            )


        if not video_id:

            return None


        description = video.get(
            "description"
        )


        if not description:

            description = video.get(
                "title"
            )


        if not description:

            description = (
                "New TikTok posted!"
            )


        thumbnail = video.get(
            "thumbnail"
        )


        uploader = video.get(
            "uploader"
        )


        if not uploader:

            uploader = username


        return {

            "id": str(
                video_id
            ),

            "url": video_url,

            "description": description,

            "thumbnail": thumbnail,

            "uploader": uploader

        }


    # ======================================================
    # SEND NOTIFICATION
    # ======================================================

    async def send_notification(
        self,
        guild,
        settings,
        video
    ):

        channel_id = settings.get(
            "channel_id"
        )


        if not channel_id:

            return False


        channel = guild.get_channel(
            channel_id
        )


        if channel is None:

            try:

                channel = await self.bot.fetch_channel(
                    channel_id
                )

            except Exception:

                return False


        username = settings.get(
            "username"
        )


        role_id = settings.get(
            "role_id"
        )


        role_mention = None


        if role_id:

            role = guild.get_role(
                role_id
            )


            if role:

                role_mention = (
                    role.mention
                )


        profile_url = (
            f"https://www.tiktok.com/@{username}"
        )


        description = video.get(
            "description",
            "New TikTok posted!"
        )


        if len(description) > 1000:

            description = (
                description[:997]
                + "..."
            )


        # ==================================================
        # CREATE EMBED
        # ==================================================

        embed = discord.Embed(

            title="🎵 New TikTok!",

            description=description,

            color=EMBED_COLOR,

            timestamp=datetime.now(
                timezone.utc
            )

        )


        embed.set_author(

            name=(
                f"@{username}"
            ),

            url=profile_url

        )


        embed.add_field(

            name="📱 Watch",

            value=(
                f"[Click here to watch the TikTok]"
                f"({video['url']})"
            ),

            inline=False

        )


        if video.get(
            "thumbnail"
        ):

            embed.set_image(

                url=video[
                    "thumbnail"
                ]

            )


        embed.set_footer(

            text=(
                "Grid Guardian • TikTok Notifications"
            )

        )


        # ==================================================
        # BUTTON
        # ==================================================

        view = discord.ui.View()


        button = discord.ui.Button(

            label="Watch TikTok",

            url=video[
                "url"
            ],

            emoji="🎵"

        )


        view.add_item(
            button
        )


        # ==================================================
        # NOTIFICATION MESSAGE
        # ==================================================

        if role_mention:

            content = (
                f"{role_mention} 🎵 **New TikTok from "
                f"@{username}!**"
            )

        else:

            content = (
                f"🎵 **New TikTok from "
                f"@{username}!**"
            )


        try:

            await channel.send(

                content=content,

                embed=embed,

                view=view,

                allowed_mentions=discord.AllowedMentions(
                    roles=True
                )

            )


            return True


        except discord.Forbidden:

            print(
                "⚠️ Grid Guardian does not have permission "
                "to send TikTok notifications."
            )


            return False


        except Exception as error:

            print(
                "⚠️ Could not send TikTok notification: "
                f"{error}"
            )


            return False


    # ======================================================
    # CHECK ONE GUILD
    # ======================================================

    async def check_guild(
        self,
        guild
    ):

        settings = self.get_settings(
            guild.id
        )


        if settings is None:

            return


        username = settings.get(
            "username"
        )


        channel_id = settings.get(
            "channel_id"
        )


        if not username:

            return


        if not channel_id:

            return


        video = await self.get_latest_tiktok(
            username
        )


        if video is None:

            return


        last_video_id = settings.get(
            "last_video_id"
        )


        # --------------------------------------------------
        # FIRST CHECK
        # --------------------------------------------------

        if last_video_id is None:

            self.update_last_video(

                guild.id,

                video["id"],

                video["url"]

            )


            print(
                "🎵 TikTok monitoring started for "
                f"@{username}."
            )


            return


        # --------------------------------------------------
        # SAME VIDEO
        # --------------------------------------------------

        if str(
            last_video_id
        ) == str(
            video["id"]
        ):

            return


        # --------------------------------------------------
        # NEW VIDEO
        # --------------------------------------------------

        sent = await self.send_notification(

            guild,

            settings,

            video

        )


        if sent:

            self.update_last_video(

                guild.id,

                video["id"],

                video["url"]

            )


            print(
                "🎵 New TikTok detected from "
                f"@{username}!"
            )


    # ======================================================
    # CHECK ALL GUILDS
    # ======================================================

    async def check_all_guilds(self):

        async with self.check_lock:

            for guild in self.bot.guilds:

                try:

                    await self.check_guild(
                        guild
                    )


                except Exception as error:

                    print(
                        "⚠️ TikTok monitoring error in "
                        f"{guild.name}: {error}"
                    )


    # ======================================================
    # AUTOMATIC CHECK LOOP
    # ======================================================

    @tasks.loop(
        minutes=CHECK_INTERVAL_MINUTES
    )
    async def tiktok_check_loop(self):

        await self.check_all_guilds()


    @tiktok_check_loop.before_loop
    async def before_tiktok_check_loop(self):

        await self.bot.wait_until_ready()


    # ======================================================
    # SET TIKTOK ACCOUNT
    # ======================================================

    @commands.command(
        name="settiktok",
        aliases=[
            "tiktoksetup",
            "tiktokuser"
        ]
    )
    @commands.has_permissions(
        administrator=True
    )
    async def settiktok(
        self,
        ctx,
        username=None
    ):

        if not username:

            return await ctx.send(
                "❌ Please provide a TikTok username.\n\n"
                "**Example:** `!settiktok wattasticc`"
            )


        username = self.clean_username(
            username
        )


        if not username:

            return await ctx.send(
                "❌ Please provide a valid TikTok username."
            )


        self.update_username(
            ctx.guild.id,
            username
        )


        checking_message = await ctx.send(
            "🔄 Checking the TikTok account..."
        )


        video = await self.get_latest_tiktok(
            username
        )


        if video is None:

            return await checking_message.edit(
                content=(
                    "⚠️ The username was saved, but Grid "
                    "Guardian could not currently read the "
                    "TikTok profile.\n\n"
                    "Make sure the username is correct and "
                    "the account is public."
                )
            )


        self.update_last_video(

            ctx.guild.id,

            video["id"],

            video["url"]

        )


        await checking_message.edit(
            content=(
                "✅ TikTok monitoring is now enabled for "
                f"**@{username}**!\n\n"
                "New TikToks posted after this setup will "
                "trigger notifications."
            )
        )


    # ======================================================
    # SET NOTIFICATION CHANNEL
    # ======================================================

    @commands.command(
        name="tiktokchannel",
        aliases=[
            "settiktokchannel"
        ]
    )
    @commands.has_permissions(
        administrator=True
    )
    async def tiktokchannel(
        self,
        ctx,
        channel: discord.TextChannel = None
    ):

        if channel is None:

            return await ctx.send(
                "❌ Please mention a text channel.\n\n"
                "**Example:** "
                "`!tiktokchannel #tiktok-notifications`"
            )


        self.update_channel(
            ctx.guild.id,
            channel.id
        )


        await ctx.send(
            "✅ TikTok notifications will now be sent to "
            f"{channel.mention}!"
        )


    # ======================================================
    # SET PING ROLE
    # ======================================================

    @commands.command(
        name="tiktokrole",
        aliases=[
            "settiktokrole",
            "tiktokping"
        ]
    )
    @commands.has_permissions(
        administrator=True
    )
    async def tiktokrole(
        self,
        ctx,
        role: discord.Role = None
    ):

        if role is None:

            return await ctx.send(
                "❌ Please mention a role.\n\n"
                "**Example:** `!tiktokrole @TikTok Pings`\n\n"
                "To remove the ping role, use:\n"
                "`!tiktokrole none`"
            )


        if role.is_default():

            return await ctx.send(
                "❌ You cannot use the `@everyone` role "
                "as the TikTok notification role."
            )


        self.update_role(
            ctx.guild.id,
            role.id
        )


        await ctx.send(
            "✅ New TikTok notifications will now ping "
            f"{role.mention}!"
        )


    # ======================================================
    # REMOVE PING ROLE
    # ======================================================

    @commands.command(
        name="removetiktokrole",
        aliases=[
            "cleartiktokrole",
            "untiktokrole"
        ]
    )
    @commands.has_permissions(
        administrator=True
    )
    async def removetiktokrole(
        self,
        ctx
    ):

        self.update_role(
            ctx.guild.id,
            None
        )


        await ctx.send(
            "✅ TikTok role pinging has been disabled."
        )


    # ======================================================
    # TIKTOK STATUS
    # ======================================================

    @commands.command(
        name="tiktokstatus",
        aliases=[
            "tiktokinfo"
        ]
    )
    async def tiktokstatus(
        self,
        ctx
    ):

        settings = self.get_settings(
            ctx.guild.id
        )


        if settings is None:

            return await ctx.send(
                "❌ TikTok notifications have not been "
                "configured yet."
            )


        username = settings.get(
            "username"
        )


        channel_id = settings.get(
            "channel_id"
        )


        role_id = settings.get(
            "role_id"
        )


        if not username:

            return await ctx.send(
                "❌ No TikTok username has been configured."
            )


        channel_text = "Not configured"

        role_text = "No role ping"


        if channel_id:

            channel = ctx.guild.get_channel(
                channel_id
            )


            if channel:

                channel_text = (
                    channel.mention
                )


        if role_id:

            role = ctx.guild.get_role(
                role_id
            )


            if role:

                role_text = (
                    role.mention
                )


        embed = discord.Embed(

            title="🎵 TikTok Notifications",

            color=EMBED_COLOR

        )


        embed.add_field(

            name="👤 TikTok Account",

            value=(
                f"[@{username}]"
                f"(https://www.tiktok.com/@{username})"
            ),

            inline=False

        )


        embed.add_field(

            name="📢 Notification Channel",

            value=channel_text,

            inline=False

        )


        embed.add_field(

            name="🔔 Ping Role",

            value=role_text,

            inline=False

        )


        embed.add_field(

            name="🔄 Check Interval",

            value=(
                f"Every "
                f"{CHECK_INTERVAL_MINUTES} minutes"
            ),

            inline=False

        )


        embed.set_footer(
            text=(
                "Grid Guardian • TikTok Notifications"
            )
        )


        await ctx.send(
            embed=embed
        )


    # ======================================================
    # MANUAL CHECK
    # ======================================================

    @commands.command(
        name="checktiktok",
        aliases=[
            "refreshtiktok"
        ]
    )
    @commands.has_permissions(
        administrator=True
    )
    async def checktiktok(
        self,
        ctx
    ):

        settings = self.get_settings(
            ctx.guild.id
        )


        if settings is None:

            return await ctx.send(
                "❌ TikTok notifications have not been "
                "configured yet."
            )


        username = settings.get(
            "username"
        )


        channel_id = settings.get(
            "channel_id"
        )


        if not username:

            return await ctx.send(
                "❌ No TikTok account has been configured.\n\n"
                "Use `!settiktok <username>` first."
            )


        if not channel_id:

            return await ctx.send(
                "❌ No notification channel has been set.\n\n"
                "Use `!tiktokchannel #channel` first."
            )


        checking_message = await ctx.send(
            "🔄 Checking for a new TikTok..."
        )


        video = await self.get_latest_tiktok(
            username
        )


        if video is None:

            return await checking_message.edit(
                content=(
                    "⚠️ I couldn't check the TikTok account "
                    "right now."
                )
            )


        last_video_id = settings.get(
            "last_video_id"
        )


        if str(
            last_video_id
        ) == str(
            video["id"]
        ):

            return await checking_message.edit(
                content=(
                    "✅ No new TikTok was found."
                )
            )


        sent = await self.send_notification(

            ctx.guild,

            settings,

            video

        )


        if sent:

            self.update_last_video(

                ctx.guild.id,

                video["id"],

                video["url"]

            )


            await checking_message.edit(
                content=(
                    "🎵 New TikTok found and posted!"
                )
            )


        else:

            await checking_message.edit(
                content=(
                    "⚠️ A new TikTok was found, but I "
                    "couldn't send the notification."
                )
            )


    # ======================================================
    # ERROR HANDLERS
    # ======================================================

    @settiktok.error
    async def settiktok_error(
        self,
        ctx,
        error
    ):

        if isinstance(
            error,
            commands.MissingPermissions
        ):

            await ctx.send(
                "❌ You need the **Administrator** permission "
                "to configure TikTok notifications."
            )


    @tiktokchannel.error
    async def tiktokchannel_error(
        self,
        ctx,
        error
    ):

        if isinstance(
            error,
            commands.MissingPermissions
        ):

            await ctx.send(
                "❌ You need the **Administrator** permission "
                "to configure TikTok notifications."
            )


    @tiktokrole.error
    async def tiktokrole_error(
        self,
        ctx,
        error
    ):

        if isinstance(
            error,
            commands.MissingPermissions
        ):

            await ctx.send(
                "❌ You need the **Administrator** permission "
                "to configure the TikTok ping role."
            )


    @removetiktokrole.error
    async def removetiktokrole_error(
        self,
        ctx,
        error
    ):

        if isinstance(
            error,
            commands.MissingPermissions
        ):

            await ctx.send(
                "❌ You need the **Administrator** permission "
                "to configure the TikTok ping role."
            )


    @checktiktok.error
    async def checktiktok_error(
        self,
        ctx,
        error
    ):

        if isinstance(
            error,
            commands.MissingPermissions
        ):

            await ctx.send(
                "❌ You need the **Administrator** permission "
                "to manually check TikTok notifications."
            )


# ==========================================================
# SETUP
# ==========================================================

async def setup(bot):

    await bot.add_cog(
        TikTok(bot)
    )