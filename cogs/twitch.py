import asyncio
import os
import sqlite3
import time

import aiohttp
import discord

from discord.ext import commands, tasks
from dotenv import load_dotenv


# ==========================================================
# LOAD ENVIRONMENT VARIABLES
# ==========================================================

load_dotenv()


TWITCH_CLIENT_ID = os.getenv(
    "TWITCH_CLIENT_ID"
)

TWITCH_CLIENT_SECRET = os.getenv(
    "TWITCH_CLIENT_SECRET"
)


# ==========================================================
# CONFIGURATION
# ==========================================================

DATABASE_PATH = "gridguardian.db"

CHECK_INTERVAL_MINUTES = 2

EMBED_COLOR = discord.Color.from_rgb(
    145,
    70,
    255
)


# ==========================================================
# TWITCH API URLS
# ==========================================================

TWITCH_TOKEN_URL = (
    "https://id.twitch.tv/oauth2/token"
)

TWITCH_STREAMS_URL = (
    "https://api.twitch.tv/helix/streams"
)

TWITCH_USERS_URL = (
    "https://api.twitch.tv/helix/users"
)


# ==========================================================
# DATABASE
# ==========================================================

def setup_database():

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    cursor = connection.cursor()


    cursor.execute("""
    CREATE TABLE IF NOT EXISTS twitch_notifications (
        guild_id INTEGER NOT NULL,
        streamer_login TEXT NOT NULL,
        channel_id INTEGER NOT NULL,
        last_stream_id TEXT,

        PRIMARY KEY (
            guild_id,
            streamer_login
        )
    )
    """)


    connection.commit()

    connection.close()


setup_database()


# ==========================================================
# TWITCH COG
# ==========================================================

class Twitch(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.access_token = None

        self.token_expires_at = 0

        self.check_twitch_streams.start()


    # ======================================================
    # COG UNLOAD
    # ======================================================

    def cog_unload(self):

        self.check_twitch_streams.cancel()


    # ======================================================
    # DATABASE HELPERS
    # ======================================================

    def get_streamers(self):

        connection = sqlite3.connect(
            DATABASE_PATH
        )

        cursor = connection.cursor()


        cursor.execute("""
        SELECT
            guild_id,
            streamer_login,
            channel_id,
            last_stream_id
        FROM twitch_notifications
        """)


        results = cursor.fetchall()

        connection.close()


        return results


    def add_streamer(
        self,
        guild_id,
        streamer_login,
        channel_id
    ):

        connection = sqlite3.connect(
            DATABASE_PATH
        )

        cursor = connection.cursor()


        cursor.execute("""
        INSERT OR REPLACE INTO twitch_notifications (
            guild_id,
            streamer_login,
            channel_id,
            last_stream_id
        )
        VALUES (?, ?, ?, NULL)
        """, (
            guild_id,
            streamer_login.lower(),
            channel_id
        ))


        connection.commit()

        connection.close()


    def remove_streamer(
        self,
        guild_id,
        streamer_login
    ):

        connection = sqlite3.connect(
            DATABASE_PATH
        )

        cursor = connection.cursor()


        cursor.execute("""
        DELETE FROM twitch_notifications
        WHERE guild_id = ?
        AND LOWER(streamer_login) = ?
        """, (
            guild_id,
            streamer_login.lower()
        ))


        removed = (
            cursor.rowcount
            >
            0
        )


        connection.commit()

        connection.close()


        return removed


    def update_last_stream(
        self,
        guild_id,
        streamer_login,
        stream_id
    ):

        connection = sqlite3.connect(
            DATABASE_PATH
        )

        cursor = connection.cursor()


        cursor.execute("""
        UPDATE twitch_notifications
        SET last_stream_id = ?
        WHERE guild_id = ?
        AND LOWER(streamer_login) = ?
        """, (
            stream_id,
            guild_id,
            streamer_login.lower()
        ))


        connection.commit()

        connection.close()


    # ======================================================
    # GET TWITCH ACCESS TOKEN
    # ======================================================

    async def get_access_token(self):

        # Reuse the current token until it is close
        # to expiring.

        if (
            self.access_token is not None
            and time.time()
            <
            self.token_expires_at
        ):

            return self.access_token


        # --------------------------------------------------
        # CHECK CREDENTIALS
        # --------------------------------------------------

        if not TWITCH_CLIENT_ID:

            print(
                "❌ TWITCH_CLIENT_ID was not found."
            )

            return None


        if not TWITCH_CLIENT_SECRET:

            print(
                "❌ TWITCH_CLIENT_SECRET was not found."
            )

            return None


        # --------------------------------------------------
        # REQUEST TOKEN
        # --------------------------------------------------

        payload = {
            "client_id": (
                TWITCH_CLIENT_ID
            ),

            "client_secret": (
                TWITCH_CLIENT_SECRET
            ),

            "grant_type": (
                "client_credentials"
            )
        }


        try:

            async with aiohttp.ClientSession() as session:

                async with session.post(
                    TWITCH_TOKEN_URL,
                    data=payload
                ) as response:

                    data = await response.json()


                    if response.status != 200:

                        print(
                            "❌ Twitch authentication failed:"
                        )

                        print(
                            data
                        )

                        return None


        except Exception as error:

            print(
                "❌ Twitch authentication error:"
            )

            print(
                error
            )

            return None


        self.access_token = (
            data.get(
                "access_token"
            )
        )


        expires_in = (
            data.get(
                "expires_in",
                0
            )
        )


        # Refresh slightly before expiration.

        self.token_expires_at = (

            time.time()

            +

            expires_in

            -

            60

        )


        return self.access_token


    # ======================================================
    # GET STREAM INFORMATION
    # ======================================================

    async def get_stream_data(
        self,
        streamer_login
    ):

        access_token = (
            await self.get_access_token()
        )


        if access_token is None:

            return None


        headers = {

            "Client-ID": (
                TWITCH_CLIENT_ID
            ),

            "Authorization": (
                f"Bearer {access_token}"
            )

        }


        params = {

            "user_login": (
                streamer_login
            )

        }


        try:

            async with aiohttp.ClientSession() as session:

                async with session.get(
                    TWITCH_STREAMS_URL,
                    headers=headers,
                    params=params
                ) as response:

                    if response.status != 200:

                        return None


                    data = await response.json()


        except Exception as error:

            print(
                "❌ Twitch stream check error:"
            )

            print(
                error
            )

            return None


        streams = (
            data.get(
                "data",
                []
            )
        )


        if not streams:

            return None


        return streams[0]


    # ======================================================
    # GET USER INFORMATION
    # ======================================================

    async def get_user_data(
        self,
        streamer_login
    ):

        access_token = (
            await self.get_access_token()
        )


        if access_token is None:

            return None


        headers = {

            "Client-ID": (
                TWITCH_CLIENT_ID
            ),

            "Authorization": (
                f"Bearer {access_token}"
            )

        }


        params = {

            "login": (
                streamer_login
            )

        }


        try:

            async with aiohttp.ClientSession() as session:

                async with session.get(
                    TWITCH_USERS_URL,
                    headers=headers,
                    params=params
                ) as response:

                    if response.status != 200:

                        return None


                    data = await response.json()


        except Exception:

            return None


        users = (
            data.get(
                "data",
                []
            )
        )


        if not users:

            return None


        return users[0]


    # ======================================================
    # TWITCH CHECK LOOP
    # ======================================================

    @tasks.loop(
        minutes=CHECK_INTERVAL_MINUTES
    )
    async def check_twitch_streams(self):

        streamers = (
            self.get_streamers()
        )


        for (

            guild_id,

            streamer_login,

            channel_id,

            last_stream_id

        ) in streamers:


            # ------------------------------------------------
            # GET GUILD
            # ------------------------------------------------

            guild = (
                self.bot.get_guild(
                    guild_id
                )
            )


            if guild is None:

                continue


            # ------------------------------------------------
            # GET CHANNEL
            # ------------------------------------------------

            channel = (
                guild.get_channel(
                    channel_id
                )
            )


            if channel is None:

                continue


            # ------------------------------------------------
            # CHECK STREAM
            # ------------------------------------------------

            stream = (
                await self.get_stream_data(
                    streamer_login
                )
            )


            # Streamer is offline.

            if stream is None:

                continue


            stream_id = (
                stream.get(
                    "id"
                )
            )


            # Already notified for this stream.

            if (
                stream_id
                ==
                last_stream_id
            ):

                continue


            # ------------------------------------------------
            # USER INFORMATION
            # ------------------------------------------------

            user_data = (
                await self.get_user_data(
                    streamer_login
                )
            )


            display_name = (
                stream.get(
                    "user_name",
                    streamer_login
                )
            )


            profile_image = None


            if user_data is not None:

                profile_image = (
                    user_data.get(
                        "profile_image_url"
                    )
                )


            # ------------------------------------------------
            # STREAM DATA
            # ------------------------------------------------

            stream_title = (
                stream.get(
                    "title",
                    "No stream title"
                )
            )


            game_name = (
                stream.get(
                    "game_name",
                    "Unknown Game"
                )
            )


            viewer_count = (
                stream.get(
                    "viewer_count",
                    0
                )
            )


            thumbnail_url = (
                stream.get(
                    "thumbnail_url"
                )
            )


            if thumbnail_url:

                thumbnail_url = (
                    thumbnail_url
                    .replace(
                        "{width}",
                        "1280"
                    )
                    .replace(
                        "{height}",
                        "720"
                    )
                )


            stream_url = (
                f"https://www.twitch.tv/"
                f"{streamer_login}"
            )


            # ------------------------------------------------
            # CREATE EMBED
            # ------------------------------------------------

            embed = discord.Embed(

                title=(
                    f"🔴 {display_name} is LIVE!"
                ),

                description=(
                    f"**{stream_title}**"
                ),

                url=stream_url,

                color=EMBED_COLOR

            )


            embed.add_field(

                name="🎮 Playing",

                value=game_name,

                inline=True

            )


            embed.add_field(

                name="👀 Viewers",

                value=f"{viewer_count:,}",

                inline=True

            )


            embed.add_field(

                name="📺 Watch Now",

                value=(
                    f"[Click here to watch "
                    f"{display_name} on Twitch]"
                    f"({stream_url})"
                ),

                inline=False

            )


            if thumbnail_url:

                embed.set_image(
                    url=thumbnail_url
                )


            if profile_image:

                embed.set_thumbnail(
                    url=profile_image
                )


            embed.set_footer(
                text=(
                    "Grid Guardian • Twitch Notifications"
                )
            )


            # ------------------------------------------------
            # SEND NOTIFICATION
            # ------------------------------------------------

            try:

                await channel.send(
                    content=(
                        f"🔴 **{display_name} "
                        f"is now LIVE on Twitch!**"
                    ),

                    embed=embed
                )


                # Save the stream ID so we don't
                # announce the same stream again.

                self.update_last_stream(

                    guild_id,

                    streamer_login,

                    stream_id

                )


                print(
                    f"🔴 Twitch notification sent: "
                    f"{streamer_login}"
                )


            except discord.HTTPException as error:

                print(
                    "❌ Could not send Twitch "
                    "notification:"
                )

                print(
                    error
                )


            # Small delay to avoid hitting the API
            # too quickly if many streamers are tracked.

            await asyncio.sleep(
                0.5
            )


    # ======================================================
    # BEFORE LOOP
    # ======================================================

    @check_twitch_streams.before_loop
    async def before_check_twitch_streams(self):

        await self.bot.wait_until_ready()


    # ======================================================
    # ADD TWITCH STREAMER
    # ======================================================

    @commands.command(
        name="twitchadd",
        aliases=[
            "addtwitch",
            "tracktwitch"
        ]
    )
    @commands.has_permissions(
        administrator=True
    )
    async def twitchadd(
        self,
        ctx,
        streamer_login,
        channel: discord.TextChannel = None
    ):

        # Use the current channel if another
        # channel isn't specified.

        if channel is None:

            channel = ctx.channel


        streamer_login = (
            streamer_login
            .strip()
            .lower()
        )


        # Check that the Twitch user exists.

        user_data = (
            await self.get_user_data(
                streamer_login
            )
        )


        if user_data is None:

            return await ctx.send(
                "❌ I couldn't find that Twitch account.\n\n"
                "**Example:**\n"
                "`!twitchadd shroud #live-notifications`"
            )


        self.add_streamer(

            ctx.guild.id,

            streamer_login,

            channel.id

        )


        display_name = (
            user_data.get(
                "display_name",
                streamer_login
            )
        )


        embed = discord.Embed(

            title="✅ Twitch Notifications Enabled",

            description=(
                f"Grid Guardian will now watch "
                f"**{display_name}**."
            ),

            color=EMBED_COLOR

        )


        embed.add_field(

            name="📺 Twitch Channel",

            value=(
                f"https://www.twitch.tv/"
                f"{streamer_login}"
            ),

            inline=False

        )


        embed.add_field(

            name="📢 Notifications Channel",

            value=channel.mention,

            inline=False

        )


        embed.set_footer(

            text=(
                "Grid Guardian • Twitch Notifications"
            )

        )


        await ctx.send(
            embed=embed
        )


    # ======================================================
    # REMOVE TWITCH STREAMER
    # ======================================================

    @commands.command(
        name="twitchremove",
        aliases=[
            "removetwitch",
            "untwitch"
        ]
    )
    @commands.has_permissions(
        administrator=True
    )
    async def twitchremove(
        self,
        ctx,
        streamer_login
    ):

        removed = (
            self.remove_streamer(

                ctx.guild.id,

                streamer_login

            )
        )


        if not removed:

            return await ctx.send(
                f"❌ **{streamer_login}** "
                "isn't currently being tracked."
            )


        await ctx.send(
            f"✅ Stopped tracking "
            f"**{streamer_login}**."
        )


    # ======================================================
    # LIST TWITCH STREAMERS
    # ======================================================

    @commands.command(
        name="twitchlist",
        aliases=[
            "twitchstreamers"
        ]
    )
    @commands.has_permissions(
        administrator=True
    )
    async def twitchlist(
        self,
        ctx
    ):

        streamers = [
            streamer

            for streamer in (
                self.get_streamers()
            )

            if (
                streamer[0]
                ==
                ctx.guild.id
            )
        ]


        if not streamers:

            return await ctx.send(
                "❌ No Twitch streamers are being "
                "tracked in this server."
            )


        embed = discord.Embed(

            title="📺 Tracked Twitch Streamers",

            color=EMBED_COLOR

        )


        for (

            guild_id,

            streamer_login,

            channel_id,

            last_stream_id

        ) in streamers:


            channel = (
                ctx.guild.get_channel(
                    channel_id
                )
            )


            channel_name = (

                channel.mention

                if channel is not None

                else "❌ Channel not found"

            )


            embed.add_field(

                name=(
                    f"🔴 {streamer_login}"
                ),

                value=(
                    f"Notifications: "
                    f"{channel_name}"
                ),

                inline=False

            )


        embed.set_footer(

            text=(
                "Grid Guardian • Twitch Notifications"
            )

        )


        await ctx.send(
            embed=embed
        )


# ==========================================================
# SETUP
# ==========================================================

async def setup(bot):

    await bot.add_cog(
        Twitch(bot)
    )