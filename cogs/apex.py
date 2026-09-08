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
    }

    return platforms.get(platform.lower())


def find_stat(data, stat_name):

    stat_name = stat_name.lower()

    # ======================================================
    # GLOBAL TRACKERS
    # ======================================================

    global_data = data.get(
        "global",
        {}
    )

    rank_data = global_data.get(
        "rank",
        {}
    )

    if stat_name in rank_data:

        return rank_data.get(
            stat_name
        )

    # ======================================================
    # LEGEND TRACKERS
    # ======================================================

    legends = data.get(
        "legends",
        {}
    )

    all_legends = legends.get(
        "all",
        {}
    )

    for legend_data in all_legends.values():

        if not isinstance(
            legend_data,
            dict
        ):
            continue

        trackers = legend_data.get(
            "data",
            []
        )

        if not isinstance(
            trackers,
            list
        ):
            continue

        for tracker in trackers:

            name = str(
                tracker.get(
                    "name",
                    ""
                )
            ).lower()

            key = str(
                tracker.get(
                    "key",
                    ""
                )
            ).lower()

            if (
                stat_name in name
                or stat_name in key
            ):

                return tracker.get(
                    "value"
                )

    return None


# ==========================================================
# APEX COG
# ==========================================================

class Apex(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        # Prevent multiple API requests
        # from happening at the same time.
        self.request_lock = asyncio.Lock()


    # ======================================================
    # API REQUEST
    # ======================================================

    async def api_request(
        self,
        endpoint,
        params=None,
        fallback_endpoint=None
    ):

        if not APEX_API_KEY:

            return None, (
                "❌ `APEX_API_KEY` is missing from "
                "your Railway variables."
            )

        if params is None:

            params = {}

        # ==================================================
        # API KEY
        # ==================================================

        # The Apex Legends Status API officially supports
        # the API key through the "auth" query parameter.
        params = dict(params)

        params["auth"] = APEX_API_KEY

        endpoints = [endpoint]

        if fallback_endpoint:

            endpoints.append(
                fallback_endpoint
            )

        try:

            async with self.request_lock:

                timeout = aiohttp.ClientTimeout(
                    total=15
                )

                async with aiohttp.ClientSession(
                    timeout=timeout
                ) as session:

                    for current_endpoint in endpoints:

                        url = (
                            f"{API_BASE_URL}"
                            f"{current_endpoint}"
                        )

                        try:

                            async with session.get(
                                url,
                                params=params,
                                headers={
                                    "Accept": "application/json",
                                    "User-Agent": (
                                        "GridGuardian/1.0"
                                    )
                                }
                            ) as response:

                                # ==================================
                                # SUCCESS
                                # ==================================

                                if response.status == 200:

                                    content_type = (
                                        response.headers.get(
                                            "Content-Type",
                                            ""
                                        )
                                    )

                                    try:

                                        data = (
                                            await response.json(
                                                content_type=None
                                            )
                                        )

                                        if isinstance(
                                            data,
                                            (dict, list)
                                        ):

                                            return data, None

                                        print(
                                            "❌ Apex API returned "
                                            "unexpected JSON data."
                                        )

                                        return None, (
                                            "❌ The Apex API returned "
                                            "unexpected data."
                                        )

                                    except Exception as error:

                                        body = await response.text()

                                        print(
                                            "❌ Apex API returned "
                                            "HTTP 200 but invalid JSON."
                                        )

                                        print(
                                            f"Content-Type: "
                                            f"{content_type}"
                                        )

                                        print(
                                            f"Response: "
                                            f"{body[:1500]}"
                                        )

                                        return None, (
                                            "❌ The Apex API returned "
                                            "invalid data."
                                        )

                                # ==================================
                                # 406
                                # ==================================

                                if response.status == 406:

                                    body = await response.text()

                                    print(
                                        "❌ Apex API returned "
                                        "HTTP 406."
                                    )

                                    print(
                                        f"URL: {url}"
                                    )

                                    print(
                                        f"Endpoint: "
                                        f"{current_endpoint}"
                                    )

                                    print(
                                        f"Response: "
                                        f"{body[:2000]}"
                                    )

                                    # Try the fallback endpoint
                                    # if one was provided.
                                    if (
                                        current_endpoint
                                        != endpoints[-1]
                                    ):

                                        print(
                                            "⚠️ Trying Apex API "
                                            "fallback endpoint..."
                                        )

                                        continue

                                    return None, (
                                        "❌ The Apex API returned "
                                        "HTTP 406 (Not Acceptable)."
                                    )

                                # ==================================
                                # 400
                                # ==================================

                                if response.status == 400:

                                    return None, (
                                        "⚠️ The Apex API asked "
                                        "you to try again in a "
                                        "few minutes."
                                    )

                                # ==================================
                                # 403
                                # ==================================

                                if response.status == 403:

                                    return None, (
                                        "❌ The Apex API key was "
                                        "rejected.\n\n"
                                        "Check the `APEX_API_KEY` "
                                        "variable in Railway."
                                    )

                                # ==================================
                                # 404
                                # ==================================

                                if response.status == 404:

                                    return None, (
                                        "❌ The requested Apex "
                                        "API resource could not "
                                        "be found."
                                    )

                                # ==================================
                                # 405
                                # ==================================

                                if response.status == 405:

                                    return None, (
                                        "❌ The Apex API reported "
                                        "an external API error "
                                        "(HTTP 405)."
                                    )

                                # ==================================
                                # 410
                                # ==================================

                                if response.status == 410:

                                    return None, (
                                        "❌ That Apex platform "
                                        "isn't supported."
                                    )

                                # ==================================
                                # 429
                                # ==================================

                                if response.status == 429:

                                    return None, (
                                        "⚠️ The Apex API rate "
                                        "limit was reached. "
                                        "Please wait a moment."
                                    )

                                # ==================================
                                # 500
                                # ==================================

                                if response.status == 500:

                                    return None, (
                                        "❌ The Apex API is "
                                        "currently experiencing "
                                        "an internal error."
                                    )

                                # ==================================
                                # OTHER ERROR
                                # ==================================

                                body = await response.text()

                                print(
                                    f"❌ Apex API HTTP "
                                    f"{response.status}"
                                )

                                print(
                                    f"URL: {url}"
                                )

                                print(
                                    f"Response: "
                                    f"{body[:1000]}"
                                )

                                return None, (
                                    f"❌ Apex API returned "
                                    f"HTTP {response.status}."
                                )

                        except asyncio.TimeoutError:

                            print(
                                f"⚠️ Apex API timeout: "
                                f"{current_endpoint}"
                            )

                            return None, (
                                "⚠️ The Apex API took too "
                                "long to respond."
                            )

        except aiohttp.ClientError as error:

            print(
                f"❌ Apex API connection error: "
                f"{error}"
            )

            return None, (
                "❌ Couldn't connect to the Apex API."
            )

        except Exception as error:

            print(
                f"❌ Unexpected Apex API error: "
                f"{error}"
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

        converted_platform = get_platform(
            platform
        )

        if converted_platform is None:

            return await ctx.send(
                "❌ Invalid platform.\n\n"
                "**Available platforms:**\n"
                "`PC`, `PS4`, or `Xbox`"
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

        if not isinstance(
            data,
            dict
        ):

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

        rank_text = rank_name

        if rank_division:

            rank_text += (
                f" {rank_division}"
            )

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
    # ======================================================

    @commands.command(
        name="apexmap",
        aliases=[
            "maprotation",
            "maps",
            "map"
        ]
    )
    async def apexmap(self, ctx):

        async with ctx.typing():

            # The .php endpoint is included because the
            # server shown in your Railway logs is currently
            # advertising it as an available variant.
            data, error = await self.api_request(
                "/maprotation.php",
                {
                    "version": 2
                },
                fallback_endpoint="/maprotation"
            )

        if error:

            return await ctx.send(error)

        if not isinstance(
            data,
            dict
        ):

            return await ctx.send(
                "❌ The Apex API returned unexpected "
                "map rotation data."
            )

        embed = discord.Embed(
            title="🗺️ Apex Legends Map Rotation",
            description=(
                "Current and upcoming Apex Legends maps."
            ),
            color=EMBED_COLOR
        )

        displayed = 0

        # ==================================================
        # MAP DATA
        # ==================================================

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

            if not current_map:

                current_map = "Unknown"

            if not next_map_name:

                next_map_name = "Unknown"

            if (
                current_map == "Unknown"
                and next_map_name == "Unknown"
            ):
                continue

            clean_name = (
                mode_name
                .replace("_", " ")
                .title()
            )

            embed.add_field(
                name=clean_name,
                value=(
                    f"**Now:** {current_map}\n"
                    f"**Next:** {next_map_name}"
                ),
                inline=False
            )

            displayed += 1

        if displayed == 0:

            embed.description = (
                "⚠️ The API responded, but no map "
                "rotation information was returned."
            )

        embed.set_footer(
            text=(
                "Live data provided by "
                "Apex Legends Status"
            )
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

        if not isinstance(
            data,
            dict
        ):

            return await ctx.send(
                "❌ The Apex API returned unexpected data."
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

            "PC": rp_data.get(
                "PC"
            ),

            "PlayStation": rp_data.get(
                "PS4"
            ),

            "Xbox": rp_data.get(
                "X1"
            ),

            "Switch": rp_data.get(
                "SWITCH"
            )
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
                "⚠️ The API returned Predator data "
                "in an unexpected format."
            )

        embed.set_footer(
            text=(
                "Live data provided by "
                "Apex Legends Status"
            )
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

        if not isinstance(
            data,
            dict
        ):

            return await ctx.send(
                "❌ The Apex API returned unexpected "
                "server status data."
            )

        embed = discord.Embed(
            title="🟢 Apex Legends Server Status",
            description=(
                "Current Apex Legends service status."
            ),
            color=EMBED_COLOR
        )

        count = 0

        # ==================================================
        # SERVER SERVICES
        # ==================================================

        for name, value in data.items():

            if count >= 12:

                break

            display_name = (
                name
                .replace("_", " ")
                .title()
            )

            status = value

            if isinstance(
                value,
                dict
            ):

                status = (
                    value.get(
                        "Status"
                    )
                    or value.get(
                        "status"
                    )
                    or value.get(
                        "statusText"
                    )
                    or "Unknown"
                )

            if isinstance(
                status,
                dict
            ):

                status = str(
                    status
                )

            status_text = str(
                status
            )[:500]

            embed.add_field(
                name=display_name,
                value=status_text,
                inline=True
            )

            count += 1

        if count == 0:

            embed.description = (
                "⚠️ The API responded, but no "
                "server status information was found."
            )

        embed.set_footer(
            text=(
                "Data from apexlegendsstatus.com"
            )
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

        converted_platform = get_platform(
            platform
        )

        if converted_platform is None:

            return await ctx.send(
                "❌ Invalid platform. "
                "Use `PC`, `PS4`, or `Xbox`."
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

        if not isinstance(
            data,
            dict
        ):

            return await ctx.send(
                "❌ The Apex API returned unexpected data."
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
            text=(
                "Data provided by "
                "Apex Legends Status"
            )
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
                "Commands powered by live "
                "Apex Legends data."
            ),
            color=EMBED_COLOR
        )

        embed.add_field(
            name="📊 Player Stats",
            value=(
                "`!apexstats PC PlayerName`\n"
                "`!apexstats PS4 PlayerName`\n"
                "`!apexstats Xbox PlayerName`"
            ),
            inline=False
        )

        embed.add_field(
            name="🗺️ Map Rotation",
            value=(
                "`!maps`\n"
                "`!apexmap`\n"
                "`!maprotation`\n"
                "`!map`"
            ),
            inline=False
        )

        embed.add_field(
            name="👑 Predator RP",
            value=(
                "`!predator`"
            ),
            inline=True
        )

        embed.add_field(
            name="🟢 Server Status",
            value=(
                "`!apexservers`"
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
            text=(
                "Grid Guardian • "
                "Live Apex Legends System"
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
        Apex(bot)
    )

    print(
        "✅ Apex cog loaded"
    )