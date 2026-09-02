import asyncio
import sqlite3

import discord
from discord.ext import commands, tasks
from googleapiclient.discovery import build

EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)

YOUTUBE_HANDLE = "wattasticc"
CHECK_INTERVAL = 5  # minutes

db = sqlite3.connect("gridguardian.db")
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS youtube_settings (
    guild_id INTEGER PRIMARY KEY,
    channel_id INTEGER,
    youtube_channel_id TEXT,
    last_video_id TEXT
)
""")

db.commit()


class YouTube(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        self.youtube_api_key = None
        self.youtube = None
        self.channel_id = None

        self.youtube_check.start()

    def cog_unload(self):
        self.youtube_check.cancel()

    # =========================================================
    # GET YOUTUBE CHANNEL
    # =========================================================

    async def get_youtube_channel(self):

        if self.youtube is None:
            return None

        try:
            request = self.youtube.channels().list(
                part="id,snippet,contentDetails",
                forHandle=YOUTUBE_HANDLE
            )

            response = await asyncio.to_thread(
                request.execute
            )

            items = response.get("items", [])

            if not items:
                print(
                    f"❌ Could not find YouTube channel "
                    f"@{YOUTUBE_HANDLE}"
                )
                return None

            return items[0]

        except Exception as error:

            print(
                f"❌ YouTube API error: {error}"
            )

            return None

    # =========================================================
    # FIND NEW VIDEO
    # =========================================================

    async def get_latest_video(self, channel):

        try:

            uploads_playlist = (
                channel["contentDetails"]
                ["relatedPlaylists"]
                ["uploads"]
            )

            request = self.youtube.playlistItems().list(
                part="snippet",
                playlistId=uploads_playlist,
                maxResults=1
            )

            response = await asyncio.to_thread(
                request.execute
            )

            items = response.get("items", [])

            if not items:
                return None

            item = items[0]

            video_id = (
                item["snippet"]
                ["resourceId"]
                ["videoId"]
            )

            title = item["snippet"]["title"]

            thumbnail = (
                item["snippet"]
                ["thumbnails"]
                .get(
                    "maxres",
                    item["snippet"]
                    ["thumbnails"]
                    .get("high")
                )
            )

            thumbnail_url = (
                thumbnail["url"]
                if thumbnail
                else None
            )

            published_at = (
                item["snippet"]["publishedAt"]
            )

            return {
                "id": video_id,
                "title": title,
                "thumbnail": thumbnail_url,
                "published_at": published_at
            }

        except Exception as error:

            print(
                f"❌ Error getting latest YouTube video: "
                f"{error}"
            )

            return None

    # =========================================================
    # CHECK YOUTUBE
    # =========================================================

    @tasks.loop(minutes=CHECK_INTERVAL)
    async def youtube_check(self):

        await self.bot.wait_until_ready()

        if self.youtube is None:
            return

        channel = await self.get_youtube_channel()

        if channel is None:
            return

        video = await self.get_latest_video(channel)

        if video is None:
            return

        cursor.execute("""
        SELECT guild_id, channel_id, last_video_id
        FROM youtube_settings
        WHERE youtube_channel_id=?
        """, (channel["id"],))

        settings = cursor.fetchall()

        for guild_id, discord_channel_id, last_video_id in settings:

            discord_guild = self.bot.get_guild(guild_id)

            if discord_guild is None:
                continue

            discord_channel = discord_guild.get_channel(
                discord_channel_id
            )

            if discord_channel is None:
                continue

            # First time setup:
            # Remember the current video without announcing it.
            if last_video_id is None:

                cursor.execute("""
                UPDATE youtube_settings
                SET last_video_id=?
                WHERE guild_id=?
                """, (
                    video["id"],
                    guild_id
                ))

                db.commit()

                continue

            # Nothing new
            if last_video_id == video["id"]:
                continue

            # =================================================
            # FIND NOTIFICATION ROLE
            # =================================================

            role = discord.utils.get(
                discord_guild.roles,
                name="YouTube Notifications"
            )

            role_mention = (
                role.mention
                if role
                else ""
            )

            # =================================================
            # CREATE EMBED
            # =================================================

            embed = discord.Embed(
                title="▶️ New YouTube Video!",
                description=(
                    f"**{video['title']}**\n\n"
                    f"[🎬 Watch the video]"
                    f"(https://www.youtube.com/watch?v="
                    f"{video['id']})"
                ),
                color=EMBED_COLOR
            )

            embed.set_author(
                name="Wattasticc"
            )

            if video["thumbnail"]:
                embed.set_image(
                    url=video["thumbnail"]
                )

            embed.set_footer(
                text="Grid Guardian • YouTube"
            )

            # =================================================
            # SEND NOTIFICATION
            # =================================================

            try:

                await discord_channel.send(
                    content=role_mention,
                    embed=embed
                )

                print(
                    f"✅ New YouTube video announced: "
                    f"{video['title']}"
                )

            except discord.Forbidden:

                print(
                    f"❌ Missing permissions in "
                    f"#{discord_channel.name}"
                )

                continue

            # =================================================
            # SAVE VIDEO ID
            # =================================================

            cursor.execute("""
            UPDATE youtube_settings
            SET last_video_id=?
            WHERE guild_id=?
            """, (
                video["id"],
                guild_id
            ))

            db.commit()

    # =========================================================
    # SET YOUTUBE NOTIFICATION CHANNEL
    # =========================================================

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setyoutube(
        self,
        ctx,
        channel: discord.TextChannel
    ):

        youtube_channel = (
            await self.get_youtube_channel()
        )

        if youtube_channel is None:

            return await ctx.send(
                "❌ I couldn't find the YouTube channel "
                f"@{YOUTUBE_HANDLE}."
            )

        cursor.execute("""
        INSERT OR REPLACE INTO youtube_settings
        VALUES (?, ?, ?, ?)
        """, (
            ctx.guild.id,
            channel.id,
            youtube_channel["id"],
            None
        ))

        db.commit()

        # =====================================================
        # INITIALIZE WITHOUT ANNOUNCING OLD VIDEO
        # =====================================================

        latest_video = await self.get_latest_video(
            youtube_channel
        )

        if latest_video:

            cursor.execute("""
            UPDATE youtube_settings
            SET last_video_id=?
            WHERE guild_id=?
            """, (
                latest_video["id"],
                ctx.guild.id
            ))

            db.commit()

        embed = discord.Embed(
            title="✅ YouTube Notifications Enabled",
            description=(
                f"New uploads from **@{YOUTUBE_HANDLE}** "
                f"will now be announced in {channel.mention}."
            ),
            color=discord.Color.green()
        )

        await ctx.send(embed=embed)

    # =========================================================
    # YOUTUBE STATUS
    # =========================================================

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def youtubestatus(self, ctx):

        cursor.execute("""
        SELECT channel_id, last_video_id
        FROM youtube_settings
        WHERE guild_id=?
        """, (ctx.guild.id,))

        data = cursor.fetchone()

        if data is None:

            return await ctx.send(
                "⚠️ YouTube notifications aren't configured."
            )

        channel_id, last_video_id = data

        channel = ctx.guild.get_channel(channel_id)

        embed = discord.Embed(
            title="▶️ YouTube Notification Status",
            color=EMBED_COLOR
        )

        embed.add_field(
            name="Channel",
            value=(
                channel.mention
                if channel
                else "Channel not found"
            ),
            inline=False
        )

        embed.add_field(
            name="YouTube",
            value=f"@{YOUTUBE_HANDLE}",
            inline=False
        )

        embed.add_field(
            name="Monitoring",
            value="🟢 Active",
            inline=False
        )

        embed.set_footer(
            text="Checks for new uploads every 5 minutes."
        )

        await ctx.send(embed=embed)


# =========================================================
# SETUP
# =========================================================

async def setup(bot):

    cog = YouTube(bot)

    # =====================================================
    # YOUTUBE API
    # =====================================================

    import os

    api_key = os.getenv("YOUTUBE_API_KEY")

    if not api_key:

        print(
            "❌ YOUTUBE_API_KEY is missing from .env"
        )

        return

    cog.youtube_api_key = api_key

    cog.youtube = build(
        "youtube",
        "v3",
        developerKey=api_key
    )

    await bot.add_cog(cog)

    print("✅ YouTube API connected")