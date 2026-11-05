import os
import asyncio
from datetime import datetime, timezone

import aiohttp
import discord
from discord.ext import commands


EMBED_COLOR = discord.Color.from_rgb(190, 0, 20)
API_BASE_URL = "https://api.apexlegendsstatus.com"
APEX_API_KEY = os.getenv("APEX_API_KEY")

MAP_ART = {
    "worlds edge": "https://apexlegendsstatus.com/assets/maps/Worlds_Edge.png",
    "world's edge": "https://apexlegendsstatus.com/assets/maps/Worlds_Edge.png",
    "olympus": "https://apexlegendsstatus.com/assets/maps/Olympus.png",
    "broken moon": "https://apexlegendsstatus.com/assets/maps/Broken_Moon.png",
}

MAP_EMOJI = {
    "worlds edge": "🌋",
    "world's edge": "🌋",
    "olympus": "☁️",
    "broken moon": "🌙",
    "storm point": "🌴",
    "kings canyon": "🏜️",
    "e-district": "🌃",
    "district": "🌃",
}


def format_number(value):
    if value is None:
        return "Unknown"
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value)


def get_platform(platform):
    platforms = {
        "pc": "PC", "computer": "PC", "steam": "PC", "origin": "PC",
        "ps": "PS4", "ps4": "PS4", "ps5": "PS4", "playstation": "PS4",
        "xbox": "X1", "x1": "X1",
    }
    return platforms.get(platform.lower())


def walk_dicts(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_dicts(child)


def first_value(data, *keys):
    wanted = {str(key).lower() for key in keys}
    for obj in walk_dicts(data):
        for key, value in obj.items():
            if str(key).lower() in wanted and value not in (None, ""):
                return value
    return None


def find_stat(data, stat_name):
    stat_name = stat_name.lower()
    for obj in walk_dicts(data):
        for key, value in obj.items():
            if stat_name in str(key).lower() and isinstance(value, (int, float, str)):
                return value
        name = str(obj.get("name", "")).lower()
        key = str(obj.get("key", "")).lower()
        if stat_name in name or stat_name in key:
            if "value" in obj:
                return obj.get("value")
    return None


def format_remaining(timestamp):
    if timestamp is None:
        return None
    try:
        if isinstance(timestamp, (int, float)):
            ts = float(timestamp)
            if ts > 10_000_000_000:
                ts /= 1000
            target = datetime.fromtimestamp(ts, tz=timezone.utc)
        else:
            text = str(timestamp).strip().replace("Z", "+00:00")
            target = datetime.fromisoformat(text)
            if target.tzinfo is None:
                target = target.replace(tzinfo=timezone.utc)
        seconds = max(0, int((target - datetime.now(timezone.utc)).total_seconds()))
        days, rem = divmod(seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, secs = divmod(rem, 60)
        if days:
            return f"{days}d {hours}h {minutes}m"
        if hours:
            return f"{hours}h {minutes}m {secs}s"
        return f"{minutes}m {secs}s"
    except Exception:
        return None


def map_artwork(map_name):
    normalized = str(map_name or "").strip().lower()
    for map_key, image_url in MAP_ART.items():
        if map_key in normalized:
            return image_url
    return None


def map_emoji(map_name):
    normalized = str(map_name or "").strip().lower()
    for map_key, emoji in MAP_EMOJI.items():
        if map_key in normalized:
            return emoji
    return "🗺️"


class Apex(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.request_lock = asyncio.Lock()

    async def api_request(self, endpoint, params=None, fallback_endpoint=None):
        if not APEX_API_KEY:
            return None, "❌ `APEX_API_KEY` is missing from your hosting environment variables."

        params = dict(params or {})
        params["auth"] = APEX_API_KEY
        endpoints = [endpoint]
        if fallback_endpoint:
            endpoints.append(fallback_endpoint)

        try:
            async with self.request_lock:
                timeout = aiohttp.ClientTimeout(total=20)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    for current_endpoint in endpoints:
                        url = f"{API_BASE_URL}{current_endpoint}"
                        headers = {
                            "Authorization": APEX_API_KEY,
                            "User-Agent": "GridGuardian/1.0",
                        }
                        async with session.get(url, params=params, headers=headers) as response:
                            if response.status == 200:
                                try:
                                    data = await response.json(content_type=None)
                                except Exception:
                                    body = await response.text()
                                    print(f"Apex API invalid JSON: {body[:1500]}")
                                    return None, "❌ The Apex API returned invalid data."
                                if isinstance(data, (dict, list)):
                                    return data, None
                                return None, "❌ The Apex API returned unexpected data."

                            if response.status == 406:
                                body = await response.text()
                                print(f"Apex API HTTP 406 at {current_endpoint}: {body[:1000]}")
                                retry_params = dict(params)
                                retry_params.pop("auth", None)
                                try:
                                    async with session.get(
                                        url,
                                        params=retry_params,
                                        headers={"Authorization": APEX_API_KEY, "User-Agent": "Mozilla/5.0"},
                                    ) as retry:
                                        if retry.status == 200:
                                            retry_data = await retry.json(content_type=None)
                                            if isinstance(retry_data, (dict, list)):
                                                return retry_data, None
                                        retry_body = await retry.text()
                                        print(f"Apex API retry HTTP {retry.status}: {retry_body[:1000]}")
                                except aiohttp.ClientError as retry_error:
                                    print(f"Apex API retry failed: {retry_error}")
                                if current_endpoint != endpoints[-1]:
                                    continue
                                return None, "❌ The Apex API rejected this request (HTTP 406)."

                            if response.status == 400:
                                return None, "⚠️ The Apex API asked you to try again in a few minutes."
                            if response.status == 403:
                                return None, "❌ The Apex API key was rejected. Check `APEX_API_KEY` in your hosting variables."
                            if response.status == 404:
                                return None, "❌ The requested Apex API resource could not be found."
                            if response.status == 405:
                                return None, "❌ The Apex API reported an external API error (HTTP 405)."
                            if response.status == 410:
                                return None, "❌ That Apex platform isn't supported."
                            if response.status == 429:
                                return None, "⚠️ The Apex API rate limit was reached. Please wait a moment."
                            if response.status >= 500:
                                return None, "❌ The Apex API is currently experiencing an internal error."

                            body = await response.text()
                            print(f"Apex API HTTP {response.status}: {body[:1000]}")
                            return None, f"❌ Apex API returned HTTP {response.status}."

        except asyncio.TimeoutError:
            return None, "⚠️ The Apex API took too long to respond."
        except aiohttp.ClientError as error:
            print(f"Apex API connection error: {error}")
            return None, "❌ Couldn't connect to the Apex API."
        except Exception as error:
            print(f"Unexpected Apex API error: {error}")
            return None, "❌ An unexpected error occurred while contacting the Apex API."

    @commands.command(name="apexstats", aliases=["apexplayer", "playerstats"])
    async def apexstats(self, ctx, platform, *, player):
        converted_platform = get_platform(platform)
        if converted_platform is None:
            return await ctx.send("❌ Invalid platform. Use `PC`, `PS4`, or `Xbox`.")

        async with ctx.typing():
            data, error = await self.api_request(
                "/bridge", {"player": player, "platform": converted_platform, "version": 5}
            )
        if error:
            return await ctx.send(error)
        if not isinstance(data, dict):
            return await ctx.send("❌ The Apex API returned unexpected player data.")

        global_data = data.get("global", {}) if isinstance(data.get("global"), dict) else {}
        rank_data = global_data.get("rank", {}) if isinstance(global_data.get("rank"), dict) else {}
        rank_name = rank_data.get("rankName") or rank_data.get("rank") or first_value(data, "rankName", "rank_name") or "Unranked"
        rank_division = rank_data.get("rankDiv") or rank_data.get("division") or first_value(data, "rankDiv", "rankDivision", "division") or ""
        rank_score = rank_data.get("rankScore") or rank_data.get("rankedScore") or rank_data.get("score") or first_value(data, "rankScore", "rankedScore", "RP", "AP") or 0
        level = global_data.get("level") or first_value(data, "level") or "Unknown"
        player_name = global_data.get("name") or first_value(data, "name", "playerName") or player
        platform_name = global_data.get("platform") or converted_platform
        avatar = global_data.get("avatar")
        kills = find_stat(data, "kills")
        damage = find_stat(data, "damage")
        wins = find_stat(data, "wins")
        rank_text = f"{rank_name} {rank_division}".strip()

        embed = discord.Embed(
            title=f"📊 {player_name} • Apex Player Stats",
            description=f"🎮 Live profile overview for **{player_name}**",
            color=EMBED_COLOR,
            timestamp=discord.utils.utcnow(),
        )
        if avatar:
            embed.set_thumbnail(url=avatar)
        embed.add_field(name="🖥️ Platform", value=str(platform_name), inline=True)
        embed.add_field(name="⭐ Level", value=format_number(level), inline=True)
        embed.add_field(name="🏆 Rank", value=rank_text, inline=True)
        embed.add_field(name="📈 RP", value=format_number(rank_score), inline=True)
        embed.add_field(name="💀 Kills", value=format_number(kills), inline=True)
        embed.add_field(name="🏅 Wins", value=format_number(wins), inline=True)
        embed.add_field(name="💥 Damage", value=format_number(damage), inline=True)
        embed.set_footer(text="Grid Guardian • Player data from Apex Legends Status")
        await ctx.send(embed=embed)

    @commands.command(name="apexmap", aliases=["maprotation", "maps", "map"])
    async def apexmap(self, ctx):
        async with ctx.typing():
            data, error = await self.api_request(
                "/maprotation.php", {"version": 2}, fallback_endpoint="/maprotation"
            )
        if error:
            return await ctx.send(error)
        if not isinstance(data, dict):
            return await ctx.send("❌ The Apex API returned unexpected map rotation data.")

        embeds = []
        for mode_name, mode_data in data.items():
            if not isinstance(mode_data, dict):
                continue
            current = mode_data.get("current") if isinstance(mode_data.get("current"), dict) else {}
            nxt = mode_data.get("next") if isinstance(mode_data.get("next"), dict) else {}
            current_map = current.get("map") or current.get("name") or "Unknown"
            next_map = nxt.get("map") or nxt.get("name") or "Unknown"
            if current_map == "Unknown" and next_map == "Unknown":
                continue

            end_time = (
                current.get("end") or current.get("endTime") or current.get("end_timestamp")
                or current.get("endsAt") or current.get("remaining") or current.get("duration")
            )
            remaining = format_remaining(end_time)
            if end_time is not None and remaining is None:
                remaining = str(end_time)

            description = f"{map_emoji(current_map)} **CURRENT MAP**\n## {current_map}\n"
            if remaining:
                description += f"⏳ **Time remaining:** {remaining}\n"
            description += f"\n{map_emoji(next_map)} **NEXT MAP**\n**{next_map}**"
            embed = discord.Embed(
                title=f"🗺️ {mode_name.replace('_', ' ').title()} Rotation",
                description=description,
                color=EMBED_COLOR,
                timestamp=discord.utils.utcnow(),
            )
            artwork = map_artwork(current_map)
            if artwork:
                embed.set_thumbnail(url=artwork)
            embed.set_footer(text="Grid Guardian • Live Apex map rotation")
            embeds.append(embed)

        if not embeds:
            embed = discord.Embed(
                title="🗺️ Apex Legends Map Rotation",
                description="⚠️ The API responded, but no map rotation information was found.",
                color=EMBED_COLOR,
            )
            return await ctx.send(embed=embed)
        await ctx.send(embeds=embeds[:10])

    @commands.command(name="predator", aliases=["predrp", "predatorrp"])
    async def predator(self, ctx):
        async with ctx.typing():
            data, error = await self.api_request("/predator")
        if error:
            return await ctx.send(error)
        if not isinstance(data, dict):
            return await ctx.send("❌ The Apex API returned unexpected Predator data.")

        rp_data = data.get("RP") if isinstance(data.get("RP"), dict) else data
        platforms = [
            ("PC", ["PC", "pc"], "🖥️"),
            ("PlayStation", ["PS4", "PS", "playstation"], "🎮"),
            ("Xbox", ["X1", "Xbox", "xbox"], "🟢"),
            ("Switch", ["SWITCH", "Switch", "switch"], "🔴"),
        ]
        lines = []
        for label, keys, icon in platforms:
            platform_data = None
            if isinstance(rp_data, dict):
                for key in keys:
                    candidate = rp_data.get(key)
                    if isinstance(candidate, dict):
                        platform_data = candidate
                        break
            if platform_data is None:
                continue
            value = platform_data.get("val") or platform_data.get("value") or platform_data.get("rp") or platform_data.get("RP")
            masters = platform_data.get("totalMasters") or platform_data.get("masters")
            if value is None:
                continue
            line = f"{icon} **{format_number(value)} RP** on {label}"
            if masters is not None:
                line += f"\n   Masters: {format_number(masters)}"
            lines.append(line)

        if not lines:
            fallback = first_value(data, "val", "value", "rp", "RP")
            if fallback is not None:
                lines.append(f"👑 **{format_number(fallback)} RP**")

        embed = discord.Embed(
            title="How many points to reach Apex Predator?",
            description="👑 **BATTLE ROYALE**\n\n" + (
                "\n\n".join(lines) if lines else
                "⚠️ Predator data was returned in a format this bot doesn't recognize yet."
            ),
            color=EMBED_COLOR,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_footer(text="Grid Guardian • Live data from Apex Legends Status")
        await ctx.send(embed=embed)

    @commands.command(name="apexservers", aliases=["apexserverstatus", "serverstatus"])
    async def apexservers(self, ctx):
        async with ctx.typing():
            data, error = await self.api_request("/servers")
        if error:
            return await ctx.send(error)
        if not isinstance(data, dict):
            return await ctx.send("❌ The Apex API returned unexpected server status data.")

        embed = discord.Embed(
            title="🛰️ Apex Legends Server Status",
            description="Live service checks across Apex Legends.",
            color=EMBED_COLOR,
            timestamp=discord.utils.utcnow(),
        )
        count = 0
        for name, value in data.items():
            if count >= 12:
                break
            display_name = name.replace("_", " ").title()
            status = value
            if isinstance(value, dict):
                status = value.get("Status") or value.get("status") or value.get("statusText") or "Unknown"
            if isinstance(status, dict):
                status = str(status)
            status_text = str(status)[:500]
            embed.add_field(name=f"🌐 {display_name}", value=status_text, inline=True)
            count += 1
        if count == 0:
            embed.description = "⚠️ The API responded, but no server status information was found."
        embed.set_footer(text="Grid Guardian • Data from Apex Legends Status")
        await ctx.send(embed=embed)

    @commands.command(name="apexuid", aliases=["playeruid"])
    async def apexuid(self, ctx, platform, *, player):
        converted_platform = get_platform(platform)
        if converted_platform is None:
            return await ctx.send("❌ Invalid platform. Use `PC`, `PS4`, or `Xbox`.")
        async with ctx.typing():
            data, error = await self.api_request(
                "/nametouid", {"player": player, "platform": converted_platform}
            )
        if error:
            return await ctx.send(error)
        if not isinstance(data, dict):
            return await ctx.send("❌ The Apex API returned unexpected data.")
        uid = data.get("uid") or data.get("UID") or data.get("id")
        embed = discord.Embed(
            title="🆔 Apex Player ID Lookup",
            description=f"🔎 Lookup result for **{player}**",
            color=EMBED_COLOR,
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="👤 Player", value=player, inline=True)
        embed.add_field(name="🎮 Platform", value=converted_platform, inline=True)
        embed.add_field(name="🆔 UID", value=f"`{uid}`" if uid else "Not returned by API", inline=False)
        embed.set_footer(text="Grid Guardian • Data from Apex Legends Status")
        await ctx.send(embed=embed)

    @commands.command(name="apexhelp")
    async def apexhelp(self, ctx):
        embed = discord.Embed(
            title="🎮 Grid Guardian — Apex Commands",
            description="Live Apex Legends tools and player information.",
            color=EMBED_COLOR,
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(
            name="📊 Player Stats",
            value="`!apexstats PC PlayerName`\n`!apexstats PS4 PlayerName`\n`!apexstats Xbox PlayerName`",
            inline=False,
        )
        embed.add_field(
            name="🗺️ Map Rotation",
            value="`!maps`  •  `!apexmap`  •  `!maprotation`  •  `!map`",
            inline=False,
        )
        embed.add_field(name="👑 Predator RP", value="`!predator`", inline=True)
        embed.add_field(name="🛰️ Server Status", value="`!apexservers`", inline=True)
        embed.add_field(name="🆔 Player UID", value="`!apexuid PC PlayerName`", inline=False)
        embed.set_footer(text="Grid Guardian • Live Apex Legends System")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Apex(bot))
    print("✅ Apex cog loaded")