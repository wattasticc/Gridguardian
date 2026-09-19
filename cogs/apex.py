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


def _walk_dicts(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def _first_value(data, *keys):
    wanted = {str(k).lower() for k in keys}
    for obj in _walk_dicts(data):
        for key, value in obj.items():
            if str(key).lower() in wanted and value not in (None, ''):
                return value
    return None


def find_stat(data, stat_name):
    stat_name = stat_name.lower()
    for obj in _walk_dicts(data):
        for key, value in obj.items():
            key_text = str(key).lower()
            if stat_name in key_text and isinstance(value, (int, float, str)):
                return value
        name = str(obj.get('name', '')).lower()
        key = str(obj.get('key', '')).lower()
        if stat_name in name or stat_name in key:
            if 'value' in obj:
                return obj.get('value')
    return None


def format_remaining(timestamp):
    if timestamp is None:
        return None
    try:
        from datetime import datetime, timezone
        if isinstance(timestamp, (int, float)):
            ts = float(timestamp)
            if ts > 10_000_000_000:
                ts /= 1000
            target = datetime.fromtimestamp(ts, tz=timezone.utc)
        else:
            text = str(timestamp).strip().replace('Z', '+00:00')
            target = datetime.fromisoformat(text)
            if target.tzinfo is None:
                target = target.replace(tzinfo=timezone.utc)
        seconds = max(0, int((target - datetime.now(timezone.utc)).total_seconds()))
        days, rem = divmod(seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, secs = divmod(rem, 60)
        if days:
            return f'{days}d {hours}h {minutes}m'
        if hours:
            return f'{hours}h {minutes}m {secs}s'
        return f'{minutes}m {secs}s'
    except Exception:
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

        global_data = data.get("global", {}) if isinstance(data.get("global"), dict) else {}
        rank_data = global_data.get("rank", {}) if isinstance(global_data.get("rank"), dict) else {}

        rank_name = (rank_data.get("rankName") or rank_data.get("rank") or
                     _first_value(data, "rankName", "rank_name") or "Unranked")
        rank_division = (rank_data.get("rankDiv") or rank_data.get("division") or
                         _first_value(data, "rankDiv", "rankDivision", "division") or "")
        rank_score = (rank_data.get("rankScore") or rank_data.get("rankedScore") or
                      rank_data.get("score") or _first_value(data, "rankScore", "rankedScore", "RP", "AP") or 0)
        level = global_data.get("level") or _first_value(data, "level") or "Unknown"
        player_name = global_data.get("name") or _first_value(data, "name", "playerName") or player
        platform_name = global_data.get("platform") or converted_platform
        avatar = global_data.get("avatar")

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
        aliases=["maprotation", "maps", "map"]
    )
    async def apexmap(self, ctx):
        async with ctx.typing():
            data, error = await self.api_request(
                "/maprotation.php", {"version": 2}, fallback_endpoint="/maprotation"
            )
        if error:
            return await ctx.send(error)
        if not isinstance(data, dict):
            return await ctx.send("❌ The Apex API returned unexpected map rotation data.")

        embed = discord.Embed(
            title="🗺️ Apex Legends Map Rotation",
            description="Current maps and how long they have left.",
            color=EMBED_COLOR
        )
        displayed = 0
        for mode_name, mode_data in data.items():
            if not isinstance(mode_data, dict):
                continue
            current = mode_data.get("current") if isinstance(mode_data.get("current"), dict) else {}
            nxt = mode_data.get("next") if isinstance(mode_data.get("next"), dict) else {}
            current_map = current.get("map") or current.get("name") or "Unknown"
            next_map = nxt.get("map") or nxt.get("name") or "Unknown"
            end_time = (current.get("end") or current.get("endTime") or current.get("end_timestamp") or
                        current.get("endsAt") or current.get("remaining") or current.get("duration"))
            remaining = format_remaining(end_time)
            if end_time is not None and remaining is None:
                remaining = str(end_time)
            if current_map == "Unknown" and next_map == "Unknown":
                continue
            value = f"**Now:** {current_map}"
            if remaining:
                value += f"\n⏳ **Time left:** {remaining}"
            value += f"\n**Next:** {next_map}"
            embed.add_field(name=mode_name.replace("_", " ").title(), value=value, inline=False)
            displayed += 1
        if not displayed:
            embed.description = "⚠️ The API responded, but no map rotation information was found."
        embed.set_footer(text="Live data provided by Apex Legends Status")
        await ctx.send(embed=embed)


    # ======================================================
    # PREDATOR RP
    # ======================================================

    @commands.command(
        name="predator", aliases=["predrp", "predatorrp"]
    )
    async def predator(self, ctx):
        async with ctx.typing():
            data, error = await self.api_request("/predator")
        if error:
            return await ctx.send(error)
        if not isinstance(data, dict):
            return await ctx.send("❌ The Apex API returned unexpected Predator data.")

        embed = discord.Embed(
            title="👑 Apex Predator Thresholds",
            description="Current ranked points needed for Predator.",
            color=EMBED_COLOR
        )
        rp_data = data.get("RP") if isinstance(data.get("RP"), dict) else data
        platforms = {"PC": ["PC", "pc"], "PlayStation": ["PS4", "PS", "playstation"], "Xbox": ["X1", "Xbox", "xbox"], "Switch": ["SWITCH", "Switch", "switch"]}
        added = False
        for label, keys in platforms.items():
            obj = None
            for key in keys:
                if isinstance(rp_data, dict) and isinstance(rp_data.get(key), dict):
                    obj = rp_data[key]; break
            if obj is None:
                continue
            value = obj.get("val") or obj.get("value") or obj.get("rp") or obj.get("RP")
            masters = obj.get("totalMasters") or obj.get("masters")
            if value is None:
                continue
            text = f"**Required RP:** {format_number(value)}"
            if masters is not None:
                text += f"\n**Masters:** {format_number(masters)}"
            embed.add_field(name=label, value=text, inline=True)
            added = True
        if not added:
            fallback = _first_value(data, "val", "value", "rp", "RP")
            if fallback is not None:
                embed.add_field(name="Predator", value=f"**Required RP:** {format_number(fallback)}", inline=False)
                added = True
        if not added:
            embed.description = "⚠️ Predator data was returned in a format this bot doesn't recognize yet."
        embed.set_footer(text="Live data provided by Apex Legends Status")
        await ctx.send(embed=embed)


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