import asyncio
import re
import sqlite3
from datetime import datetime
from html import unescape
from urllib.parse import urljoin

import aiohttp
import discord
from discord.ext import commands, tasks


# =========================================================
# CONFIGURATION
# =========================================================

EA_NEWS_URL = (
    "https://www.ea.com/games/apex-legends/"
    "apex-legends/news"
)

CHECK_INTERVAL_MINUTES = 10

EMBED_COLOR = discord.Color.from_rgb(
    80,
    220,
    255
)

USER_AGENT = (
    "Grid Guardian Apex News Bot/1.0 "
    "(Discord community bot)"
)


# =========================================================
# DATABASE
# =========================================================

db = sqlite3.connect(
    "gridguardian.db",
    timeout=30,
    check_same_thread=False
)

db.execute("PRAGMA busy_timeout = 30000")
db.execute("PRAGMA journal_mode = WAL")
db.execute("PRAGMA synchronous = NORMAL")

cursor = db.cursor()


cursor.execute("""
CREATE TABLE IF NOT EXISTS apex_news_settings (
    guild_id INTEGER PRIMARY KEY,
    channel_id INTEGER,
    last_article_url TEXT,
    updated_at TEXT
)
""")

db.commit()


# =========================================================
# HELPERS
# =========================================================

def clean_text(text: str) -> str:
    """Clean HTML entities and excess whitespace."""

    if not text:
        return ""

    text = unescape(text)

    text = re.sub(
        r"<[^>]+>",
        "",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def extract_latest_article(html: str):
    """
    Extract the newest Apex Legends article from
    the official EA news page.

    Returns:
        {
            "title": str,
            "url": str,
            "category": str,
            "date": str
        }

    or None if nothing useful was found.
    """

    if not html:
        return None

    # -----------------------------------------------------
    # Find Apex article URLs.
    #
    # EA's page contains links in the form:
    # /games/apex-legends/apex-legends/news/ARTICLE
    # -----------------------------------------------------

    pattern = re.compile(
        r'href=["\']'
        r'([^"\']*?/games/apex-legends/'
        r'apex-legends/news/[^"\']+)'
        r'["\']',
        re.IGNORECASE
    )

    matches = pattern.findall(html)

    if not matches:
        return None

    # Remove duplicates while preserving order.
    article_urls = []

    for url in matches:
        full_url = urljoin(
            EA_NEWS_URL,
            unescape(url)
        )

        if full_url not in article_urls:
            article_urls.append(full_url)

    if not article_urls:
        return None

    # -----------------------------------------------------
    # The EA page is ordered newest first.
    # -----------------------------------------------------

    latest_url = article_urls[0]

    # -----------------------------------------------------
    # Try to locate the title associated with the article.
    #
    # We search around the first occurrence of the URL.
    # -----------------------------------------------------

    url_index = html.find(
        latest_url.replace(
            "https://www.ea.com",
            ""
        )
    )

    if url_index == -1:
        url_index = html.find(latest_url)

    surrounding = ""

    if url_index != -1:
        surrounding = html[
            max(0, url_index - 2500):
            min(len(html), url_index + 2500)
        ]

    # -----------------------------------------------------
    # Extract visible text around the article.
    # -----------------------------------------------------

    text_candidates = []

    for match in re.findall(
        r">([^<>]{5,300})<",
        surrounding
    ):
        cleaned = clean_text(match)

        if cleaned:
            text_candidates.append(cleaned)

    # -----------------------------------------------------
    # Remove obvious navigation/UI text.
    # -----------------------------------------------------

    ignored = {
        "read more",
        "learn more",
        "see all",
        "latest news",
        "news",
        "game updates",
        "guides",
        "apex legends",
    }

    useful_candidates = [
        text
        for text in text_candidates
        if text.lower() not in ignored
    ]

    title = (
        useful_candidates[-1]
        if useful_candidates
        else "Latest Apex Legends News"
    )

    # -----------------------------------------------------
    # Try to find a date.
    # -----------------------------------------------------

    date_match = re.search(
        r"\b("
        r"January|February|March|April|May|June|"
        r"July|August|September|October|November|December"
        r")\s+"
        r"\d{1,2},\s+\d{4}\b",
        surrounding,
        re.IGNORECASE
    )

    date_text = (
        date_match.group(0)
        if date_match
        else "Latest"
    )

    # -----------------------------------------------------
    # Try to determine the article category.
    # -----------------------------------------------------

    category = "News"

    lower_surrounding = surrounding.lower()

    if "game updates" in lower_surrounding:
        category = "Game Update"
    elif "guides" in lower_surrounding:
        category = "Guide"

    return {
        "title": title[:256],
        "url": latest_url,
        "category": category,
        "date": date_text[:100],
    }


async def fetch_latest_article():
    """Fetch the newest article from EA."""

    timeout = aiohttp.ClientTimeout(
        total=20
    )

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml"
    }

    try:
        async with aiohttp.ClientSession(
            timeout=timeout,
            headers=headers
        ) as session:

            async with session.get(
                EA_NEWS_URL
            ) as response:

                if response.status != 200:
                    print(
                        "❌ Apex News HTTP error: "
                        f"{response.status}"
                    )

                    return None

                html = await response.text(
                    errors="ignore"
                )

                return extract_latest_article(
                    html
                )

    except asyncio.TimeoutError:
        print(
            "❌ Apex News request timed out."
        )

    except aiohttp.ClientError as error:
        print(
            "❌ Apex News request failed: "
            f"{error}"
        )

    except Exception as error:
        print(
            "❌ Unexpected Apex News error: "
            f"{error}"
        )

    return None


# =========================================================
# DATABASE HELPERS
# =========================================================

def get_settings(guild_id: int):
    cursor.execute("""
    SELECT
        channel_id,
        last_article_url,
        updated_at
    FROM apex_news_settings
    WHERE guild_id=?
    """, (
        guild_id,
    ))

    row = cursor.fetchone()

    if row is None:
        return None

    return {
        "channel_id": row[0],
        "last_article_url": row[1],
        "updated_at": row[2],
    }


def save_settings(
    guild_id: int,
    channel_id: int,
    last_article_url: str | None
):
    timestamp = datetime.utcnow().isoformat()

    cursor.execute("""
    INSERT INTO apex_news_settings (
        guild_id,
        channel_id,
        last_article_url,
        updated_at
    )
    VALUES (?, ?, ?, ?)
    ON CONFLICT(guild_id)
    DO UPDATE SET
        channel_id=excluded.channel_id,
        last_article_url=excluded.last_article_url,
        updated_at=excluded.updated_at
    """, (
        guild_id,
        channel_id,
        last_article_url,
        timestamp
    ))

    db.commit()


def update_last_article(
    guild_id: int,
    article_url: str
):
    cursor.execute("""
    UPDATE apex_news_settings
    SET
        last_article_url=?,
        updated_at=?
    WHERE guild_id=?
    """, (
        article_url,
        datetime.utcnow().isoformat(),
        guild_id
    ))

    db.commit()


# =========================================================
# EMBED
# =========================================================

def create_news_embed(article):
    embed = discord.Embed(
        title="📰 Apex Legends News",
        description=(
            f"**{article['title']}**\n\n"
            f"[Read the official article →]"
            f"({article['url']})"
        ),
        color=EMBED_COLOR,
        url=article["url"]
    )

    embed.add_field(
        name="📅 Date",
        value=article["date"],
        inline=True
    )

    embed.add_field(
        name="📂 Type",
        value=article["category"],
        inline=True
    )

    embed.set_footer(
        text="Grid Guardian • Official EA Apex Legends News"
    )

    return embed


# =========================================================
# APEX NEWS COG
# =========================================================

class ApexNews(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        self.check_lock = asyncio.Lock()

        self.apex_news_loop.start()

    # =====================================================
    # COG UNLOAD
    # =====================================================

    def cog_unload(self):
        self.apex_news_loop.cancel()

    # =====================================================
    # CHECK NEWS
    # =====================================================

    @tasks.loop(
        minutes=CHECK_INTERVAL_MINUTES
    )
    async def apex_news_loop(self):

        async with self.check_lock:

            article = await fetch_latest_article()

            if not article:
                return

            cursor.execute("""
            SELECT
                guild_id,
                channel_id,
                last_article_url
            FROM apex_news_settings
            WHERE channel_id IS NOT NULL
            """)

            settings = cursor.fetchall()

            for (
                guild_id,
                channel_id,
                last_article_url
            ) in settings:

                guild = self.bot.get_guild(
                    guild_id
                )

                if guild is None:
                    continue

                channel = guild.get_channel(
                    channel_id
                )

                if not isinstance(
                    channel,
                    discord.TextChannel
                ):
                    continue

                # -------------------------------------------------
                # First setup:
                # remember the current article without announcing it
                # -------------------------------------------------

                if last_article_url is None:

                    update_last_article(
                        guild_id,
                        article["url"]
                    )

                    continue

                # -------------------------------------------------
                # Nothing new
                # -------------------------------------------------

                if last_article_url == article["url"]:
                    continue

                embed = create_news_embed(
                    article
                )

                try:

                    await channel.send(
                        embed=embed
                    )

                    update_last_article(
                        guild_id,
                        article["url"]
                    )

                    print(
                        "✅ New Apex news announced in "
                        f"{guild.name}: "
                        f"{article['title']}"
                    )

                except discord.Forbidden:

                    print(
                        "❌ Missing permission to send "
                        f"Apex news in #{channel.name} "
                        f"({guild.name})"
                    )

                except discord.HTTPException as error:

                    print(
                        "❌ Failed to send Apex news: "
                        f"{error}"
                    )

    # =====================================================
    # LOOP READY
    # =====================================================

    @apex_news_loop.before_loop
    async def before_apex_news_loop(self):

        await self.bot.wait_until_ready()

    # =====================================================
    # !APEXNEWS
    # =====================================================

    @commands.command(
        name="apexnews",
        aliases=[
            "apexnews",
            "apexupdates"
        ]
    )
    @commands.cooldown(
        1,
        15,
        commands.BucketType.user
    )
    async def apexnews(self, ctx):

        async with ctx.typing():

            article = await fetch_latest_article()

        if not article:

            return await ctx.send(
                "❌ I couldn't retrieve the latest "
                "Apex Legends news right now."
            )

        embed = create_news_embed(
            article
        )

        await ctx.send(
            embed=embed
        )

    # =====================================================
    # !SETAPEXNEWS
    # =====================================================

    @commands.command(
        name="setapexnews"
    )
    @commands.has_permissions(
        manage_guild=True
    )
    async def setapexnews(
        self,
        ctx,
        channel: discord.TextChannel
    ):

        article = await fetch_latest_article()

        if not article:

            return await ctx.send(
                "❌ I couldn't connect to the official "
                "Apex Legends news page.\n\n"
                "Try again in a moment."
            )

        # -------------------------------------------------
        # Save the latest article immediately.
        #
        # This prevents the bot from posting the current
        # article as a "new" article immediately after setup.
        # -------------------------------------------------

        save_settings(
            ctx.guild.id,
            channel.id,
            article["url"]
        )

        embed = discord.Embed(
            title="✅ Apex News Notifications Enabled",
            description=(
                f"New official Apex Legends news will now "
                f"be posted in {channel.mention}."
            ),
            color=discord.Color.green()
        )

        embed.add_field(
            name="📰 Source",
            value="Official EA Apex Legends News",
            inline=False
        )

        embed.add_field(
            name="⏱️ Checking",
            value=(
                f"Every {CHECK_INTERVAL_MINUTES} minutes"
            ),
            inline=True
        )

        embed.set_footer(
            text="Existing news will not be reposted."
        )

        await ctx.send(
            embed=embed
        )

    # =====================================================
    # !APEXNEWSSTATUS
    # =====================================================

    @commands.command(
        name="apexnewsstatus"
    )
    @commands.has_permissions(
        manage_guild=True
    )
    async def apexnewsstatus(self, ctx):

        settings = get_settings(
            ctx.guild.id
        )

        if not settings:

            return await ctx.send(
                "⚠️ Apex News notifications "
                "aren't configured."
            )

        channel = ctx.guild.get_channel(
            settings["channel_id"]
        )

        embed = discord.Embed(
            title="📰 Apex News Status",
            color=EMBED_COLOR
        )

        embed.add_field(
            name="Channel",
            value=(
                channel.mention
                if channel
                else "❌ Channel not found"
            ),
            inline=False
        )

        embed.add_field(
            name="Monitoring",
            value="🟢 Active",
            inline=True
        )

        embed.add_field(
            name="Interval",
            value=(
                f"{CHECK_INTERVAL_MINUTES} minutes"
            ),
            inline=True
        )

        embed.add_field(
            name="Last Article",
            value=(
                settings["last_article_url"]
                or "None"
            ),
            inline=False
        )

        embed.set_footer(
            text="Source: Official EA Apex Legends News"
        )

        await ctx.send(
            embed=embed
        )

    # =====================================================
    # !DISABLEAPEXNEWS
    # =====================================================

    @commands.command(
        name="disableapexnews"
    )
    @commands.has_permissions(
        manage_guild=True
    )
    async def disableapexnews(self, ctx):

        cursor.execute("""
        DELETE FROM apex_news_settings
        WHERE guild_id=?
        """, (
            ctx.guild.id,
        ))

        db.commit()

        await ctx.send(
            "✅ Apex News notifications have been disabled."
        )

    # =====================================================
    # ERROR HANDLING
    # =====================================================

    @apexnews.error
    @setapexnews.error
    @apexnewsstatus.error
    @disableapexnews.error
    async def apex_news_error(
        self,
        ctx,
        error
    ):

        if isinstance(
            error,
            commands.CommandOnCooldown
        ):

            return await ctx.send(
                "⏳ Please wait "
                f"`{error.retry_after:.1f}` seconds "
                "before using `!apexnews` again."
            )

        if isinstance(
            error,
            commands.MissingPermissions
        ):

            return await ctx.send(
                "❌ You need **Manage Server** "
                "permission to use that command."
            )

        if isinstance(
            error,
            commands.MissingRequiredArgument
        ):

            return await ctx.send(
                "❌ You're missing the channel.\n\n"
                "Example:\n"
                "`!setapexnews #apex-news`"
            )

        if isinstance(
            error,
            commands.ChannelNotFound
        ):

            return await ctx.send(
                "❌ I couldn't find that channel."
            )

        raise error


# =========================================================
# SETUP
# =========================================================

async def setup(bot):

    await bot.add_cog(
        ApexNews(bot)
    )

    print(
        "✅ Apex News Loaded"
    )