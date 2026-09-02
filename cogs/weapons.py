import discord
from discord.ext import commands


EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)


# ==========================================================
# WEAPON DATA
# ==========================================================

WEAPONS = {

    # ======================================================
    # ASSAULT RIFLES
    # ======================================================

    "r301": {
        "name": "R-301 Carbine",
        "type": "Assault Rifle",
        "ammo": "Light Ammo",
        "fire_mode": "Automatic / Single",
        "description": "A versatile assault rifle with a fast fire rate."
    },

    "flatline": {
        "name": "VK-47 Flatline",
        "type": "Assault Rifle",
        "ammo": "Heavy Ammo",
        "fire_mode": "Automatic / Single",
        "description": "A heavy-ammo assault rifle."
    },

    "hemlok": {
        "name": "Hemlok Burst AR",
        "type": "Assault Rifle",
        "ammo": "Heavy Ammo",
        "fire_mode": "Burst / Single",
        "description": "A burst-fire assault rifle."
    },

    "nemesis": {
        "name": "Nemesis Burst AR",
        "type": "Assault Rifle",
        "ammo": "Energy Ammo",
        "fire_mode": "Burst",
        "description": "An energy assault rifle with burst fire."
    },

    "havoc": {
        "name": "HAVOC Rifle",
        "type": "Assault Rifle",
        "ammo": "Energy Ammo",
        "fire_mode": "Automatic",
        "description": "A fully automatic energy rifle."
    },


    # ======================================================
    # SMGS
    # ======================================================

    "r99": {
        "name": "R-99 SMG",
        "type": "SMG",
        "ammo": "Light Ammo",
        "fire_mode": "Automatic",
        "description": "A fast-firing light-ammo SMG."
    },

    "car": {
        "name": "C.A.R. SMG",
        "type": "SMG",
        "ammo": "Light / Heavy Ammo",
        "fire_mode": "Automatic",
        "description": "An SMG capable of using multiple ammo types."
    },

    "alternator": {
        "name": "Alternator SMG",
        "type": "SMG",
        "ammo": "Light Ammo",
        "fire_mode": "Automatic",
        "description": "A light-ammo submachine gun."
    },

    "volt": {
        "name": "Volt SMG",
        "type": "SMG",
        "ammo": "Energy Ammo",
        "fire_mode": "Automatic",
        "description": "An energy-powered submachine gun."
    },


    # ======================================================
    # MARKSMAN WEAPONS
    # ======================================================

    "3030": {
        "name": "30-30 Repeater",
        "type": "Marksman",
        "ammo": "Heavy Ammo",
        "fire_mode": "Single",
        "description": "A lever-action marksman weapon."
    },

    "g7": {
        "name": "G7 Scout",
        "type": "Marksman",
        "ammo": "Light Ammo",
        "fire_mode": "Semi-Automatic",
        "description": "A semi-automatic marksman rifle."
    },

    "triple_take": {
        "name": "Triple Take",
        "type": "Marksman",
        "ammo": "Energy Ammo",
        "fire_mode": "Triple Shot",
        "description": "An energy weapon that fires multiple projectiles."
    },

    "bocek": {
        "name": "Bocek Compound Bow",
        "type": "Marksman",
        "ammo": "Arrows",
        "fire_mode": "Single",
        "description": "A compound bow that uses arrows."
    },


    # ======================================================
    # SNIPER RIFLES
    # ======================================================

    "sentinel": {
        "name": "Sentinel",
        "type": "Sniper Rifle",
        "ammo": "Sniper Ammo",
        "fire_mode": "Single",
        "description": "A bolt-action sniper rifle."
    },

    "longbow": {
        "name": "Longbow DMR",
        "type": "Sniper Rifle",
        "ammo": "Sniper Ammo",
        "fire_mode": "Semi-Automatic",
        "description": "A semi-automatic sniper rifle."
    },

    "charge_rifle": {
        "name": "Charge Rifle",
        "type": "Sniper Rifle",
        "ammo": "Sniper Ammo",
        "fire_mode": "Energy Beam",
        "description": "A sniper weapon that fires an energy beam."
    },


    # ======================================================
    # SHOTGUNS
    # ======================================================

    "peacekeeper": {
        "name": "Peacekeeper",
        "type": "Shotgun",
        "ammo": "Shotgun Ammo",
        "fire_mode": "Pump Action",
        "description": "A pump-action shotgun."
    },

    "mastiff": {
        "name": "Mastiff Shotgun",
        "type": "Shotgun",
        "ammo": "Shotgun Ammo",
        "fire_mode": "Semi-Automatic",
        "description": "A shotgun with a distinctive horizontal pellet pattern."
    },

    "eva8": {
        "name": "EVA-8 Auto",
        "type": "Shotgun",
        "ammo": "Shotgun Ammo",
        "fire_mode": "Automatic",
        "description": "A fully automatic shotgun."
    },


    # ======================================================
    # PISTOLS
    # ======================================================

    "wingman": {
        "name": "Wingman",
        "type": "Pistol",
        "ammo": "Sniper Ammo",
        "fire_mode": "Semi-Automatic",
        "description": "A powerful revolver-style pistol."
    },

    "p2020": {
        "name": "P2020",
        "type": "Pistol",
        "ammo": "Light Ammo",
        "fire_mode": "Semi-Automatic",
        "description": "A semi-automatic light-ammo pistol."
    },

    "re45": {
        "name": "RE-45 Auto",
        "type": "Pistol",
        "ammo": "Light Ammo",
        "fire_mode": "Automatic",
        "description": "A fully automatic pistol."
    }
}


# ==========================================================
# WEAPON COG
# ==========================================================

class Weapons(commands.Cog):

    def __init__(self, bot):
        self.bot = bot


    # ======================================================
    # WEAPON COMMAND
    # ======================================================

    @commands.command()
    async def weapon(self, ctx, *, weapon_name=None):

        if weapon_name is None:

            embed = discord.Embed(
                title="🎮 Weapon Lookup",
                description=(
                    "Please provide a weapon name.\n\n"
                    "**Example:** `!weapon r301`"
                ),
                color=EMBED_COLOR
            )

            return await ctx.send(embed=embed)


        # Normalize input
        search = (
            weapon_name
            .lower()
            .strip()
            .replace("-", "")
            .replace("_", "")
            .replace(" ", "")
        )


        # Find weapon
        weapon = None

        for key, data in WEAPONS.items():

            normalized_key = (
                key
                .lower()
                .replace("-", "")
                .replace("_", "")
                .replace(" ", "")
            )

            normalized_name = (
                data["name"]
                .lower()
                .replace("-", "")
                .replace("_", "")
                .replace(" ", "")
            )

            if (
                search == normalized_key
                or search == normalized_name
                or search in normalized_key
                or search in normalized_name
            ):

                weapon = data
                break


        # Weapon not found
        if weapon is None:

            embed = discord.Embed(
                title="❌ Weapon Not Found",
                description=(
                    f"I couldn't find **{weapon_name}**.\n\n"
                    "Use `!weapons` to see available weapons."
                ),
                color=discord.Color.red()
            )

            return await ctx.send(embed=embed)


        # Weapon embed
        embed = discord.Embed(
            title=f"🔫 {weapon['name']}",
            description=weapon["description"],
            color=EMBED_COLOR
        )

        embed.add_field(
            name="🏷️ Weapon Type",
            value=weapon["type"],
            inline=True
        )

        embed.add_field(
            name="📦 Ammo",
            value=weapon["ammo"],
            inline=True
        )

        embed.add_field(
            name="⚡ Fire Mode",
            value=weapon["fire_mode"],
            inline=True
        )

        embed.set_footer(
            text="Grid Guardian • Apex Legends Weapon Database"
        )

        await ctx.send(embed=embed)


    # ======================================================
    # WEAPONS LIST
    # ======================================================

    @commands.command()
    async def weapons(self, ctx):

        categories = {

            "🔫 Assault Rifles": [],
            "⚡ SMGs": [],
            "🎯 Marksman": [],
            "🔭 Sniper Rifles": [],
            "💥 Shotguns": [],
            "🔫 Pistols": []
        }


        for weapon in WEAPONS.values():

            if weapon["type"] == "Assault Rifle":
                categories["🔫 Assault Rifles"].append(
                    weapon["name"]
                )

            elif weapon["type"] == "SMG":
                categories["⚡ SMGs"].append(
                    weapon["name"]
                )

            elif weapon["type"] == "Marksman":
                categories["🎯 Marksman"].append(
                    weapon["name"]
                )

            elif weapon["type"] == "Sniper Rifle":
                categories["🔭 Sniper Rifles"].append(
                    weapon["name"]
                )

            elif weapon["type"] == "Shotgun":
                categories["💥 Shotguns"].append(
                    weapon["name"]
                )

            elif weapon["type"] == "Pistol":
                categories["🔫 Pistols"].append(
                    weapon["name"]
                )


        embed = discord.Embed(
            title="🎮 Apex Legends Weapons",
            description=(
                "Use `!weapon <name>` to look up a weapon.\n\n"
                "**Example:** `!weapon r301`"
            ),
            color=EMBED_COLOR
        )


        for category, weapon_list in categories.items():

            if weapon_list:

                embed.add_field(
                    name=category,
                    value="\n".join(
                        f"• {weapon}"
                        for weapon in weapon_list
                    ),
                    inline=False
                )


        embed.set_footer(
            text="Grid Guardian • Apex Legends Weapon Database"
        )

        await ctx.send(embed=embed)


# ==========================================================
# SETUP
# ==========================================================

async def setup(bot):

    await bot.add_cog(
        Weapons(bot)
    )