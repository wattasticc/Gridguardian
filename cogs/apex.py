import os
import asyncio

import aiohttp
import discord
from discord.ext import commands


# ==========================================================
# CONFIGURATION
# ==========================================================

EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)

API_BASE_URL = "https://api.apexlegendsstatus.com"

APEX_API_KEY = os.getenv("APEX_API_KEY")


# ==========================================================
# HELPER FUNCTIONS
# ==========================================================

def format_number(value):
    if value is None:
        return "Unknown"

    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value)


def get_platform(platform):
    platforms = {
        "pc": "PC",
        "computer": "PC",
        "steam": "PC",
        "origin": "PC",

        "ps": "PS4",
        "ps4": "PS4",
        "ps5": "PS4",
        "playstation": "PS4",

        "xbox": "X1",
        "x1": "X1",

        "switch": "SWITCH",
        "nintendo": "SWITCH",
    }

    return platforms.get(platform.lower())


def find_stat(data, stat_name):
    stat_name = stat_name.lower()

    global_data = data.get("global", {})
    rank_data = global_data.get("rank", {})

    if stat_name in rank_data:
        return rank_data.get(stat_name)

    legends = data.get("legends", {})
    all_legends = legends.get("all", {})

    if not isinstance(all_legends, dict):
        return None

    for legend_data in all_legends.values():

        if not isinstance(legend_data, dict):
            continue

        trackers = legend_data.get("data", [])

        if not isinstance(trackers, list):
            continue

        for tracker in trackers:

            if not isinstance(tracker, dict):
                continue

            name = str(
                tracker.get("name", "")
            ).lower()

            key = str(
                tracker.get("key", "")
            ).lower()

            if (
                stat_name in name
                or stat_name in key
            ):
                return tracker.get("value")

    return None


# ==========================================================
# APEX COG
# ==========================================================

class Apex(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        # Prevent multiple API requests from happening
        # simultaneously.
        self.request_lock = asyncio.Lock()

        print("🎮 Apex cog loaded.")

        if APEX_API_KEY:
            print("✅ APEX_API_KEY detected.")
        else:
            print("❌ APEX_API_KEY is missing.")

    # ======================================================
    # API REQUEST
    # ======================================================

    async def api_request(
        self,
        endpoint,
        params=None
    ):
        if not APEX_API_KEY:
            return None, (
                "❌ `APEX_API_KEY` is missing from Railway "
                "Variables."
            )

        if params is None:
            params = {}

        # --------------------------------------------------
        # IMPORTANT:
        # Current Apex Legends Status API documentation
        # supports authentication through:
        #
        # ?auth=YOUR_API_KEY
        #
        # We also send Authorization as a fallback.
        # --------------------------------------------------

        params = dict(params)
        params["auth"] = APEX_API_KEY

        url = f"{API_BASE_URL}{endpoint}"

        headers = {
            "Authorization": APEX_API_KEY,
            "Accept": "application/json",
            "User-Agent": "GridGuardian/1.0",
        }

        try:

            async with self.request_lock:

                async with aiohttp.ClientSession(
                    headers=headers
                ) as session:

                    async with session.get(
                        url,
                        params=params,
                        timeout=aiohttp.ClientTimeout(
                            total=20
                        )
                    ) as response:

                        response_text = await response.text()

                        print(
                            f"📡 Apex API: "
                            f"{response.status} "
                            f"{endpoint}"
                        )

                        # ----------------------------------
                        # SUCCESS
                        # ----------------------------------

                        if response.status == 200:

                            try:

                                data = await response.json(
                                    content_type=None
                                )

                                return data, None

                            except Exception as error:

                                print(
                                    "❌ Apex API returned "
                                    f"invalid JSON: {error}"
                                )

                                print(
                                    "Response:"
                                    f" {response_text[:1000]}"
                                )

                                return None, (
                                    "❌ The Apex API returned "
                                    "invalid data."
                                )

                        # ----------------------------------
                        # ERROR CODES
                        # ----------------------------------

                        if response.status == 400:

                            return None, (
                                "⚠️ The Apex API asked you "
                                "to try again in a few "
                                "minutes."
                            )

                        if response.status == 403:

                            return None, (
                                "❌ The Apex API rejected "
                                "your API key.\n\n"
                                "Check that `APEX_API_KEY` "
                                "in Railway is correct."
                            )

                        if response.status == 404:

                            return None, (
                                "❌ The requested Apex "
                                "player/data could not "
                                "be found."
                            )

                        if response.status == 405:

                            return None, (
                                "❌ The Apex API reported "
                                "an external API error "
                                "(HTTP 405)."
                            )

                        if response.status == 406:

                            print(
                                "❌ Apex API returned HTTP 406."
                            )

                            print(
                                f"URL: {url}"
                            )

                            print(
                                f"Endpoint: {endpoint}"
                            )

                            print(
                                "Response:"
                                f" {response_text[:2000]}"
                            )

                            return None, (
                                "❌ The Apex API returned "
                                "HTTP 406 (Not Acceptable)."
                            )

                        if response.status == 410:

                            return None, (
                                "❌ That Apex platform "
                                "isn't supported."
                            )

                        if response.status == 429:

                            return None, (
                                "⚠️ The Apex API rate limit "
                                "was reached. Please wait "
                                "a moment."
                            )

                        if response.status == 500:

                            return None, (
                                "❌ The Apex API encountered "
                                "an internal error."
                            )

                        print(
                            "❌ Unexpected Apex API response:"
                            f" {response.status}"
                        )

                        print(
                            f"Response: {response_text[:1000]}"
                        )

                        return None, (
                            f"❌ Apex API error: "
                            f"HTTP {response.status}"
                        )

        except asyncio.TimeoutError:

            return None, (
                "⚠️ The Apex API took too long "
                "to respond."
            )

        except aiohttp.ClientError as error:

            print(
                f"❌ Apex API connection error: {error}"
            )

            return None, (
                "❌ Couldn't connect to the Apex API."
            )

        except Exception as error:

            print(
                f"❌ Unexpected Apex API error: {error}"
            )

            return None, (
                "❌ An unexpected error occurred "
                "while contacting the Apex API."
            )

    # ======================================================
    # PLAYER STATS
    # ======================================================

    @commands.command(
        name="apexstats",
        aliases=[
            "apexplayer",
            "playerstats"
        ]
    )
    async def apexstats(
        self,
        ctx,
        platform,
        *,
        player
    ):

        converted_platform = get_platform(platform)

        if converted_platform is None:

            return await ctx.send(
                "❌ Invalid platform.\n\n"
                "**Available platforms:**\n"
                "`PC`, `PS4`, `Xbox`, `Switch`"
            )

        async with ctx.typing():

            data, error = await self.api_request(
                "/bridge",
                {
                    "player": player,
                    "platform": converted_platform,
                    "version": 5
                }
            )

        if error:
            return await ctx.send(error)

        if not isinstance(data, dict):

            return await ctx.send(
                "❌ The Apex API returned unexpected data."
            )

        global_data = data.get(
            "global",
            {}
        )

        rank_data = global_data.get(
            "rank",
            {}
        )

        rank_name = rank_data.get(
            "rankName",
            "Unranked"
        )

        rank_division = rank_data.get(
            "rankDiv",
            ""
        )

        rank_score = rank_data.get(
            "rankScore",
            0
        )

        level = global_data.get(
            "level",
            "Unknown"
        )

        player_name = global_data.get(
            "name",
            player
        )

        platform_name = global_data.get(
            "platform",
            converted_platform
        )

        avatar = global_data.get(
            "avatar"
        )

        kills = find_stat(
            data,
            "kills"
        )

        damage = find_stat(
            data,
            "damage"
        )

        wins = find_stat(
            data,
            "wins"
        )

        rank_text = str(rank_name)

        if rank_division:
            rank_text += f" {rank_division}"

        embed = discord.Embed(
            title="🎮 Apex Legends Player Stats",
            description=(
                f"Statistics for **{player_name}**"
            ),
            color=EMBED_COLOR
        )

        if avatar:

            embed.set_thumbnail(
                url=avatar
            )

        embed.add_field(
            name="🖥️ Platform",
            value=str(platform_name),
            inline=True
        )

        embed.add_field(
            name="⭐ Level",
            value=format_number(level),
            inline=True
        )

        embed.add_field(
            name="🏆 Rank",
            value=rank_text,
            inline=True
        )

        embed.add_field(
            name="📈 RP",
            value=format_number(rank_score),
            inline=True
        )

        embed.add_field(
            name="💀 Kills",
            value=format_number(kills),
            inline=True
        )

        embed.add_field(
            name="🏅 Wins",
            value=format_number(wins),
            inline=True
        )

        embed.add_field(
            name="💥 Damage",
            value=format_number(damage),
            inline=True
        )

        embed.set_footer(
            text="Data provided by Apex Legends Status"
        )

        await ctx.send(
            embed=embed
        )

    # ======================================================
    # MAP ROTATION
    # !apexmap
    # !maprotation
    # !maps
    # ======================================================

    @commands.command(
        name="apexmap",
        aliases=[
            "maprotation",
            "maps"
        ]
    )
    async def apexmap(self, ctx):

        async with ctx.typing():

            data, error = await self.api_request(
                "/maprotation",
                {
                    "version": 2
                }
            )

        if error:
            return await ctx.send(error)

        if not isinstance(data, dict):

            return await ctx.send(
                "❌ The Apex API returned unexpected "
                "map data."
            )

        embed = discord.Embed(
            title="🗺️ Apex Legends Map Rotation",
            description=(
                "Current and upcoming Apex Legends maps."
            ),
            color=EMBED_COLOR
        )

        displayed = 0

        # --------------------------------------------------
        # API returns different mode names depending on
        # the current API data.
        # --------------------------------------------------

        for mode_name, mode_data in data.items():

            if not isinstance(
                mode_data,
                dict
            ):
                continue

            current = mode_data.get(
                "current",
                {}
            )

            next_map = mode_data.get(
                "next",
                {}
            )

            if not isinstance(
                current,
                dict
            ):
                current = {}

            if not isinstance(
                next_map,
                dict
            ):
                next_map = {}

            current_map = current.get(
                "map"
            )

            next_map_name = next_map.get(
                "map"
            )

            if not current_map and not next_map_name:
                continue

            value = (
                f"**Now:** "
                f"{current_map or 'Unknown'}\n"
                f"**Next:** "
                f"{next_map_name or 'Unknown'}"
            )

            embed.add_field(
                name=mode_name.replace(
                    "_",
                    " "
                ).title(),
                value=value,
                inline=False
            )

            displayed += 1

        if displayed == 0:

            # Some API versions can return a different
            # structure. Show the raw response so we can
            # diagnose it instead of silently failing.
            embed.description = (
                "⚠️ The API responded, but its map "
                "data format was different than expected."
            )

            embed.add_field(
                name="API Response",
                value=(
                    "```json\n"
                    f"{str(data)[:3500]}"
                    "\n```"
                ),
                inline=False
            )

        embed.set_footer(
            text="Data provided by Apex Legends Status"
        )

        await ctx.send(
            embed=embed
        )

    # ======================================================
    # PREDATOR RP
    # ======================================================

    @commands.command(
        name="predator",
        aliases=[
            "predrp",
            "predatorrp"
        ]
    )
    async def predator(self, ctx):

        async with ctx.typing():

            data, error = await self.api_request(
                "/predator"
            )

        if error:
            return await ctx.send(error)

        if not isinstance(data, dict):

            return await ctx.send(
                "❌ The Apex API returned unexpected "
                "Predator data."
            )

        embed = discord.Embed(
            title="👑 Apex Predator Thresholds",
            description=(
                "Current RP/AP requirements for "
                "Apex Predator."
            ),
            color=EMBED_COLOR
        )

        rp_data = data.get(
            "RP",
            {}
        )

        if not isinstance(
            rp_data,
            dict
        ):
            rp_data = {}

        platforms = {
            "🖥️ PC": rp_data.get("PC"),
            "🎮 PlayStation": rp_data.get("PS4"),
            "🎮 Xbox": rp_data.get("X1"),
            "🎮 Switch": rp_data.get("SWITCH"),
        }

        added = False

        for name, platform_data in platforms.items():

            if not isinstance(
                platform_data,
                dict
            ):
                continue

            value = platform_data.get(
                "val"
            )

            total_masters = platform_data.get(
                "totalMasters"
            )

            if value is None:
                continue

            text = (
                f"**Required RP:** "
                f"{format_number(value)}"
            )

            if total_masters is not None:

                text += (
                    f"\n**Masters:** "
                    f"{format_number(total_masters)}"
                )

            embed.add_field(
                name=name,
                value=text,
                inline=True
            )

            added = True

        if not added:

            embed.description = (
                "⚠️ The API responded, but the "
                "Predator data format changed."
            )

            embed.add_field(
                name="API Response",
                value=(
                    "```json\n"
                    f"{str(data)[:3500]}"
                    "\n```"
                ),
                inline=False
            )

        embed.set_footer(
            text="Data provided by Apex Legends Status"
        )

        await ctx.send(
            embed=embed
        )

    # ======================================================
    # SERVER STATUS
    # ======================================================

    @commands.command(
        name="apexservers",
        aliases=[
            "apexserverstatus",
            "serverstatus"
        ]
    )
    async def apexservers(self, ctx):

        async with ctx.typing():

            data, error = await self.api_request(
                "/servers"
            )

        if error:
            return await ctx.send(error)

        if not isinstance(data, dict):

            return await ctx.send(
                "❌ The Apex API returned unexpected "
                "server data."
            )

        embed = discord.Embed(
            title="🟢 Apex Legends Server Status",
            description=(
                "Current Apex Legends service status."
            ),
            color=EMBED_COLOR
        )

        displayed = 0

        # --------------------------------------------------
        # The server endpoint can contain several nested
        # service categories.
        # --------------------------------------------------

        for name, value in data.items():

            if displayed >= 12:
                break

            if not isinstance(
                value,
                dict
            ):
                continue

            status = (
                value.get("Status")
                or value.get("status")
                or value.get("State")
                or value.get("state")
            )

            if isinstance(
                status,
                dict
            ):
                status = (
                    status.get("Status")
                    or status.get("status")
                    or str(status)
                )

            if status is None:
                continue

            status_text = str(status)

            # Pick an indicator.
            lower_status = status_text.lower()

            if any(
                word in lower_status
                for word in [
                    "running",
                    "online",
                    "operational",
                    "up"
                ]
            ):
                indicator = "🟢"

            elif any(
                word in lower_status
                for word in [
                    "partial",
                    "slow",
                    "degraded"
                ]
            ):
                indicator = "🟡"

            else:
                indicator = "🔴"

            embed.add_field(
                name=(
                    f"{indicator} "
                    f"{name.replace('_', ' ').title()}"
                ),
                value=status_text[:200],
                inline=True
            )

            displayed += 1

        if displayed == 0:

            embed.description = (
                "⚠️ The API responded, but the "
                "server-status format changed."
            )

            embed.add_field(
                name="API Response",
                value=(
                    "```json\n"
                    f"{str(data)[:3500]}"
                    "\n```"
                ),
                inline=False
            )

        embed.set_footer(
            text="Data provided by Apex Legends Status"
        )

        await ctx.send(
            embed=embed
        )

    # ======================================================
    # PLAYER UID
    # ======================================================

    @commands.command(
        name="apexuid",
        aliases=[
            "playeruid"
        ]
    )
    async def apexuid(
        self,
        ctx,
        platform,
        *,
        player
    ):

        converted_platform = get_platform(platform)

        if converted_platform is None:

            return await ctx.send(
                "❌ Invalid platform.\n"
                "Use `PC`, `PS4`, `Xbox`, or `Switch`."
            )

        async with ctx.typing():

            data, error = await self.api_request(
                "/nametouid",
                {
                    "player": player,
                    "platform": converted_platform
                }
            )

        if error:
            return await ctx.send(error)

        if not isinstance(data, dict):

            return await ctx.send(
                "❌ The Apex API returned unexpected "
                "UID data."
            )

        uid = (
            data.get("uid")
            or data.get("UID")
            or data.get("id")
        )

        embed = discord.Embed(
            title="🆔 Apex Player UID",
            color=EMBED_COLOR
        )

        embed.add_field(
            name="Player",
            value=player,
            inline=True
        )

        embed.add_field(
            name="Platform",
            value=converted_platform,
            inline=True
        )

        embed.add_field(
            name="UID",
            value=(
                f"`{uid}`"
                if uid
                else "Not returned by API"
            ),
            inline=False
        )

        embed.set_footer(
            text="Data provided by Apex Legends Status"
        )

        await ctx.send(
            embed=embed
        )

    # ======================================================
    # APEX HELP
    # ======================================================

    @commands.command(
        name="apexhelp"
    )
    async def apexhelp(self, ctx):

        embed = discord.Embed(
            title="🎮 Grid Guardian — Apex Commands",
            description=(
                "Commands powered by live Apex Legends data."
            ),
            color=EMBED_COLOR
        )

        embed.add_field(
            name="📊 Player Stats",
            value=(
                "`!apexstats PC PlayerName`\n"
                "`!apexstats PS4 PlayerName`\n"
                "`!apexstats Xbox PlayerName`\n"
                "`!apexstats Switch PlayerName`"
            ),
            inline=False
        )

        embed.add_field(
            name="🗺️ Map Rotation",
            value=(
                "`!apexmap`\n"
                "`!maps`\n"
                "`!maprotation`"
            ),
            inline=True
        )

        embed.add_field(
            name="👑 Predator RP",
            value=(
                "`!predator`\n"
                "`!predrp`"
            ),
            inline=True
        )

        embed.add_field(
            name="🟢 Server Status",
            value=(
                "`!apexservers`\n"
                "`!serverstatus`"
            ),
            inline=True
        )

        embed.add_field(
            name="🆔 Player UID",
            value=(
                "`!apexuid PC PlayerName`"
            ),
            inline=False
        )

        embed.set_footer(
            text="Grid Guardian • Apex Legends Status API"
        )

        await ctx.send(
            embed=embed
        )


# ==========================================================
# SETUP
# ==========================================================

async def setup(bot):

    await bot.add_cog(
        Apex(bot)
    )

    print("✅ Apex cog loaded successfully.")