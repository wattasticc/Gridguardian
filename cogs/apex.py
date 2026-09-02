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


def get_nested(data, *keys, default=None):

    current = data

    for key in keys:

        if not isinstance(current, dict):
            return default

        current = current.get(key)

    return current if current is not None else default


def find_stat(data, stat_name):

    stat_name = stat_name.lower()

    # Check global trackers.
    global_data = data.get("global", {})

    rank_data = global_data.get("rank", {})

    if stat_name in rank_data:
        return rank_data.get(stat_name)

    # Check legends.
    legends = data.get("legends", {})

    all_legends = legends.get("all", {})

    for legend_data in all_legends.values():

        if not isinstance(legend_data, dict):
            continue

        trackers = legend_data.get("data", [])

        if not isinstance(trackers, list):
            continue

        for tracker in trackers:

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

        # Prevent requests from happening too quickly.
        self.request_lock = asyncio.Lock()


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
                "❌ `APEX_API_KEY` is missing from "
                "your `.env` file."
            )

        url = f"{API_BASE_URL}{endpoint}"

        headers = {
            "Authorization": APEX_API_KEY
        }

        if params is None:
            params = {}

        try:

            async with self.request_lock:

                async with aiohttp.ClientSession() as session:

                    async with session.get(
                        url,
                        params=params,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(
                            total=15
                        )
                    ) as response:

                        if response.status == 200:

                            try:
                                data = await response.json()

                                return data, None

                            except Exception:

                                return None, (
                                    "❌ The Apex API returned "
                                    "invalid data."
                                )

                        # ---------------------------------
                        # ERROR CODES
                        # ---------------------------------

                        if response.status == 400:

                            return None, (
                                "⚠️ The Apex API asked you to "
                                "try again in a few minutes."
                            )

                        if response.status == 403:

                            return None, (
                                "❌ The Apex API key was rejected. "
                                "Check your `APEX_API_KEY`."
                            )

                        if response.status == 404:

                            return None, (
                                "❌ That Apex player could not "
                                "be found."
                            )

                        if response.status == 410:

                            return None, (
                                "❌ That platform isn't supported."
                            )

                        if response.status == 429:

                            return None, (
                                "⚠️ The Apex API rate limit was "
                                "reached. Please wait a moment "
                                "and try again."
                            )

                        return None, (
                            f"❌ Apex API error: "
                            f"HTTP {response.status}"
                        )

        except asyncio.TimeoutError:

            return None, (
                "⚠️ The Apex API took too long to respond."
            )

        except aiohttp.ClientError as error:

            print(
                f"Apex API connection error: {error}"
            )

            return None, (
                "❌ Couldn't connect to the Apex API."
            )

        except Exception as error:

            print(
                f"Unexpected Apex API error: {error}"
            )

            return None, (
                "❌ An unexpected error occurred while "
                "contacting the Apex API."
            )


    # ======================================================
    # LIVE PLAYER STATS
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

        embed = discord.Embed(
            title="🗺️ Apex Legends Map Rotation",
            description=(
                "Current and upcoming Apex Legends maps."
            ),
            color=EMBED_COLOR
        )

        if isinstance(data, dict):

            displayed = 0

            for mode_name, mode_data in data.items():

                if not isinstance(
                    mode_data,
                    dict
                ):
                    continue

                current = (
                    mode_data
                    .get("current", {})
                )

                next_map = (
                    mode_data
                    .get("next", {})
                )

                current_map = (
                    current.get(
                        "map",
                        "Unknown"
                    )
                    if isinstance(current, dict)
                    else "Unknown"
                )

                next_map_name = (
                    next_map.get(
                        "map",
                        "Unknown"
                    )
                    if isinstance(next_map, dict)
                    else "Unknown"
                )

                if (
                    current_map == "Unknown"
                    and next_map_name == "Unknown"
                ):
                    continue

                embed.add_field(
                    name=mode_name.replace(
                        "_",
                        " "
                    ).title(),
                    value=(
                        f"**Now:** {current_map}\n"
                        f"**Next:** {next_map_name}"
                    ),
                    inline=False
                )

                displayed += 1

            if displayed == 0:

                embed.description = (
                    "The API did not return map rotation "
                    "information right now."
                )

        embed.set_footer(
            text="Live data provided by Apex Legends Status"
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

        embed = discord.Embed(
            title="👑 Apex Predator Thresholds",
            description=(
                "Current RP/AP requirements for "
                "Apex Predator."
            ),
            color=EMBED_COLOR
        )

        if isinstance(data, dict):

            platforms = {

                "PC": data.get(
                    "RP",
                    {}
                ).get("PC"),

                "PlayStation": data.get(
                    "RP",
                    {}
                ).get("PS4"),

                "Xbox": data.get(
                    "RP",
                    {}
                ).get("X1"),

                "Switch": data.get(
                    "RP",
                    {}
                ).get("SWITCH")
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

                # Fallback if API structure changes.
                embed.description = (
                    "```"
                    + str(data)[:3500]
                    + "```"
                )

        embed.set_footer(
            text="Live data provided by Apex Legends Status"
        )

        await ctx.send(
            embed=embed
        )


    # ======================================================
    # APEX SERVER STATUS
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

        embed = discord.Embed(
            title="🟢 Apex Legends Server Status",
            description=(
                "Current Apex Legends service status."
            ),
            color=EMBED_COLOR
        )

        if isinstance(data, dict):

            services = data.get(
                "Origin_login",
                {}
            )

            if services:

                embed.add_field(
                    name="EA / Origin",
                    value=(
                        str(services)
                        [:500]
                    ),
                    inline=False
                )

            # Add major API categories.
            count = 0

            for name, value in data.items():

                if name == "Origin_login":
                    continue

                if count >= 8:
                    break

                if isinstance(
                    value,
                    dict
                ):

                    status = value.get(
                        "Status",
                        value.get(
                            "status",
                            "Unknown"
                        )
                    )

                    if isinstance(
                        status,
                        dict
                    ):

                        status = str(status)

                    embed.add_field(
                        name=name.replace(
                            "_",
                            " "
                        ).title(),
                        value=str(status)[:200],
                        inline=True
                    )

                    count += 1

        embed.set_footer(
            text="Data from apexlegendsstatus.com"
        )

        await ctx.send(
            embed=embed
        )


    # ======================================================
    # PLAYER UID LOOKUP
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

        uid = None

        if isinstance(data, dict):

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
            title="🎮 Grid Guardian — Live Apex Commands",
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
                "`!apexstats Xbox PlayerName`"
            ),
            inline=False
        )

        embed.add_field(
            name="🗺️ Live Maps",
            value=(
                "`!apexmap`"
            ),
            inline=True
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
            text="Grid Guardian • Live Apex Legends System"
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